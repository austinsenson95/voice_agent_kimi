"""
Conversation State Machine

Manages the flow of a sales conversation through discrete states.
Each state has specific goals and transitions based on user input keywords.

States (linear with back-edges):
    OPENING   → greeting + quick intro
    DISCOVERY → ask qualifying questions (budget, timeline, course)
    PITCH     → present the offering with value props
    OBJECTION → handle pushback (price, timing, competition)
    CLOSE     → call-to-action (book demo, share payment link)

Escape hatches (from any state):
    HUMAN_HANDOFF — "speak to manager", "not a robot", "human"
    ENDED           — "bye", "hang up", "don't call"

This is intentionally simple (keyword-based) for the MVP. A production
version would use an LLM-based router or LangGraph for richer logic.
"""

from __future__ import annotations

from app.config import get_settings, STATE_PROMPTS
from app.config import (
    build_system_prompt as _config_build_system_prompt,
    validate_response,
)
from app.schemas import ConversationState


# ---------------------------------------------------------------------------
# Keyword-based routing
# ---------------------------------------------------------------------------

# Keywords that trigger state transitions FROM any state
_ESCAPE_HUMAN = {"human", "manager", "supervisor", "agent", "representative",
                 "admi", "person", "real person", "baat karo", "manager se"}
_ESCAPE_END = {"bye", "goodbye", "hang up", "end call", "stop calling",
               "don't call", "do not call", "disconnect", "rakho", "band karo"}

# State-specific transitions: keywords → next state
_TRANSITIONS: dict[str, dict[str, str]] = {
    ConversationState.OPENING.value: {
        # If user asks about pricing/courses directly → skip discovery
        "price": ConversationState.PITCH.value,
        "fees": ConversationState.PITCH.value,
        "cost": ConversationState.PITCH.value,
        "course": ConversationState.DISCOVERY.value,
        "program": ConversationState.DISCOVERY.value,
        "tell me more": ConversationState.DISCOVERY.value,
        "kya hai": ConversationState.DISCOVERY.value,
        "kaise": ConversationState.DISCOVERY.value,
        "details": ConversationState.DISCOVERY.value,
    },
    ConversationState.DISCOVERY.value: {
        # Discovery answers → move to pitch
        "budget": ConversationState.PITCH.value,
        "yes": ConversationState.PITCH.value,
        "haan": ConversationState.PITCH.value,
        "interested": ConversationState.PITCH.value,
        "batao": ConversationState.PITCH.value,
        "bataiye": ConversationState.PITCH.value,
        # Objections during discovery
        "expensive": ConversationState.OBJECTION.value,
        "mahanga": ConversationState.OBJECTION.value,
    },
    ConversationState.PITCH.value: {
        # Post-pitch reactions
        "okay": ConversationState.CLOSE.value,
        "theek": ConversationState.CLOSE.value,
        "book": ConversationState.CLOSE.value,
        "demo": ConversationState.CLOSE.value,
        "interested": ConversationState.CLOSE.value,
        "karunga": ConversationState.CLOSE.value,
        "karungi": ConversationState.CLOSE.value,
        # Objections
        "expensive": ConversationState.OBJECTION.value,
        "mahanga": ConversationState.OBJECTION.value,
        "think": ConversationState.OBJECTION.value,
        "soch": ConversationState.OBJECTION.value,
        "compare": ConversationState.OBJECTION.value,
        "already": ConversationState.OBJECTION.value,
    },
    ConversationState.OBJECTION.value: {
        # Resolved objection → close
        "okay": ConversationState.CLOSE.value,
        "theek": ConversationState.CLOSE.value,
        "samajh": ConversationState.CLOSE.value,
        "haan": ConversationState.CLOSE.value,
        "yes": ConversationState.CLOSE.value,
        # Still resistant → keep in objection
        "still": ConversationState.OBJECTION.value,
        "phir bhi": ConversationState.OBJECTION.value,
        # User wants to end
        "no": ConversationState.ENDED.value,
        "nahi": ConversationState.ENDED.value,
    },
    ConversationState.CLOSE.value: {
        # Close succeeded
        "done": ConversationState.ENDED.value,
        "booked": ConversationState.ENDED.value,
        "payment": ConversationState.ENDED.value,
        "thank": ConversationState.ENDED.value,
        "dhanyavad": ConversationState.ENDED.value,
        # Close failed → objection
        "think": ConversationState.OBJECTION.value,
        "soch": ConversationState.OBJECTION.value,
        "later": ConversationState.OBJECTION.value,
        "baad mein": ConversationState.OBJECTION.value,
    },
}


