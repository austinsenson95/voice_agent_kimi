# TASK: Build the Hamza AI Phone Agent (DEMO Mode)

You are working in the `voice-agent-kimi/backend` repo. The goal is end-to-end personality testing of the voice agent before any real calls are made. This task generates the context layer, wires the runtime, and adds production-blocking safeguards.

---

## Inputs

- **Master context pack:** `backend/context/HAMZA_AGENT_CONTEXT_PACK_v0.3_DEMO.md`
- **Existing modules:** `backend/app/{battle_card,calendar,config,llm_provider,memory,objections,routes,schemas,state_machine,voice_pipeline,whatsapp}.py`

---

## Critical Constraints

These are non-negotiable. The agent must NOT pass sanity checks if any are violated.

### C1. DEMO_MODE
- The pack contains fabricated content tagged `[DEMO: ...]`.
- A `DEMO_MODE` env var (default `true`) must be wired in `config.py`.
- When `DEMO_MODE=true`:
  - Agent runs against test numbers only (whitelisted in env).
  - Outbound calls to non-whitelisted numbers must be REJECTED at the routing layer with a clear error.
  - Every call log line, every system prompt, and the startup banner must include `[DEMO MODE]`.
- When `DEMO_MODE=false`:
  - On startup, `config.py` MUST scan all loaded `.md` context files for the literal string `[DEMO:` — if found, refuse to start with a fatal error listing every offending file.

### C2. English-only
- Enforced at THREE layers:
  - **LLM:** every system prompt explicitly contains "Respond in English only. Do not use Hindi, Hinglish, transliteration, or any other language."
  - **STT:** Deepgram (or chosen provider) configured with `language=en-IN` only.
  - **Post-LLM validation:** before sending to TTS, run `if re.search(r'[\u0900-\u097F\u0B80-\u0BFF\u0C00-\u0C7F\u0980-\u09FF]', response): reject_and_regenerate()` — covers Devanagari, Tamil, Telugu, Bengali. If a regenerated response also fails, fall back to the language-switch script in §3.3 of the pack and end the call gracefully.
- If a lead speaks non-English, agent uses the language-switch script and ends the call warmly.

### C3. Source-attribution preservation
- All `<!-- source: ... -->` HTML comments in the pack are FACTS extracted from `hamzaccoaching.com` and confirmed by the human operator.
- These comments MUST be preserved in derived files. Do not strip them.
- All `[DEMO: ...]` tags MUST also be preserved in derived files for visibility during dev.

### C4. Do not invent
- This pack is the ONLY source of truth. If a field is missing, leave it missing. Do not generate additional `[DEMO: ...]` content.
- If you find ambiguity that blocks generation, stop and ask.

---

## Phase 1 — Context File Generation

### 1.1 Read the master pack end-to-end
Read `HAMZA_AGENT_CONTEXT_PACK_v0.3_DEMO.md`. Pay particular attention to:
- §0 (DEMO MODE notice)
- §3.1 (Mode B identity, agent name "Aisha")
- §3.3 + §11.4 (English-only enforcement)
- §13 (file mapping table)

### 1.2 Generate `backend/context/` files
Per the §13 mapping in the pack:

- `persona.md` ← §2 + §3 distilled
- `battle_card.md` ← §5
- `objections.md` ← §6 (preserve {Acknowledge → Reframe → Bridge → Re-engage} structure)
- `state_prompts.md` ← per-state LLM prompt templates derived from §4
- `memory_schema.md` ← §7
- `voice_persona.md` ← §8
- `whatsapp_persona.md` ← §9
- `calendar_rules.md` ← §10
- `compliance.md` ← §11
- `eval_cases.md` ← §12

### 1.3 Frontmatter for every derived file
```yaml
---
source: HAMZA_AGENT_CONTEXT_PACK_v0.3_DEMO.md §<section>
loaded_by: <module>.py
version: 0.3-demo
demo_tags: <count of [DEMO: occurrences in this file>
source_attributions: <count of <!-- source: comments in this file>
language_policy: english_only
---
```

### 1.4 State prompts — special structure
`state_prompts.md` should contain ONE prompt block per state from §4.3:

