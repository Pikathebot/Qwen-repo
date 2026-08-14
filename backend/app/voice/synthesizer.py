import logging
import re
from typing import Any, Optional
import io

logger = logging.getLogger("jarvis.voice.synthesizer")

AVAILABLE_NEURAL_VOICES = {
    "jarvis-british": "en-GB-RyanNeural",
    "jarvis-american": "en-US-ChristopherNeural",
    "natural-male": "en-US-GuyNeural",
    "natural-female": "en-US-JennyNeural",
    "british-female": "en-GB-SoniaNeural",
}


class VoiceSynthesizer:
    """
    Studio-grade Neural Text-to-Speech synthesis and natural phrasing sanitizer.
    """

    def __init__(self, voice_name: str = "en-GB-RyanNeural", rate: str = "+0%"):
        self.voice_name = voice_name
        self.rate = rate

    def sanitize_for_speech(self, text: str) -> str:
        """
        Strip markdown tags, code blocks, and URLs to ensure natural vocalization.
        """
        if not text:
            return ""

        # Remove code blocks
        clean = re.sub(r"```[\s\S]*?```", " [code block omitted] ", text)
        # Remove inline code
        clean = re.sub(r"`([^`]+)`", r"\1", clean)
        # Remove markdown bold/italics
        clean = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", clean)
        # Remove markdown links [text](url) -> text
        clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
        # Remove markdown headers
        clean = re.sub(r"^#{1,6}\s+", "", clean, flags=re.MULTILINE)
        # Remove emojis and bullet points
        clean = re.sub(r"[•⚡🎯📝⚠️📊🔍💬✓]", "", clean)
        # Collapse whitespace
        clean = re.sub(r"\s+", " ", clean).strip()

        return clean

    def synthesize(self, text: str) -> dict[str, Any]:
        """
        Synthesize text into a speech-ready payload.
        """
        speech_text = self.sanitize_for_speech(text)
        return {
            "spoken_text": speech_text,
            "voice": self.voice_name,
            "rate": self.rate,
            "length_chars": len(speech_text)
        }

    async def generate_neural_audio_bytes(self, text: str, voice: Optional[str] = None) -> bytes:
        """
        Generate ultra-realistic humanlike MP3 audio stream using Edge Neural TTS.
        """
        clean_text = self.sanitize_for_speech(text)
        if not clean_text:
            return b""

        chosen_voice = voice or self.voice_name
        if chosen_voice in AVAILABLE_NEURAL_VOICES:
            chosen_voice = AVAILABLE_NEURAL_VOICES[chosen_voice]

        try:
            import edge_tts
            communicate = edge_tts.Communicate(clean_text, chosen_voice, rate=self.rate)
            buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buffer.write(chunk["data"])
            return buffer.getvalue()
        except Exception as e:
            logger.error("Failed to generate neural TTS audio: %s", e)
            return b""
