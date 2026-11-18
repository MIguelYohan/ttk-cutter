"""
Etapa 1: Validação da Conexão com o Twitch EventSub (WebSocket)
Monitora o chat ao vivo e exibe estatísticas em tempo real no terminal.
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

total_messages = 0
start_time = time.time()

def on_chat_message(msg: dict):
    global total_messages
    total_messages += 1
    
    elapsed = max(1, time.time() - start_time)
    msg_rate = (total_messages / elapsed) * 60 # msgs por minuto
    
    hora = datetime.fromtimestamp(msg["timestamp"]).strftime("%H:%M:%S")
    chatter = msg["chatter_user_name"]
    text = msg["text"]
    
    # Exibe no terminal
    print(f"[{hora}] ({total_messages:04d} msgs | ~{msg_rate:.1f} m/min) {chatter}: {text}")

async def main():
    print("=" * 65)
    print("      ETAPA 1 — TESTE DO TWITCH EVENTSUB (WEBSOCKET)")
    print("=" * 65)

    client_id = config.TWITCH_CLIENT_ID
    user_token = config.TWITCH_USER_TOKEN
    channel = config.TWITCH_CHANNEL

    if not client_id or not user_token or not channel:
        print("\n[!] Atenção: Credenciais não encontradas no arquivo '.env'.")
        print("\nPara configurar rapidamente:")
        print("1. Abra o arquivo '.env' e insira seu TWITCH_CLIENT_ID e TWITCH_USER_TOKEN.")
        print("   OU execute: python get_twitch_token.py")
        print("2. Defina o TWITCH_CHANNEL para o canal que estiver ao vivo agora (ex: gaules).")
        return

    print(f"\nCanal alvo: '{channel}'")
    print(f"Client ID: {client_id[:6]}... (ocultado)")
    print("Pressione Ctrl+C para encerrar o teste a qualquer momento.\n")

    service = TwitchChatService(
        client_id=client_id,
        user_token=user_token,
        channel_name=channel,
        on_message_callback=on_chat_message
    )

    try:
        await service.connect()
    except KeyboardInterrupt:
        print("\n[Encerrando teste a pedido do usuário...]")
        service.stop()

if __name__ == "__main__":
    asyncio.run(main())
