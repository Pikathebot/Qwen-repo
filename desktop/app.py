import logging
import os
import sys
import socket
from pathlib import Path
import webview

from desktop.tray import JarvisTray
from desktop.hotkey import GlobalHotkeyListener

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("jarvis.desktop")


class DesktopAPI:
    """
    Python bridge exposed to JavaScript in pywebview.
    """

    def __init__(self, window_holder: list):
        self._window_holder = window_holder

    def hide_window(self) -> None:
        if self._window_holder and self._window_holder[0]:
            self._window_holder[0].hide()

    def minimize_window(self) -> None:
        if self._window_holder and self._window_holder[0]:
            self._window_holder[0].minimize()


def launch_desktop(lock_socket: socket.socket = None):
    # Cache directory for persistent WebView2 user data & permissions
    cache_dir = Path(__file__).resolve().parent.parent / "data" / "webview_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Use secure local HTTP origin so Chromium remembers microphone permissions permanently
    ui_url = "http://127.0.0.1:8000/ui/index.html"

    window_holder = [None]
    api = DesktopAPI(window_holder)

    # 1. Create standard modern windowed desktop app with persistent origin
    window = webview.create_window(
        title="Jarvis - Local AI Command Center",
        url=ui_url,
        js_api=api,
        width=1040,
        height=720,
        min_size=(800, 540),
        resizable=True,
        frameless=False,
        easy_drag=False,
        on_top=False,
        background_color='#0b0f19'
    )
    window_holder[0] = window

    # 2. Window Toggle & Show Functions
    is_visible = [True]

    def show_window():
        if window_holder[0]:
            window_holder[0].show()
            window_holder[0].restore()
            is_visible[0] = True

    def toggle_window():
        if window_holder[0]:
            if is_visible[0]:
                window_holder[0].hide()
                is_visible[0] = False
            else:
                window_holder[0].show()
                window_holder[0].restore()
                is_visible[0] = True

    def quit_app():
        if hotkey_listener:
            hotkey_listener.stop()
        if tray_service:
            tray_service.stop()
        if window_holder[0]:
            window_holder[0].destroy()
        sys.exit(0)

    # 3. Start System Tray & Global Hotkey
    tray_service = JarvisTray(on_toggle=toggle_window, on_quit=quit_app)
    tray_service.start()

    hotkey_listener = GlobalHotkeyListener(on_trigger=toggle_window)
    hotkey_listener.start()

    # 4. Listen on single-instance lock socket for focus/show requests
    if lock_socket:
        import threading
        def _socket_listener():
            try:
                lock_socket.listen(5)
                while True:
                    conn, _ = lock_socket.accept()
                    with conn:
                        data = conn.recv(128)
                        if b"SHOW" in data:
                            show_window()
            except Exception:
                pass

        listener_thread = threading.Thread(target=_socket_listener, daemon=True)
        listener_thread.start()

    logger.info("Jarvis Desktop App ready. Press Alt+Space to summon.")

    # 5. Start GUI Event Loop with persistent storage path
    webview.start(debug=False, storage_path=str(cache_dir), private_mode=False)



if __name__ == "__main__":
    launch_desktop()
