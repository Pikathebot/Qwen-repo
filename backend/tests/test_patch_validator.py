import pytest
from app.services.patch_validator import PatchValidator, PatchValidationResult, parse_unified_diff_hunks


@pytest.fixture
def validator():
    return PatchValidator(tolerance_window=5, normalize_whitespace=True)


SAMPLE_PYTHON_CODE = (
    "def calculate_total(items):\n"
    "    total = 0\n"
    "    for item in items:\n"
    "        total += item.price\n"
    "    return total\n"
)


def test_parse_unified_diff_hunks_standard():
    patch = (
        "--- a/math.py\n"
        "+++ b/math.py\n"
        "@@ -1,5 +1,5 @@\n"
        " def calculate_total(items):\n"
        "-    total = 0\n"
        "+    total = 0.0\n"
        "     for item in items:\n"
        "         total += item.price\n"
        "     return total\n"
    )
    hunks = parse_unified_diff_hunks(patch)
    assert len(hunks) == 1
    assert hunks[0].old_start == 1
    assert hunks[0].old_count == 5
    assert hunks[0].new_start == 1
    assert hunks[0].new_count == 5
    assert len(hunks[0].lines) == 6


def test_parse_unified_diff_markdown_fenced():
    patch = (
        "```diff\n"
        "@@ -2,3 +2,3 @@\n"
        "-    total = 0\n"
        "+    total = 100\n"
        "     for item in items:\n"
        "```"
    )
    hunks = parse_unified_diff_hunks(patch)
    assert len(hunks) == 1
    assert hunks[0].old_start == 2


def test_valid_patch_passes_validation(validator):
    patch = (
        "@@ -1,5 +1,5 @@\n"
        " def calculate_total(items):\n"
        "-    total = 0\n"
        "+    total = 0.0\n"
        "     for item in items:\n"
        "         total += item.price\n"
        "     return total\n"
    )
    res: PatchValidationResult = validator.validate_patch(SAMPLE_PYTHON_CODE, patch)
    assert res.valid is True
    assert len(res.errors) == 0


def test_llm_tolerant_whitespace_and_offset(validator):
    """Test LLM-tolerant matching with trailing whitespace and offset header."""
    # Note trailing spaces in context lines and slightly shifted line header
    patch = (
        "@@ -2,3 +2,3 @@\n"
        "-    total = 0   \n"
        "+    total = 0.0\n"
        "     for item in items:  \n"
        "         total += item.price\n"
    )
    res = validator.validate_patch(SAMPLE_PYTHON_CODE, patch)
    assert res.valid is True


def test_patch_context_mismatch_fails_validation(validator):
    """Test that genuinely mismatched context lines are caught and reported."""
    patch = (
        "@@ -1,3 +1,3 @@\n"
        " def non_existent_function(foo, bar):\n"
        "-    invalid = True\n"
        "+    invalid = False\n"
        "     return invalid\n"
    )
    res = validator.validate_patch(SAMPLE_PYTHON_CODE, patch)
    assert res.valid is False
    assert len(res.errors) >= 1
    assert "context mismatch" in res.errors[0].lower()


def test_empty_or_malformed_patch_rejected(validator):
    """Verify empty or headerless patch text is rejected with clear errors."""
    assert validator.validate_patch(SAMPLE_PYTHON_CODE, "").valid is False
    assert validator.validate_patch(SAMPLE_PYTHON_CODE, "   \n\t").valid is False
    assert validator.validate_patch(SAMPLE_PYTHON_CODE, "random text without hunk headers").valid is False


def test_apply_unified_diff_output_accuracy(validator):
    """Verify applying a valid unified diff modifies the content precisely."""
    patch = (
        "@@ -1,5 +1,6 @@\n"
        " def calculate_total(items):\n"
        "-    total = 0\n"
        "+    total = 0.0\n"
        "+    tax = 0.05\n"
        "     for item in items:\n"
        "         total += item.price\n"
        "     return total\n"
    )
    new_content, summary = validator.apply_unified_diff(SAMPLE_PYTHON_CODE, patch)
    assert "total = 0.0" in new_content
    assert "tax = 0.05" in new_content
    assert "total = 0\n" not in new_content
    assert "Applied 1 hunk(s)" in summary


def test_apply_unified_diff_invalid_raises_value_error(validator):
    """Verify applying an invalid patch raises ValueError with diagnostic error."""
    invalid_patch = (
        "@@ -1,3 +1,3 @@\n"
        " def wrong_function():\n"
        "-    x = 1\n"
        "+    x = 2\n"
    )
    with pytest.raises(ValueError, match="Patch validation failed"):
        validator.apply_unified_diff(SAMPLE_PYTHON_CODE, invalid_patch)
