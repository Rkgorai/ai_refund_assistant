import os
import tempfile
from fastapi import APIRouter, UploadFile, File
from dotenv import load_dotenv

load_dotenv()

stt_router = APIRouter()
groq_client = None

def load_stt_model():
    global groq_client
    try:
        from groq import Groq
        print("Initializing Groq API Client for Whisper...")
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("GROQ_API_KEY is missing from .env!")
        else:
            groq_client = Groq(api_key=api_key)
            print("Groq Client initialized successfully!")
    except ImportError:
        print("groq is not installed. STT endpoint will fail if called.")
    except Exception as e:
        print(f"Failed to initialize Groq Client: {e}")

@stt_router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    global groq_client
    if groq_client is None:
        return {"error": "Groq client failed to initialize."}
        
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name
        
    try:
        with open(tmp_path, "rb") as file:
            transcription = groq_client.audio.transcriptions.create(
                file=(tmp_path, file.read()),
                model="whisper-large-v3",
                prompt="The audio is a customer interacting with an AI refund and return assistant. Ensure formatting is perfect.",  # Optional prompt to guide the model
                response_format="json",
                language="en",
                temperature=0.0  # Lowest temperature for maximum determinism and no hallucinations
            )
        return {"text": transcription.text.strip()}
    except Exception as e:
        print("Groq STT Error:", e)
        return {"error": str(e)}
    finally:
        os.unlink(tmp_path)
