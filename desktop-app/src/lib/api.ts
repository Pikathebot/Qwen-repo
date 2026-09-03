import {
  Artifact,
  ArtifactVersion,
  Attachment,
  GovernorTelemetry,
  HealthResponse,
  MemoryItem,
  PersonaOverrides,
  PersonaStatus,
  AwarenessStatus,
  Briefing,
  HandsFreeStatus,
  Observation,
  VoiceListenResult,
  VoiceSayResult,
  VoiceSessionState,
  VoiceState,
  Project,
  ProjectFile,
  Session,
  UnloadResponse,
} from "./types";

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
 * Fetches the list of chat sessions from memory store, optionally filtered by active project.
 */
export async function fetchSessions(projectId?: string): Promise<Session[]> {
  const url = projectId
    ? `${API_BASE_URL}/sessions?project_id=${encodeURIComponent(projectId)}`
    : `${API_BASE_URL}/sessions`;

  const res = await fetch(url, {
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

// ==========================================
// Project / Workspace APIs
// ==========================================

export async function fetchProjects(): Promise<Project[]> {
  const res = await fetch(`${API_BASE_URL}/api/projects`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch projects: HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchActiveProject(): Promise<Project | null> {
  const res = await fetch(`${API_BASE_URL}/api/projects/active/current`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    if (res.status === 404) return null;
    throw new Error(`Failed to fetch active project: HTTP ${res.status}`);
  }
  return res.json();
}

export async function createProjectApi(data: {
  name: string;
  description?: string;
  instructions?: string;
  workspace_path?: string;
  local_folders?: string[];
}): Promise<Project> {
  const res = await fetch(`${API_BASE_URL}/api/projects`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to create project: HTTP ${res.status}`);
  }
  return res.json();
}

export async function getProjectApi(projectId: string): Promise<Project> {
  const res = await fetch(`${API_BASE_URL}/api/projects/${encodeURIComponent(projectId)}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to get project: HTTP ${res.status}`);
  }
  return res.json();
}

export async function updateProjectApi(
  projectId: string,
  data: Partial<{
    name: string;
    description: string;
    instructions: string;
    workspace_path: string;
    local_folders: string[];
    is_active: boolean;
  }>
): Promise<Project> {
  const res = await fetch(`${API_BASE_URL}/api/projects/${encodeURIComponent(projectId)}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    throw new Error(`Failed to update project: HTTP ${res.status}`);
  }
  return res.json();
}

export async function deleteProjectApi(
  projectId: string,
  cleanFiles: boolean = true
): Promise<boolean> {
  const res = await fetch(
    `${API_BASE_URL}/api/projects/${encodeURIComponent(projectId)}?clean_files=${cleanFiles}`,
    {
      method: "DELETE",
    }
  );
  return res.ok;
}

export async function activateProjectApi(projectId: string): Promise<Project> {
  const res = await fetch(
    `${API_BASE_URL}/api/projects/${encodeURIComponent(projectId)}/activate`,
    {
      method: "POST",
      headers: { Accept: "application/json" },
    }
  );
  if (!res.ok) {
    throw new Error(`Failed to activate project: HTTP ${res.status}`);
  }
  return res.json();
}

// ==========================================
// Attachments (User Uploads) APIs
// ==========================================

export async function uploadAttachmentApi(
  file: File,
  sessionId?: string,
  projectId?: string
): Promise<Attachment> {
  const formData = new FormData();
  formData.append("file", file);
  if (sessionId) formData.append("session_id", sessionId);
  if (projectId) formData.append("project_id", projectId);

  const res = await fetch(`${API_BASE_URL}/api/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload failed: HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchAttachments(
  sessionId?: string,
  projectId?: string
): Promise<Attachment[]> {
  const params = new URLSearchParams();
  if (sessionId) params.append("session_id", sessionId);
  if (projectId) params.append("project_id", projectId);

  const url = `${API_BASE_URL}/api/attachments${params.toString() ? `?${params.toString()}` : ""}`;
  const res = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch attachments: HTTP ${res.status}`);
  }
  return res.json();
}

export async function deleteAttachmentApi(attachmentId: string): Promise<boolean> {
  const res = await fetch(`${API_BASE_URL}/api/attachments/${encodeURIComponent(attachmentId)}`, {
    method: "DELETE",
  });
  return res.ok;
}

// ==========================================
// Artifacts (AI Generated Outputs) APIs
// ==========================================

export async function fetchArtifacts(
  sessionId?: string,
  projectId?: string
): Promise<Artifact[]> {
  const params = new URLSearchParams();
  if (sessionId) params.append("session_id", sessionId);
  if (projectId) params.append("project_id", projectId);

  const url = `${API_BASE_URL}/api/artifacts${params.toString() ? `?${params.toString()}` : ""}`;
  const res = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch artifacts: HTTP ${res.status}`);
  }
  return res.json();
}

export async function getArtifactApi(artifactId: string): Promise<Artifact> {
  const res = await fetch(`${API_BASE_URL}/api/artifacts/${encodeURIComponent(artifactId)}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to get artifact: HTTP ${res.status}`);
  }
  return res.json();
}

export async function createArtifactApi(data: {
  name: string;
  type: string;
  content: string;
  session_id?: string;
  project_id?: string;
  summary?: string;
}): Promise<Artifact> {
  const res = await fetch(`${API_BASE_URL}/api/artifacts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to create artifact: HTTP ${res.status}`);
  }
  return res.json();
}

export async function updateArtifactApi(
  artifactId: string,
  data: {
    name?: string;
    type?: string;
    content?: string;
    summary?: string;
    create_new_version?: boolean;
  }
): Promise<Artifact> {
  const res = await fetch(`${API_BASE_URL}/api/artifacts/${encodeURIComponent(artifactId)}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    throw new Error(`Failed to update artifact: HTTP ${res.status}`);
  }
  return res.json();
}

export async function deleteArtifactApi(artifactId: string): Promise<boolean> {
  const res = await fetch(`${API_BASE_URL}/api/artifacts/${encodeURIComponent(artifactId)}`, {
    method: "DELETE",
  });
  return res.ok;
}

export async function fetchArtifactVersions(artifactId: string): Promise<ArtifactVersion[]> {
  const res = await fetch(
    `${API_BASE_URL}/api/artifacts/${encodeURIComponent(artifactId)}/versions`,
    {
      method: "GET",
      headers: { Accept: "application/json" },
    }
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch artifact versions: HTTP ${res.status}`);
  }
  return res.json();
}

export async function createArtifactVersionApi(
  artifactId: string,
  data: { content: string; summary?: string }
): Promise<ArtifactVersion> {
  const res = await fetch(
    `${API_BASE_URL}/api/artifacts/${encodeURIComponent(artifactId)}/versions`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(data),
    }
  );
  if (!res.ok) {
    throw new Error(`Failed to create artifact version: HTTP ${res.status}`);
  }
  return res.json();
}

// ==========================================
// Project Files API (Section 19 / Amendment 4)
// ==========================================

export async function fetchProjectFiles(projectId: string): Promise<ProjectFile[]> {
  const res = await fetch(
    `${API_BASE_URL}/api/projects/${encodeURIComponent(projectId)}/files`,
    {
      method: "GET",
      headers: { Accept: "application/json" },
    }
  );
  if (!res.ok) {
    if (res.status === 404) return [];
    throw new Error(`Failed to fetch project files: HTTP ${res.status}`);
  }
  return res.json();
}

export async function restoreArtifactVersionApi(
  artifactId: string,
  version: number
): Promise<Artifact> {
  const res = await fetch(
    `${API_BASE_URL}/api/artifacts/${encodeURIComponent(artifactId)}/restore/${version}`,
    {
      method: "POST",
      headers: { Accept: "application/json" },
    }
  );
  if (!res.ok) {
    throw new Error(`Failed to restore artifact version: HTTP ${res.status}`);
  }
  return res.json();
}

// ==========================================
// Long-Term Memory APIs
// ==========================================

export async function fetchMemories(
  query?: string,
  category?: string,
  projectId?: string,
  limit: number = 20
): Promise<MemoryItem[]> {
  const params = new URLSearchParams();
  if (query) params.append("query", query);
  if (category) params.append("category", category);
  if (projectId) params.append("project_id", projectId);
  params.append("limit", String(limit));

  const res = await fetch(`${API_BASE_URL}/api/memories?${params.toString()}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch memories: HTTP ${res.status}`);
  }
  return res.json();
}

export async function createMemoryApi(data: {
  category: string;
  content: string;
  project_id?: string;
  source_session_id?: string;
  confidence?: number;
  pinned?: boolean;
}): Promise<MemoryItem> {
  const res = await fetch(`${API_BASE_URL}/api/memories`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    throw new Error(`Failed to create memory: HTTP ${res.status}`);
  }
  return res.json();
}

export async function deleteMemoryApi(memoryId: string): Promise<boolean> {
  const res = await fetch(`${API_BASE_URL}/api/memories/${encodeURIComponent(memoryId)}`, {
    method: "DELETE",
  });
  return res.ok;
}

// ==========================================
// Telemetry & Voice APIs
// ==========================================

export async function fetchGovernorStatus(): Promise<GovernorTelemetry> {
  const res = await fetch(`${API_BASE_URL}/governor/status`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch governor status: HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchVoiceStatus(): Promise<{
  wake_word_active: boolean;
  wake_words: string[];
  synthesizer_voice: string;
  voice_output_enabled: boolean;
  tts_engine_loaded: boolean;
  is_playing_audio: boolean;
}> {
  const res = await fetch(`${API_BASE_URL}/voice/status`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch voice status: HTTP ${res.status}`);
  }
  return res.json();
}

export async function toggleVoiceOutputApi(enabled: boolean): Promise<{
  enabled: boolean;
  engine: string;
  vram_required_mb: number;
  is_loaded: boolean;
  is_playing: boolean;
}> {
  const res = await fetch(`${API_BASE_URL}/voice/output`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) {
    throw new Error(`Failed to toggle voice output: HTTP ${res.status}`);
  }
  return res.json();
}

// ==========================================
// Persona APIs
// ==========================================

export async function fetchPersona(): Promise<PersonaStatus> {
  const res = await fetch(`${API_BASE_URL}/api/persona`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch persona: HTTP ${res.status}`);
  }
  return res.json();
}

export async function setPersonaApi(personaId: string): Promise<PersonaStatus> {
  const res = await fetch(`${API_BASE_URL}/api/persona`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ persona_id: personaId }),
  });
  if (!res.ok) {
    throw new Error(`Failed to set persona: HTTP ${res.status}`);
  }
  return res.json();
}

export async function setPersonaOverridesApi(
  overrides: PersonaOverrides
): Promise<PersonaStatus> {
  const res = await fetch(`${API_BASE_URL}/api/persona/overrides`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(overrides),
  });
  if (!res.ok) {
    throw new Error(`Failed to update persona: HTTP ${res.status}`);
  }
  return res.json();
}

export async function clearPersonaOverridesApi(): Promise<PersonaStatus> {
  const res = await fetch(`${API_BASE_URL}/api/persona/overrides`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to reset persona: HTTP ${res.status}`);
  }
  return res.json();
}

// ==========================================
// Hands-free Voice APIs
// ==========================================

export async function listenChunkApi(
  audio: Blob,
  sessionId: string
): Promise<VoiceListenResult> {
  const form = new FormData();
  const extension = audio.type.includes("ogg") ? "ogg" : audio.type.includes("wav") ? "wav" : "webm";
  form.append("file", audio, `utterance.${extension}`);
  form.append("session_id", sessionId);

  const res = await fetch(`${API_BASE_URL}/api/voice/listen`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(`Voice listen failed: HTTP ${res.status}`);
  }
  return res.json();
}

export async function sayApi(
  text: string,
  sessionId: string,
  voiceId?: string
): Promise<VoiceSayResult> {
  const res = await fetch(`${API_BASE_URL}/api/voice/say`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ text, session_id: sessionId, voice_id: voiceId }),
  });
  if (!res.ok) {
    throw new Error(`Voice synthesis failed: HTTP ${res.status}`);
  }
  return res.json();
}

