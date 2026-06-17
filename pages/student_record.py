import streamlit as st
import tempfile
import os
import numpy as np
import soundfile as sf
import sounddevice as sd
import time
import threading
import json
from pathlib import Path

# Import your pipeline helpers (adjust paths if needed)
from src.pipeline import WhisperASRService
from src.alignment import AlignmentEngine
from src.models import RunningRecordResult, AlignmentResult
from utils import ERROR_LABELS

# ───────── Session State & Guards ─────────
if "assessment_active" not in st.session_state:
    st.session_state["assessment_active"] = False
if "recording_in_progress" not in st.session_state:
    st.session_state["recording_in_progress"] = False

# Auto-cleanup on page load
if st.session_state.get("recording_in_progress") and not st.session_state.get("assessment_active"):
    st.warning("⚠️ Previous recording session interrupted. State reset.")
    st.session_state["recording_in_progress"] = False    

def guard_assessment():
    if not st.session_state.get("assessment_active", False):
        st.warning("🚫 Please start a new assessment from the Home page first.")
        return False
    return True

if not guard_assessment():
    st.stop()  # Prevents execution of recording/Whisper logic if guard fails

def run_assessment_pipeline(audio_path: str, target_text: str) -> AlignmentResult:
    asr_service = WhisperASRService()
    record_result = asr_service.transcribe_file(audio_path)
    record_result.target_text = target_text
    engine = AlignmentEngine()
    return engine.process_result(record_result)

