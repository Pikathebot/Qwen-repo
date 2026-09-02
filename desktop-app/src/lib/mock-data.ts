import {
  Project,
  Session,
  Message,
  Artifact,
  ProjectFile,
  MemoryItem,
  SkillItem,
  ModelTopology,
  SSERetrievalContextEvent,
  ActivityStep,
  DiffPayload,
} from "./types";

export const MOCK_PROJECTS: Project[] = [
  {
    id: "proj_unreal_inventory",
    name: "Unreal Inventory System",
    description: "Modular UE5 Inventory & Equipment subsystem with Gameplay Ability System (GAS) integration.",
    instructions: "Follow UE5 naming conventions (UInventoryComponent, FInventoryItemInstance). Prefer Gameplay Tags for item capabilities. Avoid raw pointers in replicated structs.",
    workspace_path: "D:/UnrealProjects/LyraInventory/Source/InventorySystem",
    local_folders: [
      "Source/InventorySystem/Public",
      "Source/InventorySystem/Private",
      "Source/InventorySystem/Abilities",
    ],
    is_active: true,
    created_at: "2026-08-28T10:00:00.000Z",
    updated_at: "2026-09-01T15:30:00.000Z",
    chunks_count: 12403,
    skills_active: ["Unreal Engine", "C++ Architecture", "GAS Optimization"],
  },
  {
    id: "proj_jarvis_workspace",
    name: "JARVIS Workspace",
    description: "Core local desktop agent engine and FastAPI backend orchestration.",
    instructions: "Local-first execution only. Always enforce deterministic permission checks before disk modifications.",
    workspace_path: "D:/JARVIS",
    local_folders: ["backend", "desktop-app", "skills", "tools"],
    is_active: false,
    created_at: "2026-08-15T08:00:00.000Z",
    updated_at: "2026-09-01T12:00:00.000Z",
    chunks_count: 8940,
    skills_active: ["FastAPI", "Next.js", "Tauri Desktop"],
  },
];

export const MOCK_SESSIONS: Session[] = [
  {
    session_id: "session_gas_refactor_a41f",
    project_id: "proj_unreal_inventory",
    title: "GAS Inventory Component Patch",
    chat_mode: "WORKSPACE",
    created_at: "2026-09-01T14:20:00.000Z",
    updated_at: "2026-09-01T15:45:00.000Z",
    message_count: 3,
    last_message: "Proposed patch for InventoryComponent.cpp with dynamic ability binding tags.",
  },
  {
    session_id: "session_types_definition_88bc",
    project_id: "proj_unreal_inventory",
    title: "InventoryTypes.h Replicated Structs",
    chat_mode: "WORKSPACE",
    created_at: "2026-08-31T09:15:00.000Z",
    updated_at: "2026-08-31T11:20:00.000Z",
    message_count: 8,
    last_message: "Added FInventoryEntry with NetSerialize fast array replication support.",
  },
  {
    session_id: "session_system_audit_102d",
    project_id: "proj_jarvis_workspace",
    title: "Resource Governor Telemetry Pass",
    chat_mode: "SYSTEM",
    created_at: "2026-08-30T16:00:00.000Z",
    updated_at: "2026-08-30T16:40:00.000Z",
    message_count: 4,
    last_message: "Evaluated 6-stage VRAM throttling threshold for Qwen3-30B.",
  },
];