```markdown
## STATE: GREETING
**Entry condition:** call connected
**LLM prompt template:**
> You are Aisha, on Hamza's team. The call has just connected. Greet the lead by name, identify yourself ("Aisha from Hamza's team"), state the reason for the call in one sentence, and ask permission to continue. English only. 1–2 sentences max.

**Allowed transitions:** PERMISSION_CHECK
**Timeout (10s no response):** repeat once, then END_GRACEFUL.
**Failure fallback:** END_GRACEFUL.

---

## STATE: PERMISSION_CHECK
... (continue for all states in §4.3)
```

### 1.5 Banned-phrase list as a code-loadable artifact
Generate `backend/context/banned_phrases.json` from §2.3 of the pack:

```json
{
  "corporate_jargon": ["leverage", "synergy", "circle back", "stakeholders", "deliverables", "value-add"],
  "ai_coach_cliches": ["unlock your potential", "unleash", "transform your life", "level up", "manifest"],
  "fake_urgency": ["limited time", "only X seats left"],
  "sycophancy": ["great question", "amazing", "I love that"],
  "hedge_words": ["kind of", "sort of", "maybe", "I guess"]
}
```

This file is loaded by a post-LLM validator that flags or regenerates responses containing any banned phrase.

---

## Phase 2 — Runtime Wiring (`config.py`)

### 2.1 Constants and loaders

```python
import os
import re
import json
import sys
from pathlib import Path

CONTEXT_DIR = Path(__file__).parent.parent / "context"

# DEMO_MODE control
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
DEMO_WHITELIST_NUMBERS = set(
    n.strip() for n in os.getenv("DEMO_WHITELIST_NUMBERS", "").split(",") if n.strip()
)

# Load context files
PERSONA           = (CONTEXT_DIR / "persona.md").read_text()
BATTLE_CARD       = (CONTEXT_DIR / "battle_card.md").read_text()
OBJECTIONS        = (CONTEXT_DIR / "objections.md").read_text()
STATE_PROMPTS     = (CONTEXT_DIR / "state_prompts.md").read_text()
MEMORY_SCHEMA     = (CONTEXT_DIR / "memory_schema.md").read_text()
VOICE_PERSONA     = (CONTEXT_DIR / "voice_persona.md").read_text()
WHATSAPP_PERSONA  = (CONTEXT_DIR / "whatsapp_persona.md").read_text()
CALENDAR_RULES    = (CONTEXT_DIR / "calendar_rules.md").read_text()
COMPLIANCE        = (CONTEXT_DIR / "compliance.md").read_text()

with open(CONTEXT_DIR / "banned_phrases.json") as f:
    BANNED_PHRASES = json.load(f)
BANNED_FLAT = [p for cat in BANNED_PHRASES.values() for p in cat]

# Language policy
LANGUAGE_POLICY_INSTRUCTION = (
    "Respond in English only. Do not use Hindi, Hinglish, transliteration, "
    "or any other language. If the lead speaks another language, follow "
    "the language-switch script in the persona."
)

# Non-Latin script regex (Devanagari, Tamil, Telugu, Bengali)
NON_ENGLISH_SCRIPT_PATTERN = re.compile(
    r'[\u0900-\u097F\u0B80-\u0BFF\u0C00-\u0C7F\u0980-\u09FF]'
)
```

### 2.2 Production-mode demo-tag guard

```python
def _enforce_no_demo_in_production():
    if DEMO_MODE:
        return
    offenders = []
    for md_file in CONTEXT_DIR.glob("*.md"):
        text = md_file.read_text()
        if "[DEMO:" in text:
            offenders.append(str(md_file))
    if offenders:
        print(
            "FATAL: DEMO_MODE=false but [DEMO:] tags still present in context files:\n  "
            + "\n  ".join(offenders),
            file=sys.stderr,
        )
        sys.exit(1)

_enforce_no_demo_in_production()
```

### 2.3 Outbound call routing guard

```python
def can_call(phone_number: str) -> tuple[bool, str]:
    if DEMO_MODE:
        if phone_number not in DEMO_WHITELIST_NUMBERS:
            return False, f"DEMO_MODE: {phone_number} not in whitelist"
        return True, "DEMO_MODE: whitelisted"
    # Production checks: DNC list, consent records, etc.
    return True, "PRODUCTION"
```

Wire this into the outbound dispatch path in `routes.py` or wherever calls are initiated. Reject with a clear error if `can_call` returns `False`.

### 2.4 System prompt builder

