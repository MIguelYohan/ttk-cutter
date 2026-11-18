import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega .env da raiz do projeto
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Suporta tanto com prefixo TWITCH_ quanto sem prefixo
TWITCH_CLIENT_ID = (os.getenv("TWITCH_CLIENT_ID") or os.getenv("CLIENT_ID") or "").strip()
TWITCH_CLIENT_SECRET = (os.getenv("TWITCH_CLIENT_SECRET") or os.getenv("CLIENT_SECRET") or "").strip()
TWITCH_USER_TOKEN = (os.getenv("TWITCH_USER_TOKEN") or os.getenv("USER_TOKEN") or "").strip()
TWITCH_CHANNEL = (os.getenv("TWITCH_CHANNEL") or os.getenv("CHANNEL") or "").strip().lower()

# Configurações de Análise e Cortes (Uso pessoal)
WINDOW_SECONDS = int(os.getenv("WINDOW_SECONDS", "10"))
PEAK_MULTIPLIER = float(os.getenv("PEAK_MULTIPLIER", "3.0"))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "60"))
CLIP_PRE_SECONDS = int(os.getenv("CLIP_PRE_SECONDS", "30"))
CLIP_POST_SECONDS = int(os.getenv("CLIP_POST_SECONDS", "30"))

# Diretórios temporários locais
BASE_DIR = Path(__file__).resolve().parent.parent.parent
BUFFER_DIR = BASE_DIR / "temp_video_buffer"
CLIPS_DIR = BASE_DIR / "extracted_clips"
TRANSCRIBE_API_URL = os.getenv("TRANSCRIBE_API_URL", "http://127.0.0.1:8000/api/transcribe")
