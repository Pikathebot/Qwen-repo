import {
  MOCK_PROJECTS,
  MOCK_SESSIONS,
  MOCK_PROJECT_FILES,
  MOCK_MESSAGES,
  MOCK_ACTIVITY_STEPS,
  MOCK_MEMORIES,
  MOCK_SKILLS,
  MOCK_MODELS,
  MOCK_RETRIEVAL_CONTEXT,
  MOCK_ARTIFACTS,
  MOCK_SAMPLE_DIFF,
} from "./mock-data";
import {
  Project,
  Session,
  Message,
  Artifact,
  ProjectFile,
  MemoryItem,
  SkillItem,
  ModelTopology,
  SSEEventCallbacks,
  HealthResponse,
  GovernorStatus,
} from "./types";

/**
 * MockAdapter — Typed Offline Simulator
 * Simulates SSE token streaming, tool call execution, and state persistence for offline testing.
 */
export class MockAdapter {
  private static projects: Project[] = [...MOCK_PROJECTS];
  private static sessions: Session[] = [...MOCK_SESSIONS];
  private static messagesMap: Map<string, Message[]> = new Map([
    ["session_gas_refactor_a41f", [...MOCK_MESSAGES]],
    ["default", [...MOCK_MESSAGES]],
  ]);
  private static memories: MemoryItem[] = [...MOCK_MEMORIES];
  private static skills: SkillItem[] = [...MOCK_SKILLS];
  private static artifacts: Artifact[] = [...MOCK_ARTIFACTS];

  static async getHealth(): Promise<HealthResponse> {
    return {
      status: "ok",
      active_backend: "Mock (Local Simulator)",
      configured_model: "Qwen3-30B",
      available_models: ["Qwen3-30B", "Qwen3-4B", "Qwen3-0.6B", "Qwen2.5-Coder-32B"],
      governor_throttled: false,
      ollama_connected: true,
      ollama_model: "Qwen3-30B",
      active_sessions_count: this.sessions.length,
      voice_enabled: false,
      vram_used_mb: 18400,
      vram_total_mb: 24576,
      is_mock: true,
    };
  }

  static async getGovernor(): Promise<GovernorStatus> {
    return {
      status: "ok",
      tier: "IDLE",
      throttled: false,
      activeBackend: "vLLM (Local)",
      configuredModel: "Qwen3-30B",
      availableModels: ["Qwen3-30B", "Qwen3-4B", "Qwen3-0.6B"],
      ollamaConnected: true,
      vram_percent: 75,
      system_load: 0.18,
    };
  }

  static async getProjects(): Promise<Project[]> {
    return this.projects;
  }

  static async getActiveProject(): Promise<Project | null> {
    return this.projects.find((p) => p.is_active) || this.projects[0] || null;
  }

  static async getSessions(projectId?: string): Promise<Session[]> {
    if (projectId) {
      return this.sessions.filter((s) => s.project_id === projectId);
    }
    return this.sessions;
  }

  static async getMessages(sessionId: string): Promise<Message[]> {
    return this.messagesMap.get(sessionId) || [];
  }

  static async getArtifacts(sessionId?: string, projectId?: string): Promise<Artifact[]> {
    return this.artifacts;
  }

  static async getProjectFiles(projectId?: string): Promise<ProjectFile[]> {
    return MOCK_PROJECT_FILES;
  }

  static async getMemories(): Promise<MemoryItem[]> {
    return this.memories;
  }

  static async addMemory(item: Omit<MemoryItem, "id" | "created_at">): Promise<MemoryItem> {
    const newMem: MemoryItem = {
      ...item,
      id: `mem_${Date.now()}`,
      created_at: new Date().toISOString(),
    };
    this.memories.unshift(newMem);
    return newMem;
  }

  static async deleteMemory(id: string): Promise<boolean> {
    this.memories = this.memories.filter((m) => m.id !== id);
    return true;
  }

  static async getSkills(): Promise<SkillItem[]> {
    return this.skills;
  }

  static async toggleSkill(id: string): Promise<SkillItem[]> {
    this.skills = this.skills.map((s) =>
      s.id === id ? { ...s, isActive: !s.isActive } : s
    );
    return this.skills;
  }

  static async getModels(): Promise<ModelTopology> {
    return MOCK_MODELS;
  }

