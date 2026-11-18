"""
Etapa 2: Teste do Analisador de Atividade e Detector de Picos em Tempo Real
Mede o fluxo do chat em janelas de 10s, calcula a média móvel de referência
e emite alertas de picos com controle de cooldown.
"""
import asyncio
import os
import sys
import time
from datetime import datetime

# Adiciona diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.twitch_clipper import config
from backend.twitch_clipper.twitch_chat_service import TwitchChatService
from backend.twitch_clipper.chat_activity_analyzer import ChatActivityAnalyzer
from backend.twitch_clipper.peak_detector import PeakDetector

analyzer = None
detector = None

def on_peak(peak: dict):
    print("\n" + "=" * 65)
    print(f" 🔥 PICO DETECTADO! Horário: {peak['formatted_time']}")
    print(f"    Msgs na Janela: {peak['message_count']} msgs")
    print(f"    Média de Referência: {peak['baseline_mean']} msgs")
    print(f"    Aumento: {peak['multiplier']}x da média normal!")
    print(f"    [Candidato a Corte gerado] Cooldown ativo por {config.COOLDOWN_SECONDS}s")
    print("=" * 65 + "\n")

def on_window_closed(window: dict):
    global analyzer, detector
    hora = datetime.fromtimestamp(window["timestamp"]).strftime("%H:%M:%S")
    count = window["message_count"]
    users = window["unique_users_count"]
    baseline = window["baseline_mean"]
    ratio = round(count / max(0.1, baseline), 1)

    # Processa com o detector de picos
    peak_res = detector.process_window(window)

    if peak_res and not peak_res.get("is_ongoing", False):
        # Protege o histórico para que este pico não infle as próximas médias
        analyzer.mark_last_window_as_peak()
    elif peak_res and peak_res.get("is_ongoing", False):
        print(f"[{hora}] ↳ [Pico Contínuo] Janela: {count:3d} msgs | Duração acumulada: {peak_res['duration_seconds']}s")
    else:
        # Exibição normal
        bar_len = min(30, int(ratio * 5))
        bar = "█" * bar_len
        print(f"[{hora}] Janela 10s: {count:3d} msgs ({users:2d} users) | Média ref: {baseline:4.1f} | Ratio: {ratio:3.1f}x  {bar}")

def on_chat_message(msg: dict):
    if analyzer:
        analyzer.record_message(msg)

async def tick_loop():
    """Garante que janelas de tempo continuem avançando a cada segundo mesmo sem novas mensagens"""
    while True:
        await asyncio.sleep(1)
        if analyzer:
            analyzer.check_tick()

async def main():
    global analyzer, detector
    print("=" * 65)
    print(" ETAPA 2 — ANALISADOR DE ATIVIDADE & DETECTOR DE PICOS NO CHAT")
    print("=" * 65)

    client_id = config.TWITCH_CLIENT_ID
    user_token = config.TWITCH_USER_TOKEN
    channel = config.TWITCH_CHANNEL

    if not client_id or not user_token or not channel:
        print("[ERRO] Configure TWITCH_CLIENT_ID, TWITCH_USER_TOKEN e TWITCH_CHANNEL no .env.")
        return

    print(f"Canal: '{channel}' | Janela: {config.WINDOW_SECONDS}s | Limiar de Pico: {config.PEAK_MULTIPLIER}x | Cooldown: {config.COOLDOWN_SECONDS}s\n")
    print("Calculando linha de base... Acompanhe as janelas de 10s abaixo:")
    print("-" * 65)

    analyzer = ChatActivityAnalyzer(
        window_seconds=config.WINDOW_SECONDS,
        baseline_windows=18, # 3 minutos de histórico de referência
        on_window_closed=on_window_closed
    )

    detector = PeakDetector(
        peak_multiplier=config.PEAK_MULTIPLIER,
        min_messages=5,
        cooldown_seconds=config.COOLDOWN_SECONDS,
        on_peak_detected=on_peak
    )

    service = TwitchChatService(
        client_id=client_id,
        user_token=user_token,
        channel_name=channel,
        on_message_callback=on_chat_message
    )

    # Inicia o loop de ticks em paralelo com o WebSocket
    asyncio.create_task(tick_loop())

    try:
        await service.connect()
    except KeyboardInterrupt:
        print("\n[Encerrando análise a pedido do usuário...]")
        service.stop()

if __name__ == "__main__":
    asyncio.run(main())
