import os
import time
import subprocess
import threading
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import streamlink

from .video_buffer import VideoBuffer

logger = logging.getLogger("StreamCaptureService")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class StreamCaptureService:
    def __init__(
        self,
        channel_name: str,
        buffer_dir: Path,
        quality: str = "720p60,720p,480p,best",
        max_buffer_seconds: int = 600,
        segment_duration: float = 2.0
    ):
        self.channel_name = channel_name.strip().lower()
        self.buffer_dir = Path(buffer_dir)
        self.quality = quality
        self.segment_duration = segment_duration

        self.buffer = VideoBuffer(
            buffer_dir=self.buffer_dir,
            max_buffer_seconds=max_buffer_seconds,
            segment_duration=self.segment_duration
        )

        self.session = streamlink.Streamlink()
        try:
            self.session.set_option("twitch-disable-ads", True)
            self.session.set_option("twitch-low-latency", True)
        except Exception:
            pass

        self.is_running: bool = False
        self._capture_thread: Optional[threading.Thread] = None
        self._watcher_thread: Optional[threading.Thread] = None
        self._ffmpeg_process: Optional[subprocess.Popen] = None

    def start(self):
        """Inicia a captura contínua e o gerenciador de buffer em threads dedicadas"""
        if self.is_running:
            return
        
        # Garante que o diretório do buffer esteja limpo antes de iniciar
        self.buffer.clear_all()
        self.buffer_dir.mkdir(parents=True, exist_ok=True)

        self.is_running = True
        logger.info(f"[StreamCaptureService] Iniciando serviço de captura contínua para '{self.channel_name}'...")

        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

        self._watcher_thread = threading.Thread(target=self._watcher_loop, daemon=True)
        self._watcher_thread.start()

    def stop(self):
        """Para a captura, encerra o FFmpeg e limpa os arquivos temporários do buffer"""
        logger.info("[StreamCaptureService] Parando serviço de captura...")
        self.is_running = False
        if self._ffmpeg_process:
            try:
                self._ffmpeg_process.stdin.close()
                self._ffmpeg_process.terminate()
                self._ffmpeg_process.wait(timeout=3)
            except Exception:
                pass
        
        # Aguarda Windows liberar os handles de arquivo e limpa todo o buffer
        time.sleep(0.5)
        self.buffer.clear_all()
        logger.info("[StreamCaptureService] [✓] Diretório do buffer temporário limpo com sucesso.")

    def _capture_loop(self):
        """Loop contínuo de conexão ao Streamlink e alimentação do FFmpeg"""
        url = f"https://twitch.tv/{self.channel_name}"

        while self.is_running:
            try:
                logger.info(f"[StreamCaptureService] Buscando streams disponíveis em {url}...")
                streams = self.session.streams(url)
                if not streams:
                    logger.warning(f"[StreamCaptureService] Canal '{self.channel_name}' parece estar offline. Tentando em 15s...")
                    time.sleep(15)
                    continue

                # Seleciona a melhor qualidade conforme preferência
                stream = None
                for q in self.quality.split(","):
                    q = q.strip()
                    if q in streams:
                        stream = streams[q]
                        logger.info(f"[StreamCaptureService] Qualidade selecionada: '{q}'")
                        break
                if not stream:
                    stream = streams.get("best")
                    logger.info("[StreamCaptureService] Usando qualidade padrão 'best'")

                # Inicia o FFmpeg para segmentar em blocos de 2 segundos (.ts)
                output_pattern = str(self.buffer_dir / "seg_%06d.ts")
                ffmpeg_cmd = [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
                    "-i", "pipe:0",
                    "-c", "copy",
                    "-f", "segment",
                    "-segment_time", str(self.segment_duration),
                    "-reset_timestamps", "1",
                    output_pattern
                ]

                self._ffmpeg_process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE
                )

                fd = stream.open()
                logger.info("[StreamCaptureService] Gravando fluxo de vídeo no buffer circular...")

                while self.is_running:
                    chunk = fd.read(64 * 1024)
                    if not chunk:
                        logger.warning("[StreamCaptureService] Fim do fluxo de dados (stream offline ou queda).")
                        break
                    try:
                        self._ffmpeg_process.stdin.write(chunk)
                    except (BrokenPipeError, OSError):
                        break

                fd.close()
                if self._ffmpeg_process and self._ffmpeg_process.poll() is None:
                    self._ffmpeg_process.stdin.close()
                    self._ffmpeg_process.wait(timeout=5)

            except Exception as e:
                logger.error(f"[StreamCaptureService] Erro na captura de vídeo: {e}")
                time.sleep(5)

    def _watcher_loop(self):
        """
        Monitora os arquivos de segmentos gerados no diretório do buffer,
        registra segmentos prontos e descarta os mais antigos (circular).
        """
        registered_files = set()

        while self.is_running:
            try:
                # Lista todos os arquivos .ts ordenados por nome
                ts_files = sorted(list(self.buffer_dir.glob("seg_*.ts")))

                # Um segmento só é considerado concluído quando o próximo segmento já começou a ser gravado
                # (ou seja, todos os arquivos exceto o último da lista)
                if len(ts_files) > 1:
                    completed_files = ts_files[:-1]
                    for f in completed_files:
                        if f.name not in registered_files:
                            self.buffer.register_new_segment(f)
                            registered_files.add(f.name)

                # Limpa segmentos expirados do buffer circular
                removed = self.buffer.clean_old_segments()
                if removed > 0:
                    # Remove do conjunto de conhecidos os arquivos que foram excluídos
                    registered_files = {name for name in registered_files if (self.buffer_dir / name).exists()}

            except Exception as e:
                logger.error(f"[StreamCaptureService] Erro no watcher de buffer: {e}")

            time.sleep(2)

    def get_buffer_stats(self) -> Dict[str, Any]:
        return self.buffer.get_stats()
