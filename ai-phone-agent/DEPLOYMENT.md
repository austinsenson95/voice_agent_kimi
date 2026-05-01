# AI Phone Agent — Deployment Guide

## What Was Built

This is a complete 3-day MVP for an AI Phone Agent with the following components:

### Backend (Python FastAPI)
| Component | File | Description |
|---|---|---|
| Voice Pipeline | `app/voice_pipeline.py` | Sarvam STT (audio→text) + TTS (text→audio) |
| LLM Provider | `app/llm_provider.py` | Groq/OpenAI/Anthropic/DeepSeek with hot-swap |
| State Machine | `app/state_machine.py` | 7-state conversation engine |
| Session Memory | `app/memory.py` | Redis-backed with 24h TTL |
| Webhooks | `app/main.py` | Vobiz answer/recording/hangup handlers |
| Calendar | `app/calendar.py` | Cal.com availability + booking |
| WhatsApp | `app/whatsapp.py` | Chat Mitra follow-up + confirmation |
| Battle Cards | `app/battle_card.py` | Business context injection |
| Objections | `app/objections.py` | 7-type objection detection + responses |

### Frontend (React + TypeScript + Tailwind)
| Component | File | Description |
|---|---|---|
| Live Calls | `views/LiveCallsView.tsx` | Real-time active call monitoring |
| History | `views/HistoryView.tsx` | Past calls with transcripts + CSV export |
| Analytics | `views/AnalyticsView.tsx` | Charts: calls/day, outcomes, objections |
| Settings | `views/SettingsView.tsx` | LLM provider switcher + business config |

---

## Deploy Backend to Render (Free Tier)

### Step 1: Push to GitHub
```bash
cd ai-phone-agent
git init
git add -A
git commit -m "mvp: ai phone agent v0.1.0"
# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/ai-phone-agent.git
git push -u origin master
```

