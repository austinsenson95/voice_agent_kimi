# AI Phone Agent — Agent Guide

> This file is for AI coding agents. Read this first before making any changes to the project.

---

## Project Overview

This is a **3-Day MVP** for an AI Phone Agent built for Indian coaching/consulting businesses. It makes real phone calls, handles Hindi/English/Hinglish conversations, books appointments via Cal.com, sends WhatsApp follow-ups, and monitors everything through a React dashboard.

**Core Loop**: Vobiz telephony webhook → Sarvam STT (audio→text) → LLM (Groq/OpenAI/Anthropic/DeepSeek) → Sarvam TTS (text→audio) → Vobiz playback.

The project lives under `ai-phone-agent/` and is split into a Python FastAPI backend and a React 19 + TypeScript frontend.

---

## Technology Stack

### Backend (`ai-phone-agent/backend/`)
- **Language**: Python 3.11+
- **Framework**: FastAPI 0.109.0
- **Server**: Uvicorn 0.27.0 (standard)
- **HTTP Client**: httpx 0.26.0
- **Validation/Settings**: pydantic 2.5.0 + pydantic-settings >=2.0.0
- **State Store**: Redis 5.0.1 (async, with in-memory fallback)
- **Env Loading**: python-dotenv 1.0.0
- **File Uploads**: python-multipart 0.0.6

### Frontend (`ai-phone-agent/frontend/`)
- **Framework**: React ^19.0.0
- **Language**: TypeScript ^5.7.0
- **Build Tool**: Vite ^6.0.0
- **Styling**: Tailwind CSS ^3.4.17 + tailwindcss-animate
- **UI Components**: shadcn/ui (Radix UI primitives)
- **Charts**: Recharts ^2.15.0
- **Icons**: Lucide React ^0.468.0
- **Routing**: React Router DOM ^7.1.0
- **Date Utils**: date-fns ^4.1.0
- **Class Utils**: clsx ^2.1.1 + tailwind-merge ^2.6.0

### External Services
- **Telephony**: Vobiz (webhooks for answer/recording/hangup)
- **STT/TTS**: Sarvam AI (`saarika:v2` STT, `bulbul:v1` TTS, speaker "meera")
- **LLMs**: Groq (default), OpenAI, Anthropic, DeepSeek
- **Calendar**: Cal.com REST API
- **WhatsApp**: Chat Mitra Business API
- **State Store**: Redis (optional; falls back to in-memory)

---

## Project Structure

