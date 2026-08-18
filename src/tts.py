"""Offline text-to-speech synthesis for the Assessment "model reading" audio
source. Dispatches to the native OS engine per platform rather than a pip TTS
package: pyttsx3's macOS backend pulls in the entire pyobjc/Cocoa binding
suite (~190 packages) for a single subprocess call `say` already does, and
similar per-OS bulk isn't worth it when the OS ships a synthesizer already.

Target platforms: macOS (`say` + `ffmpeg`, mirroring tests/conftest.py's
say_wav_factory) and Windows 11 (SAPI5 via pywin32). No Streamlit imports —
stays part of the UI-agnostic core.

Future: revisit piper/piper-plus (neural TTS, better voice quality) if
quality becomes a priority — see the [[assessment-feature]] project memory
for the license trade-off notes (piper is GPL-3.0; piper-plus is the
MIT-licensed fork, but newer/less proven).
"""
import os
import platform
import shutil
import subprocess
import tempfile

SAMPLE_RATE = 16000

# SAPI5 SpeechAudioFormatType.SAFT16kHz16BitMono and
# SpeechStreamFileMode.SSFMCreateForWrite — passed as raw ints since we use
# late-bound win32com.client.Dispatch (no makepy/gencache), so the named
# constants from the SpeechLib type library aren't available.
_SAFT_16KHZ_16BIT_MONO = 18
_SSFM_CREATE_FOR_WRITE = 3


def synthesize_speech(text: str) -> bytes:
    """Synthesize `text` to 16kHz mono WAV audio bytes using the OS's native
    TTS engine. Raises RuntimeError on an unsupported/misconfigured host."""
    system = platform.system()
    if system == "Darwin":
        return _synthesize_macos(text)
    if system == "Windows":
        return _synthesize_windows(text)
    raise RuntimeError(f"Text-to-speech is not supported on this platform ({system}).")


def _synthesize_macos(text: str) -> bytes:
    if shutil.which("say") is None or shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "Text-to-speech requires macOS's `say` command and `ffmpeg`, "
            "neither of which was found on this host."
        )

    aiff_path = wav_path = None
    try:
        fd, aiff_path = tempfile.mkstemp(suffix=".aiff")
        os.close(fd)
        fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        subprocess.run(["say", "-o", aiff_path, text], check=True)
        subprocess.run(
            ["ffmpeg", "-y", "-i", aiff_path, "-ar", str(SAMPLE_RATE), "-ac", "1", wav_path],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        with open(wav_path, "rb") as f:
            return f.read()
    finally:
        for p in (aiff_path, wav_path):
            if p and os.path.exists(p):
                os.unlink(p)


def _synthesize_windows(text: str) -> bytes:
    try:
        import win32com.client
    except ImportError as e:
        raise RuntimeError(
            "Text-to-speech on Windows requires the `pywin32` package "
            "(pip install pywin32)."
        ) from e

    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        audio_format = win32com.client.Dispatch("SAPI.SpAudioFormat")
        audio_format.Type = _SAFT_16KHZ_16BIT_MONO
        stream.Format = audio_format
        stream.Open(wav_path, _SSFM_CREATE_FOR_WRITE)
        try:
            speaker.AudioOutputStream = stream
            speaker.Speak(text)
        finally:
            stream.Close()

        with open(wav_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(wav_path):
            os.unlink(wav_path)
