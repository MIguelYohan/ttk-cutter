"""
Etapa 3: Teste da Captura Contínua com Streamlink + FFmpeg e Buffer Circular
Grava a live em segmentos de 2 segundos e descarta automaticamente os segmentos mais antigos.
"""
import os
import sys
import time
from datetime import datetime

# Adiciona diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.twitch_clipper import config
from backend.twitch_clipper.stream_capture_service import StreamCaptureService

def main():
    print("=" * 65)
    print(" ETAPA 3 — CAPTURA CONTÍNUA COM BUFFER CIRCULAR (STREAMLINK + FFMPEG)")
    print("=" * 65)

    channel = config.TWITCH_CHANNEL
    if not channel:
        print("[ERRO] TWITCH_CHANNEL não configurado no .env.")
        return

    buffer_dir = config.BUFFER_DIR
    print(f"\nCanal alvo: '{channel}'")
    print(f"Diretório do buffer temporário: '{buffer_dir}'")
    print(f"Tamanho do buffer para este teste: 60 segundos (demonstra o descarte automático)")
    print("\nIniciando captura... Pressione Ctrl+C para encerrar o teste a qualquer momento.\n")

    # Inicia captura com buffer limitado a 60 segundos para teste visível
    service = StreamCaptureService(
        channel_name=channel,
        buffer_dir=buffer_dir,
        quality="720p60,720p,480p,best",
        max_buffer_seconds=60, # 60s para demonstração rápida do descarte circular
        segment_duration=2.0
    )

    service.start()

    try:
        while True:
            time.sleep(4)
            stats = service.get_buffer_stats()
            seg_count = stats["segment_count"]
            dur = stats["buffered_duration_seconds"]
            size_mb = stats["size_mb"]

            hora = datetime.now().strftime("%H:%M:%S")
            print(f"[{hora}] 📹 Buffer: {seg_count:2d} segmentos | Duração em cache: {dur:4.1f}s | Espaço em disco: {size_mb:5.2f} MB", flush=True)

    except KeyboardInterrupt:
        print("\n[Encerrando captura...]")
        service.stop()
        print(f"[OK] Teste finalizado com sucesso. Segmentos gravados em '{buffer_dir}'.")

if __name__ == "__main__":
    main()
