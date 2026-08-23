import ctypes
import logging
from typing import Literal, Optional

logger = logging.getLogger("jarvis.agent.tools.media_control")

VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
KEYEVENTF_KEYUP = 0x0002


def _send_virtual_key(vk_code: int) -> None:
    """Simulate key press and release for Windows virtual key code."""
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)


def _get_endpoint_volume():
    """Helper to initialize and return pycaw master audio volume endpoint."""
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL

    devices = AudioUtilities.GetSpeakers()
    if not devices:
        raise RuntimeError("No audio output speaker devices found.")
    
    # Support both pycaw legacy and modern AudioUtilities API
    if hasattr(devices, "Activate"):
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    elif hasattr(devices, "EndpointVolume"):
        return devices.EndpointVolume
    else:
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def set_volume(level: int) -> str:
    """
    Set the Windows master audio volume level.

    Args:
        level: Master volume percentage from 0 to 100 (automatically clamped).
    """
    try:
        clamped_level = max(0, min(100, int(level)))
        scalar = clamped_level / 100.0

        try:
            volume = _get_endpoint_volume()
            volume.SetMasterVolumeLevelScalar(scalar, None)
            logger.info("Set system volume to %d%%", clamped_level)
            return f"Successfully set master volume to {clamped_level}%."
        except Exception as e:
            logger.warning("pycaw volume adjustment failed (%s), attempting virtual key fallback", e)
            # Fallback: cannot set exact scalar via keybd_event, but report attempt
            return f"Error adjusting volume to {clamped_level}%: {str(e)}"
    except Exception as e:
        logger.error("Error in set_volume: %s", e)
        return f"Error setting volume: {str(e)}"


def mute_toggle() -> str:
    """
    Toggle Windows master audio mute state (mute / unmute).
    """
    try:
        try:
            volume = _get_endpoint_volume()
            current_mute = volume.GetMute()
            new_mute = not current_mute
            volume.SetMute(new_mute, None)
            state_str = "muted" if new_mute else "unmuted"
            logger.info("Toggled mute state to: %s", state_str)
            return f"Master audio is now {state_str}."
        except Exception as pycaw_err:
            logger.warning("pycaw mute toggle failed (%s), using virtual key", pycaw_err)
            _send_virtual_key(VK_VOLUME_MUTE)
            return "Successfully toggled master audio mute state."
    except Exception as e:
        logger.error("Error in mute_toggle: %s", e)
        return f"Error toggling mute state: {str(e)}"


def media_key(action: Literal["play_pause", "next", "previous", "stop"]) -> str:
    """
    Send media playback controls (play/pause, next track, previous track, stop) to the active media player.

    Args:
        action: The media action to trigger ('play_pause', 'next', 'previous', 'stop').
    """
    raw_action = str(action or "").strip().lower().replace("-", "_").replace(" ", "_")

    key_map = {
        "play": VK_MEDIA_PLAY_PAUSE,
        "pause": VK_MEDIA_PLAY_PAUSE,
        "play_pause": VK_MEDIA_PLAY_PAUSE,
        "playpause": VK_MEDIA_PLAY_PAUSE,
        "next": VK_MEDIA_NEXT_TRACK,
        "next_track": VK_MEDIA_NEXT_TRACK,
        "prev": VK_MEDIA_PREV_TRACK,
        "previous": VK_MEDIA_PREV_TRACK,
        "prev_track": VK_MEDIA_PREV_TRACK,
        "previous_track": VK_MEDIA_PREV_TRACK,
        "stop": VK_MEDIA_STOP,
    }

    if raw_action not in key_map:
        valid_options = "play_pause, next, previous, stop"
        return f"Error: Unknown media action '{action}'. Valid actions are: {valid_options}."

    try:
        vk = key_map[raw_action]
        _send_virtual_key(vk)
        logger.info("Sent media key for action '%s' (VK: 0x%X)", raw_action, vk)
        return f"Successfully triggered media key '{raw_action}'."
    except Exception as e:
        logger.error("Error sending media key '%s': %s", action, e)
        return f"Error sending media key '{action}': {str(e)}"
