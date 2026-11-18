import os
import shutil
import tempfile
import time
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import torch

from srt_generator import (
    AVAILABLE_MODELS,
    get_system_device,
    transcribe_media,
    generate_srt_from_segments
)

app = FastAPI(title="TKK Subtitle Generator - Whisper API")

# Configuração de CORS para permitir requisições do frontend React (Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = os.path.join(tempfile.gettempdir(), "tkk_subtitles_temp")
os.makedirs(TEMP_DIR, exist_ok=True)

# Endpoint de Verificação
@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": time.time()}

# Endpoint de Informações do Sistema e Modelos Whisper
@app.get("/api/info")
def get_system_info():
    cuda_available = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if cuda_available else "Processador (CPU)"
    return {
        "device": "cuda" if cuda_available else "cpu",
        "device_name": device_name,
        "default_model": "base",
        "models": AVAILABLE_MODELS,
        "languages": [
            {"code": "pt", "label": "Português (Brasil)"},
            {"code": "auto", "label": "Detecção Automática"},
            {"code": "en", "label": "Inglês"},
            {"code": "es", "label": "Espanhol"},
            {"code": "fr", "label": "Francês"},
            {"code": "it", "label": "Italiano"},
            {"code": "de", "label": "Alemão"},
            {"code": "ja", "label": "Japonês"}
        ]
    }

# Endpoint de Transcrição e Geração de SRT
@app.post("/api/transcribe")
async def transcribe_endpoint(
    file: UploadFile = File(...),
    model: str = Form("base"),
    language: str = Form("pt"),
    mode: str = Form("short_video"), # "short_video" ou "standard"
    max_words: int = Form(3)
):
    valid_models = [m["id"] for m in AVAILABLE_MODELS]
    if model not in valid_models:
        model = "base"

    # Salva arquivo temporário
    file_ext = os.path.splitext(file.filename)[1].lower() or ".mp4"
    temp_file_path = os.path.join(TEMP_DIR, f"upload_{int(time.time()*1000)}{file_ext}")

    start_time = time.time()
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Processa áudio/vídeo com Whisper
        result = transcribe_media(
            file_path=temp_file_path,
            model_name=model,
            language=language if language != "auto" else None,
            mode=mode,
            max_words_per_line=max_words
        )

        elapsed = round(time.time() - start_time, 2)
        result["processing_time_seconds"] = elapsed
        result["filename"] = file.filename
        return {"success": True, **result}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao processar arquivo: {str(e)}")
    finally:
        # Limpa arquivo temporário
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

# Endpoint para regerar SRT a partir de segmentos editados
@app.post("/api/generate-srt")
async def generate_srt_endpoint(payload: dict):
    segments = payload.get("segments", [])
    if not segments:
        raise HTTPException(status_code=400, detail="Lista de segmentos vazia")
    
    srt_content = generate_srt_from_segments(segments)
    return {"srt_content": srt_content}

# Servir Frontend compilado (SPA)
dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(dist_dir):
    assets_dir = os.path.join(dist_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Endpoint não encontrado")
        file_path = os.path.join(dist_dir, full_path)
        if full_path and os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(dist_dir, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