  /**
   * Simulates Server-Sent Events stream with realistic tool execution steps and token deltas.
   */
  static async simulateStreamChat(
    userPrompt: string,
    sessionId: string,
    callbacks: SSEEventCallbacks,
    signal?: AbortSignal
  ): Promise<void> {
    const userMsg: Message = {
      id: `msg_user_${Date.now()}`,
      role: "user",
      content: userPrompt,
      createdAt: new Date(),
      contextChips: [
        { type: "file", label: "InventoryComponent.cpp" },
        { type: "file", label: "InventoryTypes.h" },
      ],
    };

    const currentMessages = this.messagesMap.get(sessionId) || [];
    currentMessages.push(userMsg);
    this.messagesMap.set(sessionId, currentMessages);

    // Step 1: Agent Status
    callbacks.onAgentStatus?.({
      status: "Analyzing workspace context & RAG embeddings...",
      iteration: 1,
      run_id: "a41f",
    });

    await new Promise((r) => setTimeout(r, 400));
    if (signal?.aborted) return;

    // Step 2: Retrieval context
    callbacks.onRetrievalContext?.(MOCK_RETRIEVAL_CONTEXT);

    // Step 3: Tool Start & End (filesystem.read)
    callbacks.onToolStart?.({
      tool: "filesystem.read",
      args: { path: "Source/InventorySystem/Public/InventoryTypes.h", lines: [1, 85] },
    });

    await new Promise((r) => setTimeout(r, 450));
    if (signal?.aborted) return;

    callbacks.onToolEnd?.({
      tool: "filesystem.read",
      args: { path: "Source/InventorySystem/Public/InventoryTypes.h" },
      status: "success",
      result: "// Inspected FInventoryEntry struct definition successfully.",
    });

    // Step 4: Token stream simulation
    const simulatedResponse = `I have analyzed the inventory subsystem architecture in \`InventoryTypes.h\` and updated \`UInventoryComponent::GiveItemAbility\` in \`InventoryComponent.cpp\`.

### Summary of Changes:
- Linked \`this\` as the source object in \`FGameplayAbilitySpec\` for damage attribution.
- Assigned dynamic Gameplay Tag \`Ability.Item.Equipped\`.
- Broadcast \`OnItemAbilityGranted\` delegate for HUD updates.

\`\`\`cpp
// Dynamic Gameplay Tag ability spec with source object linkage
FGameplayAbilitySpec Spec(ItemEntry.AbilityClass, ItemEntry.AbilityLevel, INDEX_NONE, this);
Spec.DynamicAbilityTags.AddTag(FGameplayTag::RequestGameplayTag(FName("Ability.Item.Equipped")));

FGameplayAbilitySpecHandle Handle = AbilitySystemComponent->GiveAbilityAndActivateOnce(Spec);
ItemEntry.GrantedAbilityHandle = Handle;
\`\`\`

Please review the proposed AST patch below before committing to disk:`;

    const tokens = simulatedResponse.split(" ");
    let accumulated = "";

    for (const token of tokens) {
      if (signal?.aborted) return;
      accumulated += (accumulated ? " " : "") + token;
      callbacks.onToken?.({ delta: token + " " });
      await new Promise((r) => setTimeout(r, 35));
    }

    // Step 5: Confirmation required
    callbacks.onConfirmationRequired?.({
      session_id: sessionId,
      pending_confirmations: [
        {
          action_id: `act_${Date.now()}`,
          tool: "filesystem.patch",
          args: { file: "Source/InventorySystem/Private/InventoryComponent.cpp" },
          risk_tier: "CONFIRMATION_REQUIRED",
          reason: "Agent requested permission to write patch to InventoryComponent.cpp (+7 lines, -3 lines).",
          diffPayload: MOCK_SAMPLE_DIFF,
          createdAt: new Date().toISOString(),
        },
      ],
    });

    // Step 6: Done event
    callbacks.onDone?.({
      response: accumulated,
      model: "MAIN · Qwen3-30B",
      provider: "Local (vLLM)",
      tools_used: [
        { tool: "filesystem.read", duration_ms: 18 },
        { tool: "search.project", duration_ms: 42 },
      ],
      active_skills: ["Unreal Engine", "Gameplay Ability System"],
    });

    const assistantMsg: Message = {
      id: `msg_assistant_${Date.now()}`,
      role: "assistant",
      content: accumulated,
      model: "MAIN · Qwen3-30B",
      provider: "Local (vLLM)",
      createdAt: new Date(),
      toolSteps: [
        {
          id: `step_${Date.now()}_1`,
          tool: "filesystem.read",
          args: { path: "Source/InventorySystem/Public/InventoryTypes.h" },
          status: "success",
          latency_ms: 18,
          summary: "Read 85 lines in InventoryTypes.h",
        },
      ],
      pendingConfirmations: [
        {
          action_id: `act_${Date.now()}`,
          tool: "filesystem.patch",
          args: { file: "Source/InventorySystem/Private/InventoryComponent.cpp" },
          risk_tier: "CONFIRMATION_REQUIRED",
          reason: "Agent requested write permission to modify InventoryComponent.cpp (+7 lines, -3 lines).",
          diffPayload: MOCK_SAMPLE_DIFF,
          createdAt: new Date().toISOString(),
        },
      ],
    };

    currentMessages.push(assistantMsg);
    this.messagesMap.set(sessionId, currentMessages);
  }
}
