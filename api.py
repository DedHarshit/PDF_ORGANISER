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
# Queue for live watcher events (new files dropped after sweep)
_watcher_event_queue: queue.Queue = queue.Queue()

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
    return jsonify({"status": "ok"})

@app.route("/config", methods=["GET"])
def get_config():
    return jsonify(load_config())

@app.route("/config", methods=["POST"])
def update_config():
    cfg = load_config()
    cfg.update(request.json)
    save_config(cfg)
    return jsonify({"status": "saved"})

@app.route("/files", methods=["GET"])
def get_files():
    cfg = load_config()
    output_dir = Path(cfg["output_dir"])
    files = []
    for f in output_dir.rglob("*.pdf"):
        files.append({
            "name": f.name,
            "folder": f.parent.name,
            "path": str(f)
        })
    return jsonify({"files": files})

@app.route("/watcher/status", methods=["GET"])
def watcher_status():
    return jsonify({"active": _watcher_active})

# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)