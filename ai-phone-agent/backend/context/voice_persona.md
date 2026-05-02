---
source: HAMZA_AGENT_CONTEXT_PACK_v0.3_DEMO.md §8
loaded_by: voice_all_llm_calls.py
version: 0.3-demo
demo_tags: 2
source_attributions: 0
language_policy: english_only
---

> **DEMO MODE NOTICE** — see full notice in `HAMZA_AGENT_CONTEXT_PACK_v0.3_DEMO.md` §0.
> All `[DEMO: ...]` content is fabricated scaffolding. Do not use for production calls.

## 8. Voice Pipeline Persona

### 8.1 Voice Identity [DEMO]
- **TTS engine:** ElevenLabs (Turbo v2.5 for low latency on phone audio)
- **Voice ID:** [DEMO: pick a clear English-language female voice from ElevenLabs library — suggested "Sarah" or "Aria" — until Hamza has a specific preference for Aisha's voice]
- **Voice clone source:** N/A (Mode B uses stock voice, not Hamza-cloned)

### 8.2 Speech Style
- **Pace (WPM):** [DEMO: 155 — slightly above conversational average, matches the "speed" energy of the brand]
- **Pitch range:** stock voice default
- **ElevenLabs settings:** stability 0.65, similarity 0.75, style 0.30

### 8.3 Prosody & Pauses
- Pause after a question: ~1.2s
- Pause after a reframe: ~0.8s (let it land)
- Emphasis on key word in reframe sentences (TTS markup)
- Filler density: 1 filler / 4–5 sentences max. Zero on close lines.

### 8.4 STT Configuration [DEMO]
- **Provider:** Deepgram Nova-2
- **Language model:** `en-IN` (handles Indian-accented English well, transcribes to standard English)
- **Endpointing:** aggressive (lead may speak in short bursts)
- **VAD threshold:** tuned for phone audio
- **Critical:** STT MUST reject non-English audio. If lead speaks Hindi/Tamil/etc., the agent uses the language-switch script in §3.3.

### 8.5 English-Only Enforcement
This is enforced at three layers:
1. **System prompt:** explicit instruction "Respond in English only."
2. **STT config:** `language=en-IN` only.
3. **Output validation:** post-LLM regex/script check rejects any response containing Devanagari, Tamil, or other non-Latin scripts before sending to TTS.

---
