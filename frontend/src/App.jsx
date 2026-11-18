import React, { useState, useEffect, useRef } from 'react'
import {
  FileVideo,
  Upload,
  Cpu,
  Zap,
  Play,
  Pause,
  Download,
  Copy,
  Check,
  Clock,
  Sparkles,
  Settings2,
  Trash2,
  FileText,
  AlertCircle
} from 'lucide-react'
import './App.css'

export default function App() {
  const [systemInfo, setSystemInfo] = useState({
    device: 'cpu',
    device_name: 'Processador (CPU)',
    default_model: 'base',
    models: [],
    languages: []
  })
  const [isBackendOnline, setIsBackendOnline] = useState(false)

  // Form states
  const [selectedFile, setSelectedFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [selectedModel, setSelectedModel] = useState('base')
  const [selectedLanguage, setSelectedLanguage] = useState('pt')
  const [mode, setMode] = useState('short_video') // 'short_video' ou 'standard'
  const [maxWords, setMaxWords] = useState(3)

  // Execution states
  const [loading, setLoading] = useState(false)
  const [loadingTimer, setLoadingTimer] = useState(0)
  const [result, setResult] = useState(null)
  const [activeTab, setActiveTab] = useState('segments') // 'segments' ou 'srt'
  const [toastMessage, setToastMessage] = useState(null)

  // Video playback sync
  const videoRef = useRef(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const fileInputRef = useRef(null)

  // Fetch system info on mount
  useEffect(() => {
    fetch('/api/info')
      .then(res => res.json())
      .then(data => {
        setSystemInfo(data)
        setIsBackendOnline(true)
        if (data.default_model) {
          setSelectedModel(data.default_model)
        }
      })
      .catch(err => {
        console.warn('API backend não acessível ainda:', err)
        setIsBackendOnline(false)
      })
  }, [])

  // Timer while transcribing
  useEffect(() => {
    let interval = null
    if (loading) {
      setLoadingTimer(0)
      interval = setInterval(() => {
        setLoadingTimer(t => t + 1)
      }, 1000)
    } else {
      clearInterval(interval)
    }
    return () => clearInterval(interval)
  }, [loading])

  // Toast auto-hide
  const showToast = (msg) => {
    setToastMessage(msg)
    setTimeout(() => setToastMessage(null), 3000)
  }

  // Handle file select
  const handleFileChange = (file) => {
    if (!file) return
    setSelectedFile(file)
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
    }
    const url = URL.createObjectURL(file)
    setPreviewUrl(url)
    setResult(null)
  }

  // Handle Drag & Drop
  const onDragOver = (e) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const onDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0])
    }
  }

  // Handle Transcribe Submission
  const handleTranscribe = async () => {
    if (!selectedFile) {
      showToast('Por favor, selecione um arquivo de vídeo ou áudio.')
      return
    }

    setLoading(true)
    const formData = new FormData()
    formData.append('file', selectedFile)
    formData.append('model', selectedModel)
    formData.append('language', selectedLanguage)
    formData.append('mode', mode)
    formData.append('max_words', maxWords)

    try {
      const response = await fetch('/api/transcribe', {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || 'Falha ao processar arquivo.')
      }

      const data = await response.json()
      setResult(data)
      showToast(`Legendas geradas com sucesso em ${data.processing_time_seconds}s!`)
    } catch (error) {
      console.error(error)
      alert(`Erro: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  // Segment editing
  const handleSegmentChange = (index, newText) => {
    if (!result || !result.segments) return
    const updated = [...result.segments]
    updated[index].text = newText

    // Recalcula SRT em texto
    const updatedSrt = updated
      .map((seg, i) => {
        const formatTime = (sec) => {
          const ms = Math.round(sec * 1000)
          const h = Math.floor(ms / 3600000)
          const m = Math.floor((ms % 3600000) / 60000)
          const s = Math.floor((ms % 60000) / 1000)
          const remMs = ms % 1000
          const pad = (n, len = 2) => String(n).padStart(len, '0')
          return `${pad(h)}:${pad(m)}:${pad(s)},${pad(remMs, 3)}`
        }
        return `${i + 1}\n${formatTime(seg.start)} --> ${formatTime(seg.end)}\n${seg.text.trim()}\n`
      })
      .join('\n')

    setResult({
      ...result,
      segments: updated,
      srt_content: updatedSrt
    })
  }

  const handleDeleteSegment = (index) => {
    if (!result || !result.segments) return
    const updated = result.segments.filter((_, i) => i !== index)
    setResult({
      ...result,
      segments: updated
    })
  }

  // Video Time Update
  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime)
    }
  }

  const handleSeek = (seconds) => {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds
      videoRef.current.play()
      setIsPlaying(true)
    }
  }

  // Find active subtitle for video overlay
  const activeSegment = result?.segments?.find(
    (seg) => currentTime >= seg.start && currentTime <= seg.end
  )

  // Download SRT
  const handleDownloadSrt = () => {
    if (!result?.srt_content) return
    const blob = new Blob([result.srt_content], { type: 'text/plain;charset=utf-8' })
    const baseName = selectedFile?.name?.replace(/\.[^/.]+$/, '') || 'legendas'
    const fileName = `${baseName}.srt`

    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    showToast(`Arquivo ${fileName} baixado!`)
  }

  // Copy SRT
  const handleCopySrt = () => {
    if (!result?.srt_content) return
    navigator.clipboard.writeText(result.srt_content)
    showToast('SRT copiado para a área de transferência!')
  }

  // Selected Model metadata
  const currentModelMeta = systemInfo.models.find(m => m.id === selectedModel)

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-content">
          <div className="logo-area">
            <div className="logo-icon-wrapper">
              <FileVideo size={24} />
            </div>
            <div>
              <h1 className="logo-title">TKK Subtitles</h1>
              <p className="logo-subtitle">Gerador de Legendas SRT para Vídeos Curtos (Whisper)</p>
            </div>
          </div>

          <div className="header-badges">
            <div className="badge badge-hardware" title={systemInfo.device_name}>
              <Cpu size={14} />
              <span>{systemInfo.device === 'cuda' ? 'GPU (CUDA)' : 'CPU'}</span>
            </div>

            <div className={`badge ${isBackendOnline ? 'badge-online' : 'badge-offline'}`}>
              <div className="pulse-dot"></div>
              <span>{isBackendOnline ? 'Whisper Pronto' : 'Desconectado'}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Layout */}
      <main className="main-layout">
        {/* Left Side: Configuration & Upload Panel */}
        <section className="card-panel">
          <h2 className="panel-title">
            <Settings2 size={18} />
            Configuração da Transcrição
          </h2>

          {/* Upload Dropzone */}
          <div
            className="dropzone"
            onDragOver={onDragOver}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: 'none' }}
              accept="video/*,audio/*,.mp4,.mov,.mkv,.avi,.mp3,.wav,.m4a"
              onChange={(e) => handleFileChange(e.target.files?.[0])}
            />
            <Upload className="dropzone-icon" />
            <div className="dropzone-text">Arraste ou clique para selecionar o vídeo</div>
            <div className="dropzone-hint">Suporta MP4, MOV, MKV, MP3, WAV, etc.</div>
          </div>

          {/* File Selected Badge */}
          {selectedFile && (
            <div className="file-selected-box">
              <div className="file-info">
                <FileVideo size={20} color="#818cf8" />
                <div>
                  <div className="file-name" title={selectedFile.name}>{selectedFile.name}</div>
                  <div className="file-meta">
                    {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • {selectedFile.type || 'Mídia'}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Whisper Model Selector */}
          <div className="form-group">
            <label className="form-label">
              <span>Modelo Whisper</span>
              <span style={{ fontSize: '0.72rem', color: '#818cf8' }}>Ajuste conforme seu hardware</span>
            </label>
            <select
              className="select-input"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
            >
              {systemInfo.models.map(m => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
            {currentModelMeta && (
              <div className="model-desc-box">
                <span>{currentModelMeta.desc}</span>
                <span className="model-vram-tag">{currentModelMeta.vram}</span>
              </div>
            )}
          </div>

          {/* Language Selector */}
          <div className="form-group">
            <label className="form-label">Idioma do Áudio</label>
            <select
              className="select-input"
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value)}
            >
              {systemInfo.languages.map(l => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>

          {/* Mode Selector: Short Video vs Standard */}
          <div className="form-group">
            <label className="form-label">Estilo de Legenda</label>
            <div className="mode-selector">
              <div
                className={`mode-card ${mode === 'short_video' ? 'selected' : ''}`}
                onClick={() => setMode('short_video')}
              >
                <div className="mode-card-title">
                  <Sparkles size={16} color="#818cf8" />
                  <span>Reels / TikTok</span>
                </div>
                <div className="mode-card-desc">Blocos curtos e dinâmicos de palavras</div>
              </div>

              <div
                className={`mode-card ${mode === 'standard' ? 'selected' : ''}`}
                onClick={() => setMode('standard')}
              >
                <div className="mode-card-title">
                  <FileText size={16} color="#818cf8" />
                  <span>Padrão</span>
                </div>
                <div className="mode-card-desc">Frases naturais e completas</div>
              </div>
            </div>
          </div>

          {/* Words per Segment Slider (when in short_video mode) */}
          {mode === 'short_video' && (
            <div className="form-group">
              <label className="form-label">
                <span>Palavras por linha na tela</span>
                <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Recomendado: 3 ou 4</span>
              </label>
              <div className="slider-container">
                <input
                  type="range"
                  min="1"
                  max="6"
                  value={maxWords}
                  onChange={(e) => setMaxWords(parseInt(e.target.value))}
                  className="slider-input"
                />
                <span className="slider-val">{maxWords}</span>
              </div>
            </div>
          )}

          {/* Generate Button */}
          <button
            className="btn-primary"
            onClick={handleTranscribe}
            disabled={loading || !selectedFile}
          >
            {loading ? (
              <>
                <div className="spinner"></div>
                <span>Processando ({loadingTimer}s)...</span>
              </>
            ) : (
              <>
                <Zap size={18} />
                <span>Gerar Legendas (.SRT)</span>
              </>
            )}
          </button>
        </section>

        {/* Right Side: Studio Preview & SRT Editor */}
        <section className="card-panel">
          <div className="tabs-header">
            <div className="tab-nav">
              <button
                className={`tab-btn ${activeTab === 'segments' ? 'active' : ''}`}
                onClick={() => setActiveTab('segments')}
              >
                Editor de Segmentos {result?.segments ? `(${result.segments.length})` : ''}
              </button>
              <button
                className={`tab-btn ${activeTab === 'srt' ? 'active' : ''}`}
                onClick={() => setActiveTab('srt')}
              >
                Código SRT
              </button>
            </div>

            {result && (
              <div className="action-buttons-group">
                <button className="btn-secondary" onClick={handleCopySrt} title="Copiar SRT">
                  <Copy size={14} />
                  <span>Copiar</span>
                </button>
                <button className="btn-success" onClick={handleDownloadSrt} title="Baixar .srt">
                  <Download size={14} />
                  <span>Baixar .SRT</span>
                </button>
              </div>
            )}
          </div>

          {/* Main Area: Empty State vs Active Result */}
          {!result && !previewUrl ? (
            <div className="empty-state">
              <FileVideo className="empty-state-icon" />
              <h3>Nenhum vídeo carregado</h3>
              <p>Envie um vídeo ou áudio à esquerda para gerar as legendas automáticas em SRT.</p>
            </div>
          ) : (
            <div className="studio-grid">
              {/* Short Video Preview Box with TikTok-Style Caption Overlay */}
              <div className="video-box">
                {previewUrl ? (
                  <>
                    <video
                      ref={videoRef}
                      src={previewUrl}
                      controls
                      className="video-element"
                      onTimeUpdate={handleTimeUpdate}
                      onPlay={() => setIsPlaying(true)}
                      onPause={() => setIsPlaying(false)}
                    />
                    {/* Live Subtitle Overlay */}
                    {activeSegment && (
                      <div className="video-subtitle-overlay">
                        <div className="overlay-text">{activeSegment.text}</div>
                      </div>
                    )}
                  </>
                ) : (
                  <div style={{ color: '#64748b', fontSize: '0.85rem' }}>Pré-visualização indisponível</div>
                )}
              </div>

              {/* Subtitle Editor or Raw SRT */}
              <div>
                {activeTab === 'segments' ? (
                  <div className="segments-list">
                    {result?.segments && result.segments.length > 0 ? (
                      result.segments.map((seg, idx) => {
                        const isCurrent =
                          currentTime >= seg.start && currentTime <= seg.end
                        return (
                          <div
                            key={seg.id || idx}
                            className={`segment-item ${isCurrent ? 'active' : ''}`}
                          >
                            <div className="segment-header">
                              <span className="segment-index">#{idx + 1}</span>
                              <div
                                className="segment-time"
                                onClick={() => handleSeek(seg.start)}
                                title="Clique para pular o vídeo até aqui"
                              >
                                <Clock size={12} />
                                <span>
                                  {seg.start.toFixed(2)}s - {seg.end.toFixed(2)}s
                                </span>
                              </div>
                              <button
                                style={{ background: 'transparent', color: '#64748b' }}
                                onClick={() => handleDeleteSegment(idx)}
                                title="Excluir este segmento"
                              >
                                <Trash2 size={13} />
                              </button>
                            </div>
                            <input
                              type="text"
                              className="segment-text-input"
                              value={seg.text}
                              onChange={(e) => handleSegmentChange(idx, e.target.value)}
                            />
                          </div>
                        )
                      })
                    ) : (
                      <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
                        Clique em <strong>"Gerar Legendas (.SRT)"</strong> para criar a transcrição sincronizada.
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="srt-code-viewer">
                    {result?.srt_content || 'O conteúdo do arquivo .SRT aparecerá aqui após a geração.'}
                  </div>
                )}
              </div>
            </div>
          )}
        </section>
      </main>

      {/* Floating Toast Notification */}
      {toastMessage && (
        <div className="toast">
          <Check size={16} color="#34d399" />
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  )
}