export const MOCK_PROJECT_FILES: ProjectFile[] = [
  {
    name: "Source",
    path: "Source",
    size_bytes: 0,
    is_dir: true,
    children: [
      {
        name: "InventorySystem",
        path: "Source/InventorySystem",
        size_bytes: 0,
        is_dir: true,
        children: [
          {
            name: "Public",
            path: "Source/InventorySystem/Public",
            size_bytes: 0,
            is_dir: true,
            children: [
              {
                name: "InventoryComponent.h",
                path: "Source/InventorySystem/Public/InventoryComponent.h",
                size_bytes: 4890,
                is_dir: false,
                status: "unmodified",
              },
              {
                name: "InventoryTypes.h",
                path: "Source/InventorySystem/Public/InventoryTypes.h",
                size_bytes: 8120,
                is_dir: false,
                status: "unmodified",
              },
            ],
          },
          {
            name: "Private",
            path: "Source/InventorySystem/Private",
            size_bytes: 0,
            is_dir: true,
            children: [
              {
                name: "InventoryComponent.cpp",
                path: "Source/InventorySystem/Private/InventoryComponent.cpp",
                size_bytes: 14320,
                is_dir: false,
                status: "pending_edit",
              },
              {
                name: "InventoryItemInstance.cpp",
                path: "Source/InventorySystem/Private/InventoryItemInstance.cpp",
                size_bytes: 6540,
                is_dir: false,
                status: "unmodified",
              },
            ],
          },
          {
            name: "AbilitySystem.Build.cs",
            path: "Source/InventorySystem/AbilitySystem.Build.cs",
            size_bytes: 1840,
            is_dir: false,
            status: "unmodified",
          },
        ],
      },
    ],
  },
];

export const MOCK_SAMPLE_DIFF: DiffPayload = {
  filePath: "Source/InventorySystem/Private/InventoryComponent.cpp",
  oldContent: `void UInventoryComponent::GiveItemAbility(FInventoryEntry& ItemEntry)
{
    if (!GetOwner()->HasAuthority() || !AbilitySystemComponent)
    {
        return;
    }

    // Direct spec grant without dynamic tag tracking
    FGameplayAbilitySpec Spec(ItemEntry.AbilityClass, ItemEntry.AbilityLevel);
    FGameplayAbilitySpecHandle Handle = AbilitySystemComponent->GiveAbility(Spec);
    ItemEntry.GrantedAbilityHandle = Handle;
}`,
  newContent: `void UInventoryComponent::GiveItemAbility(FInventoryEntry& ItemEntry)
{
    if (!GetOwner()->HasAuthority() || !AbilitySystemComponent)
    {
        return;
    }

    // Dynamic Gameplay Tag ability spec with source object linkage
    FGameplayAbilitySpec Spec(ItemEntry.AbilityClass, ItemEntry.AbilityLevel, INDEX_NONE, this);
    Spec.DynamicAbilityTags.AddTag(FGameplayTag::RequestGameplayTag(FName("Ability.Item.Equipped")));
    
    FGameplayAbilitySpecHandle Handle = AbilitySystemComponent->GiveAbilityAndActivateOnce(Spec);
    ItemEntry.GrantedAbilityHandle = Handle;
    
    OnItemAbilityGranted.Broadcast(ItemEntry.ItemInstance, Handle);
}`,
  additions: 7,
  deletions: 3,
};