```
ai-phone-agent/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, webhooks, dashboard API
│   │   ├── config.py            # Settings manager (env vars)
│   │   ├── schemas.py           # Pydantic models (webhooks, LLM, sessions)
│   │   ├── llm_provider.py      # 4 LLM providers + hot-swap factory
│   │   ├── voice_pipeline.py    # Sarvam STT + TTS integration
│   │   ├── state_machine.py     # 7-state keyword-based conversation FSM
│   │   ├── memory.py            # Redis-backed session store (in-memory fallback)
│   │   ├── calendar.py          # Cal.com REST API integration
│   │   ├── whatsapp.py          # Chat Mitra WhatsApp Business API
│   │   ├── battle_card.py       # Business context injection ("Battle Cards")
│   │   ├── objections.py        # 7-type objection detection & response
│   │   └── routes.py            # Integration API routers (calendar, WhatsApp, etc.)
│   ├── requirements.txt         # Python dependencies (8 packages, pinned versions)
│   ├── .env.example             # Environment variable template
│   └── run.py                   # Entry point (uvicorn wrapper)
├── frontend/
│   ├── src/
│   │   ├── main.tsx             # React entry point
│   │   ├── App.tsx              # Main layout (sidebar + router)
│   │   ├── index.css
│   │   ├── types.ts             # TypeScript type definitions
│   │   ├── vite-env.d.ts
│   │   ├── components/
│   │   │   ├── Header.tsx       # Top bar (health, refresh, connection)
│   │   │   ├── Sidebar.tsx      # Navigation sidebar
│   │   │   └── CallCard.tsx     # Live call card with transcript
│   │   ├── views/
│   │   │   ├── LiveCallsView.tsx   # Real-time active call monitoring
│   │   │   ├── HistoryView.tsx     # Past calls table + CSV export
│   │   │   ├── AnalyticsView.tsx   # Charts (Recharts): calls, outcomes, latency
│   │   │   └── SettingsView.tsx    # LLM switcher, business config, objections
│   │   ├── hooks/
│   │   │   └── useApi.ts        # useApi + useMutation hooks
│   │   └── lib/
│   │       ├── utils.ts         # cn(), formatDuration, formatPhone, timeAgo
│   │       └── mockData.ts      # Extensive mock data for all views
│   ├── package.json             # NPM dependencies & scripts
│   ├── package-lock.json
│   ├── tsconfig.json            # Strict TS config, path alias `@/*`
│   ├── tsconfig.node.json
│   ├── vite.config.ts           # Vite config + dev proxy to localhost:3000
│   ├── tailwind.config.js       # Tailwind theme with shadcn/ui CSS variables
│   ├── postcss.config.js        # PostCSS with tailwindcss + autoprefixer
│   └── index.html
├── docs/
│   └── 3-DAY-MVP-GUIDE.md       # Full day-by-day build instructions
├── README.md                    # Human-facing project overview & quick start
└── DEPLOYMENT.md                # Deploy guide (Render/Vercel/Railway)
```

---

## Build and Run Commands

### Prerequisites
- Python 3.11+
- Node.js 20+
- Redis (optional — falls back to in-memory)

### Backend
```bash
cd ai-phone-agent/backend
cp .env.example .env    # Fill in your API keys
pip install -r requirements.txt
python run.py
# Server runs on http://localhost:8000
```

**Production run command**:
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Frontend
```bash
cd ai-phone-agent/frontend
npm install
npm run dev
# Dashboard runs on http://localhost:5173
```

**Production build**:
```bash
npm run build
# Outputs to frontend/dist/
```

### ngrok (for local webhook testing)
```bash
# Terminal 1: Start backend
python run.py

# Terminal 2: Expose localhost
ngrok http 8000
# Note the HTTPS URL: https://xxxx.ngrok-free.app

# Terminal 3: Test
curl https://xxxx.ngrok-free.app/health
```

---

## Code Style Guidelines

### Python (Backend)
- Follow PEP 8.
- Use type hints (`from __future__ import annotations` for forward references).
- Use Google-style docstrings for modules, classes, and functions.
- Use `lru_cache` for singletons (e.g., `get_settings()`).
- Configuration is centralized in `app/config.py` via a `Settings` class using `os.getenv` with defaults. **Do not scatter `os.getenv` calls** throughout the codebase.
- Use `logging` (not print). Log level is controlled by `DEBUG` env var.
- Use `httpx` for async HTTP requests (not `requests`).
- Use Pydantic v2 models in `app/schemas.py` for all request/response shapes.
- Modules use `try/except ImportError` for optional integrations (see `main.py` for the pattern).

### TypeScript / React (Frontend)
- Strict TypeScript (`strict: true`, `noUnusedLocals: true`, `noUnusedParameters: true`).
- Use path alias `@/*` for imports from `src/`.
- Use functional components with hooks.
- Prefer `useCallback` for event handlers passed to children.
- Use `cn()` from `@/lib/utils` for conditional Tailwind class merging.
- UI components follow shadcn/ui conventions (CSS variables in `tailwind.config.js`).
- Mock data lives in `@/lib/mockData.ts` and is used as a fallback when the backend is unreachable.

---

## Testing Instructions

**There is no formal test suite** (no unit, integration, or E2E test files present). Testing is done manually:

1. **Manual Webhook Simulation** (recommended for local dev):
   ```bash
   # Answer webhook
   curl -X POST http://localhost:8000/webhook/vobiz/answer \
     -H "Content-Type: application/json" \
     -d '{"call_sid":"test-001","from_number":"+919999999999"}'

   # Recording webhook (simulate user speech)
   curl -X POST http://localhost:8000/webhook/vobiz/recording \
     -H "Content-Type: application/json" \
     -d '{"call_sid":"test-001","user_text":"Hi, I am interested in coaching but I am worried about the price"}'

   # Hangup
   curl -X POST http://localhost:8000/webhook/vobiz/hangup \
     -H "Content-Type: application/json" \
     -d '{"call_sid":"test-001","duration_seconds":120}'
   ```

2. **Dashboard Mock Data**: The frontend automatically falls back to `mockData.ts` if the backend is unavailable, so UI work can proceed without a running server.

3. **Real Call Testing**: Deploy backend → Configure Vobiz webhooks → Call the Vobiz number from your phone.

---

## Deployment Process

### Backend — Render (Primary)
1. Push code to GitHub.
2. Create a new Web Service on Render.
3. Set **Root Directory** to `backend`.
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `python run.py`
6. Add all environment variables from `.env.example` in the Render dashboard.
7. Configure Vobiz webhooks to the deployed URL.

### Backend — Railway (Alternative)
```bash
cd backend
railway init
railway add --database redis
railway variables set GROQ_API_KEY=...
railway up
```

### Frontend — Vercel (Primary)
```bash
cd frontend
npm install
npm run build
vercel --prod
```
Or drag-and-drop `frontend/dist/` to Vercel.

Set environment variable in Vercel:
```
VITE_API_URL=https://ai-phone-agent.onrender.com
```

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in all keys. Key groups:

| Group | Vars |
|---|---|
| Server | `HOST`, `PORT`, `DEBUG` |
| Telephony | `VOBIZ_API_KEY`, `VOBIZ_BASE_URL` |
| Voice | `SARVAM_API_KEY`, `SARVAM_BASE_URL` |
| LLM | `LLM_PROVIDER`, `GROQ_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY` (plus model/temperature/max_tokens per provider) |
| State | `REDIS_URL`, `SESSION_TTL_SECONDS` |
| Business | `BUSINESS_NAME`, `BUSINESS_TYPE`, `AGENT_LANGUAGE`, `BATTLE_CARD_TEXT` |

The frontend only needs `VITE_API_URL` at build time.

---

## Key Architecture Decisions & Conventions

1. **LLM Provider Hot-Swap**: The signature feature. Providers can be swapped at runtime via API (`POST /api/settings/provider`), env var, or dashboard UI — zero restart needed. To add a new provider, subclass `LLMProvider` in `app/llm_provider.py` and register it in the factory dict.

2. **Provider-Agnostic Interface**: All LLM providers return a standardized `LLMResponse` Pydantic model with latency, tokens, cost, and finish reason.

3. **Keyword-Based State Machine**: A simple 7-state FSM (`opening → discovery → pitch → objection → close → human_handoff → ended`) using lowercase substring matching. Escape hatches exist from any state.

4. **Hinglish-First**: System prompts and TTS are optimized for Hinglish (Hindi + English in Roman script) for Indian audiences.

5. **Redis with In-Memory Fallback**: `SessionMemory` auto-detects Redis availability and falls back to `_InMemoryStore` for local dev.

6. **Mock Data Fallback**: Frontend gracefully degrades to mock data when the backend API is unreachable.

7. **Cost Tracking**: Built-in per-token cost calculation for all 4 LLM providers.

8. **IST Timezone Hardcoding**: Calendar and formatting utilities assume `Asia/Kolkata` (UTC+5:30).

9. **No Authentication/Authorization**: The MVP has no auth. The dashboard and API are open.

10. **Polling-Based Dashboard**: The frontend polls `/health` and API endpoints every 5 seconds. There are no WebSockets.

---

## Security Considerations

- **No PII redaction** is implemented yet. Call transcripts, phone numbers, and session data are stored verbatim in Redis/in-memory. This is a known gap planned for Week 2 (Presidio).
- **No authentication** on dashboard or API endpoints. Anyone with the URL can access call data and change LLM providers.
- **CORS is wide open** (`allow_origins=["*"]` in `main.py`). This is intentional for the MVP but should be restricted in production.
- **API keys** are stored as plain environment variables. There is no secrets manager integration.
- **No rate limiting** on webhooks or dashboard APIs.
- **No input sanitization** beyond Pydantic validation.
- **No HTTPS enforcement** in the backend code — rely on the reverse proxy (Render/Railway) for TLS termination.
- When adding new features, **do not** introduce authentication complexity unless explicitly asked — the current architecture assumes an open MVP. Document any security gaps you introduce.

---

## Common Troubleshooting

| Issue | Solution |
|---|---|
| `npm install` hangs | Use `--ignore-scripts` or try `yarn` |
| Redis connection fails | App auto-falls back to in-memory. Set `REDIS_URL` for persistence. |
| STT returns empty | Check audio format (must be WAV, 16kHz). Verify Sarvam API key. |
| LLM slow (>1s) | Switch to Groq (fastest) or reduce `max_tokens` to 150 |
| Webhook not reaching | Verify ngrok is running. Check URL in Vobiz dashboard. |
| CORS errors | Backend allows all origins. Check `VITE_API_URL` in frontend env. |

---

## Important Files to Know

| File | Why it matters |
|---|---|
| `backend/app/config.py` | Centralized env-var configuration. Add new settings here. |
| `backend/app/llm_provider.py` | The LLM factory. To add a provider, edit this file. |
| `backend/app/state_machine.py` | Conversation logic. State transitions and system prompts. |
| `backend/app/memory.py` | Session storage. Abstracts Redis vs in-memory. |
| `backend/app/schemas.py` | All Pydantic models. Change request/response shapes here. |
| `frontend/vite.config.ts` | Dev proxy config. If you change backend port, update the proxy. |
| `frontend/src/lib/mockData.ts` | Frontend fallback data. Update this when you add new API fields. |
| `frontend/src/types.ts` | TypeScript types. Keep in sync with backend `schemas.py`. |

---

## Post-MVP Roadmap (from `README.md`)

| Week | Feature |
|---|---|
| 2 | PII redaction (Presidio) |
| 3 | Vector memory (Qdrant) |
| 4 | Warm-path orchestrator (Claude Sonnet) |
| 5 | Profile research (Apollo.io) |
| 6 | Human takeover bridge |
| 7 | Eval harness + regression |
| 8 | TRAI/DPDP compliance |
| 9-12 | Multi-language, scale testing |
