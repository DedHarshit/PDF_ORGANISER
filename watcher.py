"""
watcher.py
----------
Watchdog-based filesystem monitor. Detects new PDFs dropped into the
watch directory and feeds them through the classify → organise pipeline.
"""

import time
import logging
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from classifier import classify_pdf, PDFExtractionError, PDFNoContentError
from organiser  import organise_pdf, move_to_error, OrganiserError

logger = logging.getLogger(__name__)

# How long to wait after a file-creation event before reading the file.
# Prevents reading a half-written file if it's being copied in.
WRITE_SETTLE_SECONDS = 2.0


class PDFHandler(FileSystemEventHandler):
    """
    Listens for new .pdf files in the watch directory.
    On each new file: classify → move to organised folder (or _errors on failure).
    """

    def __init__(self, output_dir: str):
        super().__init__()
        self.output_dir = output_dir
        self._in_flight: set[str] = set()   # Guard against duplicate events

    # ── Watchdog callback ─────────────────────────────────────────────────────

    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(".pdf"):
            return
        if event.src_path in self._in_flight:
            logger.debug("Already processing '%s', skipping duplicate event.", event.src_path)
            return

        self._in_flight.add(event.src_path)
        try:
            self._handle(event.src_path)
        finally:
            self._in_flight.discard(event.src_path)

    # Some tools trigger on_moved (e.g. "Save As" from another app)
    def on_moved(self, event):
        if not event.is_directory and event.dest_path.lower().endswith(".pdf"):
            self.on_created(type("_E", (), {"is_directory": False, "src_path": event.dest_path})())

    # ── Core processing ───────────────────────────────────────────────────────

    def _handle(self, pdf_path: str):
        logger.info("▶  New PDF detected: %s", Path(pdf_path).name)

        # Wait for the file to finish being written
        if not self._wait_for_file(pdf_path):
            logger.error("File never became readable (deleted or stuck): %s", pdf_path)
            return

        try:
            folder = classify_pdf(pdf_path)
            organise_pdf(pdf_path, self.output_dir, folder)

        except PDFExtractionError as exc:
            # Corrupted, encrypted, or completely unreadable
            logger.error("PDF extraction error — %s: %s", Path(pdf_path).name, exc)
            move_to_error(pdf_path, self.output_dir, "extraction_error")

        except PDFNoContentError as exc:
            # Valid PDF but no text or images we can work with
            logger.error("PDF has no content — %s: %s", Path(pdf_path).name, exc)
            move_to_error(pdf_path, self.output_dir, "no_content")

        except RuntimeError as exc:
            # API failed after all retries
            logger.error("API classification failed — %s: %s", Path(pdf_path).name, exc)
            move_to_error(pdf_path, self.output_dir, "api_error")

        except OrganiserError as exc:
            # Filesystem move failed
            logger.error("File organiser error — %s: %s", Path(pdf_path).name, exc)
            # File is still in watch dir; log but don't loop

        except Exception as exc:
            logger.exception("Unexpected error processing '%s': %s", pdf_path, exc)
            move_to_error(pdf_path, self.output_dir, "unknown_error")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _wait_for_file(path: str, timeout: float = 30.0) -> bool:
        """
        Poll until the file exists and isn't growing (i.e. fully written).
        Returns True when ready, False if timeout exceeded.
        """
        deadline = time.time() + timeout
        prev_size = -1

        while time.time() < deadline:
            p = Path(path)
            if not p.exists():
                time.sleep(0.5)
                continue
            cur_size = p.stat().st_size
            if cur_size == prev_size and cur_size > 0:
                time.sleep(WRITE_SETTLE_SECONDS)
                return True
            prev_size = cur_size
            time.sleep(0.5)

        return False


# ── Public entry point ────────────────────────────────────────────────────────

def start_watching(watch_dir: str, output_dir: str) -> None:
    """
    Start the blocking watchdog loop.
    Exits cleanly on KeyboardInterrupt (Ctrl-C).

    Args:
        watch_dir:  Directory to monitor for new PDF files.
        output_dir: Root directory where organised PDFs are placed.
    """
    logger.info("=" * 60)
    logger.info("PDF Organiser started")
    logger.info("  Watch dir  :  %s", watch_dir)
    logger.info("  Output dir :  %s", output_dir)
    logger.info("=" * 60)

    handler  = PDFHandler(output_dir)
    observer = Observer()
    observer.schedule(handler, watch_dir, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutdown requested…")
    finally:
        observer.stop()
        observer.join()
        logger.info("PDF Organiser stopped.")
