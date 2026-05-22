"""Demo script: Record audio, transcribe with Whisper, and show alignment results.

Usage:
    python demo_pipeline.py [--duration 15] [--target "The quick brown fox"]
    
Examples:
    # Record for 15 seconds, then show results
    python demo_pipeline.py
    
    # Record for 30 seconds with custom target text
    python demo_pipeline.py --duration 30 --target "A red fox jumped over the fence"
"""

import argparse
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.recording import record_audio_with_stop, list_audio_devices
from src.pipeline import WhisperASRService
from src.alignment import AlignmentEngine


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Running Record Demo: Record audio, transcribe, and analyze errors"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=15,
        help="Recording duration in seconds (default: 15)"
    )
    parser.add_argument(
        "--target",
        type=str,
        default=None,
        help="Target text to read aloud (if not provided, user is prompted)"
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio devices and exit"
    )
    return parser.parse_args()


def prompt_target_text():
    """Prompt user for target text to read aloud."""
    print("\n📖 Enter the target text you want to read aloud:")
    print("   (Type your passage, then press Enter when done)")
    print("   (Use Ctrl+D or Ctrl+Z on a new line to finish)\n")
    
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    
    target_text = " ".join(lines).strip()
    if not target_text:
        print("⚠️  No text provided. Using default sample.")
        target_text = "The cat sat on the mat"
    
    return target_text


def display_results(asr_result, alignment):
    """Display formatted results to the user."""
    print("\n" + "=" * 70)
    print("📊 RUNNING RECORD RESULTS")
    print("=" * 70)
    
    # Target vs Transcript
    print(f"\n📝 TARGET TEXT:     {alignment.target_text}")
    print(f"🎤 TRANSCRIPT:      {alignment.transcript_text}")
    
    # Metrics
    metrics = alignment.metrics
    print(f"\n📈 METRICS:")
    print(f"   Accuracy:         {metrics.accuracy * 100:.1f}%")
    print(f"   Words per Minute: {metrics.wpm:.1f}")
    print(f"   Total Words:      {metrics.total_words}")
    print(f"   Errors Detected:  {metrics.error_count}")
    
    # Error breakdown
    if alignment.errors:
        error_types = {}
        for error in alignment.errors:
            etype = error.error_type
            error_types[etype] = error_types.get(etype, 0) + 1
        
        print(f"\n🔍 ERROR BREAKDOWN:")
        for etype, count in sorted(error_types.items()):
            print(f"   {etype.capitalize():20s} {count}")
    
    # Detailed errors
    errors = [e for e in alignment.errors if e.error_type != "unknown"]
    if errors:
        print(f"\n❌ DETAILED ERRORS:")
        for i, error in enumerate(errors[:10], 1):  # Show first 10
            print(f"   {i}. [{error.error_type.upper()}] {error.reason}")
        
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more errors")
    
    print("\n" + "=" * 70)


def main():
    """Main demo pipeline."""
    args = parse_args()
    
    # List devices if requested
    if args.list_devices:
        list_audio_devices()
        return
    
    # Get target text
    target_text = args.target if args.target else prompt_target_text()
    print(f"\n📖 Target text: \"{target_text}\"")
    
    # Record audio
    try:
        audio_path = record_audio_with_stop(sample_rate=16000)
    except KeyboardInterrupt:
        print("\n⏹️  Recording cancelled.")
        return
    except RuntimeError as e:
        print(f"\n❌ Recording failed: {e}")
        return
    
    # Transcribe with Whisper
    print("\n🔄 Transcribing audio with Whisper...")
    try:
        asr_service = WhisperASRService()
        asr_result = asr_service.transcribe_file(audio_path)
        
        # Set target text in result for alignment
        asr_result.target_text = target_text
    except Exception as e:
        print(f"\n❌ Transcription failed: {e}")
        print("\n💡 Make sure you have HUGGING_FACE_HUB_TOKEN set in your environment.")
        return
    
    # Align and analyze
    print("\n🔄 Analyzing errors...")
    alignment_engine = AlignmentEngine()
    alignment = alignment_engine.process_result(asr_result)
    
    # Display results
    display_results(asr_result, alignment)
    
    # Cleanup
    from src.recording import delete_audio_file
    delete_audio_file(audio_path)


if __name__ == "__main__":
    main()
