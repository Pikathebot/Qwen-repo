import io
import logging
import threading
from typing import Optional, Union

logger = logging.getLogger("jarvis.agent.tools.audio_playback")

_audio_lock = threading.Lock()
_is_playing = False
_current_playback_thread: Optional[threading.Thread] = None


def is_playing() -> bool:
    """Returns True if audio playback is currently active."""
    global _is_playing
    return _is_playing


def stop_playback() -> str:
    """
    Immediately interrupts and stops any ongoing audio playback.
    """
    global _is_playing
    with _audio_lock:
        try:
            import sounddevice as sd
            sd.stop()
        except Exception as e:
            logger.debug("Error stopping sounddevice stream: %s", e)
        _is_playing = False
    logger.info("Audio playback stopped.")
    return "Audio playback stopped."


def play_audio(audio_bytes: bytes) -> str:
    """
    Plays synthesized audio bytes (WAV/FLAC/OGG) non-blockingly on a background thread.
    """
    global _is_playing, _current_playback_thread

    if not audio_bytes or len(audio_bytes) == 0:
        return "No audio bytes provided for playback."

    # Stop any currently playing audio before starting new playback
    stop_playback()

    def _playback_worker(data: bytes):
        global _is_playing
        try:
            import soundfile as sf
            import sounddevice as sd

            with io.BytesIO(data) as bio:
                audio_data, sample_rate = sf.read(bio, dtype="float32")

            with _audio_lock:
                _is_playing = True

            sd.play(audio_data, sample_rate)
            sd.wait()
        except Exception as e:
            logger.warning("Playback worker error: %s", e)
        finally:
            with _audio_lock:
                _is_playing = False

    with _audio_lock:
        _current_playback_thread = threading.Thread(
            target=_playback_worker,
            args=(bytes(audio_bytes),),
            daemon=True,
            name="JarvisAudioPlaybackThread"
        )
        _current_playback_thread.start()

    return f"Audio playback started ({len(audio_bytes)} bytes)."
