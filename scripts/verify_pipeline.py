"""Real-model verification harness for the transcribe→align path.

Feeds a sample WAV through the *actual* whisper-medium model and the alignment
engine, then prints a Running Record report. The microphone step is bypassed:
audio is either supplied via --wav or synthesized from text with macOS `say`.

Requires HUGGING_FACE_HUB_TOKEN in the environment, plus `ffmpeg` (and `say` for
synthesis). The whisper-medium model (~2.8 GB) is downloaded on first use if it
isn't already in the Hugging Face cache.

Examples:
    # Perfect read of the default passage (synthesized speech)
    python scripts/verify_pipeline.py

    # Introduce miscues by speaking something slightly different
    python scripts/verify_pipeline.py \
        --target "The rain in Spain stays mainly in the plain." \
        --text   "The rain in Spain stays mostly in the plane."

    # Use your own recording
    python scripts/verify_pipeline.py --wav my_reading.wav \
        --target "The rain in Spain stays mainly in the plain."
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Make repo-root imports (src/, demo_pipeline) work when run as a script.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.alignment import AlignmentEngine          # noqa: E402
from src.pipeline import WhisperASRService          # noqa: E402
from demo_pipeline import display_results           # noqa: E402

DEFAULT_TARGET = "The rain in Spain stays mainly in the plain."
SAMPLE_RATE = 16000


def synthesize_wav(text: str, voice: str | None = None) -> str:
    """Synthesize speech to a 16 kHz mono WAV via macOS `say` + ffmpeg."""
    if shutil.which("say") is None:
        sys.exit("❌ macOS `say` not found. Supply audio with --wav instead.")
    if shutil.which("ffmpeg") is None:
        sys.exit("❌ `ffmpeg` not found. Install it (e.g. `brew install ffmpeg`).")

    tmpdir = tempfile.mkdtemp(prefix="verify_pipeline_")
    aiff = os.path.join(tmpdir, "speech.aiff")
    wav = os.path.join(tmpdir, "speech.wav")

    say_cmd = ["say", "-o", aiff]
    if voice:
        say_cmd += ["-v", voice]
    say_cmd.append(text)
    subprocess.run(say_cmd, check=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", aiff, "-ar", str(SAMPLE_RATE), "-ac", "1", wav],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    os.unlink(aiff)
    return wav


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", default=DEFAULT_TARGET, help="Target passage text to align against.")
    p.add_argument("--text", default=None, help="Text to speak (defaults to --target ⇒ a perfect read).")
    p.add_argument("--wav", default=None, help="Use an existing WAV instead of synthesizing.")
    p.add_argument("--say-voice", default=None, help="Voice for macOS `say` (e.g. Samantha).")
    return p.parse_args()


def main():
    args = parse_args()

    if not os.getenv("HUGGING_FACE_HUB_TOKEN"):
        sys.exit("❌ HUGGING_FACE_HUB_TOKEN is not set. Export it before running "
                 "(e.g. `export $(grep -v '^#' .env | xargs)`).")

    if args.wav:
        wav_path = args.wav
        if not os.path.exists(wav_path):
            sys.exit(f"❌ WAV not found: {wav_path}")
        print(f"🎧 Using audio: {wav_path}")
    else:
        speech = args.text if args.text is not None else args.target
        print(f"🗣️  Synthesizing speech: \"{speech}\"")
        wav_path = synthesize_wav(speech, voice=args.say_voice)

    print(f"📖 Target text:    \"{args.target}\"")
    print("🔄 Transcribing with Whisper (downloads the model only if not cached)...")

    asr = WhisperASRService()
    asr_result = asr.transcribe_file(wav_path)
    asr_result.target_text = args.target

    alignment = AlignmentEngine().process_result(asr_result)
    display_results(asr_result, alignment)


if __name__ == "__main__":
    main()
