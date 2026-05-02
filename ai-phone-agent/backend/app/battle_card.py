"""Business context injection system ("Battle Cards") for the AI Phone Agent.

The *BattleCard* class aggregates everything the AI needs to know about the
business it represents — name, owner, pricing, testimonials, ideal client,
etc. — and formats it into LLM-friendly system prompts.

Usage::

    from app.battle_card import BattleCard

    bc = BattleCard()
    system_prompt = bc.format_for_llm(state="PITCH")
    # Pass *system_prompt* to the LLM as the system message.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.objections import (
    detect_objection,
    get_objection_response,
    get_all_objections,
    should_escalate,
)
from app.config import BATTLE_CARD

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State definitions
# ---------------------------------------------------------------------------

_STATE_PROMPTS: dict[str, str] = {
    "OPENING": (
        "## CURRENT STATE: OPENING\n"
        "- Greet the caller warmly in Hindi-English mix (Hinglish) if they seem comfortable.\n"
        "- Introduce yourself as the AI assistant for {business_name}.\n"
        "- Ask for their name and what brought them to the call today.\n"
        "- Keep it brief — 2-3 sentences max. Sound human, not robotic.\n"
        "- If they seem rushed, get to the point quickly."
    ),
    "DISCOVERY": (
        "## CURRENT STATE: DISCOVERY\n"
        "- Ask open-ended questions about their goals, challenges, and timeline.\n"
        "- Listen more than you talk. Use phrases like \"I see\", \"That makes sense\", \"Go on\".\n"
        "- Try to uncover the *real* pain — not just surface-level problems.\n"
        "- If they mention revenue, team issues, or feeling stuck, probe deeper.\n"
        "- Remember: you're a consultant, not a salesperson."
    ),
    "PITCH": (
        "## CURRENT STATE: PITCH\n"
        "- Connect their stated problems directly to {owner_name}'s solution.\n"
        "- Share ONE relevant testimonial that matches their situation.\n"
        "- Mention the {session_duration} session format and {pricing_range} pricing briefly.\n"
        "- Don't oversell. Let the testimonial and framework do the work.\n"
        "- End by asking if they'd like to book a session."
    ),
    "OBJECTION": (
        "## CURRENT STATE: OBJECTION\n"
        "- Handle objections with empathy. Never be defensive or pushy.\n"
        "- Use the objection response provided below as your guide.\n"
        "- Acknowledge their concern genuinely before offering a perspective.\n"
        "- If they push back twice on the same point, offer to connect them with a human.\n"
        "- Your tone: understanding, patient, confident but not forceful."
    ),
    "CLOSE": (
        "## CURRENT STATE: CLOSE\n"
        "- Ask directly if they'd like to book a session. Make it easy.\n"
        "- Offer 3 specific time slots from the available list.\n"
        "- If they hesitate, reduce friction: \"No payment needed to book\".\n"
        "- Once they agree, collect: name, phone, email, preferred slot.\n"
        "- Confirm everything back to them clearly before ending."
    ),
}

# ---------------------------------------------------------------------------
# BattleCard class
# ---------------------------------------------------------------------------


class BattleCard:
    """Aggregates business configuration and formats it for LLM consumption.

    Configuration is loaded from environment variables (see module docstring).
    Callers can override any field after instantiation via attribute assignment.

    Attributes:
        business_name: Display name of the coaching / consulting business.
        business_owner: Name of the founder / lead coach.
        service_description: One-line description of the core service.
        pricing_range: Human-readable pricing (e.g. "Rs. 15,000 - 50,000 / month").
        session_duration: Session length in human terms (e.g. "45 minutes").
        ideal_client: One-liner describing the perfect-fit customer.
        unique_selling_prop: What makes this business different.
        testimonial_1: First client testimonial string.
        testimonial_2: Second client testimonial string.
        website: Business website URL.
        calendar_link: Cal.com (or other) booking URL.
        whatsapp_number: Business WhatsApp contact number.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        """Load configuration from environment variables."""
        self.business_name: str = os.getenv("BUSINESS_NAME", "Your Coaching Business")
        self.business_owner: str = os.getenv("BUSINESS_OWNER", "Your Name")
        self.service_description: str = os.getenv(
            "SERVICE_DESCRIPTION", "1-on-1 executive coaching for business owners"
        )
        self.pricing_range: str = os.getenv("PRICING_RANGE", "Rs. 15,000 - 50,000 per month")
        self.session_duration: str = os.getenv("SESSION_DURATION", "45 minutes")
        self.ideal_client: str = os.getenv(
            "IDEAL_CLIENT", "Business owners doing 50L-5Cr revenue feeling stuck"
        )
        self.unique_selling_prop: str = os.getenv(
            "UNIQUE_SELLING_PROP", "Proven framework used by 200+ Indian business owners"
        )
        self.testimonial_1: str = os.getenv(
            "TESTIMONIAL_1", '"Changed my business completely" - Raj, Mumbai'
        )
        self.testimonial_2: str = os.getenv(
            "TESTIMONIAL_2", '"Best investment I made" - Priya, Bangalore'
        )
        self.website: str = os.getenv("WEBSITE", "https://yourcoaching.com")
        self.calendar_link: str = os.getenv(
            "CALENDAR_LINK", "https://cal.com/yourname/intro"
        )
        self.whatsapp_number: str = os.getenv("WHATSAPP_NUMBER", "+919999999999")

        logger.info("BattleCard loaded for business: %s", self.business_name)

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------

    @property
    def _context(self) -> dict[str, str]:
        """Return a dict of all business variables for template substitution."""
        return {
            "business_name": self.business_name,
            "owner_name": self.business_owner,
            "service_description": self.service_description,
            "pricing_range": self.pricing_range,
            "session_duration": self.session_duration,
            "ideal_client": self.ideal_client,
            "unique_selling_prop": self.unique_selling_prop,
            "testimonial_1": self.testimonial_1,
            "testimonial_2": self.testimonial_2,
            "website": self.website,
            "calendar_link": self.calendar_link,
            "whatsapp_number": self.whatsapp_number,
        }

    def get_context_prompt(self) -> str:
        """Return a formatted business-context string suitable for LLM system prompts.

        The output is structured with clear sections and bullet points so the
        model can easily reference specific facts during the conversation.
        """
        ctx = self._context

        prompt = (
            "# BUSINESS CONTEXT\n"
            "You are the AI phone assistant for {business_name}, founded by {owner_name}.\n"
            "Use the following information to sound knowledgeable and authentic.\n\n"
            "## Business Info\n"
            "- **Business Name**: {business_name}\n"
            "- **Owner / Lead Coach**: {owner_name}\n"
            "- **Service**: {service_description}\n"
            "- **Session Duration**: {session_duration}\n"
            "- **Pricing**: {pricing_range}\n"
            "- **Website**: {website}\n"
            "- **Booking Link**: {calendar_link}\n"
            "- **WhatsApp**: {whatsapp_number}\n\n"
            "## Ideal Client\n"
            "{ideal_client}\n\n"
            "## Unique Selling Proposition\n"
            "{unique_selling_prop}\n\n"
            "## Testimonials\n"
            "1. {testimonial_1}\n"
            "2. {testimonial_2}\n\n"
            "## Personality & Tone Instructions\n"
            "- Speak like a warm, knowledgeable Indian business consultant.\n"
            "- Use Hinglish (Hindi + English) naturally when the caller does.\n"
            "- Be confident but never pushy. Respect the caller's time and decisions.\n"
            "- Keep responses concise — 2-3 sentences unless explaining something complex.\n"
            "- Always sound like you genuinely care about their success.\n"
            "- If you don't know something, be honest and offer to connect them with {owner_name}.\n"
            "- Never make up facts, prices, or testimonials not listed above.\n"
            "- Your goal is to help them see if {business_name} is the right fit — not to hard-sell.\n"
        ).format(**ctx)

        return prompt

    def get_state_prompt(self, state: str) -> str:
        """Return state-specific instructions for the given conversation *state*.

        Args:
            state: One of ``OPENING``, ``DISCOVERY``, ``PITCH``, ``OBJECTION``, ``CLOSE``.

        Returns:
            A formatted string with state-specific guidance.

        Raises:
            ValueError: If *state* is not a recognised state.
        """
        state = state.upper()
        template = _STATE_PROMPTS.get(state)
        if template is None:
            raise ValueError(
                f"Unknown state: {state!r}. "
                f"Valid states: {', '.join(_STATE_PROMPTS)}"
            )
        return template.format(**self._context)

    def find_objection_response(self, user_text: str) -> str | None:
        """Check *user_text* against known objection triggers and return a response.

        This is a convenience wrapper around :func:`objections.detect_objection`
        that automatically substitutes business context variables into the
        response template.

        Args:
            user_text: Raw caller text / transcript.

        Returns:
            Rendered response string, or ``None`` when no objection is detected.
        """
        obj = detect_objection(user_text)
        if obj is None:
            return None

        response = get_objection_response(obj["id"], self._context)
        logger.info("Objection '%s' detected, returning response", obj["id"])
        return response

    def format_for_llm(self, state: str = "OPENING") -> str:
        # TODO: integrate BATTLE_CARD context constant into prompt assembly
        """Combine business context, state instructions, and objection guide.

        This is the **primary entry-point** for generating the LLM system prompt.

        Args:
            state: Conversation state (default ``OPENING``).

        Returns:
            A single formatted string ready to be passed as the LLM ``system`` message.
        """
        parts = [
            self.get_context_prompt(),
            self.get_state_prompt(state),
            self._objection_guide(),
        ]
        return "\n\n".join(parts)

    def to_dict(self) -> dict[str, str]:
        """Return the full business configuration as a plain dict.

        Useful for serialising to JSON (dashboard display, API responses, etc.).
        """
        return dict(self._context)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _objection_guide(self) -> str:
        """Build a compact objection-handling guide for the LLM."""
        lines = [
            "## OBJECTION HANDLING GUIDE",
            "When the caller raises a concern, respond with empathy using these guidelines:",
            "",
        ]
        for obj in get_all_objections():
            lines.append(f"- **{obj['id']}**: {obj['response'][:120]}...")
            if obj.get("escalate_to_human"):
                lines.append(f"  → *Escalate to human if this persists.*")
            lines.append("")

        lines.append(
            "Always acknowledge their concern first, then offer perspective, "
            "then ask a gentle follow-up question."
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module-level singleton (convenient default import)
# ---------------------------------------------------------------------------

_default_card: BattleCard | None = None


def get_default_card() -> BattleCard:
    """Return the module-level singleton :class:`BattleCard` instance."""
    global _default_card
    if _default_card is None:
        _default_card = BattleCard()
    return _default_card
