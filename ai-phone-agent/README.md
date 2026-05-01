# AI Phone Agent MVP

> **3-Day MVP**: A voice AI agent that makes real phone calls, handles objections, books appointments, and demonstrates the core STT → LLM → TTS loop. Built for Indian coaching/consulting businesses.

## What It Does

1. **Answers Calls** — Vobiz phone number triggers webhook to your server
2. **Understands Speech** — Sarvam STT converts Hindi/English/Hinglish audio to text
3. **Thinks** — LLM (Groq Llama 3.3 70B) generates contextual responses with business context
4. **Speaks** — Sarvam TTS converts responses to natural-sounding speech
5. **Handles Objections** — Detects price/time/interest objections, responds empathetically
6. **Books Appointments** — Checks Cal.com availability, creates bookings during the call
7. **Follows Up** — Sends WhatsApp message after call with booking link
8. **Monitors** — React dashboard shows live calls, transcripts, analytics
9. **Swaps LLMs** — Change provider (Groq/OpenAI/Anthropic/DeepSeek) without code changes

## Quick Start

```bash
# Clone
git clone <your-repo>
cd ai-phone-agent

# Backend
cd backend
cp .env.example .env  # Fill in your API keys
pip install -r requirements.txt
python run.py

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

## API Endpoints

### Webhooks (from Vobiz)
```
POST /webhook/vobiz/answer      — Call answered
POST /webhook/vobiz/recording   — User spoke (core loop)
POST /webhook/vobiz/hangup      — Call ended
```

### Dashboard API
```
GET  /health                    — Health check
GET  /api/calls                 — Active calls
GET  /api/calls/:sid            — Call details
POST /api/settings/provider     — Switch LLM provider
GET  /api/settings/provider     — Current provider info
POST /api/calendar/check        — Check availability
POST /api/calendar/book         — Create booking
POST /api/whatsapp/followup    — Send follow-up
GET  /api/battle-card           — Business context
PUT  /api/battle-card           — Update context
GET  /api/objections            — List objections
```

## Swapping LLM Providers

The killer feature — change LLM providers without restarting:

```bash
# Via API (instant)
curl -X POST /api/settings/provider -d '{"provider":"openai"}'

# Via env var (on restart)
export LLM_PROVIDER=anthropic
python run.py

# Via dashboard (click dropdown, select provider, done)
```

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Voice** | Sarvam AI (Saaras STT + Bulbul TTS) |
| **LLM** | Groq (default), OpenAI, Anthropic, DeepSeek |
| **State** | LangGraph-style state machine |
| **Memory** | Redis (with in-memory fallback) |
| **Calendar** | Cal.com REST API |
| **WhatsApp** | Chat Mitra Business API |
| **Frontend** | React 19, TypeScript, Tailwind CSS, shadcn/ui, Recharts |
| **Deploy** | Render/Railway (backend), Vercel (frontend) |

## Project Structure

```
ai-phone-agent/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI + webhooks
│   │   ├── llm_provider.py      # 4 LLM providers + hot-swap
│   │   ├── voice_pipeline.py    # Sarvam STT/TTS
│   │   ├── state_machine.py     # Conversation engine
│   │   ├── memory.py            # Redis sessions
│   │   ├── calendar.py          # Cal.com integration
│   │   ├── whatsapp.py          # Chat Mitra integration
│   │   ├── battle_card.py       # Business context
│   │   ├── objections.py        # Objection handling
│   │   ├── schemas.py           # Pydantic models
│   │   └── config.py            # Settings
│   ├── requirements.txt
│   ├── .env.example
│   └── run.py
├── frontend/
│   └── src/
│       ├── App.tsx              # Main layout
│       ├── views/               # LiveCalls, History, Analytics, Settings
│       ├── components/          # Sidebar, Header, CallCard
│       └── hooks/               # useApi with auto-refresh
├── docs/
│   └── 3-DAY-MVP-GUIDE.md       # Full build guide
└── DEPLOYMENT.md                # Deploy to Render/Vercel
```

## Cost Projection

| Scale | Calls/Month | AI Agent Cost | Human SDR Cost | Savings |
|---|---|---|---|---|
| **MVP** | 250 | Rs. 2,445 | Rs. 80,000 | **97%** |
| **Growth** | 2,500 | Rs. 37,000 | Rs. 80,000 | **54%** |
| **Scale** | 25,000 | Rs. 4,58,000 | Rs. 4,00,000 (5 SDRs) | **Similar** |

## From MVP to Production

| Week | Feature | Spec Reference |
|---|---|---|
| 1 | **MVP** (this build) | Core voice loop + dashboard |
| 2 | PII redaction (Presidio) | ADR-011 |
| 3 | Vector memory (Qdrant) | ADR-012 |
| 4 | Warm-path orchestrator (Claude Sonnet) | ADR-003 |
| 5 | Profile research (Apollo.io) | Spec Issue 3 |
| 6 | Human takeover bridge | ADR-013 |
| 7 | Eval harness + regression | Section 6 |
| 8 | TRAI/DPDP compliance | Section 8 |
| 9-12 | Multi-language, scale testing | Phase 3 |

## Documentation

- **[3-DAY-MVP-GUIDE.md](docs/3-DAY-MVP-GUIDE.md)** — Complete day-by-day build instructions with code
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — Deploy to Render + Vercel in minutes
- **Original Spec** — See `/mnt/agents/upload/specs.md` for full production architecture

## License

MIT
