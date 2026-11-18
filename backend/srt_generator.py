import os
import torch
import whisper
from typing import List, Dict, Any, Optional

# Cache for loaded models: { (model_name, device): model_instance }
_LOADED_MODELS: Dict[tuple, Any] = {}

AVAILABLE_MODELS = [
    {"id": "tiny", "name": "Tiny (~39M)", "desc": "Ultrarrápido, menor precisão. Bom para testes rápidos.", "vram": "~1 GB"},
    {"id": "base", "name": "Base (~74M) [Recomendado]", "desc": "Equilíbrio ideal entre velocidade e qualidade para vídeos curtos.", "vram": "~1 GB"},
    {"id": "small", "name": "Small (~244M)", "desc": "Boa precisão, um pouco mais pesado.", "vram": "~2 GB"},
    {"id": "medium", "name": "Medium (~769M)", "desc": "Alta precisão para vocabulário complexo.", "vram": "~5 GB"},
    {"id": "turbo", "name": "Turbo / Large-v3-Turbo (~809M)", "desc": "Excelente precisão com velocidade otimizada.", "vram": "~6 GB"},
    {"id": "large", "name": "Large-v3 (~1550M)", "desc": "Precisão máxima, requer GPU potente ou bastante CPU/tempo.", "vram": "~10 GB"}
]

def get_system_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"

def get_loaded_model(model_name: str = "base", device: Optional[str] = None):
    if not device:
        device = get_system_device()
    
    key = (model_name, device)
    if key not in _LOADED_MODELS:
        print(f"[*] Carregando modelo Whisper '{model_name}' no dispositivo '{device}'...")
        # whisper.load_model downloads weights to ~/.cache/whisper if not cached
        model = whisper.load_model(model_name, device=device)
        _LOADED_MODELS[key] = model
        print(f"[✓] Modelo '{model_name}' carregado com sucesso.")
    return _LOADED_MODELS[key]

def format_timestamp(seconds: float) -> str:
    """Converte segundos em formato SRT HH:MM:SS,mmm"""
    millis = int(round(seconds * 1000))
    hours = millis // 3600000
    millis %= 3600000
    minutes = millis // 60000
    millis %= 60000
    secs = millis // 1000
    millis %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def generate_srt_from_segments(segments: List[Dict[str, Any]]) -> str:
    """Gera string no formato SRT a partir de uma lista de segmentos"""
    srt_lines = []
    for idx, seg in enumerate(segments, start=1):
        start_ts = format_timestamp(seg["start"])
        end_ts = format_timestamp(seg["end"])
        text = seg["text"].strip()
        srt_lines.append(f"{idx}\n{start_ts} --> {end_ts}\n{text}\n")
    return "\n".join(srt_lines)

def group_words_into_short_segments(raw_segments: List[Dict[str, Any]], max_words: int = 3) -> List[Dict[str, Any]]:
    """
    Agrupa palavras individuais em blocos curtos (1 a N palavras),
    estilo legendas dinâmicas de Reels/TikTok/Shorts.
    """
    words_all = []
    for seg in raw_segments:
        if "words" in seg and seg["words"]:
            for w in seg["words"]:
                clean_word = w.get("word", "").strip()
                if clean_word:
                    words_all.append({
                        "word": clean_word,
                        "start": w.get("start", seg.get("start", 0)),
                        "end": w.get("end", seg.get("end", 0))
                    })
        else:
            # Fallback caso não venha word_timestamps: divide por palavras aproximando tempo
            words = seg["text"].strip().split()
            if not words:
                continue
            seg_start = seg["start"]
            seg_end = seg["end"]
            duration = max(0.1, seg_end - seg_start)
            word_dur = duration / len(words)
            for i, w in enumerate(words):
                w_start = seg_start + (i * word_dur)
                w_end = min(seg_end, w_start + word_dur)
                words_all.append({
                    "word": w,
                    "start": round(w_start, 3),
                    "end": round(w_end, 3)
                })

    if not words_all:
        return []

    # Agrupa em chunks de max_words
    result_segments = []
    chunk = []
    for w in words_all:
        chunk.append(w)
        if len(chunk) >= max_words:
            start_time = chunk[0]["start"]
            end_time = chunk[-1]["end"]
            if end_time <= start_time:
                end_time = start_time + 0.3
            text = " ".join([cw["word"] for cw in chunk])
            result_segments.append({
                "id": len(result_segments) + 1,
                "start": round(start_time, 3),
                "end": round(end_time, 3),
                "text": text
            })
            chunk = []

    # Restante
    if chunk:
        start_time = chunk[0]["start"]
        end_time = chunk[-1]["end"]
        if end_time <= start_time:
            end_time = start_time + 0.3
        text = " ".join([cw["word"] for cw in chunk])
        result_segments.append({
            "id": len(result_segments) + 1,
            "start": round(start_time, 3),
            "end": round(end_time, 3),
            "text": text
        })

    return result_segments

def transcribe_media(
    file_path: str,
    model_name: str = "base",
    language: Optional[str] = None,
    mode: str = "short_video", # "standard" or "short_video"
    max_words_per_line: int = 3,
    device: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executa a transcrição completa de um arquivo de áudio ou vídeo.
    Retorna srt_content, segments, language_detected, etc.
    """
    model = get_loaded_model(model_name=model_name, device=device)
    
    # Se language for 'auto' ou None, deixa o Whisper detectar
    lang_param = None if (not language or language.lower() == "auto") else language.lower()

    # Opções do whisper
    actual_device = model.device.type
    transcribe_options = {
        "task": "transcribe",
        "verbose": False,
        "word_timestamps": True,  # Permite alinhamento fino por palavra
        "fp16": (actual_device == "cuda")
    }
    if lang_param:
        transcribe_options["language"] = lang_param

    print(f"[*] Iniciando transcrição com modelo '{model_name}' (língua: {lang_param or 'auto'})...")
    result = model.transcribe(file_path, **transcribe_options)
    detected_lang = result.get("language", "pt")
    raw_segments = result.get("segments", [])

    if mode == "short_video":
        final_segments = group_words_into_short_segments(raw_segments, max_words=max_words_per_line)
    else:
        # Modo standard: usa frases completas do Whisper
        final_segments = []
        for idx, seg in enumerate(raw_segments, start=1):
            final_segments.append({
                "id": idx,
                "start": round(seg["start"], 3),
                "end": round(seg["end"], 3),
                "text": seg["text"].strip()
            })

    srt_text = generate_srt_from_segments(final_segments)

    return {
        "language": detected_lang,
        "mode": mode,
        "model_used": model_name,
        "segments": final_segments,
        "srt_content": srt_text,
        "total_segments": len(final_segments)
    }