```python
def build_system_prompt(state: str, lead_memory: dict) -> str:
    demo_banner = "[DEMO MODE — fabricated context, test calls only]\n\n" if DEMO_MODE else ""
    return f"""{demo_banner}{PERSONA}

{LANGUAGE_POLICY_INSTRUCTION}

{COMPLIANCE}

CURRENT STATE: {state}
{_extract_state_block(STATE_PROMPTS, state)}

RELEVANT BATTLE CARD:
{BATTLE_CARD}

LEAD CONTEXT:
{_format_memory(lead_memory)}
"""

def build_objection_prompt(objection_text: str, lead_memory: dict) -> str:
    return f"""{PERSONA}

{LANGUAGE_POLICY_INSTRUCTION}

OBJECTION HANDLING TASK:
The lead just said: "{objection_text}"

Respond using the Acknowledge → Reframe → Bridge → Re-engage pattern from:
{OBJECTIONS}

LEAD CONTEXT:
{_format_memory(lead_memory)}
"""
```

Helper functions `_extract_state_block` and `_format_memory` should also be implemented — keep them simple, parsing the state-marker headings in `state_prompts.md` and rendering memory dict as a readable bullet list.

### 2.5 Output validators

```python
def validate_response_english_only(response: str) -> tuple[bool, str]:
    if NON_ENGLISH_SCRIPT_PATTERN.search(response):
        return False, "non_latin_script_detected"
    return True, ""

def validate_response_no_banned_phrases(response: str) -> tuple[bool, str]:
    lower = response.lower()
    hits = [p for p in BANNED_FLAT if p.lower() in lower]
    if hits:
        return False, f"banned_phrases: {hits}"
    return True, ""

def validate_response(response: str) -> tuple[bool, list[str]]:
    failures = []
    ok1, msg1 = validate_response_english_only(response)
    if not ok1: failures.append(msg1)
    ok2, msg2 = validate_response_no_banned_phrases(response)
    if not ok2: failures.append(msg2)
    return (len(failures) == 0, failures)
```

The LLM call wrapper in `llm_provider.py` should call `validate_response` and regenerate (max 2 retries) if validation fails. After 2 failures, fall back to a safe templated response (e.g. "Let me have Hamza follow up with you directly on this — what's the best time?").

### 2.6 Startup banner

```python
def startup_banner():
    mode = "DEMO" if DEMO_MODE else "PRODUCTION"
    print(f"""
╔══════════════════════════════════════════════════╗
║  voice-agent-kimi  —  Mode: {mode:<20}║
║  Language policy: ENGLISH ONLY                   ║
║  Whitelist: {len(DEMO_WHITELIST_NUMBERS)} number(s)                          ║
╚══════════════════════════════════════════════════╝
""")
```

Call this from `main.py` on startup.

---

## Phase 3 — Module Hookups

For each consumer module, add the import and a `# TODO` marker. Do NOT refactor existing logic.

### 3.1 `state_machine.py`
```python
from app.config import build_system_prompt, validate_response
# TODO: integrate build_system_prompt(state, lead_memory) into LLM call dispatch
```

### 3.2 `objections.py`
```python
from app.config import build_objection_prompt, validate_response
# TODO: integrate build_objection_prompt for each detected objection
```

### 3.3 `battle_card.py`
```python
from app.config import BATTLE_CARD
# TODO: surface relevant proof_points from BATTLE_CARD based on lead profile tags
```

### 3.4 `memory.py`
```python
from app.config import MEMORY_SCHEMA
# TODO: validate writes against schema in MEMORY_SCHEMA
```

### 3.5 `voice_pipeline.py`
```python
from app.config import VOICE_PERSONA, NON_ENGLISH_SCRIPT_PATTERN
# TODO: configure STT with language=en-IN only
# TODO: configure TTS engine + voice_id from VOICE_PERSONA
# TODO: reject STT transcripts containing non-Latin scripts before LLM dispatch
```

### 3.6 `whatsapp.py`
```python
from app.config import WHATSAPP_PERSONA
# TODO: load templates from WHATSAPP_PERSONA for post-call/no-show/reminder/nurture flows
```

### 3.7 `calendar.py`
```python
from app.config import CALENDAR_RULES
# TODO: parse working hours, buffer, max bookings/day from CALENDAR_RULES
```

### 3.8 `routes.py`
```python
from app.config import can_call
# TODO: gate outbound dispatch with can_call(phone) — reject with 403 if False
```

---

## Phase 4 — Sanity Checks (always run)

### 4.1 Compile check
- `python -m compileall backend/app/` — must succeed.
- `from app.config import build_system_prompt, can_call, validate_response` — must succeed in REPL.

