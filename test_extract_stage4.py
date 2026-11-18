"""
Etapa 4: Teste da Extração de Cortes a partir do Buffer de Vídeo
Demonstra a recuperação de trechos [T - pre, T + post] e geração de arquivo .mp4 independente.
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# Adiciona diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.twitch_clipper import config
from backend.twitch_clipper.stream_capture_service import StreamCaptureService
from backend.twitch_clipper.clip_extractor import ClipExtractor

def main():
    print("=" * 65)
    print("      ETAPA 4 — TESTE DE EXTRAÇÃO DE CORTES (.MP4)")
    print("=" * 65)

    channel = config.TWITCH_CHANNEL
    if not channel:
        print("[ERRO] TWITCH_CHANNEL não configurado no .env.")
        return

    buffer_dir = config.BUFFER_DIR
    clips_dir = config.CLIPS_DIR

    print(f"\nCanal: '{channel}'")
    print(f"Diretório de buffer: '{buffer_dir}'")
    print(f"Diretório de cortes: '{clips_dir}'")
    print("\n1. Iniciando captura de vídeo temporária...")

    # Inicializa o serviço de captura
    capture_service = StreamCaptureService(
        channel_name=channel,
        buffer_dir=buffer_dir,
        max_buffer_seconds=300,
        segment_duration=2.0
    )
    capture_service.start()

    # Inicializa o extrator de cortes (para o teste rápido: 10s antes e 10s depois)
    pre_sec = 10
    post_sec = 10
    extractor = ClipExtractor(
        video_buffer=capture_service.buffer,
        output_dir=clips_dir,
        clip_pre_seconds=pre_sec,
        clip_post_seconds=post_sec
    )

    try:
        print(f"\n2. Aguardando buffer acumular {pre_sec + 4}s de histórico inicial...")
        for i in range(pre_sec + 4):
            time.sleep(1)
            stats = capture_service.get_buffer_stats()
            print(f"   [Buffer acumulado: {stats['buffered_duration_seconds']:.1f}s / {stats['segment_count']} segmentos]", end="\r")

        print("\n\n3. Simulando ocorrência de um PICO DE ATIVIDADE AGORA!")
        peak_time = time.time()
        simulated_peak = {
            "timestamp": peak_time,
            "formatted_time": datetime.fromtimestamp(peak_time).strftime("%H:%M:%S"),
            "multiplier": 4.5,
            "message_count": 80
        }

        print(f"   -> Horário do pico: {simulated_peak['formatted_time']}")
        print(f"   -> Intervalo solicitado: [{pre_sec}s antes, +{post_sec}s depois]")
        print("   -> Aguardando gravação dos próximos segundos e montagem do .mp4...\n")

        clip_path = extractor.extract_clip(simulated_peak)

        if clip_path and clip_path.exists():
            size_mb = clip_path.stat().st_size / (1024 * 1024)
            print("\n" + "=" * 65)
            print(" [✓] SUCESSO! Corte gerado e validado:")
            print(f"     Arquivo: {clip_path.resolve()}")
            print(f"     Tamanho: {size_mb:.2f} MB")
            print("=" * 65)
        else:
            print("\n[!] Falha ao gerar o corte.")

    finally:
        print("\nEncerrando captura...")
        capture_service.stop()

if __name__ == "__main__":
    main()
