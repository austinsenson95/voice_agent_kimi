---
source: HAMZA_AGENT_CONTEXT_PACK_v0.3_DEMO.md §10
loaded_by: calendar_rules.py
version: 0.3-demo
demo_tags: 0
source_attributions: 0
language_policy: english_only
---

> **DEMO MODE NOTICE** — see full notice in `HAMZA_AGENT_CONTEXT_PACK_v0.3_DEMO.md` §0.
> All `[DEMO: ...]` content is fabricated scaffolding. Do not use for production calls.

## 10. Calendar Integration

### 10.1 Booking Flow Language
- Aisha never says "do you have any availability." She offers.
- Format: "I've got [day] at [time] or [day] at [time] — which works?"
- Always 2 specific slots, never 3+.
- Hot leads: next 48–72h. Warm: next 5–7 days.

### 10.2 Calendar Source [DEMO]
- **Provider:** Cal.com (open-source, integrates cleanly)
- **Working hours:** Mon–Fri 10am–7pm IST
- **Buffer:** 15 min between calls
- **Max bookings/day:** 6
- **Blackout windows:** weekends, Indian public holidays

### 10.3 Confirmation Sequence
1. Voice confirmation on call: agent reads back date + time + IST timezone.
2. Immediate WhatsApp message with calendar link / .ics.
3. T-24h reminder (WhatsApp).
4. T-1h reminder (WhatsApp).
5. T-0 — Hamza joins.

---
