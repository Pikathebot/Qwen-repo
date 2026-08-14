import logging
import os
import sys
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


def launch_desktop():
    ui_path = Path(__file__).resolve().parent / "ui" / "index.html"
    if not ui_path.exists():
        logger.error("UI HTML not found at %s", ui_path)
        sys.exit(1)

    window_holder = [None]
    api = DesktopAPI(window_holder)

    # 1. Create standard modern windowed desktop app
    window = webview.create_window(
        title="Jarvis — Local AI Assistant",
        url=str(ui_path.as_uri()),
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

    # 2. Window Toggle Function
    is_visible = [True]

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

    logger.info("Jarvis Desktop App ready. Press Alt+Space to summon.")

    # 4. Start GUI Event Loop
    webview.start(debug=False)


if __name__ == "__main__":
    launch_desktop()
