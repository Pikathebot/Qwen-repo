/**
 * Thin bridge to the Tauri shell.
 *
 * The app also runs as a plain web page during development, where none of
 * these exist — every helper degrades to a no-op rather than throwing, so the
 * UI can call them unconditionally.
 */

export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_IPC__" in window;
}

async function invokeCommand<T>(command: string): Promise<T | null> {
  if (!isTauri()) return null;
  try {
    const { invoke } = await import("@tauri-apps/api/tauri");
    return (await invoke(command)) as T;
  } catch {
    return null;
  }
}

/** Show or hide the always-on-top HUD window. */
export async function toggleHudWindow(): Promise<void> {
  await invokeCommand<void>("toggle_hud_window");
}

/** The global shortcut that summons the HUD, for display in the UI. */
export async function getHudHotkey(): Promise<string | null> {
  return invokeCommand<string>("hud_hotkey");
}