async function voiceSessionAction(
  sessionId: string,
  action: "start" | "stop" | "arm"
): Promise<VoiceSessionState> {
  const res = await fetch(
    `${API_BASE_URL}/api/voice/session/${encodeURIComponent(sessionId)}/${action}`,
    { method: "POST", headers: { Accept: "application/json" } }
  );
  if (!res.ok) {
    throw new Error(`Voice ${action} failed: HTTP ${res.status}`);
  }
  return res.json();
}

export const startHandsFreeApi = (sessionId: string) => voiceSessionAction(sessionId, "start");
export const stopHandsFreeApi = (sessionId: string) => voiceSessionAction(sessionId, "stop");
export const armFollowUpApi = (sessionId: string) => voiceSessionAction(sessionId, "arm");

export async function setVoiceStateApi(
  sessionId: string,
  state: VoiceState
): Promise<VoiceSessionState> {
  const res = await fetch(
    `${API_BASE_URL}/api/voice/session/${encodeURIComponent(sessionId)}/state`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ state }),
    }
  );
  if (!res.ok) {
    throw new Error(`Voice state update failed: HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchHandsFreeStatus(): Promise<HandsFreeStatus> {
  const res = await fetch(`${API_BASE_URL}/api/voice/hands-free`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch hands-free status: HTTP ${res.status}`);
  }
  return res.json();
}

