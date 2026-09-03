"""
Canonical speech-shaping helpers.

Screen text and spoken text have different requirements: markdown, code blocks
and long enumerations read well on screen and terribly out loud. These helpers
are shared by the voice synthesizer and the persona layer so both produce the
same spoken form.
"""
import re

_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_EMPHASIS_RE = re.compile(r"[*_]{1,3}([^*_]+)[*_]{1,3}")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_HEADER_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_DECORATION_RE = re.compile(r"[•⚡🎯📝⚠️📊🔍💬✓]")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def sanitize_markdown_for_speech(text: str) -> str:
    """Strip markdown, code and decoration so the text vocalizes naturally."""
    if not text:
        return ""

    clean = _CODE_BLOCK_RE.sub(" [code block omitted] ", text)
    clean = _INLINE_CODE_RE.sub(r"\1", clean)
    clean = _EMPHASIS_RE.sub(r"\1", clean)
    clean = _LINK_RE.sub(r"\1", clean)
    clean = _HEADER_RE.sub("", clean)
    clean = _DECORATION_RE.sub("", clean)
    clean = _BULLET_RE.sub("", clean)
    clean = re.sub(r"\s+", " ", clean).strip()

    return clean


def split_sentences(text: str) -> list[str]:
    """Split into sentences for length-capped speech."""
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def condense_for_speech(text: str, max_sentences: int = 0) -> str:
    """
    Sanitize and optionally cap spoken output to the first `max_sentences`.

    A cap of 0 (or less) means no limit. When the text is truncated the caller
    is expected to have the full version on screen, so we say so rather than
    trailing off mid-thought.
    """
    clean = sanitize_markdown_for_speech(text)
    if max_sentences <= 0 or not clean:
        return clean

    sentences = split_sentences(clean)
    if len(sentences) <= max_sentences:
        return clean

    spoken = " ".join(sentences[:max_sentences])
    return f"{spoken} The full details are on screen."
