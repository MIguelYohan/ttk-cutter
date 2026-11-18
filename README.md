# TKK Subtitles & Auto Twitch Clipper

Aplicação web e sistema automatizado para:
1. **Geração de Legendas SRT (Interface Web React + Whisper)**.
2. **Auto Clipper de Lives da Twitch**: monitoramento do chat em tempo real via Twitch EventSub (WebSocket), detecção de anomalias/picos de mensagens, extração do buffer de vídeo com FFmpeg e transcrição automática em arquivos `.srt`.

---

## 🚀 Como Iniciar

### 1. Interface Web de Legendas (React + FastAPI)
Basta dar um duplo clique no arquivo:
```cmd
iniciar.bat
```
Acesse no navegador: `http://127.0.0.1:8000`

---

### 2. Auto Clipper da Twitch (Detecção Automática de Cortes)

Dê um duplo clique no arquivo:
```cmd
iniciar_clipper.bat
```
*(Ou execute no terminal: `.\venv\Scripts\python.exe run_clipper.py`)*

#### Como funciona o fluxo automático:
1. **Chat ao Vivo (Twitch EventSub):** Conecta via WebSocket oficial e escuta todas as mensagens sem delay.
2. **Analisador de Atividade:** Agrupa mensagens em blocos de 10 segundos e calcula a média móvel.
3. **Detector de Picos:** Quando o chat ultrapassa 3x a média normal (configurável), um novo momento interessante é registrado e entra em cooldown de 60s.
4. **Buffer Circular de Vídeo:** O Streamlink + FFmpeg gravam a transmissão continuamente em blocos leves de 2 segundos, descartando segmentos mais velhos que 10 minutos.
5. **Extrator de Cortes:** Aguarda os 30s posteriores ao pico, recupera os 30s anteriores no buffer e junta os blocos em um vídeo `.mp4` independente (ex: `corte_20261117_224530_4.2x.mp4`) dentro da pasta `extracted_clips/`.
6. **Integração com Whisper:** O vídeo é enviado para a rota `POST /api/transcribe` e gera automaticamente o arquivo de legendas `.srt` com o mesmo nome ao lado do vídeo!

---

## ⚙️ Configurações no arquivo `.env`

```env
# Credenciais da Twitch
TWITCH_CLIENT_ID=seu_client_id
TWITCH_USER_TOKEN=seu_user_token

# Canal a ser monitorado (altere para o streamer que quiser)
TWITCH_CHANNEL=tioorochitwitch

# Parâmetros de Detecção e Cortes
WINDOW_SECONDS=10       # Janela de contagem (10 segundos)
PEAK_MULTIPLIER=3.0     # Dispara quando chat for 3x maior que a média
COOLDOWN_SECONDS=60     # Intervalo mínimo entre cortes
CLIP_PRE_SECONDS=30     # Segundos gravados antes do pico
CLIP_POST_SECONDS=30    # Segundos gravados após o pico
```

---

## 🧪 Scripts de Validação Individual por Etapa

Para testar cada parte separadamente:
* **Etapa 1 (Conexão e Chat):** `.\venv\Scripts\python.exe test_chat_stage1.py`
* **Etapa 2 (Atividade e Picos):** `.\venv\Scripts\python.exe test_activity_stage2.py`
* **Etapa 3 (Captura e Buffer):** `.\venv\Scripts\python.exe test_capture_stage3.py`
* **Etapa 4 (Extração de Cortes):** `.\venv\Scripts\python.exe test_extract_stage4.py`
