# audio_control.py

from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL

def get_audio_endpoint():
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    return volume

def is_muted():
    volume = get_audio_endpoint()
    return volume.GetMute()

def set_volume(volume_level):
    volume = get_audio_endpoint()
    volume.SetMasterVolumeLevelScalar(volume_level, None)

def mute_volume():
    volume = get_audio_endpoint()
    volume.SetMute(1, None)

def unmute_volume():
    volume = get_audio_endpoint()
    volume.SetMute(0, None)

def increase_volume(increment=0.1):
    volume = get_audio_endpoint()
    current_volume = volume.GetMasterVolumeLevelScalar()
    new_volume = min(1, current_volume + increment)
    set_volume(new_volume)
    return int(new_volume * 100)

def decrease_volume(decrement=0.1):
    volume = get_audio_endpoint()
    current_volume = volume.GetMasterVolumeLevelScalar()
    new_volume = max(0, current_volume - decrement)
    set_volume(new_volume)
    return int(new_volume * 100)