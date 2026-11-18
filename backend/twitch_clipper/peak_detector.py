import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict

@dataclass
class PeakEvent:
    timestamp: float           # Timestamp (epoch) do pico
    formatted_time: str        # Horário legível HH:MM:SS
    message_count: int         # Quantidade de mensagens na janela
    baseline_mean: float       # Média de referência recente
    multiplier: float          # Multiplicador (ex: 3.5x)
    duration_seconds: int      # Duração acumulada do pico
    is_ongoing: bool           # Se o pico ainda está ativo dentro do cooldown

class PeakDetector:
    def __init__(
        self,
        peak_multiplier: float = 3.0,
        min_messages: int = 5,
        cooldown_seconds: int = 60,
        min_history_windows: int = 3,
        on_peak_detected: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.peak_multiplier = peak_multiplier
        self.min_messages = min_messages
        self.cooldown_seconds = cooldown_seconds
        self.min_history_windows = min_history_windows
        self.on_peak_detected = on_peak_detected

        self.windows_processed: int = 0
        self.last_peak_time: float = 0
        self.active_peak_start_time: float = 0
        self.is_in_peak_state: bool = False

    def process_window(self, window_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analisa uma janela de 10 segundos recém-fechada.
        Retorna os dados do pico se detectado, ou None.
        """
        self.windows_processed += 1
        count = window_data["message_count"]
        baseline = window_data["baseline_mean"]
        timestamp = window_data["timestamp"]
        multiplier = round(count / max(0.1, baseline), 2)

        # Durante o warm-up (primeiras janelas), apenas aprende a média normal sem disparar alertas
        if self.windows_processed <= self.min_history_windows:
            return None

        # Verifica se atinge os critérios numéricos de pico
        is_spike = (count >= self.min_messages) and (multiplier >= self.peak_multiplier)

        now = timestamp
        time_since_last_peak = now - self.last_peak_time

        # Se for um pico e já passou o período de cooldown: PICO NOVO!
        if is_spike and (time_since_last_peak >= self.cooldown_seconds):
            self.last_peak_time = now
            self.active_peak_start_time = window_data.get("start_time", now)
            self.is_in_peak_state = True

            peak = PeakEvent(
                timestamp=now,
                formatted_time=time.strftime("%H:%M:%S", time.localtime(now)),
                message_count=count,
                baseline_mean=baseline,
                multiplier=multiplier,
                duration_seconds=int(window_data.get("end_time", now) - self.active_peak_start_time),
                is_ongoing=False
            )
            peak_dict = asdict(peak)

            if self.on_peak_detected:
                self.on_peak_detected(peak_dict)

            return peak_dict

        # Se ainda está em cooldown mas continua com atividade alta: estende a duração do pico ativo
        elif is_spike and (time_since_last_peak < self.cooldown_seconds):
            duration = int(window_data.get("end_time", now) - self.active_peak_start_time)
            # Não dispara novo alerta para não duplicar corte, apenas acompanha
            return {
                "timestamp": now,
                "is_ongoing": True,
                "duration_seconds": duration,
                "message_count": count
            }

        # Atividade voltou ao normal
        if time_since_last_peak >= self.cooldown_seconds:
            self.is_in_peak_state = False

        return None
