import { HealthResponse, Session, UnloadResponse } from "./types";

export const API_BASE_URL = "http://127.0.0.1:8000";

/**
 * Generate a unique session ID prefixed for clarity.
 */
export function createNewSessionId(): string {
  return `session_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 7)}`;
}

/**
 * Fetches backend health status and system telemetry.
 */
export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/health`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch health: HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Fetches the list of active chat sessions from memory store.
 */
export async function fetchSessions(): Promise<Session[]> {
  const res = await fetch(`${API_BASE_URL}/sessions`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch sessions: HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Fetches message history for a specific session ID.
 */
export async function fetchSessionMessages(
  sessionId: string
): Promise<Array<Record<string, unknown>>> {
  const res = await fetch(`${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}/messages`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    if (res.status === 404) return [];
    throw new Error(`Failed to fetch session messages: HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Deletes a session and clears its associated context.
 */
export async function deleteSessionApi(sessionId: string): Promise<boolean> {
  const res = await fetch(`${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
  return res.ok;
}

/**
 * Requests immediate model eviction from GPU VRAM.
 */
export async function unloadModelsApi(): Promise<UnloadResponse> {
  const res = await fetch(`${API_BASE_URL}/models/unload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to unload models: HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Manually pause governor activities.
 */
export async function pauseGovernor(reason?: string): Promise<void> {
  await fetch(`${API_BASE_URL}/governor/pause`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason || "User requested manual pause" }),
  });
}

/**
 * Manually resume governor activities.
 */
export async function resumeGovernor(): Promise<void> {
  await fetch(`${API_BASE_URL}/governor/resume`, {
    method: "POST",
  });
}