### Step 2: Create Render Account
- Go to [render.com](https://render.com)
- Sign up with GitHub
- Click "New Web Service"
- Connect your GitHub repo

### Step 3: Configure on Render
```
Name: ai-phone-agent
Root Directory: backend
Build Command: pip install -r requirements.txt
Start Command: python run.py
Instance Type: Free
```

### Step 4: Add Environment Variables
In Render dashboard, add all variables from `.env.example`:
```
VOBIZ_API_KEY=...
SARVAM_API_KEY=...
GROQ_API_KEY=...
GROQ_MODEL=llama-3.3-70b-versatile
REDIS_URL=... (get from redis.io/cloud free tier)
CAL_API_KEY=...
CAL_EVENT_TYPE_ID=...
CHATMITRA_API_KEY=...
CHATMITRA_PHONE_ID=...
BUSINESS_NAME=Your Coaching
BUSINESS_OWNER=Your Name
SERVICE_DESCRIPTION=...
PRICING_RANGE=...
SESSION_DURATION=45 minutes
LLM_PROVIDER=groq
```

### Step 5: Deploy
Click "Create Web Service". Render will build and deploy automatically.

Your API will be at: `https://ai-phone-agent.onrender.com`

### Step 6: Configure Vobiz Webhook
In Vobiz dashboard:
- Set Answer Webhook: `https://ai-phone-agent.onrender.com/webhook/vobiz/answer`
- Set Recording Webhook: `https://ai-phone-agent.onrender.com/webhook/vobiz/recording`
- Set Hangup Webhook: `https://ai-phone-agent.onrender.com/webhook/vobiz/hangup`

---

## Deploy Frontend to Vercel (Free Tier)

### Step 1: Build Locally
```bash
cd frontend
npm install
npm run build
```

### Step 2: Deploy to Vercel
```bash
npm i -g vercel
vercel --prod
# Follow prompts
```

Or drag-and-drop the `frontend/dist/` folder to [vercel.com](https://vercel.com).

### Step 3: Set API URL
In Vercel dashboard, add environment variable:
```
VITE_API_URL=https://ai-phone-agent.onrender.com
```

Redeploy after setting the variable.

---

## Deploy Backend to Railway (Alternative)

### Step 1: Install Railway CLI
```bash
npm i -g @railway/cli
railway login
```

### Step 2: Create Project
```bash
cd ai-phone-agent/backend
railway init
railway add --database redis
```

### Step 3: Add Variables & Deploy
```bash
railway variables set GROQ_API_KEY=...
railway variables set SARVAM_API_KEY=...
# ... add all other vars
railway up
```

---

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- Redis (optional — falls back to in-memory)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env
# Edit .env with your API keys

python run.py
# Server runs on http://localhost:8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# Dashboard runs on http://localhost:5173
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

## Testing the Full Flow

### Option 1: Manual Webhook Simulation
```bash
# 1. Answer webhook
curl -X POST http://localhost:8000/webhook/vobiz/answer \
  -H "Content-Type: application/json" \
  -d '{"call_sid":"test-001","from_number":"+919999999999"}'

# 2. Recording webhook (simulating user speech)
curl -X POST http://localhost:8000/webhook/vobiz/recording \
  -H "Content-Type: application/json" \
  -d '{
    "call_sid":"test-001",
    "user_text":"Hi, I am interested in coaching but I am worried about the price"
  }'

# 3. Hangup
curl -X POST http://localhost:8000/webhook/vobiz/hangup \
  -H "Content-Type: application/json" \
  -d '{"call_sid":"test-001","duration_seconds":120}'
```

### Option 2: Run E2E Test Script
```bash
cd backend
python test_e2e.py
```

### Option 3: Real Call via Vobiz
1. Deploy backend (Render/Railway)
2. Configure Vobiz webhooks to your deployed URL
3. Call your Vobiz number from your phone
4. Listen to the AI respond!

---

## Swapping LLM Providers (Key Feature!)

### Method 1: Environment Variable (Restart Required)
```bash
# Switch from Groq to OpenAI
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
python run.py
```

### Method 2: API Call (No Restart!)
```bash
curl -X POST http://localhost:8000/api/settings/provider \
  -H "Content-Type: application/json" \
  -d '{"provider": "anthropic"}'
```

### Method 3: Dashboard UI
1. Open dashboard Settings page
2. Select provider from dropdown
3. Click "Test & Switch"

### Adding a New Provider
1. Create new class in `app/llm_provider.py`:
```python
class GeminiProvider(LLMProvider):
    @property
    def name(self): return "gemini"
    @property
    def model(self): return "gemini-2.5-flash"
    async def generate(self, messages, system="", tools=None):
        # Implementation
        pass
```

2. Register in factory:
```python
providers = {
    "groq": GroqProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "deepseek": DeepSeekProvider,
    "gemini": GeminiProvider,
}
```

3. Use immediately:
```bash
curl -X POST /api/settings/provider -d '{"provider": "gemini"}'
```

---

## Project Structure
```
ai-phone-agent/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app + webhooks
│   │   ├── config.py            # Settings from env vars
│   │   ├── schemas.py           # Pydantic models
│   │   ├── llm_provider.py      # Groq/OpenAI/Anthropic/DeepSeek
│   │   ├── voice_pipeline.py    # Sarvam STT + TTS
│   │   ├── state_machine.py     # Conversation states
│   │   ├── memory.py            # Redis session store
│   │   ├── calendar.py          # Cal.com integration
│   │   ├── whatsapp.py          # Chat Mitra integration
│   │   ├── battle_card.py       # Business context
│   │   ├── objections.py        # Objection handler
│   │   └── routes.py            # Integration API routes
│   ├── requirements.txt
│   ├── .env.example
│   └── run.py                   # Entry point
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Main layout
│   │   ├── views/               # LiveCalls, History, Analytics, Settings
│   │   ├── components/          # Sidebar, Header, CallCard
│   │   ├── hooks/               # useApi
│   │   ├── lib/                 # utils, mockData
│   │   └── types.ts             # TypeScript types
│   ├── package.json
│   └── vite.config.ts
└── docs/
    └── 3-DAY-MVP-GUIDE.md       # Full implementation guide
```

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `npm install` hangs | Use `--ignore-scripts` flag or try `yarn` |
| Redis connection fails | App auto-falls back to in-memory. Set `REDIS_URL` for persistence. |
| STT returns empty | Check audio format (must be WAV, 16kHz). Verify Sarvam API key. |
| LLM slow (>1s) | Switch to Groq (fastest) or reduce `max_tokens` to 150 |
| Webhook not reaching | Verify ngrok is running. Check URL in Vobiz dashboard. |
| CORS errors | Backend allows all origins. Check API URL in dashboard `.env` |

---

## Cost at 1,000 Calls/Month (MVP Load)

| Component | Monthly Cost |
|---|---|
| Vobiz telephony | Rs. 450 |
| Sarvam STT+TTS | Rs. 720 |
| Groq LLM | Rs. 1,275 |
| Render hosting | Free |
| Redis Cloud | Free |
| Cal.com | Free (self-hosted) |
| Chat Mitra | Free (Starter) |
| **Total** | **~Rs. 2,445 ($29)** |

vs. Human SDR: **Rs. 80,000/month** — **97% cheaper** at MVP scale.
