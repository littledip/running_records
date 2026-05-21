import os
from transformers import pipeline
import sys

def get_token():
    token = os.getenv("HUGGING_FACE_HUB_TOKEN")
    if not token:
        print("⚠️  WARNING: HUGGING_FACE_HUB_TOKEN not found in environment.")
        return None
    return token

def main():
    token = get_token()
    if not token:
        sys.exit(1)

    # ✅ Use a verified, public model ID
    model_id = "openai/whisper-medium"  # Change to "openai/whisper-large-v3-turbo" if preferred
    
    print(f"🚀 Loading Whisper '{model_id}' with Environment Token...")
    
    try:
        pipe = pipeline(
            "automatic-speech-recognition", 
            model=model_id,
            token=token
        )
        
        print("✅ SUCCESS! Model loaded without errors.")
        print(f"   Pipeline ready for transcription tasks.\n")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
