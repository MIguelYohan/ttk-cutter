import time
import math
from collections import deque
from typing import Dict, Any, List, Optional, Callable

class ChatActivityAnalyzer:
    """
    Agrupa mensagens em janelas fixas de tempo (ex: 10s) e calcula a
    média de referência móvel (baseline), protegendo contra distorções causadas por picos.
    """
    def __init__(
        self,
        window_seconds: int = 10,
        baseline_windows: int = 18, # 18 janelas de 10s = 3 minutos de histórico
        on_window_closed: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.window_seconds = window_seconds
        self.baseline_windows = baseline_windows
        self.on_window_closed = on_window_closed

        # Janela de tempo atual
        self.current_window_start: float = time.time()
        self.current_window_messages: int = 0
        self.current_window_users: set = set()

        # Histórico recente de janelas para cálculo de linha de base (baseline)
        # Cada item: {"timestamp": float, "count": int, "is_peak": bool}
        self.history: deque = deque(maxlen=self.baseline_windows)

    def record_message(self, message: Dict[str, Any]):
        """Registra uma mensagem recebida"""
        msg_time = message.get("timestamp", time.time())
        user_id = message.get("chatter_user_id")

        # Se ultrapassou a janela atual, fecha as janelas pendentes
        while msg_time >= self.current_window_start + self.window_seconds:
            self._close_current_window()

        self.current_window_messages += 1
        if user_id:
            self.current_window_users.add(user_id)

    def check_tick(self):
        """
        Pode ser chamado periodicamente por um timer caso não cheguem mensagens
        durante uma janela (chat lento).
        """
        now = time.time()
        while now >= self.current_window_start + self.window_seconds:
            self._close_current_window()

    def get_baseline_mean(self) -> float:
        """
        Calcula a média de referência móvel.
        Para evitar que picos anteriores distorçam a média, janelas marcadas
        como 'is_peak' são desconsideradas ou atenuadas no cálculo.
        """
        if not self.history:
            return 1.0

        # Filtra apenas janelas normais (sem picos)
        normal_counts = [w["count"] for w in self.history if not w.get("is_peak", False)]
        
        # Se todas forem picos ou histórico muito curto, usa a mediana geral
        if not normal_counts:
            all_counts = sorted([w["count"] for w in self.history])
            median = all_counts[len(all_counts) // 2]
            return max(1.0, float(median))

        return max(1.0, float(sum(normal_counts) / len(normal_counts)))

    def mark_last_window_as_peak(self):
        """Marca a última janela fechada como pico para não inflar a média móvel futura"""
        if self.history:
            self.history[-1]["is_peak"] = True

    def _close_current_window(self):
        window_end = self.current_window_start + self.window_seconds
        baseline = self.get_baseline_mean()

        window_data = {
            "start_time": self.current_window_start,
            "end_time": window_end,
            "timestamp": window_end,
            "message_count": self.current_window_messages,
            "unique_users_count": len(self.current_window_users),
            "baseline_mean": round(baseline, 2),
            "is_peak": False
        }

        # Armazena no histórico
        self.history.append({
            "timestamp": window_end,
            "count": self.current_window_messages,
            "is_peak": False
        })

        # Notifica callback
        if self.on_window_closed:
            self.on_window_closed(window_data)

        # Avança para a próxima janela
        self.current_window_start += self.window_seconds
        self.current_window_messages = 0
        self.current_window_users = set()
