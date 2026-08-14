import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class RiskTier(str, Enum):
    LOW_RISK = "LOW_RISK"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    HIGH_RISK = "HIGH_RISK"


# Base hardcoded lookup table mapping tool name -> default RiskTier.
# Lookups take O(1) time.
BASE_TOOL_RISK_MAP: dict[str, RiskTier] = {
    "read_file": RiskTier.LOW_RISK,
    "list_directory": RiskTier.LOW_RISK,
    "execute_command": RiskTier.CONFIRMATION_REQUIRED,
    "delete_file": RiskTier.HIGH_RISK,
}

# Fast compiled regex patterns for argument-aware dynamic risk analysis
SAFE_COMMAND_PREFIXES = (
    "git status",
    "git log",
    "git branch",
    "git diff",
    "dir",
    "ls",
    "echo",
    "pwd",
    "whoami",
    "cat",
    "type",
    "head",
    "tail",
    "more",
    "get-content",
    "findstr",
    "python --version",
    "pytest --version",
)

DANGEROUS_COMMAND_PATTERNS = re.compile(
    r"\b(rm\s+-rf|del\s+/[sSfFqQ]|format|diskpart|shutdown|mkfs|rmdir\s+/s)\b",
    re.IGNORECASE
)

SYSTEM_CRITICAL_DIRECTORIES = (
    r"c:/windows",
    r"c:/program files",
    r"c:/program files (x86)",
    r"c:/system32",
    "/etc",
    "/bin",
    "/usr/bin",
    "/sbin"
)


def normalize_arguments(args: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize argument keys and path strings to produce stable, canonical hashes.
    """
    normalized = {}
    for k, v in sorted(args.items()):
        canonical_key = "file_path" if k in ("path", "filePath", "filename", "file") else (
            "command" if k in ("cmd", "command_line", "cli") else (
                "directory_path" if k in ("dir", "dir_path", "directory") else k
            )
        )
        if isinstance(v, str):
            cleaned = v.strip().lstrip("./\\").replace("\\", "/")
            normalized[canonical_key] = cleaned
        else:
            normalized[canonical_key] = v
    return normalized


def generate_action_id(tool_name: str, arguments: dict[str, Any]) -> str:
    """
    Generate a deterministic, tamper-evident action ID hash for approval gating.
    """
    normalized = normalize_arguments(arguments)
    serialized = json.dumps({"tool": tool_name, "args": normalized}, sort_keys=True)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
    return f"act_{digest}"


def evaluate_command_argument_risk(command: str) -> RiskTier:
    """
    Argument-aware optimization for command execution:
    Safe read-only commands downgrade to LOW_RISK for zero friction;
    Destructive commands escalate to HIGH_RISK.
    """
    cmd_clean = str(command).strip().strip("'\"")

    # Destructive pattern check
    if DANGEROUS_COMMAND_PATTERNS.search(cmd_clean):
        return RiskTier.HIGH_RISK

    cmd_lower = cmd_clean.lower().replace("\\", "/")
    # Known safe read-only prefix check
    for prefix in SAFE_COMMAND_PREFIXES:
        if cmd_lower.startswith(prefix):
            return RiskTier.LOW_RISK

    return RiskTier.CONFIRMATION_REQUIRED


def evaluate_file_path_risk(file_path: str) -> RiskTier:
    """
    Check if a file path targets protected OS system directories.
    """
    norm_path = os.path.normpath(str(file_path)).lower().replace("\\", "/")
    for sys_dir in SYSTEM_CRITICAL_DIRECTORIES:
        if norm_path.startswith(sys_dir):
            return RiskTier.HIGH_RISK
    return RiskTier.LOW_RISK


@dataclass
class PermissionDecision:
    tool: str
    args: dict[str, Any]
    risk_tier: RiskTier
    allowed: bool
    action_id: str
    reason: str


@dataclass
class BatchPermissionResult:
    all_allowed: bool
    approved_actions: list[PermissionDecision] = field(default_factory=list)
    pending_confirmations: list[PermissionDecision] = field(default_factory=list)


def evaluate_tool_permission(
    tool_name: str,
    arguments: dict[str, Any],
    approved_action_ids: Optional[list[str]] = None
) -> PermissionDecision:
    """
    Evaluate permission for a single tool call.
    Default policy: If tool is not in BASE_TOOL_RISK_MAP, default to CONFIRMATION_REQUIRED.
    """
    approved_ids = set(approved_action_ids or [])
    action_id = generate_action_id(tool_name, arguments)

    # 1. Base lookup (unclassified defaults to CONFIRMATION_REQUIRED)
    base_tier = BASE_TOOL_RISK_MAP.get(tool_name, RiskTier.CONFIRMATION_REQUIRED)
    effective_tier = base_tier

    # 2. Argument-aware dynamic rule optimizations
    if tool_name == "execute_command":
        cmd = arguments.get("command") or arguments.get("cmd") or arguments.get("command_line") or ""
        effective_tier = evaluate_command_argument_risk(str(cmd))
    elif tool_name in ("delete_file", "write_file"):
        path = arguments.get("file_path") or arguments.get("path") or ""
        if evaluate_file_path_risk(str(path)) == RiskTier.HIGH_RISK:
            effective_tier = RiskTier.HIGH_RISK

    # 3. Check if user already provided explicit approval token or tool/target approval
    path_val = str(arguments.get("file_path") or arguments.get("path") or "")
    path_base = os.path.basename(path_val).strip().lower() if path_val else ""
    if action_id in approved_ids or tool_name in approved_ids or (path_base and path_base in approved_ids):
        return PermissionDecision(
            tool=tool_name,
            args=arguments,
            risk_tier=effective_tier,
            allowed=True,
            action_id=action_id,
            reason="Explicitly approved by user approval token."
        )

    # 4. Determine authorization based on tier
    if effective_tier == RiskTier.LOW_RISK:
        return PermissionDecision(
            tool=tool_name,
            args=arguments,
            risk_tier=effective_tier,
            allowed=True,
            action_id=action_id,
            reason="Tool categorized as LOW_RISK. Auto-approved."
        )
    else:
        return PermissionDecision(
            tool=tool_name,
            args=arguments,
            risk_tier=effective_tier,
            allowed=False,
            action_id=action_id,
            reason=f"Action requires user confirmation (Risk Tier: {effective_tier.value})."
        )


def evaluate_tool_calls_batch(
    tool_calls: list[dict[str, Any]],
    approved_action_ids: Optional[list[str]] = None
) -> BatchPermissionResult:
    """
    Batch evaluate multiple tool calls in a single pass to prevent fragmented confirmation prompts.
    """
    approved: list[PermissionDecision] = []
    pending: list[PermissionDecision] = []

    for tc in tool_calls:
        fn_name = tc.get("name", "")
        fn_args = tc.get("args", {})
        decision = evaluate_tool_permission(fn_name, fn_args, approved_action_ids)

        if decision.allowed:
            approved.append(decision)
        else:
            pending.append(decision)

    all_allowed = len(pending) == 0
    return BatchPermissionResult(
        all_allowed=all_allowed,
        approved_actions=approved,
        pending_confirmations=pending
    )
