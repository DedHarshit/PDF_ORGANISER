"""
api.py
------
Flask REST backend for the PDF Organiser GUI.
"""

import os
import json
import logging
import threading
import time
import queue
from pathlib import Path
from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv, set_key

load_dotenv()

BASE_DIR    = Path(__file__).parent
CONFIG_FILE = BASE_DIR / ".gui_config.json"
LOG_FILE    = BASE_DIR / "pdf_organiser.log"
ENV_FILE    = BASE_DIR / ".env"

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

# ── In-memory state ────────────────────────────────────────────────────────────
_watcher_thread: threading.Thread | None = None
_watcher_stop   = threading.Event()
_watcher_active = False
_run_lock       = threading.Lock()

# Broadcast queue: each SSE subscriber gets its own Queue so reconnects
# never lose events and multiple tabs stay in sync.
_watcher_subscribers: list[queue.Queue] = []
_watcher_subscribers_lock = threading.Lock()


def _broadcast(evt: dict):
    """Push an event to every active /api/watcher/events subscriber."""
    with _watcher_subscribers_lock:
        for q in _watcher_subscribers:
            q.put(evt)


def _subscribe() -> queue.Queue:
    q: queue.Queue = queue.Queue()
    with _watcher_subscribers_lock:
        _watcher_subscribers.append(q)
    return q


def _unsubscribe(q: queue.Queue):
    with _watcher_subscribers_lock:
        try:
            _watcher_subscribers.remove(q)
        except ValueError:
            pass

# ── Config helpers ─────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "watch_dir":   str(BASE_DIR / "inbox"),
    "output_dir":  str(BASE_DIR / "organised"),
    "github_token": "",
    "file_action":  "move",
    "log_level":    "INFO",
    "auto_watcher": False,
    "skip_dupes":   True,
    "auto_mkdir":   True,
}

def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return dict(DEFAULT_CONFIG)

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    if cfg.get("github_token"):
        ENV_FILE.touch(exist_ok=True)
        set_key(str(ENV_FILE), "GITHUB_TOKEN", cfg["github_token"])
    if cfg.get("watch_dir"):
        set_key(str(ENV_FILE), "WATCH_DIR", cfg["watch_dir"])
    if cfg.get("output_dir"):
        set_key(str(ENV_FILE), "OUTPUT_DIR", cfg["output_dir"])
    if cfg.get("log_level"):
        set_key(str(ENV_FILE), "LOG_LEVEL", cfg["log_level"])

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(BASE_DIR), "pdf_organiser.html")

@app.route("/api/status")
def status():
    cfg = load_config()
    watch = Path(cfg["watch_dir"])
    out   = Path(cfg["output_dir"])
    pdf_count = len(list(watch.glob("*.pdf"))) if watch.exists() else 0
    return jsonify({
        "ok": True,
        "watcher_active": _watcher_active,
        "watch_dir": str(watch),
        "output_dir": str(out),
        "watch_dir_exists": watch.exists(),
        "output_dir_exists": out.exists(),
        "pdf_count": pdf_count,
        "token_set": bool(cfg.get("github_token")),
    })

@app.route("/api/config", methods=["GET"])
def get_config():
    cfg = load_config()
    cfg_safe = dict(cfg)
    if cfg_safe.get("github_token"):
        t = cfg_safe["github_token"]
        cfg_safe["github_token_masked"] = t[:4] + "\u2022" * (len(t) - 8) + t[-4:] if len(t) > 8 else "\u2022" * len(t)
    return jsonify(cfg_safe)

@app.route("/api/config", methods=["POST"])
def post_config():
    data = request.json or {}
    cfg  = load_config()
    cfg.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
    save_config(cfg)
    return jsonify({"ok": True})

@app.route("/api/scan")
def scan():
    cfg   = load_config()
    watch = Path(cfg["watch_dir"])
    if not watch.exists():
        return jsonify({"files": [], "error": f"Directory not found: {watch}"})
    files = [
        {"name": p.name, "size": p.stat().st_size, "path": str(p)}
        for p in sorted(watch.glob("*.pdf"))
    ]
    return jsonify({"files": files, "count": len(files)})

