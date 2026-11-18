import os
import time
import queue
import threading
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger("TranscriptionClient")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class TranscriptionClient:
    """
    Consome uma fila assíncrona de cortes gerados e os envia para a
    API de transcrição existente (POST /api/transcribe), salvando o .srt resultante.
    Se a API estiver offline, não interrompe a captura e preserva os vídeos.
    """
    def __init__(
        self,
        api_url: str = "http://127.0.0.1:8000/api/transcribe",
        model: str = "base",
        language: str = "pt",
        mode: str = "short_video",
        max_words: int = 3
    ):
        self.api_url = api_url
        self.model = model
        self.language = language
        self.mode = mode
        self.max_words = max_words

        self.queue: queue.Queue = queue.Queue()
        self.is_running: bool = False
        self._worker_thread: Optional[threading.Thread] = None

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info(f"[TranscriptionClient] Fila de transcrição pronta. API alvo: {self.api_url}")

    def stop(self):
        self.is_running = False

    def enqueue_clip(self, clip_path: Path, peak_info: Optional[Dict[str, Any]] = None):
        """Adiciona um corte na fila de processamento"""
        self.queue.put({
            "clip_path": Path(clip_path),
            "peak_info": peak_info or {},
            "enqueued_at": time.time()
        })
        logger.info(f"[TranscriptionClient] Corte '{clip_path.name}' enfileirado para transcrição.")

    def _worker_loop(self):
        while self.is_running:
            try:
                task = self.queue.get(timeout=2)
            except queue.Empty:
                continue

            clip_path: Path = task["clip_path"]
            if not clip_path.exists():
                logger.warning(f"[TranscriptionClient] Arquivo '{clip_path}' não encontrado no disco. Ignorando.")
                self.queue.task_done()
                continue

            logger.info(f"[TranscriptionClient] Enviando '{clip_path.name}' para a API de transcrição...")
            try:
                with open(clip_path, "rb") as f:
                    files = {"file": (clip_path.name, f, "video/mp4")}
                    data = {
                        "model": self.model,
                        "language": self.language,
                        "mode": self.mode,
                        "max_words": self.max_words
                    }
                    resp = requests.post(self.api_url, files=files, data=data, timeout=300)

                if resp.status_code == 200:
                    result = resp.json()
                    srt_content = result.get("srt_content", "")
                    elapsed = result.get("processing_time_seconds", 0)

                    # Salva o arquivo .srt ao lado do vídeo
                    srt_path = clip_path.with_suffix(".srt")
                    with open(srt_path, "w", encoding="utf-8") as srt_file:
                        srt_file.write(srt_content)

                    logger.info(
                        f"[TranscriptionClient] [✓] Transcrição concluída em {elapsed}s! "
                        f"Legenda gerada: '{srt_path.name}' ({result.get('total_segments', 0)} blocos)"
                    )
                else:
                    logger.error(
                        f"[TranscriptionClient] API de transcrição retornou erro {resp.status_code}: {resp.text}. "
                        f"O vídeo '{clip_path.name}' foi preservado no disco."
                    )

            except requests.exceptions.ConnectionError:
                logger.warning(
                    f"[TranscriptionClient] Não foi possível conectar à API de transcrição ({self.api_url}). "
                    f"Certifique-se de que o servidor principal está rodando. O corte '{clip_path.name}' foi mantido."
                )
            except Exception as e:
                logger.error(f"[TranscriptionClient] Erro ao transcrever corte: {e}")
            finally:
                self.queue.task_done()
