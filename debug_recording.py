import sys
from pathlib import Path
import tempfile
import os
import sounddevice as sd
import numpy as np
import soundfile as sf

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline import WhisperASRService
from src.alignment import AlignmentEngine
from src.models import RunningRecordResult

def debug_recording():
    print("🎤 Starting recording... Speak now. Press Enter when finished.")
    
    # 1. Record Audio
    audio_buffer = []
    def callback(indata, frames, time, status):
        if status:
            print(status)
        audio_buffer.append(indata.copy())

    sd.default.channels = 1
    with sd.InputStream(samplerate=16000, channels=1, callback=callback):
        input("Recording... Press Enter to stop.\n")
    
    # 2. Save to WAV
    if not audio_buffer:
        print("❌ No audio recorded.")
        return

    audio_data = np.concatenate(audio_buffer, axis=0)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, audio_data, 16000)
        wav_path = tmp.name

    print(f"✅ Audio saved to {wav_path}")

    # 3. Run ASR Pipeline
    print("🗣️ Transcribing...")
    try:
        asr_service = WhisperASRService()
        record_result = asr_service.transcribe_file(wav_path)
        
        target_text = "The rain in Spain stays mainly in the plain."
        record_result.target_text = target_text
        
        print(f"📝 Transcript: {record_result.transcript_text}")
        print(f"🎯 Target:    {record_result.target_text}")

        # 4. Run Alignment
        print("🔍 Aligning and analyzing...")
        engine = AlignmentEngine()
        result = engine.process_result(record_result)
        
        print("\n--- ANALYSIS RESULTS ---")
        print(f"Accuracy: {result.metrics.accuracy:.0%}")
        print(f"WPM:      {result.metrics.wpm:.1f}")
        print(f"Errors:   {len(result.errors)}")
        
        for i, err in enumerate(result.errors):
            print(f"  {i+1}. [{err.error_type}] {err.reason}")

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        os.unlink(wav_path)

if __name__ == "__main__":
    debug_recording()
