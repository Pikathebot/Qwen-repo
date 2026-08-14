import logging
import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw
import pystray

logger = logging.getLogger("jarvis.desktop.tray")


def create_tray_icon_image(size: int = 64) -> Image.Image:
    """
    Generate a dynamic geometric icon for Jarvis.
    """
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Outer circle
    draw.ellipse([(4, 4), (size - 4, size - 4)], outline=(33, 150, 243, 255), width=4)
    # Inner glowing core
    draw.ellipse([(18, 18), (size - 18, size - 18)], fill=(0, 180, 216, 230))
    # Center dot
    draw.ellipse([(26, 26), (size - 26, size - 26)], fill=(255, 255, 255, 255))
    
    return image


class JarvisTray:
    """
    Windows System Tray integration for Jarvis Assistant.
    """

    def __init__(self, on_toggle: Callable[[], None], on_quit: Callable[[], None]):
        self.on_toggle = on_toggle
        self.on_quit = on_quit
        self.icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        image = create_tray_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("Show / Hide Jarvis (Alt+Space)", self._on_toggle_clicked, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit Jarvis", self._on_quit_clicked)
        )

        self.icon = pystray.Icon(
            "jarvis_assistant",
            image,
            "Jarvis Assistant (Active)",
            menu
        )

        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()
        logger.info("Jarvis System Tray service initialized.")

    def stop(self) -> None:
        if self.icon:
            self.icon.stop()
            self.icon = None

    def _on_toggle_clicked(self, icon, item) -> None:
        self.on_toggle()

    def _on_quit_clicked(self, icon, item) -> None:
        self.stop()
        self.on_quit()
