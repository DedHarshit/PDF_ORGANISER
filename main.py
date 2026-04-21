"""
main.py
-------
Entry point for the PDF Organiser.
Reads config from environment / .env, sets up logging, and starts the watcher.

Usage:
    python main.py

Environment variables (can be set in .env):
    GITHUB_TOKEN   — required  — your GitHub Marketplace API token
    WATCH_DIR      — optional  — folder to monitor  (default: ./inbox)
    OUTPUT_DIR     — optional  — organised root dir  (default: ./organised)
    LOG_LEVEL      — optional  — DEBUG / INFO / WARNING (default: INFO)
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from watcher import start_watching

load_dotenv()


# ── Logging setup ─────────────────────────────────────────────────────────────

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s  [%(levelname)-8s]  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pdf_organiser.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


# ── Config validation ─────────────────────────────────────────────────────────

def _require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        logger.critical("Missing required environment variable: %s", key)
        raise SystemExit(1)
    return val


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _require_env("GITHUB_TOKEN")

    watch_dir  = os.getenv("WATCH_DIR",  "./inbox")
    output_dir = os.getenv("OUTPUT_DIR", "./organised")

    # Bootstrap directories so the user doesn't have to create them manually
    Path(watch_dir).mkdir(parents=True, exist_ok=True)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    start_watching(watch_dir, output_dir)
