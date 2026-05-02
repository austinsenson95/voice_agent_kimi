# Bootstrap Summary — Hamza AI Phone Agent v0.3 (DEMO)

> Generated after Phase 1–4 completion of the v0.3 DEMO build.

---

## Files Generated in `backend/context/`

| File | Lines | Demo Tags | Source Attributions |
|---|---|---|---|
| `persona.md` | 218 | 49 | 22 |
| `battle_card.md` | 100 | 15 | 2 |
| `objections.md` | 69 | 1 | 0 |
| `state_prompts.md` | 93 | 1 | 0 |
| `memory_schema.md` | 63 | 1 | 0 |
| `voice_persona.md` | 44 | 3 | 0 |
| `whatsapp_persona.md` | 43 | 1 | 0 |
| `calendar_rules.md` | 35 | 1 | 0 |
| `compliance.md` | 39 | 3 | 1 |
| `eval_cases.md` | 64 | 1 | 0 |
| `banned_phrases.json` | 31 | — | — |
| **Total (derived)** | **799** | **76** | **25** |

## Files Modified in `backend/app/`

| File | Δ Lines | Change |
|---|---|---|
| `config.py` | +216 | Added DEMO_MODE, whitelist, context loaders, banned phrases, language policy, script regex, production guard, can_call, build_system_prompt, build_objection_prompt, _extract_state_block, _format_memory, validate_response_english_only, validate_response_no_banned_phrases, validate_response, startup_banner |
| `state_machine.py` | +5 | Import _config_build_system_prompt + validate_response; TODO updated |
| `objections.py` | +2 | Import build_objection_prompt + validate_response; TODO updated |
| `voice_pipeline.py` | +1 | Import NON_ENGLISH_SCRIPT_PATTERN |
| `routes.py` | +1 | Import can_call + TODO |
| `main.py` | +2 | Import startup_banner; call it in lifespan |
| `battle_card.py` | 0 | BATTLE_CARD import already present |
| `calendar.py` | 0 | CALENDAR_RULES import already present |
| `memory.py` | 0 | MEMORY_SCHEMA import already present |
| `whatsapp.py` | 0 | WHATSAPP_PERSONA import already present |
| **Total** | **+239 / −5** | 10 files touched |

## Sanity Check Results

| Check | Result | Notes |
|---|---|---|
| 4.1 Compile check | **PASS** | `python3 -m compileall app/` — 0 errors |
| 4.2 Prompt assembly | **PASS** | `build_system_prompt("DISCOVERY", fake_lead)` assembled correctly. Contains "Aisha", "English only", "[DEMO MODE", persona, battle card, and lead context. **~5,910 tokens** (under 12k threshold). |
| 4.3 Demo-mode guard | **PASS** | `DEMO_MODE=false` → import exits with fatal error listing offending files. `can_call` rejects non-whitelisted numbers in demo; approves whitelisted numbers. |
| 4.4 English-only validator | **PASS** | Latin-script English passes. Devanagari fails. Hinglish in Latin script passes (documented gap — relies on LLM instruction). |
| 4.5 Banned-phrase validator | **PASS** | Corporate jargon / AI clichés correctly rejected. Clean responses pass. |

## Demo-Tag Inventory (Production Blockers)

**Total `[DEMO: ...]` tags in derived files: 76**

Before flipping `DEMO_MODE=false`, every tag below must be replaced with verified content from Hamza or replaced with `[FILL: ...]` if not yet available.

### Critical blockers (high business risk if wrong)

