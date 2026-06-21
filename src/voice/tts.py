import tempfile
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

tts_router = APIRouter()

class TTSRequest(BaseModel):
    text: str

@tts_router.post("/tts")
async def generate_tts(req: TTSRequest):
    try:
        import edge_tts
    except ImportError:
        return {"error": "edge-tts not installed"}
        
    text = req.text
    if not text:
        return {"error": "No text provided"}
        
    voice = "en-US-AriaNeural"
    output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)
    
    return FileResponse(output_file, media_type="audio/mpeg")