### 4.2 Prompt assembly check
- Construct fake `lead_memory = {"name": "Test", "phone": "+919999999999", "stated_pain": "stuck in 9-to-5"}`.
- Call `build_system_prompt(state="DISCOVERY", lead_memory=fake)`.
- Assert: output is non-empty, contains "Aisha", contains "English only", contains "[DEMO MODE", contains content from `persona.md`, contains content from `state_prompts.md` for DISCOVERY.
- Print char count + estimated token count (chars/4). Flag if >12,000 tokens.

### 4.3 Demo-mode guard checks
- Set `DEMO_MODE=false` in env, attempt to import config — assert it exits with the demo-tag error.
- Set `DEMO_MODE=true`, call `can_call("+919999999999")` against an empty whitelist — assert returns `(False, ...)`.
- Add `+919999999999` to whitelist, call again — assert returns `(True, ...)`.

### 4.4 English-only validators
- `validate_response_english_only("Hello, how are you?")` → `(True, "")`.
- `validate_response_english_only("नमस्ते, आप कैसे हैं?")` → `(False, ...)`.
- `validate_response_english_only("Hello yaar, kaise ho?")` → `(True, "")` (Hinglish in Latin script passes the regex; rely on LLM-level instruction + LLM judgement here, document this gap in summary).

### 4.5 Banned-phrase validator
- `validate_response_no_banned_phrases("Let me leverage this opportunity to circle back")` → `(False, ...)`.
- `validate_response_no_banned_phrases("Yeah, makes sense. What's the bigger picture?")` → `(True, "")`.

### 4.6 Final summary
Write `backend/context/BOOTSTRAP_SUMMARY.md` with:
- Files generated (line counts).
- Files modified in `app/` (diff stats).
- Demo-tag count per derived file.
- Source-attribution count per derived file.
- Sanity check results.
- Top 5 next actions for the human operator (Austin), in priority order — including the explicit list of `[DEMO: ...]` items in `HAMZA_AGENT_CONTEXT_PACK_v0.3_DEMO.md` that must be replaced with real Hamza inputs before flipping `DEMO_MODE=false`.

---

## What NOT to Do

- Do not modify `routes.py`, `schemas.py`, `main.py` beyond the explicit hooks listed in Phase 3.
- Do not change the existing state machine topology in `state_machine.py`. If §4.3 of the pack contradicts the existing code, flag it in `BOOTSTRAP_SUMMARY.md` — do not silently rewrite either side.
- Do not invent additional `[DEMO: ...]` content. If a slot is empty, leave it empty.
- Do not commit secrets, API keys, or PII. The whitelist env var should be set in `.env.local`, not committed.
- Do not write code that calls external APIs (ElevenLabs, Deepgram, Cal.com) during this task. Configuration only — actual integration is a separate task.
- Do not output anything in any language other than English in any context file, code comment, log line, or banner.

---

## Output expectations

```
backend/
├── app/
│   ├── battle_card.py            # +1 import, +1 TODO
│   ├── calendar.py               # +1 import, +1 TODO
│   ├── config.py                 # +DEMO_MODE wiring, +constants, +validators, +builders, +guards
│   ├── memory.py                 # +1 import, +1 TODO
│   ├── objections.py             # +1 import, +1 TODO
│   ├── routes.py                 # +1 import, +1 TODO (can_call gate)
│   ├── state_machine.py          # +1 import, +1 TODO
│   ├── voice_pipeline.py         # +imports, +3 TODOs
│   └── whatsapp.py               # +1 import, +1 TODO
└── context/
    ├── HAMZA_AGENT_CONTEXT_PACK_v0.3_DEMO.md   # (input, untouched)
    ├── persona.md
    ├── battle_card.md
    ├── objections.md
    ├── state_prompts.md
    ├── memory_schema.md
    ├── voice_persona.md
    ├── whatsapp_persona.md
    ├── calendar_rules.md
    ├── compliance.md
    ├── eval_cases.md
    ├── banned_phrases.json
    └── BOOTSTRAP_SUMMARY.md
```

---

## Begin

1. Read the master pack.
2. Phase 1 — generate context files.
3. Phase 2 — wire `config.py`.
4. Phase 3 — hook up consumer modules.
5. Phase 4 — sanity checks + summary.

If anything in the pack is ambiguous or contradicts the existing code, **stop and ask** — do not guess.
