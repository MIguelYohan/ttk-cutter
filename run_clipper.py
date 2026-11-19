"""
Ponto de entrada do sistema de detecção e extração automática de cortes da Twitch.
Monitora a live e o chat em tempo real, detecta momentos de pico, extrai os vídeos
e envia automaticamente para a API Whisper gerar as legendas SRT.
"""
import asyncio
import os
import sys

# Adiciona diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.twitch_clipper.orchestrator import TwitchClipperOrchestrator

async def main():
    try:
        orchestrator = TwitchClipperOrchestrator()
    except Exception as e:
        print(f"\n[ERRO DE CONFIGURAÇÃO] {e}")
        print("Verifique se seu arquivo .env contém TWITCH_CHANNEL, TWITCH_CLIENT_ID e TWITCH_USER_TOKEN.")
        return

    try:
        await orchestrator.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n[Encerrando sistema a pedido do usuário...]")
    finally:
        orchestrator.stop()

if __name__ == "__main__":
    asyncio.run(main())
