export type MessageRole = "user" | "assistant" | "system" | "tool";

export type ToolStatus = "pending" | "running" | "success" | "warning" | "error" | "blocked";

export type PermissionTier = "LOW_RISK" | "CONFIRMATION_REQUIRED" | "HIGH_RISK";

export type GovernorTier = "IDLE" | "LIGHT" | "MODERATE" | "HEAVY" | "CRITICAL" | "PAUSED";

export type ModelRole = "MAIN" | "FAST" | "EMBED" | "RERANK" | "VISION";

export interface DiffPayload {
  filePath: string;
  oldContent: string;
  newContent: string;
  additions?: number;
  deletions?: number;
}

export interface PendingConfirmation {
  action_id: string;
  tool: string;
  args: Record<string, unknown> | string;
  risk_tier?: PermissionTier | string;
  reason?: string;
  diffPayload?: DiffPayload;
  createdAt?: string;
}

export interface ToolStep {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  status: ToolStatus;
  result?: unknown;
  latency_ms?: number;
  summary?: string;
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
  contextChips?: Array<{ type: "file" | "memory" | "skill" | "model" | "tool"; label: string }>;
  isStreaming?: boolean;
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
  chunks_count?: number;
  skills_active?: string[];
}

export interface Session {
  session_id: string;
  project_id?: string | null;
  chat_mode?: string;
  created_at?: string;
  updated_at?: string;
  message_count?: number;
  last_message?: string;
  title?: string;
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
  status?: "unmodified" | "modified" | "pending_edit" | "accepted" | "rejected";
  children?: ProjectFile[];
}

export interface MemoryItem {
  id: string;
  category: "Preference" | "Fact" | "Workflow" | "Project";
  title: string;
  content: string;
  source?: string;
  created_at: string;
  updated_at?: string;
}

export interface SkillItem {
  id: string;
  name: string;
  description: string;
  isActive: boolean;
  icon?: string;
  toolsCount?: number;
}

export interface ModelInfo {
  role: ModelRole;
  name: string;
  provider: string;
  status: "online" | "offline" | "loading";
  contextWindow: number;
  quantization?: string;
  vramUsageMb?: number;
}

export interface ModelTopology {
  main: ModelInfo;
  fast: ModelInfo;
  embed: ModelInfo;
  rerank: ModelInfo;
  vision: ModelInfo;
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
  vram_used_mb?: number;
  vram_total_mb?: number;
  is_mock?: boolean;
}

export interface GovernorStatus {
  status: "ok" | "degraded" | "throttled" | "paused" | "offline";
  tier: GovernorTier;
  throttled: boolean;
  activeBackend: string;
  configuredModel: string;
  availableModels: string[];
  ollamaConnected: boolean;
  vram_percent?: number;
  system_load?: number;
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
  type: "status" | "tool_call" | "tool_result" | "permission_request" | "file_change";
  tool?: string;
  status?: ToolStatus | string;
  args?: Record<string, unknown>;
  result?: string | unknown;
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


