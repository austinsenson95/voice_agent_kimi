"""
FastAPI Application — AI Phone Agent Backend

This is the entry point for the entire AI phone agent. It exposes:
    - Webhook endpoints for Vobiz telephony events
    - REST API for dashboard/monitoring
    - LLM provider management (hot-swap at runtime)
    - Calendar integration (Cal.com)
    - WhatsApp integration (Chat Mitra)
    - Battle card management
    - Objection handler

Architecture:
    Vobiz --webhook--> FastAPI --> State Machine --> LLM Provider
                          |              |                  |
                          v              v                  v
                    SessionMemory   VoicePipeline <--- Response
                          |              ^
                          v              |
                        Redis    Battle Cards + Objections
                          |
                          v
                    Cal.com + WhatsApp

Request flow for a typical call:
    1. POST /webhook/vobiz/answer     --> create session, generate greeting
    2. POST /webhook/vobiz/recording  --> STT --> LLM --> TTS --> return audio
    3. POST /webhook/vobiz/hangup     --> end session, trigger follow-up
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.llm_provider import get_llm_provider, reset_provider
from app.memory import SessionMemory
from app.schemas import (
    CallSession,
    ConversationState,
    HealthResponse,
    LLMResponse,
    ProviderConfig,
    ProviderInfoResponse,
    VobizAnswerWebhook,
    VobizHangupWebhook,
    VobizRecordingWebhook,
    WebhookResponse,
)
from app.state_machine import build_system_prompt, determine_next_state
from app.voice_pipeline import sarvam_stt, sarvam_tts

# Integration modules
try:
    from app.routes import (
        calendar_router,
        whatsapp_router,
        battle_card_router,
        objections_router,
    )
    INTEGRATIONS_AVAILABLE = True
except ImportError:
    INTEGRATIONS_AVAILABLE = False
    logging.warning("Integration routes not available — calendar, WhatsApp, battle cards disabled")

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG if get_settings().DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("phone_agent")

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------
# These are instantiated at import time and reused across requests.
# SessionMemory handles its own Redis connection pooling internally.
_memory = SessionMemory()

# Track app start time for uptime calculation
_APP_START_TIME = time.monotonic()


# ---------------------------------------------------------------------------
# Lifespan context manager
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler -- runs on startup and shutdown."""
    # Startup
    logger.info("=" * 50)
    logger.info("AI Phone Agent starting up")
    logger.info("LLM Provider: %s", get_settings().LLM_PROVIDER)
    logger.info("Redis URL set: %s", bool(get_settings().REDIS_URL))
    logger.info("Debug mode: %s", get_settings().DEBUG)
    logger.info("Integrations: %s", "available" if INTEGRATIONS_AVAILABLE else "disabled")
    logger.info("=" * 50)
    yield
    # Shutdown
    logger.info("AI Phone Agent shutting down")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Phone Agent",
    description="Real-time voice AI for Indian coaching/consulting businesses",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS -- allow all origins so the React dashboard can connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register integration routers if available
if INTEGRATIONS_AVAILABLE:
    app.include_router(calendar_router, prefix="/api")
    app.include_router(whatsapp_router, prefix="/api")
    app.include_router(battle_card_router, prefix="/api")
    app.include_router(objections_router, prefix="/api")
    logger.info("Integration routers registered")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

async def _store_audio_file(call_sid: str, audio_bytes: bytes) -> str:
    """Save TTS audio to a local file and return a URL.

    In production this should upload to S3/CloudFront. For the MVP,
    we store files locally and serve them via a static endpoint.
    """
    audio_dir = "/tmp/phone_agent_audio"
    os.makedirs(audio_dir, exist_ok=True)

    filename = f"{call_sid}_{datetime.now(timezone.utc).strftime('%H%M%S')}.wav"
    filepath = os.path.join(audio_dir, filename)

    with open(filepath, "wb") as f:
        f.write(audio_bytes)

    return f"/audio/{filename}"