// ==========================================
// Ambient Awareness APIs
// ==========================================

export async function fetchAwarenessStatus(): Promise<AwarenessStatus> {
  const res = await fetch(`${API_BASE_URL}/api/awareness/status`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch awareness status: HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchObservations(
  sinceSeq = 0,
  limit = 20
): Promise<{ observations: Observation[]; active_conditions: string[]; latest_seq: number }> {
  const params = new URLSearchParams({ since_seq: String(sinceSeq), limit: String(limit) });
  const res = await fetch(`${API_BASE_URL}/api/awareness/observations?${params}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch observations: HTTP ${res.status}`);
  }
  return res.json();
}

export async function acknowledgeObservationApi(observationId: string): Promise<void> {
  const res = await fetch(
    `${API_BASE_URL}/api/awareness/observations/${encodeURIComponent(observationId)}/ack`,
    { method: "POST", headers: { Accept: "application/json" } }
  );
  if (!res.ok) {
    throw new Error(`Failed to acknowledge observation: HTTP ${res.status}`);
  }
}

export async function fetchBriefing(): Promise<Briefing> {
  const res = await fetch(`${API_BASE_URL}/api/awareness/briefing`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch briefing: HTTP ${res.status}`);
  }
  return res.json();
}

export const AWARENESS_STREAM_URL = `${API_BASE_URL}/api/awareness/stream`;
