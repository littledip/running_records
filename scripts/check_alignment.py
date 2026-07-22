"""Deterministic alignment check — no recording, no Whisper.

Feeds a target + transcript pair straight into the AlignmentEngine and prints the
same Running Record report the app would show. Because you type the transcript
yourself, ASR non-determinism is removed — ideal for verifying alignment,
word-order, homophone, and metrics behaviour by hand.

Examples:
    # Homophone: plain/plane should NOT be an error
    python scripts/check_alignment.py \
        --target     "The rain in Spain stays mainly in the plain." \
        --transcript "The rain in Spain stays in the plane."

    # Word-order: a genuine transposition
    python scripts/check_alignment.py \
        --target     "the cat sat" \
        --transcript "cat the sat"

    # Provide a duration (seconds) if you want a meaningful WPM
    python scripts/check_alignment.py --target "..." --transcript "..." --duration 7.16
"""
import argparse
import sys
from pathlib import Path

# Make repo-root imports (src/) and scripts/ imports (demo_pipeline) work.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.alignment import AlignmentEngine          # noqa: E402
from src.models import RunningRecordResult          # noqa: E402
from demo_pipeline import display_results           # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run a target/transcript pair through the alignment engine and print the report."
    )
    parser.add_argument("--target", required=True, help="The passage the student was meant to read.")
    parser.add_argument("--transcript", required=True, help="The (simulated) transcript to align against the target.")
    parser.add_argument(
        "--duration", type=float, default=0.0,
        help="Recording duration in seconds; only affects WPM. Defaults to 0 (WPM shown as 0).",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    result = RunningRecordResult(
        target_text=args.target,
        transcript_text=args.transcript,
        word_segments=[],
        metadata={"duration_s": args.duration},
    )

    alignment = AlignmentEngine().process_result(result)
    display_results(None, alignment)

    if args.duration <= 0:
        print("Note: WPM is 0 because no --duration was given (text-only check).\n")


if __name__ == "__main__":
    main()
