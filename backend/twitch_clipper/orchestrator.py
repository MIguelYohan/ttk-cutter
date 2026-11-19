import asyncio
import logging
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any

from . import config
from .twitch_chat_service import TwitchChatService
from .chat_activity_analyzer import ChatActivityAnalyzer
from .peak_detector import PeakDetector
from .stream_capture_service import StreamCaptureService
from .clip_extractor import ClipExtractor
from .transcription_client import TranscriptionClient

logger = logging.getLogger("TwitchClipperOrchestrator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class TwitchClipperOrchestrator:
    """
    Orquestrador completo que integra:
    1. Captura de Chat via EventSub
    2. Análise de Atividade e Detecção de Picos
    3. Captura Contínua de Vídeo (Streamlink + FFmpeg com Buffer Circular)
    4. Extração Assíncrona de Cortes [T-30s, T+30s]
    5. Despacho em Fila para a API de Transcrição Whisper
    """
    def __init__(self):
        self.channel = config.TWITCH_CHANNEL
        self.client_id = config.TWITCH_CLIENT_ID
        self.user_token = config.TWITCH_USER_TOKEN

        if not self.channel or not self.client_id or not self.user_token:
            raise ValueError("Configurações TWITCH_CHANNEL, TWITCH_CLIENT_ID e TWITCH_USER_TOKEN são obrigatórias no .env")

        # 1. Serviço de Captura de Vídeo e Buffer
        self.capture_service = StreamCaptureService(
            channel_name=self.channel,
            buffer_dir=config.BUFFER_DIR,
            max_buffer_seconds=600, # 10 minutos de histórico circular
            segment_duration=2.0
        )

        # 2. Extrator de Cortes
        self.extractor = ClipExtractor(
            video_buffer=self.capture_service.buffer,
            output_dir=config.CLIPS_DIR,
            clip_pre_seconds=config.CLIP_PRE_SECONDS,
            clip_post_seconds=config.CLIP_POST_SECONDS
        )

        # 3. Cliente da API de Transcrição Whisper
        self.transcription_client = TranscriptionClient(
            api_url=config.TRANSCRIBE_API_URL,
            model="base",
            language="pt",
            mode="short_video",
            max_words=3
        )

        # 4. Detector de Picos
        self.detector = PeakDetector(
            peak_multiplier=config.PEAK_MULTIPLIER,
            min_messages=config.MIN_PEAK_MESSAGES,
            cooldown_seconds=config.COOLDOWN_SECONDS,
            on_peak_detected=self._on_peak_detected
        )

        # 5. Analisador de Atividade
        self.analyzer = ChatActivityAnalyzer(
            window_seconds=config.WINDOW_SECONDS,
            baseline_windows=18,
            on_window_closed=self._on_window_closed
        )

        # 6. Serviço de Chat Twitch EventSub
        self.chat_service = TwitchChatService(
            client_id=self.client_id,
            user_token=self.user_token,
            channel_name=self.channel,
            on_message_callback=self._on_chat_message
        )

        self.is_running: bool = False

    def _on_chat_message(self, msg: Dict[str, Any]):
        self.analyzer.record_message(msg)

    def _on_window_closed(self, window: Dict[str, Any]):
        hora = time.strftime("%H:%M:%S", time.localtime(window["timestamp"]))
        count = window["message_count"]
        users = window["unique_users_count"]
        baseline = window["baseline_mean"]
        ratio = round(count / max(0.1, baseline), 1)

        # Estatísticas de vídeo no buffer
        stats = self.capture_service.get_buffer_stats()
        buf_dur = stats.get("buffered_duration_seconds", 0)

        peak_res = self.detector.process_window(window)
        if peak_res and not peak_res.get("is_ongoing", False):
            self.analyzer.mark_last_window_as_peak()
        elif peak_res and peak_res.get("is_ongoing", False):
            print(f"[{hora}] ↳ [Pico em andamento] Janela: {count:3d} msgs | Duração: {peak_res['duration_seconds']}s | Buffer vídeo: {buf_dur:.0f}s", flush=True)
        else:
            bar = "█" * min(20, int(ratio * 3))
            print(f"[{hora}] Chat 10s: {count:3d} msgs ({users:2d} users) | Mediana ref: {baseline:4.1f} (Ratio: {ratio:3.1f}x) | Buffer vídeo: {buf_dur:4.0f}s  {bar}", flush=True)

    def _on_peak_detected(self, peak_event: Dict[str, Any]):
        """Disparado quando um novo pico é detectado"""
        logger.info(
            f"\n" + "=" * 65 + "\n"
            f" 🔥 [ORQUESTRADOR] NOVO PICO DETECTADO NO CHAT!\n"
            f" Horário: {peak_event['formatted_time']} | Volume: {peak_event['message_count']} msgs ({peak_event['multiplier']}x a média normal)\n"
            f" Disparando extração do corte [{config.CLIP_PRE_SECONDS}s antes, +{config.CLIP_POST_SECONDS}s depois]...\n"
            + "=" * 65
        )

        # Executa a extração em thread separada para não travar o monitoramento do chat
        threading.Thread(target=self._process_peak_extraction, args=(peak_event,), daemon=True).start()

    def _process_peak_extraction(self, peak_event: Dict[str, Any]):
        try:
            clip_path = self.extractor.extract_clip(peak_event)
            if clip_path and clip_path.exists():
                logger.info(f"[Orquestrador] Enviando corte '{clip_path.name}' para a fila de transcrição...")
                self.transcription_client.enqueue_clip(clip_path, peak_event)
        except Exception as e:
            logger.error(f"[Orquestrador] Erro ao extrair e encaminhar corte: {e}")

    async def _tick_loop(self):
        while self.is_running:
            await asyncio.sleep(1)
            self.analyzer.check_tick()

    async def start(self):
        self.is_running = True
        logger.info("=" * 65)
        logger.info(f" INICIANDO SISTEMA COMPLETO DE DETECÇÃO AUTOMÁTICA DE CORTES")
        logger.info(f" Canal: '{self.channel}' | Pré: {config.CLIP_PRE_SECONDS}s | Pós: {config.CLIP_POST_SECONDS}s")
        logger.info("=" * 65)

        # Inicia captura de vídeo e cliente de transcrição
        self.capture_service.start()
        self.transcription_client.start()

        # Inicia loop de avanço de janelas do analisador
        asyncio.create_task(self._tick_loop())

        # Conecta ao WebSocket da Twitch
        await self.chat_service.connect()

    def stop(self):
        logger.info("[Orquestrador] Parando todos os serviços...")
        self.is_running = False
        self.chat_service.stop()
        self.capture_service.stop()
        self.transcription_client.stop()
