import pytest
import httpx
from app.main import app
from app.voice.wake_word import WakeWordDetector
from app.voice.transcriber import AudioTranscriber
from app.voice.synthesizer import VoiceSynthesizer


# --- Unit Tests for Voice Subsystems ---

def test_wake_word_detector():
    wakes = []

    def on_wake_triggered(query):
        wakes.append(query)

    detector = WakeWordDetector(on_wake=on_wake_triggered)

    # 1. Direct wake word
    detected, word, query = detector.detect_in_text("Jarvis, what time is it?")
    assert detected is True
    assert word.lower() == "jarvis"
    assert query == "what time is it?"
    assert len(wakes) == 1

    # 2. Multi-word wake phrase
    detected2, word2, query2 = detector.detect_in_text("Hey Jarvis! List the files in docs.")
    assert detected2 is True
    assert "jarvis" in word2.lower()
    assert "List the files in docs" in query2

    # 3. No wake word
    detected3, _, _ = detector.detect_in_text("Tell me a funny story.")
    assert detected3 is False


def test_voice_synthesizer_sanitization():
    synth = VoiceSynthesizer()
    raw_markdown = (
        "# System Health\n"
        "Here is the status: **Online**.\n"
        "```python\ndef foo(): pass\n```\n"
        "Check out `config.py` at [Link](http://example.com)."
    )

    clean = synth.sanitize_for_speech(raw_markdown)
    assert "#" not in clean
    assert "```" not in clean
    assert "**" not in clean
    assert "[code block omitted]" in clean
    assert "Online" in clean
    assert "config.py" in clean

    res = synth.synthesize(raw_markdown)
    assert "spoken_text" in res
    assert res["length_chars"] > 0


def test_audio_transcriber_processing():
    transcriber = AudioTranscriber()
    dummy_wav = b"RIFF" + b"\x00" * 100
    res = transcriber.transcribe_audio_bytes(dummy_wav, format="wav")
    assert "duration_seconds" in res
    assert res["format"] == "wav"


# --- API Integration Tests with FastAPI app ---

@pytest.mark.anyio
async def test_voice_status_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/voice/status")
    
    assert response.status_code == 200
    data = response.json()
    assert "wake_word_active" in data
    assert "wake_words" in data
    assert "jarvis" in data["wake_words"]


@pytest.mark.anyio
async def test_voice_speak_endpoint():
    payload = {"text": "Hello! Everything is **running smoothly** with `fastapi`."}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/voice/speak", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "spoken_text" in data
    assert "**" not in data["spoken_text"]
    assert "running smoothly" in data["spoken_text"]


@pytest.mark.anyio
async def test_voice_transcribe_endpoint():
    files = {"file": ("test.wav", b"RIFF" + b"\x00" * 50, "audio/wav")}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/voice/transcribe", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert "duration_seconds" in data


@pytest.mark.anyio
async def test_chat_with_wake_word_prefix():
    """Verify that a prompt starting with 'Jarvis, ...' executes smoothly and strips wake word."""
    payload = {
        "message": "Jarvis, say 'HELLO_VOICE_CONFIRMED'",
        "model": "qwen2.5:0.5b"
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30.0) as ac:
        response = await ac.post("/chat", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert len(data["response"]) > 0