def _format_turns_for_llm(turns: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Convert internal turn format to LLM provider message format."""
    return [{"role": t["role"], "content": t["content"]} for t in turns]


# ---------------------------------------------------------------------------
# Health & Monitoring
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    active_calls = await _memory.list_active_sessions()
    uptime = time.monotonic() - _APP_START_TIME
    current_provider = get_llm_provider()
    return {
        "status": "healthy",
        "active_calls": len(active_calls),
        "uptime_seconds": round(uptime, 1),
        "version": "0.1.0",
        "current_provider": current_provider.name,
        "current_model": current_provider.model,
    }


# ---------------------------------------------------------------------------
# Dashboard API
# ---------------------------------------------------------------------------

@app.get("/api/calls")
async def list_active_calls() -> List[Dict[str, Any]]:
    """List all active (non-ended) calls for the dashboard."""
    return await _memory.list_active_sessions()


@app.get("/api/calls/{call_sid}")
async def get_call_details(call_sid: str) -> Dict[str, Any]:
    """Get detailed information about a specific call."""
    session = await _memory.get_session(call_sid)
    if session is None:
        raise HTTPException(status_code=404, detail="Call not found")
    return session


# ---------------------------------------------------------------------------
# LLM Provider Management (hot-swap at runtime)
# ---------------------------------------------------------------------------

@app.get("/api/settings/provider", response_model=ProviderInfoResponse)
async def get_current_provider() -> Dict[str, Any]:
    """Get information about the currently active LLM provider."""
    provider = get_llm_provider()
    settings = get_settings()
    cfg = settings.provider_config(provider.name)
    is_configured = bool(cfg.get("api_key"))

    return {
        "current_provider": provider.name,
        "current_model": provider.model,
        "available_providers": ["groq", "openai", "anthropic", "deepseek"],
        "is_configured": is_configured,
    }


@app.post("/api/settings/provider")
async def switch_provider(config: ProviderConfig) -> Dict[str, str]:
    """Switch the LLM provider at runtime without restarting.

    This is a key feature -- it lets the user A/B test providers,
    switch to a backup if one goes down, or use cheaper models
    for high-volume periods.
    """
    provider_name = config.provider

    # Validate that the API key for the target provider is set
    settings = get_settings()
    cfg = settings.provider_config(provider_name)
    if not cfg.get("api_key"):
        raise HTTPException(
            status_code=400,
            detail=f"{provider_name.upper()}_API_KEY is not set in environment",
        )

    # Reset the cached provider so next request creates a new instance
    reset_provider()

    # Force-create the new provider to validate it works
    new_provider = get_llm_provider(provider_name)

    logger.info(
        "Provider switched to %s (model: %s)",
        new_provider.name,
        new_provider.model,
    )

    return {
        "provider": new_provider.name,
        "model": new_provider.model,
        "status": "switched",
    }


# ---------------------------------------------------------------------------
# Vobiz Webhooks
# ---------------------------------------------------------------------------

@app.post("/webhook/vobiz/answer", response_model=WebhookResponse)
async def webhook_answer(payload: VobizAnswerWebhook) -> Dict[str, Any]:
    """Handle 'call answered' event from Vobiz.

    This is the entry point for every call. We:
        1. Create a new CallSession in Redis/memory
        2. Generate an opening greeting via LLM
        3. Convert the greeting to speech via TTS
        4. Return the audio URL to Vobiz

    Idempotent: if called again with the same call_sid, it returns
    the same greeting (doesn't create duplicate sessions).
    """
    call_sid = payload.call_sid
    logger.info("[call:%s] Call answered from %s", call_sid, payload.from_number)

    # Check for existing session (idempotency)
    existing = await _memory.get_session(call_sid)
    if existing is not None:
        logger.info("[call:%s] Session already exists -- returning cached greeting", call_sid)
        turns = existing.get("turns", [])
        for turn in turns:
            if turn.get("role") == "assistant":
                return {"text": turn["content"], "state": existing.get("state")}

    # --- 1. Create new session ---
    session: Dict[str, Any] = {
        "call_sid": call_sid,
        "lead_phone": payload.from_number,
        "state": "opening",
        "turns": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "llm_provider": get_settings().LLM_PROVIDER,
        "llm_model": "",
        "total_llm_calls": 0,
        "total_tokens_used": 0,
        "metadata": {},
    }
    await _memory.save_session(call_sid, session)

    # --- 2. Generate opening greeting via LLM ---
    settings = get_settings()
    provider = get_llm_provider()
    system_prompt = build_system_prompt(
        "opening",
        settings.BATTLE_CARD_TEXT or "",
    )

    try:
        llm_resp = await provider.generate(
            messages=[],
            system=system_prompt,
        )
    except Exception as exc:
        logger.error("[call:%s] LLM error in answer webhook: %s", call_sid, exc)
        return {
            "text": f"Namaste! Main {settings.BUSINESS_NAME or 'aapki help'} se baat kar raha hoon. Aap kaise madad kar sakta hoon aaj?",
            "state": "opening",
        }

    ai_text = llm_resp.text or "Namaste! Main aapki kaise madad kar sakta hoon?"

    # Update session with LLM metadata
    session["llm_model"] = llm_resp.model
    session["total_llm_calls"] = 1
    session["total_tokens_used"] = llm_resp.tokens_used
    await _memory.save_session(call_sid, session)

    # --- 3. Convert to speech ---
    audio_bytes = await sarvam_tts(ai_text)
    if audio_bytes:
        audio_url = await _store_audio_file(call_sid, audio_bytes)
        return {
            "audio_url": audio_url,
            "text": ai_text,
            "state": "opening",
        }
    else:
        logger.warning("[call:%s] TTS failed -- returning text fallback", call_sid)
        return {
            "text": ai_text,
            "state": "opening",
        }


@app.post("/webhook/vobiz/recording", response_model=WebhookResponse)
async def webhook_recording(payload: VobizRecordingWebhook) -> Dict[str, Any]:
    """Handle 'recording completed' event from Vobiz.

    This is the core conversation loop -- it runs on every user utterance:
        1. Get session from memory
        2. Get user's text (STT if needed, or use provided text)
        3. Add user turn to history
        4. Determine next state via state machine
        5. Build system prompt for that state
        6. Call LLM with conversation history
        7. Add AI turn to history
        8. Convert AI text to speech (TTS)
        9. Return audio URL
    """
    call_sid = payload.call_sid
    logger.info("[call:%s] Recording received", call_sid)

    # --- 1. Get session ---
    session = await _memory.get_session(call_sid)
    if session is None:
        logger.error("[call:%s] No session found for recording", call_sid)
        session = {
            "call_sid": call_sid,
            "lead_phone": "unknown",
            "state": "opening",
            "turns": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": None,
            "llm_provider": get_settings().LLM_PROVIDER,
            "llm_model": "",
            "total_llm_calls": 0,
            "total_tokens_used": 0,
            "metadata": {},
        }

    # --- 2. Get user text ---
    user_text = ""
    if payload.user_text:
        user_text = payload.user_text.strip()
        logger.info("[call:%s] Using provided transcription: %r", call_sid, user_text[:80])
    elif payload.recording_url:
        logger.info("[call:%s] Running STT on %s", call_sid, payload.recording_url)
        user_text = await sarvam_stt(payload.recording_url)
        logger.info("[call:%s] STT result: %r", call_sid, user_text[:80] if user_text else "(empty)")
    else:
        logger.warning("[call:%s] No audio URL or text provided", call_sid)
        return {"text": "Maine aapki awaaz nahi suni. Kripya dobara boliye.", "state": session.get("state")}

    if not user_text:
        repeat_msg = "Maaf kijiye, main samajh nahi paaya. Kripya thoda saaf boliye."
        audio_bytes = await sarvam_tts(repeat_msg)
        if audio_bytes:
            audio_url = await _store_audio_file(call_sid, audio_bytes)
            return {"audio_url": audio_url, "text": repeat_msg, "state": session.get("state")}
        return {"text": repeat_msg, "state": session.get("state")}

    # --- 3. Add user turn ---
    await _memory.add_turn(call_sid, "user", user_text)

    # --- 4. Determine next state ---
    current_state = session.get("state", "opening")
    next_state = determine_next_state(current_state, user_text)
    if next_state != current_state:
        logger.info("[call:%s] State transition: %s --> %s", call_sid, current_state, next_state)
        await _memory.update_state(call_sid, next_state)

    # --- 5. Build system prompt ---
    settings = get_settings()
    system_prompt = build_system_prompt(next_state, settings.BATTLE_CARD_TEXT or "")

    # --- 6. Get conversation history and call LLM ---
    turns = await _memory.get_turns(call_sid, last_n=10)
    messages = _format_turns_for_llm(turns)

    provider = get_llm_provider()
    try:
        llm_resp = await provider.generate(
            messages=messages,
            system=system_prompt,
        )
    except Exception as exc:
        logger.error("[call:%s] LLM error: %s", call_sid, exc)
        error_msg = "Maaf kijiye, kuch technical issue aa gaya. Thodi der mein try kijiye."
        audio_bytes = await sarvam_tts(error_msg)
        if audio_bytes:
            audio_url = await _store_audio_file(call_sid, audio_bytes)
            return {"audio_url": audio_url, "text": error_msg, "state": next_state}
        return {"text": error_msg, "state": next_state}

    ai_text = llm_resp.text or "Main samajh nahi paaya. Kripya dobara boliye."

    # --- 7. Add AI turn ---
    await _memory.add_turn(call_sid, "assistant", ai_text)

    # Update session metadata
    session = await _memory.get_session(call_sid)
    if session:
        session["llm_model"] = llm_resp.model
        session["total_llm_calls"] = session.get("total_llm_calls", 0) + 1
        session["total_tokens_used"] = session.get("total_tokens_used", 0) + llm_resp.tokens_used
        await _memory.save_session(call_sid, session)

    # --- 8. TTS ---
    audio_bytes = await sarvam_tts(ai_text)
    if audio_bytes:
        audio_url = await _store_audio_file(call_sid, audio_bytes)
        return {
            "audio_url": audio_url,
            "text": ai_text,
            "state": next_state,
            "hangup": next_state == "ended",
        }
    else:
        return {
            "text": ai_text,
            "state": next_state,
            "hangup": next_state == "ended",
        }


@app.post("/webhook/vobiz/hangup")
async def webhook_hangup(payload: VobizHangupWebhook) -> Dict[str, str]:
    """Handle 'call ended' event from Vobiz.

    Marks the session as ended and sets a short TTL so the call
    data is available for post-call analytics briefly, then auto-cleaned.
    """
    call_sid = payload.call_sid
    logger.info(
        "[call:%s] Call ended. Duration: %ss",
        call_sid,
        payload.duration_seconds,
    )

    await _memory.end_session(call_sid)
    return {"status": "ok", "call_sid": call_sid}


# ---------------------------------------------------------------------------
# Static file serving (for TTS audio files)
# ---------------------------------------------------------------------------

@app.get("/audio/{filename}")
async def serve_audio(filename: str) -> Any:
    """Serve generated TTS audio files."""
    filepath = os.path.join("/tmp/phone_agent_audio", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Audio file not found")

    from fastapi.responses import FileResponse

    return FileResponse(
        filepath,
        media_type="audio/wav",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