export const MOCK_MESSAGES: Message[] = [
  {
    id: "msg_user_gas_01",
    role: "user",
    content: "Refactor `InventoryComponent.cpp` to bind equipped items to the Gameplay Ability System with dynamic activation tags and source object linkage.",
    createdAt: new Date(Date.now() - 120000),
    contextChips: [
      { type: "file", label: "InventoryComponent.cpp" },
      { type: "file", label: "InventoryTypes.h" },
      { type: "memory", label: "GAS Item Patterns" },
    ],
  },
  {
    id: "msg_assistant_gas_02",
    role: "assistant",
    model: "MAIN · Qwen3-30B",
    provider: "Local (vLLM)",
    createdAt: new Date(Date.now() - 60000),
    toolSteps: [
      {
        id: "step_read_01",
        tool: "filesystem.read",
        args: { path: "Source/InventorySystem/Public/InventoryTypes.h", lines: [1, 85] },
        status: "success",
        latency_ms: 18,
        summary: "Read 85 lines of struct definitions in InventoryTypes.h",
        result: "// Retrieved FInventoryEntry struct with GrantedAbilityHandle member.",
      },
      {
        id: "step_search_02",
        tool: "search.project",
        args: { query: "GiveAbilityAndActivateOnce", extensions: [".cpp", ".h"] },
        status: "success",
        latency_ms: 42,
        summary: "Found 4 references across AbilitySystemComponent usages",
        result: "Found active call sites in LyraEquipmentManagerComponent.cpp",
      },
      {
        id: "step_patch_03",
        tool: "filesystem.patch",
        args: {
          path: "Source/InventorySystem/Private/InventoryComponent.cpp",
          hunk_count: 1,
        },
        status: "warning",
        latency_ms: 65,
        summary: "Generated AST-safe patch for UInventoryComponent::GiveItemAbility",
        result: "Patch prepared · Awaiting confirmation",
      },
    ],
    content: `I've analyzed the inventory subsystem in \`InventoryTypes.h\` and updated \`UInventoryComponent::GiveItemAbility\` in \`InventoryComponent.cpp\`.

### Key Improvements:
1. **Source Object Association**: Passes \`this\` as the source object to \`FGameplayAbilitySpec\`, enabling gameplay effect triggers to trace damage back to the inventory component owner.
2. **Dynamic Tag Assignment**: Applies \`Ability.Item.Equipped\` so conditional gameplay tags can activate passives.
3. **Broadcasting Delegate**: Fires \`OnItemAbilityGranted\` for UI feedback and hotbar icon refresh.

\`\`\`cpp
// Dynamic Gameplay Tag ability spec with source object linkage
FGameplayAbilitySpec Spec(ItemEntry.AbilityClass, ItemEntry.AbilityLevel, INDEX_NONE, this);
Spec.DynamicAbilityTags.AddTag(FGameplayTag::RequestGameplayTag(FName("Ability.Item.Equipped")));

FGameplayAbilitySpecHandle Handle = AbilitySystemComponent->GiveAbilityAndActivateOnce(Spec);
ItemEntry.GrantedAbilityHandle = Handle;
\`\`\`

Please review the proposed file patch below before committing the changes to disk.`,
    pendingConfirmations: [
      {
        action_id: "act_patch_inv_comp_01",
        tool: "filesystem.patch",
        args: { file: "Source/InventorySystem/Private/InventoryComponent.cpp" },
        risk_tier: "CONFIRMATION_REQUIRED",
        reason: "Agent requested write permission to modify InventoryComponent.cpp (+7 lines, -3 lines).",
        diffPayload: MOCK_SAMPLE_DIFF,
        createdAt: new Date().toISOString(),
      },
    ],
  },
];

export const MOCK_ACTIVITY_STEPS: ActivityStep[] = [
  {
    id: "act_step_01",
    timestamp: new Date(Date.now() - 115000),
    type: "status",
    status: "success",
    summary: "RAG index queried: 14 relevant chunks retrieved",
    latency_ms: 34,
  },
  {
    id: "act_step_02",
    timestamp: new Date(Date.now() - 100000),
    type: "tool_call",
    tool: "filesystem.read",
    status: "success",
    args: { path: "Source/InventorySystem/Public/InventoryTypes.h" },
    result: "FInventoryEntry struct definition inspected successfully.",
    latency_ms: 18,
  },
  {
    id: "act_step_03",
    timestamp: new Date(Date.now() - 85000),
    type: "tool_call",
    tool: "search.project",
    status: "success",
    args: { query: "GiveAbilityAndActivateOnce" },
    result: "Found 4 occurrences in GameplayAbility subsystem.",
    latency_ms: 42,
  },
  {
    id: "act_step_04",
    timestamp: new Date(Date.now() - 70000),
    type: "status",
    status: "success",
    summary: "Reasoning with MAIN · Qwen3-30B (2,410 tokens)",
    latency_ms: 4800,
  },
  {
    id: "act_step_05",
    timestamp: new Date(Date.now() - 60000),
    type: "permission_request",
    tool: "filesystem.patch",
    status: "warning",
    summary: "CONFIRMATION_REQUIRED: Modifying InventoryComponent.cpp",
    latency_ms: 12,
  },
];

