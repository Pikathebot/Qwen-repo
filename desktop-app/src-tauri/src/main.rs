// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;

use tauri::{AppHandle, GlobalShortcutManager, Manager, PhysicalPosition, State, Window};

/// Label of the always-on-top HUD window declared in tauri.conf.json.
const HUD_LABEL: &str = "hud";

/// Candidate global hotkeys for summoning the HUD, tried in order.
///
/// `RegisterHotKey` grants exclusive ownership of a combination system-wide,
/// so if another running application already holds our first choice,
/// registration fails outright rather than sharing it. We fall back through
/// this list rather than leaving the HUD unreachable by keyboard.
const HUD_HOTKEY_CANDIDATES: &[&str] = &[
    "CmdOrCtrl+Shift+J",
    "CmdOrCtrl+Alt+J",
    "CmdOrCtrl+Shift+Grave",
    "Alt+Shift+J",
];

/// Gap from the screen edges, in logical pixels.
const HUD_MARGIN: f64 = 24.0;

/// The hotkey that actually registered, if any. `None` means every candidate
/// was already claimed by another application, in which case the HUD is
/// still reachable from the main window's toggle button.
struct HudHotkeyState(Mutex<Option<&'static str>>);

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

/// The hotkey that is actually live, or `null` if none could be registered
/// (another application already owns every candidate). The frontend uses
/// this to tell the user the real story instead of a hardcoded guess.
#[tauri::command]
fn hud_hotkey(state: State<HudHotkeyState>) -> Option<&'static str> {
    *state.0.lock().unwrap()
}

fn main() {
    tauri::Builder::default()
        .manage(HudHotkeyState(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![toggle_hud_window, hud_hotkey])
        .setup(|app| {
            let mut shortcuts = app.global_shortcut_manager();
            let hotkey_state: State<HudHotkeyState> = app.state();

            let mut registered = None;
            for candidate in HUD_HOTKEY_CANDIDATES {
                let handle = app.handle();
                match shortcuts.register(candidate, move || toggle_hud(&handle)) {
                    Ok(()) => {
                        registered = Some(*candidate);
                        break;
                    }
                    Err(e) => {
                        eprintln!("HUD hotkey {candidate} unavailable ({e}), trying next candidate...");
                    }
                }
            }

            match registered {
                Some(hotkey) => println!("HUD hotkey registered: {hotkey}"),
                None => eprintln!(
                    "No HUD hotkey could be registered - every candidate is already claimed by \
                     another application. The HUD remains reachable from the main window's toggle button."
                ),
            }

            *hotkey_state.0.lock().unwrap() = registered;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
