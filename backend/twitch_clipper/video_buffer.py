import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

class VideoBuffer:
    """
    Gerencia os arquivos de segmentos temporários (.ts) no disco,
    mantendo um buffer circular limitado em tempo (ex: últimos 10 minutos)
    e descartando automaticamente segmentos obsoletos.
    """
    def __init__(self, buffer_dir: Path, max_buffer_seconds: int = 600, segment_duration: float = 2.0):
        self.buffer_dir = Path(buffer_dir)
        self.max_buffer_seconds = max_buffer_seconds
        self.segment_duration = segment_duration
        self.buffer_dir.mkdir(parents=True, exist_ok=True)

        # Registro dos segmentos em memória:
        # { "filename": str, "path": Path, "start_time": float, "end_time": float, "duration": float }
        self.segments: List[Dict[str, Any]] = []

    def register_new_segment(self, filepath: Path, timestamp: Optional[float] = None) -> Dict[str, Any]:
        """Registra um novo segmento .ts concluído pelo FFmpeg"""
        now = timestamp or time.time()
        start_time = now - self.segment_duration
        end_time = now

        # Se já tivermos segmentos anteriores, alinha o início deste com o fim do anterior
        if self.segments:
            prev_end = self.segments[-1]["end_time"]
            # Se a diferença for razoável (menos de 5s), encadeia
            if abs(start_time - prev_end) < 5.0:
                start_time = prev_end
                end_time = start_time + self.segment_duration

        seg_info = {
            "filename": filepath.name,
            "path": filepath,
            "start_time": start_time,
            "end_time": end_time,
            "duration": self.segment_duration
        }
        self.segments.append(seg_info)
        return seg_info

    def clean_old_segments(self) -> int:
        """Remove segmentos que ultrapassaram o tempo máximo do buffer circular"""
        now = time.time()
        cutoff_time = now - self.max_buffer_seconds
        removed_count = 0

        surviving = []
        for seg in self.segments:
            if seg["end_time"] < cutoff_time:
                try:
                    if seg["path"].exists():
                        seg["path"].unlink()
                    removed_count += 1
                except Exception as e:
                    pass
            else:
                surviving.append(seg)

        self.segments = surviving
        return removed_count

    def get_segments_for_interval(self, start_time: float, end_time: float) -> List[Dict[str, Any]]:
        """
        Retorna a lista de segmentos que cobrem o intervalo [start_time, end_time].
        """
        matched = []
        for seg in self.segments:
            # Segmento intercepta o intervalo solicitado se start < end_interval e end > start_interval
            if seg["start_time"] < end_time and seg["end_time"] > start_time:
                if seg["path"].exists():
                    matched.append(seg)
        return matched

    def is_interval_available(self, end_time: float) -> bool:
        """Verifica se o buffer já gravou até o final do intervalo solicitado"""
        if not self.segments:
            return False
        latest_segment_end = self.segments[-1]["end_time"]
        return latest_segment_end >= end_time

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas atuais de ocupação do buffer"""
        total_duration = 0.0
        if self.segments:
            total_duration = max(0.0, self.segments[-1]["end_time"] - self.segments[0]["start_time"])

        total_bytes = 0
        valid_count = 0
        for seg in self.segments:
            try:
                if seg["path"].exists():
                    total_bytes += seg["path"].stat().st_size
                    valid_count += 1
            except Exception:
                pass

        return {
            "segment_count": valid_count,
            "buffered_duration_seconds": round(total_duration, 1),
            "size_mb": round(total_bytes / (1024 * 1024), 2)
        }

    def clear_all(self):
        """Limpa todos os arquivos do buffer"""
        for seg in self.segments:
            try:
                if seg["path"].exists():
                    seg["path"].unlink()
            except Exception:
                pass
        self.segments.clear()