| # | Location | What needs verification |
|---|---|---|
| 1 | `persona.md` §1.1 | Origin story — sales-call version |
| 2 | `persona.md` §1.1 | Podcast name + Instagram handle |
| 3 | `persona.md` §1.4 | **FBE offer format, duration, price, payment plan, outcome** |
| 4 | `persona.md` §1.4 | FBE inclusions list (sessions, calls, community, refund) |
| 5 | `persona.md` §1.5 | Lead sources, pre-call assets, agent role, handoff point, success definitions |
| 6 | `persona.md` §1.3 | ICP age range, income band, current state, desired state, all disqualifiers, all yellow flags |
| 7 | `persona.md` §2.1 | All 5 core values |
| 8 | `persona.md` §2.2 | Voice & tone positions (empathetic↔challenging, polished↔raw, humorous↔serious) |
| 9 | `persona.md` §2.3 | Filler patterns |
| 10 | `persona.md` §2.4 | Mission, promise, anti-promise |
| 11 | `persona.md` §3.1 | **Agent name "Aisha"** — confirm or change |
| 12 | `persona.md` §3.1 | Agent backstory |
| 13 | `persona.md` §3.3 | Active listening cues |
| 14 | `persona.md` §3.3 | English-only language-switch script |
| 15 | `persona.md` §4.4 | All 6 discovery questions |

### Battle card & objections

| # | Location | What needs verification |
|---|---|---|
| 16 | `battle_card.md` §5.1 | All 5 pain-point reframes |
| 17 | `battle_card.md` §5.2 | Failed-path articulations |
| 18 | `battle_card.md` §5.3 | All 4 differentiator reframes |
| 19 | `battle_card.md` §5.4 | **All 7 proof-point one-liners** — confirm client names are clearable for phone calls |
| 20 | `battle_card.md` §5.5 | **FBE pricing, payment plan terms, discount script, refund window** |
| 21 | `objections.md` §6 | All 8 objection scripts (price, spouse, think-about-it, brochure, $99-vs-FBE, tried-other-coaches, not-technical, no-skill) |

### Voice, calendar, compliance

| # | Location | What needs verification |
|---|---|---|
| 22 | `voice_persona.md` §8.1 | TTS engine choice (ElevenLabs) + voice ID |
| 23 | `voice_persona.md` §8.2 | Pace WPM target |
| 24 | `calendar_rules.md` §10.2 | Working hours, buffer, max bookings/day, blackout windows |
| 25 | `compliance.md` §11.1 | AI disclosure script |
| 26 | `compliance.md` §11.1 | Recording disclosure script |

## Verified Content Already in Place (survives demo→production)

The following `<!-- source: ... -->` attributed content is real and does NOT need replacement:

- Hamza C name, "Freedom Business Coach and Podcaster" title
- Business name: Hamza C Coaching™
- Niche description (students, professionals, freelancers)
- Core promise: "Build a skill-based business that gives you time, money and independence"
- "The New Freedom Business Era" headline framing
- 250+ clients served
- Self-built 6-figure business in 3 months
- 30-day money-back guarantee on $99 product
- $99 "1 Hour Digital Product Builder" product details
- Website, Gumroad links
- 6 named client testimonials (Ananya, Shanthi, Mahalakshmi, Sejal, Eshita, Sapna)
- Indian market focus, INR pricing evidence
- Signature vocabulary extracted from website ("freedom business", "skill-based business", "9 to 5", etc.)

## Top 5 Next Actions (for Austin)

1. **Confirm FBE pricing, format, and inclusions with Hamza.**
   This is the highest-risk demo content — the agent will quote ₹1,49,000. Get Hamza's exact offer structure, then update `persona.md` §1.4 and `battle_card.md` §5.5.

2. **Confirm client-name clearance for phone calls.**
   The 6 testimonials are public on the website, but phone-call usage is a different surface. Get explicit OK before production.

3. **Choose Aisha's voice or rename the agent.**
   Update `voice_persona.md` §8.1 with the actual ElevenLabs voice ID, or change the agent name in `persona.md` §3.1.

4. **Verify the 8 objection scripts with Hamza.**
   These are written in a Hamza-style voice but are not his words. A 20-minute review call to confirm / tweak the price and spouse scripts would close the biggest gap.

5. **Set the DEMO_WHITELIST_NUMBERS env var before any test calls.**
   In `.env`: `DEMO_MODE=true` and `DEMO_WHITELIST_NUMBERS=+919999999999` (your test number). The agent will refuse to call any other number while in demo mode.

---

*Bootstrap v0.3 DEMO completed. Agent is functional for personality testing. Production cutover requires replacing all `[DEMO: ...]` tags with verified content, then setting `DEMO_MODE=false`.*
