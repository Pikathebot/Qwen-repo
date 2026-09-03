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



export interface MemoryItem {
  id: string;
  project_id?: string | null;
  category: string;
  content: string;
  source_session_id?: string | null;
  confidence: number;
  pinned: boolean;
  score?: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  active_backend: string;
  configured_model: string;
  llama_base_url?: string;
  llama_connected: boolean;
  available_models: string[];
  governor_throttled: boolean;
  openrouter_configured?: boolean;
  active_sessions_count: number;
  active_mcp_servers_count?: number;
  available_skills_count?: number;
  voice_enabled?: boolean;
  // Backward-compatibility alias
  ollama_connected?: boolean;
  ollama_model?: string;
}

export interface GovernorTelemetry {
  enabled: boolean;
  status: string;
  throttled: boolean;
  raw_throttled: boolean;
  throttle_reasons: string[];
  is_manual_override: boolean;
  manual_override_active: boolean;
  override_expires_at?: number | null;
  pending_reload: boolean;
  active_activities: string[];
  model_unloaded: boolean;
  metrics: {
    cpu_percent: number;
    ram_percent: number;
    ram_used_mb: number;
    ram_total_mb: number;
    gpu_available: boolean;
    gpu_name?: string | null;
    gpu_util_percent: number;
    vram_util_percent: number;
    vram_used_mb: number;
    vram_total_mb: number;
    vram_free_mb: number;
    gpu_temp_c?: number | null;
    timestamp: number;
  };
  thresholds: {
    gpu_threshold: number;
    vram_threshold: number;
    cpu_threshold: number;
    ram_threshold: number;
  };
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

export interface SSERetrievalContextEvent {
  chunks_used: Array<{
    chunk_id?: string;
    file_path?: string;
    file_name?: string;
    symbol_name?: string;
    symbol_type?: string;
    start_line?: number;
    end_line?: number;
    content?: string;
    score?: number;
    similarity_score?: number;
    rrf_score?: number;
  }>;
  chunks_dropped: Array<{
    chunk_id?: string;
    file_path?: string;
    file_name?: string;
    symbol_name?: string;
    symbol_type?: string;
  }>;
  budget_report: {
    total_context_window: number;
    reserved_output_tokens: number;
    available_input_budget: number;
    tier1_system_tokens: number;
    tier2_user_tokens: number;
    tier3_rag_tokens: number;
    tier4_history_tokens: number;
    tier5_summary_included: boolean;
    total_input_tokens_used: number;
    remaining_unallocated_tokens: number;
    chunks_used_count: number;
    chunks_dropped_count: number;
    chat_mode: string;
  };
}

export interface SSEToolCallEvent {
  tool: string;
  args: Record<string, unknown>;
  call_id?: string;
}

export interface SSEToolResultEvent {
  tool: string;
  status: "success" | "error";
  summary?: string;
  result?: string;
  call_id?: string;
  latency_ms?: number;
  truncated?: boolean;
}

export interface SSEAgentStatusEvent {
  status: string;
  iteration?: number;
  run_id?: string;
  tool?: string;
}

export interface ActivityStep {
  id: string;
  timestamp: Date;
  type: "status" | "tool_call" | "tool_result";
  tool?: string;
  status?: string;
  args?: Record<string, unknown>;
  result?: string;
  summary?: string;
  latency_ms?: number;
  truncated?: boolean;
}

export interface SSEEventMap {
  token: SSETokenEvent;
  tool_draft: SSEToolDraftEvent;
  tool_start: SSEToolStartEvent;
  tool_end: SSEToolEndEvent;
  tool_call: SSEToolCallEvent;
  tool_result: SSEToolResultEvent;
  agent_status: SSEAgentStatusEvent;
  confirmation_required: SSEConfirmationRequiredEvent;
  retrieval_context: SSERetrievalContextEvent;
  done: SSEDoneEvent;
  error: SSEErrorEvent;
}

export interface SSEEventCallbacks {
  onToken?: (data: SSETokenEvent) => void;
  onToolDraft?: (data: SSEToolDraftEvent) => void;
  onToolStart?: (data: SSEToolStartEvent) => void;
  onToolEnd?: (data: SSEToolEndEvent) => void;
  onToolCall?: (data: SSEToolCallEvent) => void;
  onToolResult?: (data: SSEToolResultEvent) => void;
  onAgentStatus?: (data: SSEAgentStatusEvent) => void;
  onConfirmationRequired?: (data: SSEConfirmationRequiredEvent) => void;
  onRetrievalContext?: (data: SSERetrievalContextEvent) => void;
  onDone?: (data: SSEDoneEvent) => void;
  onError?: (data: SSEErrorEvent) => void;
}



// ==========================================
// Persona
// ==========================================

export interface PersonaProfile {
  id: string;
  name: string;
  description: string;
  address_term: string;
  voice_id: string;
  tone_directives: string[];
  acknowledgements: string[];
  greeting: string;
  max_speech_sentences: number;
}

export interface PersonaSummary {
  id: string;
  name: string;
  description: string;
}

export interface PersonaOverrides {
  address_term?: string;
  voice_id?: string;
  greeting?: string;
  max_speech_sentences?: number;
}

export interface PersonaStatus {
  active_id: string;
  active: PersonaProfile;
  overrides: PersonaOverrides;
  available: PersonaSummary[];
  available_voices: Record<string, string>;
}
