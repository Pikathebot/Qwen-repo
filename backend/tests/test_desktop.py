import os
from pathlib import Path
import pytest
from desktop.tray import create_tray_icon_image, JarvisTray
from desktop.hotkey import GlobalHotkeyListener
from desktop.app import DesktopAPI


def test_ui_assets_exist():
    base_dir = Path(__file__).resolve().parent.parent.parent
    ui_dir = base_dir / "desktop" / "ui"

    html_file = ui_dir / "index.html"
    css_file = ui_dir / "styles.css"
    js_file = ui_dir / "app.js"

    assert html_file.exists()
    assert css_file.exists()
    assert js_file.exists()

    html_content = html_file.read_text(encoding="utf-8")
    assert "app-layout" in html_content
    assert "promptInput" in html_content
    assert "confirmationPanel" in html_content

    css_content = css_file.read_text(encoding="utf-8")
    assert ".app-layout" in css_content
    assert "border-radius" in css_content

    js_content = js_file.read_text(encoding="utf-8")
    assert "handleSubmit" in js_content
    assert "pollGovernor" in js_content


def test_tray_icon_generation():
    img = create_tray_icon_image(size=64)
    assert img is not None
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


def test_hotkey_listener_initialization():
    triggered = []

    def on_hotkey():
        triggered.append(True)

    listener = GlobalHotkeyListener(on_trigger=on_hotkey)
    assert listener is not None
    listener.start()
    assert listener._listener is not None
    listener.stop()
    assert listener._listener is None


def test_desktop_api_bridge():
    mock_window = type("MockWindow", (), {"hide": lambda self: None})()
    holder = [mock_window]
    api = DesktopAPI(holder)
    # Should not raise exception
    api.hide_window()
