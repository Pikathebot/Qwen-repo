import logging
import threading
from typing import Callable, Optional
from pynput import keyboard

logger = logging.getLogger("jarvis.desktop.hotkey")


class GlobalHotkeyListener:
    """
    Listens for system-wide global hotkeys (Alt+Space or Ctrl+Space) to summon/hide Jarvis.
    """

    def __init__(self, on_trigger: Callable[[], None]):
        self.on_trigger = on_trigger
        self._listener: Optional[keyboard.GlobalHotKeys] = None

    def start(self) -> None:
        hotkeys = {
            '<alt>+<space>': self._handle_hotkey,
            '<ctrl>+<space>': self._handle_hotkey,
        }

        try:
            self._listener = keyboard.GlobalHotKeys(hotkeys)
            self._listener.start()
            logger.info("Global hotkey listener active: Alt+Space / Ctrl+Space.")
        except Exception as e:
            logger.warning("Could not register global hotkeys: %s", e)

    def stop(self) -> None:
        if self._listener:
            try:
                self._listener.stop()
                if hasattr(self._listener, "join"):
                    self._listener.join(timeout=1.0)
            except Exception:
                pass
            self._listener = None


    def _handle_hotkey(self) -> None:
        logger.info("Global hotkey triggered.")
        self.on_trigger()
