import os
import time
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from .video_buffer import VideoBuffer

logger = logging.getLogger("ClipExtractor")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class ClipExtractor:
    """
    Responsável por:
    1. Aguardar a gravação do contexto posterior ao pico (ex: 30s após o evento).
    2. Localizar no VideoBuffer os segmentos .ts correspondentes ao intervalo [T - pre, T + post].
    3. Concatenar e gerar um arquivo de vídeo independente .mp4 pronto para transcrição.
    """
    def __init__(
        self,
        video_buffer: VideoBuffer,
        output_dir: Path,
        clip_pre_seconds: int = 30,
        clip_post_seconds: int = 30
    ):
        self.buffer = video_buffer
        self.output_dir = Path(output_dir)
        self.clip_pre_seconds = clip_pre_seconds
        self.clip_post_seconds = clip_post_seconds
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_clip(self, peak_event: Dict[str, Any]) -> Optional[Path]:
        """
        Executa a extração do corte para um evento de pico.
        Aguarda o vídeo posterior, une os segmentos .ts e gera o .mp4 final.
        """
        peak_timestamp = peak_event["timestamp"]
        formatted_time = peak_event.get("formatted_time", "pico").replace(":", "")
        multiplier = peak_event.get("multiplier", 1.0)

        target_start = peak_timestamp - self.clip_pre_seconds
        target_end = peak_timestamp + self.clip_post_seconds

        logger.info(
            f"[ClipExtractor] Solicitação de corte recebida para pico das {peak_event.get('formatted_time')}."
        )
        logger.info(
            f"[ClipExtractor] Aguardando gravação do trecho futuro (+{self.clip_post_seconds}s)..."
        )

        # Aguarda até que o buffer tenha gravado até o target_end (+ margem de 4s para fechar o último .ts)
        wait_deadline = target_end + 15 # Timeout de segurança
        while time.time() < wait_deadline:
            if self.buffer.is_interval_available(target_end):
                time.sleep(3) # Aguarda fechar o arquivo
                break
            time.sleep(2)

        # Recupera os segmentos correspondentes no buffer
        segments = self.buffer.get_segments_for_interval(target_start, target_end)
        if not segments:
            logger.error("[ClipExtractor] Nenhum segmento encontrado no buffer para o intervalo do corte.")
            return None

        logger.info(f"[ClipExtractor] Extraindo corte a partir de {len(segments)} segmentos temporários...")

        # Nome do arquivo final
        timestamp_str = time.strftime("%Y%m%d_%H%M%S", time.localtime(peak_timestamp))
        output_filename = f"corte_{timestamp_str}_{multiplier:.1f}x.mp4"
        output_path = self.output_dir / output_filename

        # Cria lista de concatenação temporária para o FFmpeg
        concat_file = self.output_dir / f"concat_{int(time.time() * 1000)}.txt"
        try:
            with open(concat_file, "w", encoding="utf-8") as f:
                for seg in segments:
                    # FFmpeg concat requer barras normais (forward slashes) ou escape
                    safe_path = str(seg["path"].resolve()).replace("\\", "/")
                    f.write(f"file '{safe_path}'\n")

            # Executa concatenação do FFmpeg com stream copy (extremamente rápido e sem perda)
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                "-movflags", "+faststart",
                str(output_path)
            ]

            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"[ClipExtractor] Falha no FFmpeg ao juntar segmentos: {result.stderr}")
                return None

            # Validação do arquivo gerado
            if not output_path.exists() or output_path.stat().st_size == 0:
                logger.error("[ClipExtractor] Arquivo de corte gerado está vazio ou não foi criado.")
                return None

            file_size_mb = round(output_path.stat().st_size / (1024 * 1024), 2)
            logger.info(f"[ClipExtractor] [✓] Corte gerado com sucesso: '{output_path.name}' ({file_size_mb} MB)")
            return output_path

        except Exception as e:
            logger.error(f"[ClipExtractor] Erro durante a extração do corte: {e}")
            return None
        finally:
            if concat_file.exists():
                try:
                    concat_file.unlink()
                except Exception:
                    pass
