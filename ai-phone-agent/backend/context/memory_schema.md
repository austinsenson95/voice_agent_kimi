---
source: HAMZA_AGENT_CONTEXT_PACK_v0.3_DEMO.md §7
loaded_by: memory_schema.py
version: 0.3-demo
demo_tags: 0
source_attributions: 0
language_policy: english_only
---

> **DEMO MODE NOTICE** — see full notice in `HAMZA_AGENT_CONTEXT_PACK_v0.3_DEMO.md` §0.
> All `[DEMO: ...]` content is fabricated scaffolding. Do not use for production calls.

## 7. Memory & Context Persistence

### 7.1 Per-Lead Memory Schema
```yaml
lead:
  id: uuid
  name: str
  phone: str
  source: typeform_application | gumroad_99_buyer | podcast | instagram | referral
  first_contacted: datetime

  profile:
    icp_fit: 0-10
    skill_direction: str
    current_role: str
    stated_goal: str
    stated_pain: str

  call_history:
    - call_id: uuid
      date: datetime
      type: cold|warm|recovery|nurture
      duration_sec: int
      transcript_url: str
      qualification_scores: {...}
      objections_raised: [str]
      outcome: booked|parked|disqualified|hostile
      next_action: str
      next_action_due: datetime

  notes:
    facts_learned: [str]
    sensitivities: [str]
    promises_made: [str]
```

### 7.2 What to Remember Across Calls
- Every fact volunteered (family, business name, specific frustrations).
- Promises Aisha made.
- Topics that triggered emotion.
- Exact framing the lead used for their pain — mirror back next call.

### 7.3 What NOT to Surface Twice
- Same proof point.
- Same opener / pattern interrupt.
- Any objection lead has moved past.

### 7.4 Privacy
- Never reference memory in surveillance-y way. "Last time you mentioned ___" ✓ — "I see in our records that ___" ✗.

---
