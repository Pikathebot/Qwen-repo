// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{AppHandle, GlobalShortcutManager, Manager, PhysicalPosition, Window};

/// Label of the always-on-top HUD window declared in tauri.conf.json.
const HUD_LABEL: &str = "hud";

/// Summon/dismiss the HUD from anywhere, even with Jarvis unfocused.
const HUD_HOTKEY: &str = "CmdOrCtrl+Shift+J";

/// Gap from the screen edges, in logical pixels.
const HUD_MARGIN: f64 = 24.0;

/// Park the HUD above the taskbar in the bottom-right corner.
///
/// Done on every show rather than once at startup so the HUD lands correctly
/// after a resolution change or a move to another monitor.
fn position_hud(window: &Window) {
    let Ok(Some(monitor)) = window.current_monitor() else {
        return;
    };
    let Ok(size) = window.outer_size() else {
        return;
    };

    let screen = monitor.size();
    let scale = monitor.scale_factor();
    let margin = (HUD_MARGIN * scale) as i32;
    let origin = monitor.position();

    let x = origin.x + screen.width as i32 - size.width as i32 - margin;
    // Extra bottom margin keeps the HUD clear of the Windows taskbar.
    let y = origin.y + screen.height as i32 - size.height as i32 - (margin * 3);

    let _ = window.set_position(PhysicalPosition::new(x, y));
}

fn toggle_hud(app: &AppHandle) {
    let Some(window) = app.get_window(HUD_LABEL) else {
        return;
    };

    if window.is_visible().unwrap_or(false) {
        let _ = window.hide();
    } else {
        position_hud(&window);
        let _ = window.show();
        let _ = window.set_focus();
    }
}

#[tauri::command]
fn toggle_hud_window(app: AppHandle) {
    toggle_hud(&app);
}

#[tauri::command]
fn hud_hotkey() -> &'static str {
    HUD_HOTKEY
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![toggle_hud_window, hud_hotkey])
        .setup(|app| {
            let handle = app.handle();
            let mut shortcuts = app.global_shortcut_manager();

            // A failed registration (the combination is already taken by
            // another application) must not stop Jarvis from starting; the
            // HUD is still reachable from the main window.
            if let Err(e) = shortcuts.register(HUD_HOTKEY, move || toggle_hud(&handle)) {
                eprintln!("Could not register HUD hotkey {HUD_HOTKEY}: {e}");
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