def main():
    st.title("🎤 Student Record")

    # 1. Check for Assigned Passage
    if "current_passage_id" not in st.session_state or st.session_state.current_passage_id is None:
        st.warning("No passage assigned. Please go to Home Dashboard -> Teacher View to assign one.")
        return

    # Load passages
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    PASSAGES_FILE = PROJECT_ROOT / "passages.json"

    if not PASSAGES_FILE.exists():
        st.error("Passages file not found.")
        return
        
    with open(PASSAGES_FILE, "r", encoding="utf-8") as f:
        passages = json.load(f)
        
    # Handle both list and dict formats gracefully
    if isinstance(passages, list):
        passage = next((p for p in passages if p.get("id") == st.session_state.current_passage_id), None)
    else:
        passage = passages.get(st.session_state.current_passage_id)
        
    if not passage:
        st.error(f"Assigned passage '{st.session_state.current_passage_id}' not found.")
        return

    target_text = passage.get("text", "")
    st.markdown(f"**Reading Passage:** {passage.get('title', 'Unknown')}")
    st.text_area("📖 Target Text", value=target_text, height=150, disabled=True)
    
    st.divider()
    
    # 2. Recording Controls & State
    if "is_recording" not in st.session_state:
        st.session_state.is_recording = False
    if "recording_complete" not in st.session_state:
        st.session_state.recording_complete = False
    if "analysis_done" not in st.session_state:
        st.session_state.analysis_done = False
    if "temp_audio_file" not in st.session_state:
        st.session_state.temp_audio_file = None

    col1, col2, col3 = st.columns([0.15, 0.15, 0.7]) 
    
    with col1:
        if st.button("🎙️ Start", disabled=st.session_state.is_recording):
            st.session_state.is_recording = True
            st.session_state.recording_complete = False
            st.session_state.analysis_done = False
            st.session_state["assessment_active"] = True
            st.session_state["recording_in_progress"] = True
            # Initialize temp file for audio storage
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_file.close()
            st.session_state.temp_audio_file = temp_file.name
            st.rerun()

    with col2:
        if st.button("⏹️ Stop", disabled=not st.session_state.is_recording):
            st.session_state.is_recording = False
            st.rerun()

    with col3:
        if st.button("🔄 Reset", disabled=st.session_state.is_recording):
            # Clean up temp file if it exists
            if st.session_state.get("temp_audio_file") and os.path.exists(st.session_state.temp_audio_file):
                os.unlink(st.session_state.temp_audio_file)
            st.session_state.is_recording = False
            st.session_state.recording_complete = False
            st.session_state.analysis_done = False
            st.session_state["assessment_active"] = False
            st.session_state["recording_in_progress"] = False
            st.session_state.temp_audio_file = None
            st.rerun()

    # 3. Recording Logic (Background Thread)
    if st.session_state.is_recording:
        st.info("🔴 Recording... Click **Stop** when finished.")
        
        # Initialize recording state if needed
        if "recording_thread" not in st.session_state:
            st.session_state.recording_thread = None
        if "stop_event" not in st.session_state:
            st.session_state.stop_event = threading.Event()
        if "audio_lock" not in st.session_state:
            st.session_state.audio_lock = threading.Lock()
            # Initialize audio chunks list
            if "audio_chunks" not in st.session_state:
                st.session_state.audio_chunks = []

        def record_callback(indata, frames, time_info, status):
            """Callback for sounddevice stream."""
            if status:
                print(f"Audio callback status: {status}")
            if st.session_state.stop_event.is_set():
                sd.default.stop()
                return
            with st.session_state.audio_lock:
                st.session_state.audio_chunks.append(indata.copy())

        # Start recording thread if not already running
        if st.session_state.recording_thread is None or not st.session_state.recording_thread.is_alive():
            st.session_state.stop_event.clear()
            st.session_state.audio_chunks = []
            
            def recording_worker():
                """Worker function that runs the audio recording."""
                try:
                    with sd.InputStream(
                        samplerate=16000,
                        channels=1,
                        callback=record_callback
                    ):
                        while not st.session_state.stop_event.is_set():
                            time.sleep(0.1)
                except Exception as e:
                    print(f"Recording error: {e}")
            
            thread = threading.Thread(target=recording_worker, daemon=True)
            thread.start()
            st.session_state.recording_thread = thread

        # Check if recording should stop
        if not st.session_state.is_recording:
            st.session_state.stop_event.set()
            # Wait for thread to finish
            if st.session_state.recording_thread and st.session_state.recording_thread.is_alive():
                st.session_state.recording_thread.join(timeout=2.0)
            
            # Save audio to temp file
            with st.session_state.audio_lock:
                audio_chunks = list(st.session_state.audio_chunks)
            
            if audio_chunks:
                audio_data = np.concatenate(audio_chunks, axis=0)
                sf.write(st.session_state.temp_audio_file, audio_data, 16000)
                st.session_state.recording_complete = True
                st.session_state["recording_in_progress"] = False
            
            # Clean up thread state for next recording
            st.session_state.recording_thread = None
            st.session_state.stop_event = threading.Event()
            st.session_state.audio_lock = threading.Lock()
            st.session_state.audio_chunks = []
            st.rerun()

    # 4. Analysis Phase (Triggered when recording stops and audio exists)
    if (not st.session_state.is_recording and 
        st.session_state.get("recording_complete", False) and 
        st.session_state.get("temp_audio_file") and 
        os.path.exists(st.session_state.temp_audio_file) and
        not st.session_state.analysis_done):
        
        with st.spinner("🔍 Analyzing reading accuracy..."):
            try:
                wav_path = st.session_state.temp_audio_file
                
                # Run the pipeline
                result = run_assessment_pipeline(wav_path, target_text)
                
                # 💡 CRITICAL: Convert AlignmentResult to JSON-serializable dict
                result_dict = {
                    "student_id": st.session_state.get("current_student_id", "Unknown"),
                    "passage_id": st.session_state.current_passage_id,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "accuracy_pct": float(getattr(result, 'accuracy', 0)),
                    "miscue_count": int(getattr(result, 'miscues', 0)),
                    "word_error_rate": float(getattr(result, 'wer', 1.0)),
                    "transcript": getattr(result, 'transcript', ""),
                    "alignment_data": str(result)
                }

                # 💾 SAVE TO JSON FOR TEACHER DASHBOARD
                RECORDS_DIR = PROJECT_ROOT / "data" / "records"
                RECORDS_DIR.mkdir(parents=True, exist_ok=True)
                record_file = RECORDS_DIR / f"{result_dict['student_id']}_{time.strftime('%Y%m%d_%H%M%S')}.json"
                
                with open(record_file, "w", encoding="utf-8") as f:
                    json.dump(result_dict, f, indent=2)

                st.session_state.last_result = result
                st.session_state.analysis_done = True
                
                st.success(f"✅ Analysis complete! Saved to `{record_file.name}`")
                time.sleep(1.5)

                # Reset state for next assessment
                # Clean up temp file
                if st.session_state.get("temp_audio_file") and os.path.exists(st.session_state.temp_audio_file):
                    os.unlink(st.session_state.temp_audio_file)
                
                st.session_state["recording_complete"] = False
                st.session_state["assessment_active"] = False
                st.session_state.temp_audio_file = None
                st.session_state.analysis_done = False
                
                # Redirect to results page
                try:
                    st.switch_page("pages/student_results.py")
                except Exception:
                    st.info("ℹ️ Results saved. Navigate to Teacher Dashboard to view.")

            except Exception as e:
                st.error(f"Analysis failed: {e}")
                st.exception(e)

    elif not st.session_state.is_recording and not st.session_state.get("recording_complete", False):
        st.info("Click **Start** to begin recording.")

if __name__ == "__main__":
    main()