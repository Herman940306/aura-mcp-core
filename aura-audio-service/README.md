# Aura Audio Service (STT/TTS) - Enterprise OSS Stack

**PRD Section 8.12 Compliant** | **HNSC Layer Integration Ready**

Enterprise-grade Speech-to-Text and Text-to-Speech microservice for Aura IA MCP Concierge.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Aura Audio Service                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  FastAPI Gateway (:8001)                                │   │
│  │  - PII Redaction (email, SSN, CC, phone)               │   │
│  │  - Policy Enforcement (HNSC Layer 6 integration)       │   │
│  │  - Audit Logging (no raw audio stored)                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                              │                      │
│           ▼                              ▼                      │
│  ┌─────────────────┐          ┌──────────────────┐             │
│  │  Vosk STT       │          │  Coqui TTS       │             │
│  │  (:2700)        │          │  (:5002)         │             │
│  │  - Offline      │          │  - MOS 4.2-4.4   │             │
│  │  - CPU-only     │          │  - CPU real-time │             │
│  │  - 94-95% WER   │          │  - GPU optional  │             │
│  └─────────────────┘          └──────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## Security Guarantees (PRD 8.12)

1. **NO_RAW_AUDIO_TO_LLM** - Audio never sent to model; only sanitized text
2. **PII Redaction** - Applied before any logging or model input
3. **Policy Enforcement** - Blocked transcripts never reach Concierge
4. **Audit Trail** - All operations logged (without raw audio)

## Prerequisites

- Docker & Docker Compose
- ~2GB disk for models
- Optional: GPU for faster TTS

## Quickstart (Docker)

### 1. Download Vosk Model

```bash
mkdir -p models/vosk
cd models/vosk
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
```

### 2. Start Services

```bash
docker-compose up --build
```

### 3. Verify

```bash
# Health check
curl http://localhost:8001/health

# Test TTS
curl -X POST http://localhost:8001/api/audio/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello from Aura"}' \
  --output test.wav

# Test STT (with a WAV file)
curl -X POST http://localhost:8001/api/audio/stt \
  -F "audio=@test.wav"
```

## API Endpoints

### POST /api/audio/stt

Convert speech to text.

**Request:** `multipart/form-data` with `audio` file (WAV 16kHz mono)

**Response:**

```json
{
  "text": "transcribed text here",
  "confidence": 0.95,
  "redacted": false,
  "policy_blocked": false
}
```

### POST /api/audio/tts

Convert text to speech.

**Request:**

```json
{
  "text": "Text to synthesize",
  "voice": "default",
  "format": "wav"
}
```

**Response:** `audio/wav` binary stream

### GET /health

Service health check.

## Configuration

Environment variables (see `audio_service/.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `VOSK_SERVER_URL` | `http://vosk:2700` | Vosk STT endpoint |
| `COQUI_TTS_URL` | `http://coqui:5002` | Coqui TTS endpoint |
| `STT_ENGINE` | `vosk` | STT engine to use |
| `TTS_ENGINE` | `coqui` | TTS engine to use |
| `MAX_AUDIO_SECONDS` | `60` | Max audio length |

## Testing

```bash
# Unit tests (PII, policy)
pytest tests/test_audio_pii_redaction.py -v

# Integration tests (requires services running)
pytest tests/test_audio_stt_end_to_end.py -v --ignore-glob="*integration*"
```

## MCP Concierge Integration

### Dashboard Audio Controls

Add to your dashboard HTML:

```html
<div id="audio-service-ui"></div>
<script type="module" src="/assets/audio_client.js"></script>
```

### Chat Service Tools

The audio service exposes these MCP tools:

- `speech_to_text` - Convert audio to text
- `text_to_speech` - Convert text to audio
- `get_stt_status` - STT service status
- `get_tts_status` - TTS service status

## Kubernetes Deployment

```bash
helm upgrade --install aura-audio ./helm \
  -f helm/values-audio.yaml \
  --namespace aura-ia
```

## Engine Alternatives

| Engine | Type | Quality | Speed | Notes |
|--------|------|---------|-------|-------|
| Vosk | STT | 94-95% WER | Fast | Default, offline |
| Whisper.cpp | STT | 97%+ WER | Medium | Higher accuracy |
| Coqui TTS | TTS | MOS 4.2-4.4 | Real-time | Default |
| eSpeak-NG | TTS | MOS 3.0 | Instant | Fallback, robotic |

## SBOM & Security

Generate SBOM:

```bash
syft dir:. -o spdx-json > sbom.json
```

Verify engine versions match `helm/values-audio.yaml`:

```bash
python scripts/verify_audio_engines_pinned.py
```

## License

Apache 2.0 - See main Aura IA repository.