export const MOCK_MEMORIES: MemoryItem[] = [
  {
    id: "mem_01",
    category: "Preference",
    title: "UE5 Gameplay Ability System (GAS)",
    content: "User prefers modular UE5 C++ with Gameplay Ability System patterns, dynamic gameplay tags, and strict net serialization.",
    source: "Session: GAS Inventory Component Patch",
    created_at: "2026-08-28T11:00:00.000Z",
  },
  {
    id: "mem_02",
    category: "Workflow",
    title: "Deterministic Permission Preference",
    content: "Always ask for confirmation before executing file edits in Source/ or executing terminal commands.",
    source: "Project Constitution",
    created_at: "2026-08-15T09:30:00.000Z",
  },
  {
    id: "mem_03",
    category: "Fact",
    title: "Lyra Engine Architecture",
    content: "The target workspace is built on UE 5.4 Lyra starter game framework with enhanced input and modular gameplay features.",
    source: "Workspace Scan",
    created_at: "2026-08-20T14:15:00.000Z",
  },
];

export const MOCK_SKILLS: SkillItem[] = [
  {
    id: "skill_ue5",
    name: "Unreal Engine 5 Core",
    description: "Deep understanding of UObject lifecycle, GC safety, Smart Pointers, and UPROPERTY macros.",
    isActive: true,
    toolsCount: 6,
  },
  {
    id: "skill_gas",
    name: "Gameplay Ability System",
    description: "AttributeSets, GameplayEffects, AbilityTasks, Prediction, and Fast Array Replication.",
    isActive: true,
    toolsCount: 4,
  },
  {
    id: "skill_cpp_opt",
    name: "C++ Memory & Cache Optimization",
    description: "Cache alignment, SIMD awareness, memory arenas, and strict zero-allocation loops.",
    isActive: true,
    toolsCount: 3,
  },
  {
    id: "skill_terminal",
    name: "Local Terminal Sandbox",
    description: "Deterministic execution of build scripts, clang-format, and UnrealHeaderTool passes.",
    isActive: false,
    toolsCount: 5,
  },
];

export const MOCK_MODELS: ModelTopology = {
  main: {
    role: "MAIN",
    name: "Qwen3-30B",
    provider: "Local (vLLM)",
    status: "online",
    contextWindow: 32768,
    quantization: "AWQ 4-bit",
    vramUsageMb: 18400,
  },
  fast: {
    role: "FAST",
    name: "Qwen3-4B",
    provider: "Local (vLLM)",
    status: "online",
    contextWindow: 32768,
    quantization: "FP16",
    vramUsageMb: 8200,
  },
  embed: {
    role: "EMBED",
    name: "Qwen3-0.6B-Embed",
    provider: "Local (FastEmbed)",
    status: "online",
    contextWindow: 8192,
    vramUsageMb: 1200,
  },
  rerank: {
    role: "RERANK",
    name: "Qwen3-0.6B-Reranker",
    provider: "Local (FastEmbed)",
    status: "online",
    contextWindow: 8192,
    vramUsageMb: 1200,
  },
  vision: {
    role: "VISION",
    name: "Qwen2-VL-7B",
    provider: "Local (Ollama)",
    status: "online",
    contextWindow: 16384,
    vramUsageMb: 7600,
  },
};

