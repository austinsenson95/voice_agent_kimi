"""
Pydantic models for request/response validation and data structures.

All models use Pydantic v2 for fast serialization and deserialization.
These are the contracts between the telephony layer (Vobiz), the LLM providers,
and the internal state machine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ConversationState(str, Enum):
    """Finite states of a sales conversation.

    The flow is generally linear but can jump back for objections
    or forward to human handoff at any point.
    """
    OPENING = "opening"              # Initial greeting + intro
    DISCOVERY = "discovery"          # Ask qualifying questions
    PITCH = "pitch"                  # Present the offering
    OBJECTION = "objection"          # Handle pushback
    CLOSE = "close"                  # CTA: book demo, share payment link
    HUMAN_HANDOFF = "human_handoff"  # Escalate to human agent
    ENDED = "ended"                  # Call finished


class LLMProviderName(str, Enum):
    """Supported LLM providers that can be hot-swapped at runtime."""
    GROQ = "groq"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"


# ---------------------------------------------------------------------------
# Core Data Models
# ---------------------------------------------------------------------------

class Turn(BaseModel):
    """A single turn in the conversation (either user or assistant).

    This is the atom of conversation memory. Each call accumulates
    a list of turns that gets passed to the LLM as context.
    """
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., description="Text content of the turn")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the turn was recorded",
    )


class CallSession(BaseModel):
    """Represents an active phone call and its full state.

    This is the primary data structure stored in Redis/memory.
    It tracks where we are in the conversation, the history of turns,
    and metadata about the call itself.
    """
    call_sid: str = Field(..., description="Unique call identifier from Vobiz")
    lead_phone: str = Field(..., description="Caller phone number (E.164 format)")
    state: ConversationState = Field(
        default=ConversationState.OPENING,
        description="Current state in the conversation FSM",
    )
    turns: List[Turn] = Field(
        default_factory=list,
        description="Full conversation history",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the call started",
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Last activity timestamp",
    )
    ended_at: Optional[datetime] = Field(
        default=None,
        description="When the call ended (null if active)",
    )
    llm_provider: str = Field(
        default="groq",
        description="Which LLM provider handled this call",
    )
    llm_model: str = Field(
        default="",
        description="Specific model used",
    )
    total_llm_calls: int = Field(
        default=0,
        description="Number of LLM invocations in this session",
    )
    total_tokens_used: int = Field(
        default=0,
        description="Cumulative token count across all LLM calls",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Flexible key-value store for provider-specific data",
    )


# ---------------------------------------------------------------------------
# Webhook Payload Models (from Vobiz)
# ---------------------------------------------------------------------------

class VobizAnswerWebhook(BaseModel):
    """Payload sent by Vobiz when a call is first answered.

    This is the entry point — it creates a new CallSession.
    """
    event: str = Field(default="call.answered", description="Event type")
    call_sid: str = Field(..., description="Unique call identifier")
    from_number: str = Field(..., alias="from", description="Caller phone number")
    to_number: str = Field(..., alias="to", description="Dialed number")
    timestamp: Optional[datetime] = Field(
        default=None,
        description="When the event occurred (Vobix-provided)",
    )

    model_config = {"populate_by_name": True}


class VobizRecordingWebhook(BaseModel):
    """Payload sent by Vobiz when user speech has been recorded and transcribed.

    Contains either a pre-transcribed text (for testing/vendors that
    handle STT) or an audio_url that we need to send to Sarvam STT.
    """
    event: str = Field(default="recording.completed", description="Event type")
    call_sid: str = Field(..., description="Call this recording belongs to")
    recording_url: Optional[str] = Field(
        default=None,
        description="URL to the audio file (needs STT)",
    )
    user_text: Optional[str] = Field(
        default=None,
        description="Pre-transcribed text (skip STT if present)",
    )
    duration_ms: Optional[int] = Field(
        default=None,
        description="Recording duration in milliseconds",
    )
    timestamp: Optional[datetime] = Field(default=None)


class VobizHangupWebhook(BaseModel):
    """Payload sent by Vobiz when the call ends (caller hangs up or timeout).

    Triggers session cleanup and analytics logging.
    """
    event: str = Field(default="call.hangup", description="Event type")
    call_sid: str = Field(..., description="Call that ended")
    duration_seconds: Optional[int] = Field(
        default=None,
        description="Total call duration",
    )
    hangup_reason: Optional[str] = Field(
        default=None,
        description="Why the call ended (caller_hangup, timeout, error)",
    )
    timestamp: Optional[datetime] = Field(default=None)


# ---------------------------------------------------------------------------
# LLM Provider Models
# ---------------------------------------------------------------------------

class LLMResponse(BaseModel):
    """Standardized response from any LLM provider.

    This is the critical abstraction — every provider, regardless of
    native API format, returns this uniform structure. This lets us
    swap providers without touching any downstream code.
    """
    text: str = Field(..., description="Generated text response")
    provider: str = Field(..., description="Which provider generated this")
    model: str = Field(..., description="Specific model used")
    latency_ms: int = Field(
        default=0,
        description="End-to-end latency in milliseconds",
    )
    tokens_used: int = Field(
        default=0,
        description="Total tokens consumed (prompt + completion)",
    )
    prompt_tokens: int = Field(
        default=0,
        description="Tokens in the prompt",
    )
    completion_tokens: int = Field(
        default=0,
        description="Tokens in the completion",
    )
    cost_usd: float = Field(
        default=0.0,
        description="Approximate cost in US dollars",
    )
    finish_reason: Optional[str] = Field(
        default=None,
        description="Why generation stopped (stop, length, error)",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if the call failed",
    )


class ProviderConfig(BaseModel):
    """Runtime configuration for switching LLM providers.

    Used by the /api/settings/provider endpoints to let users
    change providers without restarting the server.
    """
    provider: LLMProviderName = Field(
        ..., description="Provider to switch to",
    )
    model: Optional[str] = Field(
        default=None,
        description="Override model (uses default if not set)",
    )
    temperature: Optional[float] = Field(
        default=None,
        description="Override temperature",
    )
    max_tokens: Optional[int] = Field(
        default=None,
        description="Override max tokens",
    )


# ---------------------------------------------------------------------------
# API Response Models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Response from the /health endpoint."""
    status: str = "healthy"
    active_calls: int = 0
    uptime_seconds: float = 0.0
    version: str = "0.1.0"


class WebhookResponse(BaseModel):
    """Standard response we send back to Vobiz after processing a webhook.

    Vobiz expects either text (which it will TTS) or audio_url (pre-generated).
    We always return audio_url since we handle TTS ourselves.
    """
    audio_url: Optional[str] = Field(
        default=None,
        description="URL of generated audio file to play to caller",
    )
    text: Optional[str] = Field(
        default=None,
        description="Fallback text (if TTS failed)",
    )
    hangup: bool = Field(
        default=False,
        description="If true, end the call after playing",
    )
    state: Optional[str] = Field(
        default=None,
        description="Current conversation state (for debugging)",
    )


class ProviderInfoResponse(BaseModel):
    """Response from GET /api/settings/provider."""
    current_provider: str
    current_model: str
    available_providers: List[str]
    is_configured: bool
