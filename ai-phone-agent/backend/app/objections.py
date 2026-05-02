"""Objection handler with structured data for the AI Phone Agent.

Provides a library of common objections faced by Indian coaching / consulting
businesses, along with empathetic response templates, follow-up questions,
and escalation flags for human handoff.

Typical flow:
    1. ``detect_objection(user_text)`` → finds the best-matching objection
    2. ``get_objection_response(obj["id"], context)`` → renders the reply
    3. ``should_escalate(obj["id"])`` → decides if a human should take over
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

from app.config import OBJECTIONS, build_objection_prompt, validate_response  # TODO: integrate build_objection_prompt for each detected objection

# ---------------------------------------------------------------------------
# Objection Library
# ---------------------------------------------------------------------------

OBJECTION_LIBRARY: list[dict[str, Any]] = [
    {
        "id": "price",
        "triggers": [
            "expensive",
            "costly",
            "bahut mehenga",
            "mehenga",
            "price",
            "price bahut zyada",
            "kitna paisa",
            "paisa nahi",
            "afford nahi",
            "budget nahi",
            "cannot afford",
            "too much money",
            "itna paisa",
            "rate bahut hai",
            "kam karo",
            "discount",
            "cheaper option",
        ],
        "response": (
            "I completely understand — investing in yourself is a big decision, "
            "and it\'s natural to feel cautious about the cost. "
            "{owner_name} has worked with many business owners who felt the same way at first, "
            "and they consistently say the growth they achieved far outweighed the investment. "
            "Our coaching is priced at {pricing_range}. Would it help if we broke down "
            "what\'s included so you can see the full value?"
        ),
        "follow_up": "What part of the investment concerns you the most — is it the upfront cost or the uncertainty about results?",
        "escalate_to_human": False,
    },
    {
        "id": "time",
        "triggers": [
            "no time",
            "time nahi",
            "busy hoon",
            "busy hun",
            "schedule full",
            "time nahi milta",
            "kitna time lagta",
            "time kahan se",
            "busy schedule",
            "time commitment",
            "free time nahi",
            "bahut busy",
        ],
        "response": (
            "I hear you — you\'re already juggling so much, and adding one more thing "
            "can feel overwhelming. The good news is that {owner_name} designed this "
            "program specifically for busy business owners. Each session is just {session_duration}, "
            "and most clients find that the clarity they gain actually *saves* them hours every week. "
            "Can we find a slot that fits into your current schedule?"
        ),
        "follow_up": "Would an early morning or late evening slot work better for you?",
        "escalate_to_human": False,
    },
    {
        "id": "think-about-it",
        "triggers": [
            "soch ke batata hoon",
            "soch kar batata",
            "think about it",
            "sochunga",
            "discuss karke",
            "family se baat",
            "baad mein call",
            "call me later",
            "baad mein baat",
            "decide later",
            "need to think",
            "let me think",
            "time chahiye",
        ],
        "response": (
            "Absolutely, take your time — this is an important decision and I respect that. "
            "What I\'ve noticed is that people who benefit the most often feel a mix of excitement "
            "and hesitation right before they commit. "
            "To help you decide, shall I send you a quick WhatsApp message with our calendar link "
            "and a success story from someone just like you? You can book whenever you\'re ready."
        ),
        "follow_up": "Is there a specific question I can answer that would help you feel more confident about this?",
        "escalate_to_human": False,
    },
    {
        "id": "not-interested",
        "triggers": [
            "not interested",
            "interest nahi",
            "man nahi",
            "nahi chahiye",
            "no thanks",
            "pass",
            "not for me",
            "mujhe nahi chahiye",
            "fir kabhi",
            "next time",
            "call mat karo",
            "do not call",
        ],
        "response": (
            "I completely respect that, and I won\'t take up more of your time. "
            "Just one quick thought — many people who initially said \'not interested\' "
            "were actually dealing with a challenge that coaching could solve, "
            "but they were hesitant to open up. If you ever feel stuck in your business "
            "and want a no-pressure conversation, {business_name} is here. "
            "Would it be okay if I sent you our details on WhatsApp for future reference?"
        ),
        "follow_up": "If I may ask — is it coaching in general you\'re not interested in, or is something else on your mind?",
        "escalate_to_human": True,
    },
    {
        "id": "who-are-you",
        "triggers": [
            "kaun ho",
            "who are you",
            "kis company se",
            "which company",
            "kahan se call",
            "how did you get",
            "number kahan se",
            "kaise call kiya",
            "pehle kabhi nahi suna",
            "never heard",
            "is this spam",
            "fake call",
        ],
        "response": (
            "Totally fair question! I\'m the AI assistant for {business_name}, "
            "founded by {owner_name}. We help {ideal_client} get unstuck and grow. "
            "You can check us out at {website} — and I\'d be happy to send you our WhatsApp "
            "so you can verify us. We\'ve worked with over 200 business owners across India. "
            "Is there a particular goal or challenge you\'re dealing with right now that "
            "made you pick up the call?"
        ),
        "follow_up": "Would you like me to send you a quick intro video or our website link on WhatsApp?",
        "escalate_to_human": False,
    },
    {
        "id": "already-have-coach",
        "triggers": [
            "already have a coach",
            "already have coach",
            "mere paas coach",
            "dusra coach",
            "another coach",
            "already enrolled",
            "pehle se coach",
            "already doing coaching",
            "mentor hai",
        ],
        "response": (
            "That\'s wonderful — having a coach shows you\'re serious about growth! "
            "{owner_name}\'s approach is quite different: {unique_selling_prop}. "
            "Many of our clients actually came to us while working with another coach, "
            "and they found our framework complemented what they were already doing. "
            "Would you be open to a no-pressure intro call to see if there\'s a fit?"
        ),
        "follow_up": "What\'s one area your current coach hasn\'t been able to help you with yet?",
        "escalate_to_human": False,
    },
    {
        "id": "not-decision-maker",
        "triggers": [
            "main decision nahi leta",
            "wife decides",
            "husband decides",
            "partner decides",
            "boss decide karega",
            "boss decide",
            "main nahi decide kar sakta",
            "i am not the decision maker",
            "senior decide karenge",
        ],
        "response": (
            "I completely understand — important decisions are often made together. "
            "Would it be possible for {owner_name} to speak directly with the decision-maker? "
            "We can arrange a quick joint call, or I can send all the details via WhatsApp "
            "so they can review at their convenience. What works best?"
        ),
        "follow_up": "Would it help if I scheduled a brief call with both of you together?",
        "escalate_to_human": True,
    },
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_objection(user_text: str) -> dict[str, Any] | None:
    """Detect the best-matching objection in *user_text*.

    The scoring algorithm is simple but effective:

    1. Lower-case the user text.
    2. For each objection, count how many trigger keywords/phrases appear.
    3. Return the objection with the highest trigger match count.
    4. Ties are broken by the order in which objections are defined.

    Args:
        user_text: Raw transcript / text from the caller.

    Returns:
        A dict from :data:`OBJECTION_LIBRARY` or ``None`` when no triggers fire.

    Example::

        result = detect_objection("Ye bahut mehenga hai bhai")
        # result["id"] == "price"
    """
    if not user_text or not user_text.strip():
        return None

    text_lower = user_text.lower()
    best_match: dict[str, Any] | None = None
    best_score = 0

    for obj in OBJECTION_LIBRARY:
        score = 0
        for trigger in obj["triggers"]:
            # Use word-boundary search for short triggers (< 4 chars)
            # and substring search for longer phrases to handle transliterations.
            if len(trigger) < 4:
                pattern = r"\b" + re.escape(trigger.lower()) + r"\b"
                if re.search(pattern, text_lower):
                    score += 1
            else:
                if trigger.lower() in text_lower:
                    score += 1

        if score > best_score:
            best_score = score
            best_match = obj

    if best_match:
        logger.info(
            "Detected objection '%s' with score %d in text: %s",
            best_match["id"],
            best_score,
            user_text[:80],
        )
        return best_match

    logger.debug("No objection detected in text: %s", user_text[:80])
    return None


def get_objection_response(objection_id: str, context: dict[str, str]) -> str:
    # TODO: integrate OBJECTIONS context constant into response rendering
    """Render the response template for a given *objection_id*.

    Substitutes placeholders like ``{business_name}``, ``{owner_name}``,
    ``{pricing_range}``, ``{session_duration}``, ``{ideal_client}``,
    ``{unique_selling_prop}``, ``{website}`` from *context*.

    Args:
        objection_id: One of the ``id`` values in :data:`OBJECTION_LIBRARY`.
        context: Mapping of template variable names → values.

    Returns:
        The rendered response string.

    Raises:
        ValueError: If *objection_id* is not found in the library.

    Example::

        reply = get_objection_response("price", {
            "business_name": "Growth Coaching",
            "owner_name": "Amit",
            "pricing_range": "Rs. 15k - 50k",
            "session_duration": "45 minutes",
            "ideal_client": "business owners",
            "unique_selling_prop": "proven framework",
            "website": "https://example.com",
        })
    """
    for obj in OBJECTION_LIBRARY:
        if obj["id"] == objection_id:
            template: str = obj["response"]
            try:
                return template.format(**context)
            except KeyError as exc:
                logger.warning("Missing template key %s for objection %s", exc, objection_id)
                # Return template with available substitutions + raw braces for missing keys
                return template.format_map(_SafeContext(context))

    raise ValueError(f"Unknown objection_id: {objection_id!r}")


def should_escalate(objection_id: str) -> bool:
    """Return ``True`` if this objection should trigger human handoff.

    Certain objections (e.g. "not-interested", "not-decision-maker") are
    signals that the AI may do more harm than good if it continues pushing.
    In those cases we gracefully hand off to a human agent.
    """
    for obj in OBJECTION_LIBRARY:
        if obj["id"] == objection_id:
            return bool(obj.get("escalate_to_human", False))
    return False


def get_all_objections() -> list[dict[str, Any]]:
    """Return the full objection library (useful for dashboard display / admin).

    Returns a **shallow copy** of the list so callers can mutate it safely.
    """
    return list(OBJECTION_LIBRARY)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _SafeContext(dict):
    """A dict subclass that returns ``{key}`` for missing keys.

    Used so that template formatting doesn't crash when a context variable
    is absent — the placeholder is left intact.
    """

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"