export const MOCK_RETRIEVAL_CONTEXT: SSERetrievalContextEvent = {
  chunks_used: [
    {
      chunk_id: "chk_inv_types_01",
      file_path: "Source/InventorySystem/Public/InventoryTypes.h",
      file_name: "InventoryTypes.h",
      symbol_name: "FInventoryEntry",
      symbol_type: "struct",
      start_line: 14,
      end_line: 42,
      content: "USTRUCT(BlueprintType)\nstruct FInventoryEntry : public FFastArraySerializerItem\n{\n    GENERATED_BODY()\n    UPROPERTY() TSubclassOf<UGameplayAbility> AbilityClass;\n    UPROPERTY() FGameplayAbilitySpecHandle GrantedAbilityHandle;\n};",
      similarity_score: 0.942,
      rrf_score: 0.88,
    },
    {
      chunk_id: "chk_inv_comp_02",
      file_path: "Source/InventorySystem/Private/InventoryComponent.cpp",
      file_name: "InventoryComponent.cpp",
      symbol_name: "UInventoryComponent::GiveItemAbility",
      symbol_type: "function",
      start_line: 88,
      end_line: 104,
      content: "void UInventoryComponent::GiveItemAbility(FInventoryEntry& ItemEntry) { ... }",
      similarity_score: 0.915,
      rrf_score: 0.82,
    },
  ],
  chunks_dropped: [
    {
      chunk_id: "chk_build_cs_03",
      file_path: "Source/InventorySystem/AbilitySystem.Build.cs",
      file_name: "AbilitySystem.Build.cs",
      symbol_name: "ModuleRules",
    },
  ],
  budget_report: {
    total_context_window: 32768,
    reserved_output_tokens: 4096,
    available_input_budget: 28672,
    tier1_system_tokens: 1450,
    tier2_user_tokens: 180,
    tier3_rag_tokens: 4820,
    tier4_history_tokens: 7550,
    tier5_summary_included: true,
    total_input_tokens_used: 14000,
    remaining_unallocated_tokens: 14672,
    chunks_used_count: 2,
    chunks_dropped_count: 1,
    chat_mode: "WORKSPACE",
  },
};

export const MOCK_ARTIFACTS: Artifact[] = [
  {
    id: "art_inventory_patch_01",
    project_id: "proj_unreal_inventory",
    session_id: "session_gas_refactor_a41f",
    name: "InventoryComponent.cpp (GAS Refactor)",
    type: "cpp",
    content: `#include "InventoryComponent.h"
#include "AbilitySystemComponent.h"
#include "GameplayAbilitySpec.h"
#include "NativeGameplayTags.h"

UE_DEFINE_GAMEPLAY_TAG_STATIC(TAG_Ability_Item_Equipped, "Ability.Item.Equipped");

UInventoryComponent::UInventoryComponent(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    PrimaryComponentTick.bCanEverTick = false;
    SetIsReplicatedByDefault(true);
}

void UInventoryComponent::GiveItemAbility(FInventoryEntry& ItemEntry)
{
    if (!GetOwner()->HasAuthority() || !AbilitySystemComponent)
    {
        return;
    }

    if (!ItemEntry.AbilityClass)
    {
        return;
    }

    // Dynamic Gameplay Tag ability spec with source object linkage
    FGameplayAbilitySpec Spec(ItemEntry.AbilityClass, ItemEntry.AbilityLevel, INDEX_NONE, this);
    Spec.DynamicAbilityTags.AddTag(TAG_Ability_Item_Equipped);

    const FGameplayAbilitySpecHandle Handle = AbilitySystemComponent->GiveAbilityAndActivateOnce(Spec);
    ItemEntry.GrantedAbilityHandle = Handle;

    OnItemAbilityGranted.Broadcast(ItemEntry.ItemInstance, Handle);
}

void UInventoryComponent::ClearItemAbility(FInventoryEntry& ItemEntry)
{
    if (!GetOwner()->HasAuthority() || !AbilitySystemComponent)
    {
        return;
    }

    if (ItemEntry.GrantedAbilityHandle.IsValid())
    {
        AbilitySystemComponent->ClearAbility(ItemEntry.GrantedAbilityHandle);
        ItemEntry.GrantedAbilityHandle = FGameplayAbilitySpecHandle();
    }
}
`,
    version: 1,
    created_at: "2026-09-01T15:35:00.000Z",
    updated_at: "2026-09-01T15:35:00.000Z",
  },
];
