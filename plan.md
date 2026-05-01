# AI Phone Agent — 3-Day MVP Plan

## Vision
Build a working voice AI agent that can make real outbound calls, handle conversations, book appointments, and hand off to humans. The MVP validates the core hot-path voice loop (STT → LLM → TTS) with a simple state machine, then layers on warm-path intelligence and integrations.

## Reality Check: Full Spec vs. MVP Scope

The v3 spec is a **20-week production build**. For a **3-day MVP**, we aggressively descope to the single question: *"Can an AI make a believable phone call that books an appointment?"*

### What's IN for 3-Day MVP
| Component | MVP Scope |
|---|---|
| **Voice Pipeline** | Sarvam STT + TTS via REST (streaming not required) |
| **Hot-Path LLM** | Single provider (Groq Llama 3.3 70B) with easy swap mechanism |
| **State Machine** | 5-state hardcoded: IDLE → OPENING → DISCOVERY → PITCH → CLOSE |
| **Telephony** | Vobiz webhook (answer + hangup + recording URL) |
| **Memory** | In-memory conversation buffer (last 10 turns), Redis optional |
| **Objections** | 5 hardcoded objections with scripted responses |
| **Calendar** | Cal.com REST API — check availability + create booking |
| **WhatsApp** | Chat Mitra — send follow-up template post-call |
| **Dashboard** | React frontend showing live calls, transcripts, basic metrics |
| **Human Handoff** | Trigger on "speak to human" keyword → log alert (no live bridge yet) |

### What's OUT for 3-Day MVP (Phase 2+)
- PII redaction pipeline (Presidio) — use local-only processing
- Vector DB / semantic memory (Qdrant) — in-memory only
- Warm-path sub-agents (Claude Sonnet orchestrator)
- Cold-path async processing (summarization, scoring)
- Profile Researcher (Apollo.io)
- Multi-LLM routing with fallback chains
- Human takeover bridge (warm transfer)
- Automated eval harness
- Full compliance automation (manual consent tracking)

## Architecture: MVP Simplified

```
Vobiz Call Webhook
       │
       ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  FastAPI Server │────▶│  LangGraph   │────▶│  Groq LLM   │
│  (webhook + API)│     │  State Mach. │     │  Llama 3.3  │
└─────────────────┘     └──────────────┘     └─────────────┘
       │                         │
       ▼                         ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  Sarvam STT/TTS │     │  In-Memory   │     │  Cal.com    │
│  (voice)        │     │  Turn Buffer │     │  (calendar) │
└─────────────────┘     └──────────────┘     └─────────────┘
       │
       ▼
┌─────────────────┐     ┌──────────────┐
│  Chat Mitra     │     │  React       │
│  (WhatsApp)     │     │  Dashboard   │
└─────────────────┘     └──────────────┘
```

## Skill Loading Strategy

| Stage | Skill | Purpose |
|---|---|---|
| Day 1–2 Backend | `vibecoding-general-swarm` | Python FastAPI backend, voice pipeline, LangGraph state machine |
| Day 3 Frontend | `vibecoding-webapp-swarm` | React dashboard for monitoring |

## Day-by-Day Execution

### Day 1: Voice Loop + State Machine
1. **Scaffold**: FastAPI project with webhook endpoints
2. **Sarvam Integration**: STT (audio → text) + TTS (text → audio)
3. **Groq Integration**: LLM call with system prompt
4. **Vobiz Webhook**: Answer call → stream audio → process turn → respond
5. **Basic State Machine**: 5-state hardcoded transitions

### Day 2: Intelligence + Integrations
1. **Battle Card Injection**: Pass business context to LLM prompt
2. **Objection Handling**: 5 hardcoded objections → scripted responses
3. **Calendar Integration**: Cal.com API for booking slots
4. **WhatsApp Follow-up**: Post-call message via Chat Mitra
5. **Redis Session Store**: Persist call state across requests

### Day 3: Dashboard + Polish + Deploy
1. **React Dashboard**: Live calls, transcripts, metrics, settings
2. **LLM Swap Interface**: Easy provider switching (Groq ↔ OpenAI ↔ Anthropic)
3. **End-to-End Test**: Real call flow validation
4. **Deploy**: Render/Railway for backend, static for dashboard

## Post-MVP Iteration Roadmap

| Iteration | Focus | LLM Swaps |
|---|---|---|
| Week 2 | Add warm-path Claude Sonnet orchestrator, PII redaction | Keep Groq hot |
| Week 3 | Vector memory (Qdrant), profile research (Apollo) | Test Claude Haiku hot-path |
| Week 4 | Human takeover bridge, eval harness | Test GPT-5.2 hot-path |
| Week 5–8 | Compliance hardening, scale testing, multi-language | Full router with A/B testing |

## Key Design Decision: LLM Provider Swapping

The MVP uses a **provider-agnostic interface** from day 1:

```python
class LLMProvider(Protocol):
    async def generate(self, messages: list, system: str, tools: list | None) -> str: ...
    @property
    def latency_ms(self) -> int: ...
    @property
    def cost_per_1m_tokens(self) -> float: ...

# Implementations:
# - GroqProvider (default)
# - OpenAIProvider (swap target)
# - AnthropicProvider (swap target)
# - DeepSeekProvider (swap target)
```

This lets you iterate on LLM providers without touching conversation logic.
