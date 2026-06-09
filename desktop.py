import threading
import time
import sys
import os
import json
import queue
import urllib.request
import webview
from dotenv import load_dotenv

load_dotenv()

# ── Start Flask in background ──────────────────────────────────────────────────

def start_flask():
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    from api import app
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False, threaded=True)

flask_thread = threading.Thread(target=start_flask, daemon=True)
flask_thread.start()

# Wait until Flask is up
for _ in range(80):
    try:
        urllib.request.urlopen('http://127.0.0.1:5000/api/status', timeout=1)
        break
    except Exception:
        time.sleep(0.1)


# ── Tray icon ──────────────────────────────────────────────────────────────────

def build_tray_icon():
    """Build a simple PDF icon as a PIL Image (no external file needed)."""
    from PIL import Image, ImageDraw, ImageFont
    size = 64
    img  = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Red rounded rectangle
    draw.rounded_rectangle([4, 2, 60, 62], radius=8, fill=(232, 69, 69, 255))
    # White "PDF" text
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
    draw.text((12, 22), "PDF", fill=(255, 255, 255, 255), font=font)
    return img


def notify(title: str, message: str):
    """Send a system tray notification (best-effort)."""
    try:
        if _tray_icon and hasattr(_tray_icon, 'notify'):
            _tray_icon.notify(message, title)
    except Exception:
        pass


_tray_icon   = None
_main_window = None
_app_quitting = False


def show_window():
    global _main_window
    if _main_window:
        try:
            _main_window.show()
            _main_window.restore()
        except Exception:
            pass


def quit_app(icon=None, item=None):
    global _app_quitting
    _app_quitting = True
    if _tray_icon:
        try:
            _tray_icon.stop()
        except Exception:
            pass
    if _main_window:
        try:
            _main_window.destroy()
        except Exception:
            pass
    os._exit(0)


def start_tray():
    global _tray_icon
    try:
        import pystray
        from pystray import MenuItem as Item

        icon_image = build_tray_icon()

        menu = pystray.Menu(
            Item('Open PDF Organiser', lambda icon, item: show_window(), default=True),
            pystray.Menu.SEPARATOR,
            Item('Quit', quit_app),
        )

        _tray_icon = pystray.Icon(
            name  = 'PDFOrganiser',
            icon  = icon_image,
            title = 'PDF Organiser',
            menu  = menu,
        )
        _tray_icon.run()          # blocks until .stop() is called
    except ImportError:
        # pystray not installed — just keep running without tray
        pass
    except Exception as e:
        print(f"Tray error: {e}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    global _main_window

    js_api = JsAPI()

    _main_window = webview.create_window(
        title            = 'PDF Organiser',
        url              = 'http://127.0.0.1:5000/',
        width            = 1100,
        height           = 780,
        min_size         = (800, 600),
        resizable        = True,
        js_api           = js_api,
        text_select      = False,
        background_color = '#0d0f12',
    )

    def on_loaded():
        _main_window.evaluate_js(INJECT_JS)

    def on_closing():
        """Intercept window close — hide to tray instead of quitting."""
        if _app_quitting:
            return True   # allow close during real quit
        try:
            _main_window.hide()
            notify('PDF Organiser', 'Running in background. Right-click tray icon to open.')
        except Exception:
            pass
        return False      # False = cancel the close, keeping app alive

    _main_window.events.loaded  += on_loaded
    _main_window.events.closing += on_closing

    # Start tray in a background thread so webview.start() can run on main thread
    tray_thread = threading.Thread(target=start_tray, daemon=True)
    tray_thread.start()

    gui = None
    if sys.platform == 'win32':
        gui = 'edgechromium'
    elif sys.platform == 'darwin':
        gui = 'cocoa'

    webview.start(gui=gui, debug=False)


if __name__ == '__main__':
    main()
