import re
import difflib
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("jarvis.services.patch_validator")


@dataclass
class PatchValidationResult:
    """Result of validating a unified diff patch against target file content."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    hunks_count: int = 0


@dataclass
class DiffHunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str] = field(default_factory=list)


def parse_unified_diff_hunks(patch_text: str) -> list[DiffHunk]:
    """
    Parses unified diff text into structured DiffHunk objects.
    Handles standard unified diff format as well as loose LLM-generated diffs.
    """
    hunks: list[DiffHunk] = []
    if not patch_text or not patch_text.strip():
        return hunks

    # Clean markdown fences if model enclosed diff in ```diff ... ```
    cleaned = re.sub(r"^```(?:diff|patch)?\s*\n", "", patch_text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\n```\s*$", "", cleaned)

    lines = cleaned.splitlines()
    current_hunk: Optional[DiffHunk] = None

    hunk_header_re = re.compile(r"^@@\s*-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s*@@")

    for line in lines:
        match = hunk_header_re.match(line)
        if match:
            if current_hunk:
                hunks.append(current_hunk)
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) is not None else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) is not None else 1
            current_hunk = DiffHunk(
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
                lines=[]
            )
        elif current_hunk is not None:
            # Skip file headers like --- a/file.py or +++ b/file.py if inside or between
            if line.startswith("--- ") or line.startswith("+++ ") or line.startswith("diff --git"):
                continue
            # Accept context (' '), addition ('+'), deletion ('-'), or no prefix if blank
            if line.startswith("+") or line.startswith("-") or line.startswith(" "):
                current_hunk.lines.append(line)
            elif line.startswith("\\ No newline at end of file"):
                continue
            elif not line.strip() and len(current_hunk.lines) > 0:
                # Treat empty line as context line with space
                current_hunk.lines.append(" " + line)
            else:
                # Treat untagged text as context line
                current_hunk.lines.append(" " + line)

    if current_hunk:
        hunks.append(current_hunk)

    return hunks


class PatchValidator:
    """
    Validates and applies unified diff patches with LLM-tolerant matching (Amendment 1).
    Accommodates whitespace variations, line ending differences, and minor line number offsets.
    """

    def __init__(self, tolerance_window: int = 5, normalize_whitespace: bool = True):
        self.tolerance_window = tolerance_window
        self.normalize_whitespace = normalize_whitespace

    def _normalize_line(self, line: str) -> str:
        """Normalizes a single line for tolerant comparison."""
        if self.normalize_whitespace:
            return line.rstrip("\r\n").rstrip()
        return line.rstrip("\r\n")

    def _find_matching_offset(
        self,
        file_lines: list[str],
        expected_old_lines: list[str],
        start_idx: int
    ) -> Optional[int]:
        """
        Locates the closest line offset where expected old context/removal lines match the file.
        Searches within a sliding window [-tolerance, +tolerance] around start_idx.
        """
        if not expected_old_lines:
            return start_idx

        # 1. Exact position check
        if start_idx + len(expected_old_lines) <= len(file_lines):
            match = True
            for i, exp in enumerate(expected_old_lines):
                if self._normalize_line(file_lines[start_idx + i]) != self._normalize_line(exp):
                    match = False
                    break
            if match:
                return start_idx

        # 2. Sliding window check
        for delta in range(1, self.tolerance_window + 1):
            # Check +delta
            pos_plus = start_idx + delta
            if 0 <= pos_plus and pos_plus + len(expected_old_lines) <= len(file_lines):
                match = True
                for i, exp in enumerate(expected_old_lines):
                    if self._normalize_line(file_lines[pos_plus + i]) != self._normalize_line(exp):
                        match = False
                        break
                if match:
                    return pos_plus

            # Check -delta
            pos_minus = start_idx - delta
            if 0 <= pos_minus and pos_minus + len(expected_old_lines) <= len(file_lines):
                match = True
                for i, exp in enumerate(expected_old_lines):
                    if self._normalize_line(file_lines[pos_minus + i]) != self._normalize_line(exp):
                        match = False
                        break
                if match:
                    return pos_minus

        return None

    def validate_patch(
        self,
        file_content: str,
        patch_text: str
    ) -> PatchValidationResult:
        """
        Validates a unified diff patch against existing file content.
        Verifies line bounds and context matches before applying changes.
        """
        if not patch_text or not patch_text.strip():
            return PatchValidationResult(
                valid=False,
                errors=["Patch content is empty or contains only whitespace."]
            )

        hunks = parse_unified_diff_hunks(patch_text)
        if not hunks:
            return PatchValidationResult(
                valid=False,
                errors=["Malformed patch: No valid unified diff hunks (@@ ... @@) detected."]
            )

        file_lines = file_content.splitlines(keepends=False)
        errors: list[str] = []
        warnings: list[str] = []

        for idx, hunk in enumerate(hunks, start=1):
            # Extract expected old lines (context ' ' and deleted '-')
            expected_old: list[str] = []
            for l in hunk.lines:
                if l.startswith(" ") or l.startswith("-"):
                    expected_old.append(l[1:])

            # Determine starting zero-indexed line
            target_start = max(0, hunk.old_start - 1)
            actual_offset = self._find_matching_offset(file_lines, expected_old, target_start)

            if actual_offset is None:
                errors.append(
                    f"Hunk #{idx} context mismatch at line {hunk.old_start}. "
                    f"Target file content does not match expected context lines."
                )
            elif actual_offset != target_start:
                warnings.append(
                    f"Hunk #{idx} matched with offset (expected line {target_start+1}, found at line {actual_offset+1})."
                )

        return PatchValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            hunks_count=len(hunks)
        )

    def apply_unified_diff(
        self,
        file_content: str,
        patch_text: str
    ) -> tuple[str, str]:
        """
        Applies a unified diff patch to the given file content.
        Returns tuple of (new_file_content, diff_summary).
        Raises ValueError if validation fails.
        """
        validation = self.validate_patch(file_content, patch_text)
        if not validation.valid:
            error_details = "\n".join(validation.errors)
            raise ValueError(f"Patch validation failed:\n{error_details}")

        hunks = parse_unified_diff_hunks(patch_text)
        file_lines = file_content.splitlines(keepends=False)
        has_trailing_newline = file_content.endswith("\n") or file_content.endswith("\r\n")

        # Track line adjustments as hunks are applied
        applied_lines = list(file_lines)
        line_offset = 0
        hunks_applied = 0

        for hunk in hunks:
            expected_old: list[str] = []
            for l in hunk.lines:
                if l.startswith(" ") or l.startswith("-"):
                    expected_old.append(l[1:])

            orig_start = max(0, hunk.old_start - 1)
            current_target = orig_start + line_offset
            match_idx = self._find_matching_offset(applied_lines, expected_old, current_target)

            if match_idx is None:
                # Fallback to direct slice
                match_idx = max(0, min(current_target, len(applied_lines)))

            # Build replacement slice
            new_slice: list[str] = []
            old_consumed = 0

            for l in hunk.lines:
                if l.startswith(" "):
                    new_slice.append(l[1:])
                    old_consumed += 1
                elif l.startswith("-"):
                    old_consumed += 1
                elif l.startswith("+"):
                    new_slice.append(l[1:])

            # Replace in applied_lines
            applied_lines[match_idx : match_idx + old_consumed] = new_slice
            line_offset += len(new_slice) - old_consumed
            hunks_applied += 1

        new_content = "\n".join(applied_lines)
        if has_trailing_newline or patch_text.endswith("\n"):
            new_content += "\n"

        summary = f"Applied {hunks_applied} hunk(s) successfully ({len(file_lines)} -> {len(applied_lines)} lines)"
        return new_content, summary