def determine_next_state(current_state: str, user_text: str) -> str:
    """Decide the next conversation state based on current state + user text.

    This is a keyword-based router. It scans the user's message for
    trigger words and returns the appropriate next state. The logic is:

        1. Check escape hatches (human handoff, end call) — highest priority
        2. Check state-specific transition keywords
        3. If no match, stay in the current state

    Args:
        current_state: One of the ConversationState values
        user_text: The transcribed user speech (lowercased for matching)

    Returns:
        The next state value (also a ConversationState string)
    """
    text_lower = user_text.lower().strip()

    # --- Priority 1: Escape hatches (from ANY state) ---
    for keyword in _ESCAPE_HUMAN:
        if keyword in text_lower:
            return ConversationState.HUMAN_HANDOFF.value

    for keyword in _ESCAPE_END:
        if keyword in text_lower:
            return ConversationState.ENDED.value

    # Already in a terminal state — don't transition out
    if current_state in (ConversationState.ENDED.value,
                         ConversationState.HUMAN_HANDOFF.value):
        return current_state

    # --- Priority 2: State-specific transitions ---
    state_transitions = _TRANSITIONS.get(current_state, {})
    for keyword, next_state in state_transitions.items():
        if keyword in text_lower:
            return next_state

    # --- Default: stay in current state ---
    # This prevents premature advancement when the user says something
    # neutral like "hmm" or "ok" that doesn't indicate clear intent.
    return current_state


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

_STATE_PROMPTS: dict[str, str] = {
    ConversationState.OPENING.value: (
        "You are {business_name}'s AI phone assistant. This is the FIRST message "
        "of the call. Greet the caller warmly in Indian English, "
        "introduce yourself briefly, and ask what they're looking for. "
        "Keep it under 3 sentences. Be friendly but professional."
    ),
    ConversationState.DISCOVERY.value: (
        "You are {business_name}'s AI phone assistant. You're in the DISCOVERY phase. "
        "Ask 1-2 qualifying questions to understand the caller's needs: "
        "What course/exam are they preparing for? What's their target year? "
        "Have they joined any coaching before? Keep questions conversational. "
        "Speak in Indian English. Keep response under 4 sentences."
    ),
    ConversationState.PITCH.value: (
        "You are {business_name}'s AI phone assistant. You're in the PITCH phase. "
        "Present the key value propositions based on what you learned in discovery. "
        "Mention: top faculty, small batch sizes, high success rate, hybrid online+offline model. "
        "Highlight the free demo class offer. Speak in Indian English. "
        "Keep it under 5 sentences. Be persuasive but not pushy."
    ),
    ConversationState.OBJECTION.value: (
        "You are {business_name}'s AI phone assistant. You're handling an OBJECTION. "
        "Listen empathetically, acknowledge the concern, and address it using the "
        "battle card information. For price concerns: mention EMI and scholarship test. "
        'For "need to think": create urgency (batches filling up). '
        'For "already in coaching": offer free trial class to compare. '
        "For parent approval: offer to speak with parents directly. "
        "Respond in Indian English. Keep it under 5 sentences."
    ),
    ConversationState.CLOSE.value: (
        "You are {business_name}'s AI phone assistant. You're in the CLOSE phase. "
        "Give a clear call-to-action: ask them to book a FREE demo class this week. "
        "Or ask if they'd like to register for the scholarship test on the 15th. "
        "Create gentle urgency without being pushy. "
        "Respond in Indian English. Keep it under 4 sentences."
    ),
    ConversationState.HUMAN_HANDOFF.value: (
        "You are {business_name}'s AI phone assistant. The caller wants to speak "
        "to a human. Apologize politely, say you're connecting them to a senior "
        "counselor, and ask them to hold for a moment. "
        "Respond in Indian English. Keep it under 3 sentences."
    ),
    ConversationState.ENDED.value: (
        "You are {business_name}'s AI phone assistant. The call is ending. "
        "Thank the caller warmly, wish them well, and say goodbye. "
        "Respond in Indian English. 1-2 sentences only."
    ),
}


def build_system_prompt(state: str, battle_card_text: str) -> str:
    # TODO: integrate STATE_PROMPTS context constant and new config.build_system_prompt
    """Build the LLM system prompt for the current conversation state.

    Each state has a specific instruction set that guides the LLM's
    tone, content, and length. The battle card is appended to give
    the LLM factual context about the business.

    Args:
        state: Current ConversationState value
        battle_card_text: Raw battle card text with business details

    Returns:
        A formatted system prompt string ready to pass to the LLM
    """
    settings = get_settings()
    business_name = settings.BUSINESS_NAME

    # Get state-specific instructions
    state_instruction = _STATE_PROMPTS.get(
        state,
        "You are a helpful AI phone assistant. Respond in Hinglish.",
    )

    system_prompt = (
        f"{state_instruction.format(business_name=business_name)}\n\n"
        f"--- BUSINESS CONTEXT ---\n"
        f"{battle_card_text}\n\n"
        f"--- RULES ---\n"
        f"1. Always respond in Indian English.\n"
        f"2. Keep responses SHORT (under 30 seconds when spoken).\n"
        f"3. Be warm, friendly, and professional.\n"
        f"4. Don't use jargon the caller won't understand.\n"
        f"5. If you don't know something, offer to connect them to a counselor.\n"
        f"6. Never make up facts — use only the business context provided above.\n"
        f"7. Current conversation state: {state}\n"
    )

    return system_prompt
