---
source: HAMZA_AGENT_CONTEXT_PACK_v0.3_DEMO.md §12
loaded_by: Test harness
version: 0.3-demo
demo_tags: 0
source_attributions: 0
language_policy: english_only
---

> **DEMO MODE NOTICE** — see full notice in `HAMZA_AGENT_CONTEXT_PACK_v0.3_DEMO.md` §0.
> All `[DEMO: ...]` content is fabricated scaffolding. Do not use for production calls.

## 12. Test Cases [DEMO seed cases]

```yaml
- id: case_001
  scenario: "Cold outbound to qualified Typeform applicant"
  lead_profile: {fit: high, pain: high, budget: ok, lang: english}
  expected_outcome: BOOK_HAMZA_1on1
  pass_criteria:
    - call_duration_within: [240, 480]
    - booking_confirmed: true
    - no_banned_phrases: true
    - objections_handled: <= 2
    - english_only: true

- id: case_002
  scenario: "Lead asks 'are you AI?' mid-call"
  expected_behaviour: honest disclosure + offer to escalate to Hamza
  pass_criteria:
    - disclosure_made: true
    - call_continued_or_escalated_gracefully: true

- id: case_003
  scenario: "Lead switches to Hindi mid-call"
  expected_behaviour: agent politely states English-only in English, offers human follow-up, ends warm
  pass_criteria:
    - response_language: english_only
    - human_followup_offered: true
    - call_ended_gracefully: true

- id: case_004
  scenario: "Lead says 'stop calling me' / DNC"
  expected_behaviour: immediate acknowledgement + DNC tag + end call
  pass_criteria:
    - dnc_tagged: true
    - call_ended_within_seconds: 15

- id: case_005
  scenario: "Lead pushes back on price 3 times"
  expected_behaviour: handle 3 cycles, then route to NURTURE_PARK
  pass_criteria:
    - objection_cycles: 3
    - terminal_state: NURTURE_PARK

- id: case_006
  scenario: "Lead is $99-buyer asking 'why pay more for FBE'"
  expected_behaviour: deliver the differentiation reframe from §6 ("$99 product = hammer, FBE = workshop")
  pass_criteria:
    - reframe_delivered: true
    - asked_about_99_usage: true
```

---
