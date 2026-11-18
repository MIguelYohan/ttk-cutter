import asyncio
import json
import logging
import time
from collections import deque
from typing import Callable, Optional, Dict, Any, List
import requests
import websockets

from .twitch_auth import TwitchAuthHelper

logger = logging.getLogger("TwitchChatService")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

EVENTSUB_WS_URL = "wss://eventsub.wss.twitch.tv/ws"
SUBSCRIPTION_URL = "https://api.twitch.tv/helix/eventsub/subscriptions"

class TwitchChatService:
    def __init__(
        self,
        client_id: str,
        user_token: str,
        channel_name: str,
        on_message_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.client_id = client_id.strip()
        self.user_token = user_token.replace("oauth:", "").strip()
        self.channel_name = channel_name.strip().lower()
        self.on_message_callback = on_message_callback

        self.auth_helper = TwitchAuthHelper(self.client_id, self.user_token)
        self.user_id: Optional[str] = None
        self.broadcaster_id: Optional[str] = None
        
        self.session_id: Optional[str] = None
        self.ws_url: str = EVENTSUB_WS_URL
        self.is_running: bool = False
        self._ws = None

        # Desduplicação de mensagens (armazena os últimos 2000 IDs em memória)
        self._seen_messages = deque(maxlen=2000)
        self._seen_set = set()

    def _is_duplicate(self, message_id: str) -> bool:
        if not message_id:
            return False
        if message_id in self._seen_set:
            return True
        if len(self._seen_messages) == self._seen_messages.maxlen:
            oldest = self._seen_messages.popleft()
            self._seen_set.discard(oldest)
        self._seen_messages.append(message_id)
        self._seen_set.add(message_id)
        return False

    def initialize_auth(self):
        """Valida token e resolve IDs numéricos necessários da Twitch"""
        logger.info("[TwitchChatService] Validando credenciais e permissões OAuth...")
        token_data = self.auth_helper.validate_token()
        self.user_id = token_data.get("user_id")
        user_login = token_data.get("login")
        logger.info(f"[TwitchChatService] Autenticado como usuário '{user_login}' (ID: {self.user_id})")

        logger.info(f"[TwitchChatService] Resolvendo ID do canal alvo '{self.channel_name}'...")
        self.broadcaster_id = self.auth_helper.get_user_id(self.channel_name)
        logger.info(f"[TwitchChatService] Canal alvo '{self.channel_name}' possui ID: {self.broadcaster_id}")

    def subscribe_to_chat(self, session_id: str):
        """Cria a subscrição no EventSub para o evento channel.chat.message"""
        headers = {
            "Client-Id": self.client_id,
            "Authorization": f"Bearer {self.user_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "type": "channel.chat.message",
            "version": "1",
            "condition": {
                "broadcaster_user_id": self.broadcaster_id,
                "user_id": self.user_id
            },
            "transport": {
                "method": "websocket",
                "session_id": session_id
            }
        }
        logger.info(f"[TwitchChatService] Registrando subscrição channel.chat.message com session_id: {session_id}...")
        resp = requests.post(SUBSCRIPTION_URL, headers=headers, json=payload, timeout=10)
        
        if resp.status_code in (200, 202):
            logger.info("[TwitchChatService] [OK] Subscrição ativa no chat da Twitch com sucesso!")
        elif resp.status_code == 409:
            logger.info("[TwitchChatService] Subscrição já existente para esta sessão.")
        else:
            raise RuntimeError(f"Erro ao criar subscrição ({resp.status_code}): {resp.text}")

    async def connect(self):
        """Loop principal de conexão e reconexão WebSocket"""
        self.initialize_auth()
        self.is_running = True

        retry_delay = 2
        while self.is_running:
            try:
                logger.info(f"[TwitchChatService] Conectando a {self.ws_url}...")
                async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=15) as ws:
                    self._ws = ws
                    retry_delay = 2 # reset backoff
                    logger.info("[TwitchChatService] Conexão WebSocket estabelecida.")

                    async for raw_message in ws:
                        if not self.is_running:
                            break
                        await self._handle_ws_message(raw_message)

            except (websockets.ConnectionClosed, websockets.WebSocketException) as e:
                logger.warning(f"[TwitchChatService] Conexão perdida: {e}. Reconectando em {retry_delay}s...")
                self.ws_url = EVENTSUB_WS_URL
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
            except Exception as e:
                logger.error(f"[TwitchChatService] Erro inesperado: {e}. Reconectando em {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

    async def _handle_ws_message(self, raw_message: str):
        try:
            data = json.loads(raw_message)
            metadata = data.get("metadata", {})
            msg_type = metadata.get("message_type")
            payload = data.get("payload", {})

            if msg_type == "session_welcome":
                session = payload.get("session", {})
                self.session_id = session.get("id")
                logger.info(f"[TwitchChatService] Sessão WebSocket recebida. ID: {self.session_id}")
                # Registra o evento de chat
                self.subscribe_to_chat(self.session_id)

            elif msg_type == "session_keepalive":
                # Heartbeat regular da Twitch
                pass

            elif msg_type == "session_reconnect":
                reconnect_url = payload.get("session", {}).get("reconnect_url")
                if reconnect_url:
                    logger.info(f"[TwitchChatService] Recebido session_reconnect. Nova URL: {reconnect_url}")
                    self.ws_url = reconnect_url
                    if self._ws:
                        await self._ws.close()

            elif msg_type == "notification":
                sub_type = metadata.get("subscription_type")
                if sub_type == "channel.chat.message":
                    event = payload.get("event", {})
                    msg_id = event.get("message_id")
                    
                    if self._is_duplicate(msg_id):
                        return

                    chat_info = {
                        "message_id": msg_id,
                        "timestamp": time.time(),
                        "chatter_user_name": event.get("chatter_user_name"),
                        "chatter_user_login": event.get("chatter_user_login"),
                        "chatter_user_id": event.get("chatter_user_id"),
                        "text": event.get("message", {}).get("text", "")
                    }

                    if self.on_message_callback:
                        if asyncio.iscoroutinefunction(self.on_message_callback):
                            await self.on_message_callback(chat_info)
                        else:
                            self.on_message_callback(chat_info)

            elif msg_type == "revocation":
                logger.warning(f"[TwitchChatService] Subscrição revogada pela Twitch: {payload}")

        except Exception as e:
            logger.error(f"[TwitchChatService] Erro ao processar mensagem do WebSocket: {e}")

    def stop(self):
        """Para a conexão de forma graciosa"""
        self.is_running = False
