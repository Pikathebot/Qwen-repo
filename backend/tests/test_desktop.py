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


def test_desktop_redesign_components():
    base_dir = Path(__file__).resolve().parent.parent.parent
    ui_dir = base_dir / "desktop" / "ui"

    html = (ui_dir / "index.html").read_text(encoding="utf-8")
    css = (ui_dir / "styles.css").read_text(encoding="utf-8")
    js = (ui_dir / "app.js").read_text(encoding="utf-8")

    # 1. Mode Toggle & Active Project DOM
    assert "chatScopeToggle" in html
    assert "modeWorkspaceBtn" in html
    assert "modeSystemBtn" in html
    assert "activeProjectIndicator" in html
    assert "active-project-name" in html

    # 2. Top Nav Model Tier & Governor Pill
    assert "modelSelect" in html
    assert "activeTierBadge" in html
    assert "governorPill" in html
    assert "governorTooltip" in html


    # 3. Empty State Mode Aware Elements
    assert "empty-state" in html
    assert "empty-state-title" in html
    assert "empty-state-subtitle" in html

    # 4. CSS Design Tokens
    assert "--governor-normal" in css
    assert "--governor-throttled" in css
    assert "--governor-paused" in css
    assert "--governor-disconnected" in css
    assert "governor-pill--disconnected" in css
    assert "--tier-1-color" in css
    assert "--tier-2-color" in css
    assert "--tier-3-color" in css

    # 5. JS Handlers
    assert "setChatMode" in js
    assert "updateModelTierBadge" in js
    assert "currentMode" in js
    assert "pollGovernor" in js
    assert "model_unloaded" in js


