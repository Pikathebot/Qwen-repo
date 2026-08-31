export type MessageRole = "user" | "assistant" | "system" | "tool";

export type ToolStatus = "running" | "success" | "error";

export interface ToolStep {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  status: ToolStatus;
  result?: unknown;
}

export interface PendingConfirmation {
  action_id: string;
  tool: string;
  args: Record<string, unknown> | string;
  risk_tier?: string;
  reason?: string;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: Date;
  toolSteps?: ToolStep[];
  model?: string;
  provider?: string;
  toolsUsed?: Array<Record<string, unknown>>;
  activeSkills?: string[];
  pendingConfirmations?: PendingConfirmation[];
}

export interface Project {
  id: string;
  name: string;
  description?: string | null;
  instructions?: string | null;
  workspace_path?: string | null;
  local_folders: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Session {
  session_id: string;
  project_id?: string | null;
  chat_mode?: string;
  created_at?: string;
  updated_at?: string;
  message_count?: number;
  last_message?: string;
}

export interface Attachment {
  id: string;
  session_id?: string | null;
  project_id?: string | null;
  filename: string;
  path: string;
  size_bytes: number;
  content_type?: string | null;
  created_at: string;
}

export interface ArtifactVersion {
  id: string;
  artifact_id: string;
  version: number;
  content: string;
  summary?: string | null;
  created_at: string;
}

export interface Artifact {
  id: string;
  project_id?: string | null;
  session_id?: string | null;
  name: string;
  type: string;
  content: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectFile {
  name: string;
  path: string;
  size_bytes: number;
  is_dir: boolean;
  updated_at?: number | null;
}



export interface HealthResponse {
  status: "ok" | "degraded";
  active_backend: string;
  configured_model: string;
  available_models: string[];
  governor_throttled: boolean;
  ollama_connected: boolean;
  ollama_model?: string;
  active_sessions_count: number;
  voice_enabled?: boolean;
}

export interface GovernorStatus {
  status: "ok" | "degraded" | "throttled" | "paused";
  throttled: boolean;
  activeBackend: string;
  configuredModel: string;
  availableModels: string[];
  ollamaConnected: boolean;
}

export interface UnloadResponse {
  success: boolean;
  unloaded_models: string[];
  message: string;
}

// SSE Event Contract shapes
export interface SSETokenEvent {
  delta: string;
}

export interface SSEToolStartEvent {
  tool: string;
  args: Record<string, unknown>;
}

export interface SSEToolEndEvent {
  tool: string;
  args: Record<string, unknown>;
  status: "success" | "error";
  result: unknown;
}

export interface SSEConfirmationRequiredEvent {
  pending_confirmations: PendingConfirmation[];
  session_id: string;
}

export interface SSEDoneEvent {
  response: string;
  model: string;
  provider: string;
  tools_used: Array<Record<string, unknown>>;
  active_skills: string[];
}

export interface SSEErrorEvent {
  error: string;
}

export interface SSEToolDraftEvent {
  tool: string;
  args_delta: string;
}

export interface SSEEventMap {
  token: SSETokenEvent;
  tool_draft: SSEToolDraftEvent;
  tool_start: SSEToolStartEvent;
  tool_end: SSEToolEndEvent;
  confirmation_required: SSEConfirmationRequiredEvent;
  done: SSEDoneEvent;
  error: SSEErrorEvent;
}

export interface SSEEventCallbacks {
  onToken?: (data: SSETokenEvent) => void;
  onToolDraft?: (data: SSEToolDraftEvent) => void;
  onToolStart?: (data: SSEToolStartEvent) => void;
  onToolEnd?: (data: SSEToolEndEvent) => void;
  onConfirmationRequired?: (data: SSEConfirmationRequiredEvent) => void;
  onDone?: (data: SSEDoneEvent) => void;
  onError?: (data: SSEErrorEvent) => void;
}