@app.route("/api/run", methods=["GET", "POST"])
def run_organiser():
    if not _run_lock.acquire(blocking=False):
        return jsonify({"error": "A run is already in progress"}), 409

    cfg = load_config()

    try:
        from classifier import classify_pdf, PDFExtractionError, PDFNoContentError
        from organiser  import organise_pdf, move_to_error
    except ImportError as e:
        _run_lock.release()
        return jsonify({"error": f"Import error: {e}"}), 500

    watch_dir  = Path(cfg["watch_dir"])
    output_dir = Path(cfg["output_dir"])
    action     = cfg.get("file_action", "move")
    pdfs       = sorted(watch_dir.glob("*.pdf")) if watch_dir.exists() else []

    def event_stream():
        try:
            total   = len(pdfs)
            sorted_ = 0
            errors_ = 0
            yield f"data: {json.dumps({'type':'start','total':total})}\n\n"
            for i, pdf in enumerate(pdfs, 1):
                try:
                    folder = classify_pdf(str(pdf))
                    if action == "dry_run":
                        msg = f"[DRY RUN] Would move -> {folder}/{pdf.name}"
                    elif action == "copy":
                        import shutil
                        dest_dir = output_dir / folder
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(pdf), str(dest_dir / pdf.name))
                        msg = f"Copied -> {folder}/{pdf.name}"
                    else:
                        organise_pdf(str(pdf), str(output_dir), folder)
                        msg = f"Moved -> {folder}/{pdf.name}"
                    sorted_ += 1
                    yield f"data: {json.dumps({'type':'progress','file':pdf.name,'dest':folder,'msg':msg,'index':i,'total':total,'status':'ok'})}\n\n"
                except (PDFExtractionError, PDFNoContentError) as exc:
                    errors_ += 1
                    move_to_error(str(pdf), str(output_dir), "extraction_error")
                    yield f"data: {json.dumps({'type':'progress','file':pdf.name,'msg':f'Error: {exc}','index':i,'total':total,'status':'error'})}\n\n"
                except RuntimeError as exc:
                    errors_ += 1
                    move_to_error(str(pdf), str(output_dir), "api_error")
                    yield f"data: {json.dumps({'type':'progress','file':pdf.name,'msg':f'API error: {exc}','index':i,'total':total,'status':'error'})}\n\n"
            yield f"data: {json.dumps({'type':'done','total':total,'sorted':sorted_,'errors':errors_})}\n\n"
        finally:
            _run_lock.release()

    return Response(event_stream(), mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@app.route("/api/watcher/start", methods=["POST"])
def watcher_start():
    """
    Just starts the filesystem observer for NEW files.
    Does NOT process existing files — that is handled by /api/watcher/sweep.
    """
    global _watcher_thread, _watcher_active
    if _watcher_active:
        return jsonify({"ok": True, "message": "Already running"})
    cfg = load_config()
    if not cfg.get("github_token"):
        return jsonify({"error": "GITHUB_TOKEN not set"}), 400

    os.environ["GITHUB_TOKEN"] = cfg["github_token"]
    _watcher_stop.clear()

    def run():
        global _watcher_active
        _watcher_active = True
        try:
            import watchdog.observers as _obs
            from watchdog.events import FileSystemEventHandler
            from classifier import classify_pdf
            from organiser  import organise_pdf, move_to_error

            class _Handler(FileSystemEventHandler):
                def on_created(self, event):
                    if event.is_directory or not event.src_path.lower().endswith(".pdf"):
                        return
                    time.sleep(2)
                    pdf_name = Path(event.src_path).name
                    try:
                        folder = classify_pdf(event.src_path)
                        organise_pdf(event.src_path, cfg["output_dir"], folder)
                        msg = f"Moved -> {folder}/{pdf_name}"
                        logger.info("Watcher: %s", msg)
                        _broadcast({"type": "file", "file": pdf_name, "dest": folder, "msg": msg, "status": "ok"})
                    except Exception as exc:
                        msg = f"Error on {pdf_name}: {exc}"
                        logger.error("Watcher: %s", msg)
                        try:
                            move_to_error(event.src_path, cfg["output_dir"], "watcher_error")
                        except Exception:
                            pass
                        _broadcast({"type": "file", "file": pdf_name, "dest": "", "msg": msg, "status": "error"})

            observer = _obs.Observer()
            observer.schedule(_Handler(), cfg["watch_dir"], recursive=False)
            observer.start()
            while not _watcher_stop.is_set():
                time.sleep(1)
            observer.stop()
            observer.join()
        finally:
            _watcher_active = False
            _broadcast({"type": "stopped"})

    _watcher_thread = threading.Thread(target=run, daemon=True)
    _watcher_thread.start()
    return jsonify({"ok": True, "message": "Watcher started"})


@app.route("/api/watcher/sweep", methods=["GET", "POST"])
def watcher_sweep():
    """
    SSE: processes PDFs already in watch folder, streams progress to UI.
    Call this BEFORE starting /api/watcher/events listener.
    The background observer is started via /api/watcher/start separately
    so there is no race — sweep finishes first, then observer watches new files.
    """
    if not _run_lock.acquire(blocking=False):
        def _skip():
            yield f"data: {json.dumps({'type':'done','total':0,'sorted':0,'errors':0})}\n\n"
        return Response(_skip(), mimetype="text/event-stream",
                        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})

    cfg = load_config()

    try:
        from classifier import classify_pdf, PDFExtractionError, PDFNoContentError
        from organiser  import organise_pdf, move_to_error
    except ImportError as e:
        _run_lock.release()
        def _err():
            yield f"data: {json.dumps({'type':'error','message': str(e)})}\n\n"
        return Response(_err(), mimetype="text/event-stream",
                        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})

    watch_dir  = Path(cfg["watch_dir"])
    output_dir = Path(cfg["output_dir"])
    action     = cfg.get("file_action", "move")
    pdfs       = sorted(watch_dir.glob("*.pdf")) if watch_dir.exists() else []

    def event_stream():
        try:
            total   = len(pdfs)
            sorted_ = 0
            errors_ = 0
            yield f"data: {json.dumps({'type':'start','total':total})}\n\n"
            for i, pdf in enumerate(pdfs, 1):
                try:
                    folder = classify_pdf(str(pdf))
                    if action == "dry_run":
                        msg = f"[DRY RUN] Would move -> {folder}/{pdf.name}"
                    elif action == "copy":
                        import shutil
                        dest_dir = output_dir / folder
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(pdf), str(dest_dir / pdf.name))
                        msg = f"Copied -> {folder}/{pdf.name}"
                    else:
                        organise_pdf(str(pdf), str(output_dir), folder)
                        msg = f"Moved -> {folder}/{pdf.name}"
                    sorted_ += 1
                    yield f"data: {json.dumps({'type':'progress','file':pdf.name,'dest':folder,'msg':msg,'index':i,'total':total,'status':'ok'})}\n\n"
                except (PDFExtractionError, PDFNoContentError) as exc:
                    errors_ += 1
                    move_to_error(str(pdf), str(output_dir), "extraction_error")
                    yield f"data: {json.dumps({'type':'progress','file':pdf.name,'msg':f'Error: {exc}','index':i,'total':total,'status':'error'})}\n\n"
                except RuntimeError as exc:
                    errors_ += 1
                    move_to_error(str(pdf), str(output_dir), "api_error")
                    yield f"data: {json.dumps({'type':'progress','file':pdf.name,'msg':f'API error: {exc}','index':i,'total':total,'status':'error'})}\n\n"
            yield f"data: {json.dumps({'type':'done','total':total,'sorted':sorted_,'errors':errors_})}\n\n"
        finally:
            _run_lock.release()

    return Response(event_stream(), mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@app.route("/api/watcher/events")
def watcher_events():
    """
    SSE: streams events for files processed by the background watcher AFTER sweep.
    Each caller gets its own queue (broadcast pattern) so reconnects never lose events.
    An immediate 'connected' event is sent so the frontend knows the stream is live.
    """
    def event_stream():
        q = _subscribe()
        try:
            # Let the frontend know the SSE pipe is open immediately
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            while True:
                try:
                    evt = q.get(timeout=25)
                    yield f"data: {json.dumps(evt)}\n\n"
                    if evt.get("type") == "stopped":
                        break
                except queue.Empty:
                    # Keepalive ping — prevents proxies/browsers from closing the stream
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            _unsubscribe(q)

    return Response(event_stream(), mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@app.route("/api/watcher/stop", methods=["POST"])
def watcher_stop():
    _watcher_stop.set()
    return jsonify({"ok": True, "message": "Watcher stopping..."})

@app.route("/api/log")
def get_log():
    n = int(request.args.get("lines", 100))
    if not LOG_FILE.exists():
        return jsonify({"lines": []})
    with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return jsonify({"lines": [l.rstrip() for l in lines[-n:]]})

if __name__ == "__main__":
    print("\n PDF Organiser API  ->  http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
