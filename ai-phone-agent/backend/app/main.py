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

import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import get_settings, startup_banner
from app.llm_provider import get_llm_provider, reset_provider
from app.memory import SessionMemory
from app.schemas import (
    CallSession,
    ConversationState,
    HealthResponse,
    LLMResponse,
    ProviderConfig,
    ProviderInfoResponse,

    WebhookResponse,
)
from app.config import (
    build_system_prompt,
    build_objection_prompt,
    validate_response,
    can_call,
    DEMO_MODE,
)
from app.objections import detect_objection
from app.state_machine import determine_next_state
from app.voice_pipeline import sarvam_stt, generate_tts

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

# Pre-generated greeting audio URL (populated at startup)
_GREETING_AUDIO_URL: Optional[str] = None


# ---------------------------------------------------------------------------
# Lifespan context manager
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler -- runs on startup and shutdown."""
    # Startup
    startup_banner()
    logger.info("=" * 50)
    logger.info("AI Phone Agent starting up")
    logger.info("LLM Provider: %s", get_settings().LLM_PROVIDER)
    logger.info("Redis URL set: %s", bool(get_settings().REDIS_URL))
    logger.info("Debug mode: %s", get_settings().DEBUG)
    logger.info("Integrations: %s", "available" if INTEGRATIONS_AVAILABLE else "disabled")
    logger.info("=" * 50)

    # Pre-generate greeting audio so answer webhook returns <Play> instantly
    try:
        await _ensure_greeting_audio()
    except Exception as exc:
        logger.warning("Failed to pre-generate greeting audio: %s", exc)

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

def _absolute_audio_url(request: Request, relative_path: str) -> str:
    """Convert a relative /audio/ path to an absolute URL.

    When the request comes through ngrok, request.base_url is 'http://'
    because the ngrok→localhost hop is HTTP. We detect the real public
    host from X-Forwarded-Host / X-Forwarded-Proto headers.

    Vobiz REQUIRES HTTPS for <Play> audio URLs. If the resulting URL is
    HTTP, the caller will hear nothing and the call will drop. We warn
    in the logs but do NOT blindly rewrite http→https (that creates an
    unreachable URL if the server has no TLS).
    """
    # Check for forwarded headers (ngrok, Cloudflare, AWS ALB, etc.)
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    forwarded_host = request.headers.get("x-forwarded-host", "") or request.headers.get("host", "")

    if forwarded_proto and forwarded_host:
        base = f"{forwarded_proto}://{forwarded_host}"
    else:
        base = str(request.base_url).rstrip("/")

    return f"{base}{relative_path}"


def _is_https_url(url: str) -> bool:
    """Return True if *url* uses HTTPS.

    Vobiz rejects HTTP <Play> URLs. This helper lets us fall back to
    <Speak> text when we know the audio URL would fail.
    """
    return url.lower().startswith("https://")


def _vobiz_xml(text: str = "", audio_url: str = "", hangup: bool = False, record_url: str = "") -> str:
    """Build a Vobiz-compatible XML response.

    Vobiz XML Applications expect Plivo/Exotel-style XML.
    We return <Speak> for text or <Play> for pre-generated audio.
    <Record> captures user speech and sends it to the recording webhook.
    """
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<Response>"]
    if audio_url:
        lines.append(f"    <Play>{audio_url}</Play>")
    elif text:
        # Escape XML special chars in text
        safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f"    <Speak>{safe_text}</Speak>")
    if record_url and not hangup:
        # Capture user speech and POST it to the recording webhook
        lines.append(f'    <Record action="{record_url}" method="POST" maxLength="8" timeout="2" playBeep="true" finishOnKey="#" />')
    if hangup:
        lines.append("    <Hangup/>")
    lines.append("</Response>")
    return "\n".join(lines)


async def _store_audio_file(call_sid: str, audio_bytes: bytes) -> str:
    """Save TTS audio to a local file and return a URL.

    In production this should upload to S3/CloudFront. For the MVP,
    we store files locally and serve them via a static endpoint.
    """
    audio_dir = "/tmp/phone_agent_audio"
    os.makedirs(audio_dir, exist_ok=True)

    # Use microseconds to avoid collisions on rapid turns
    filename = f"{call_sid}_{datetime.now(timezone.utc).strftime('%H%M%S%f')}.wav"
    filepath = os.path.join(audio_dir, filename)

    with open(filepath, "wb") as f:
        f.write(audio_bytes)

    return f"/audio/{filename}"


async def _ensure_greeting_audio() -> None:
    """Pre-generate the greeting audio so the answer webhook is instant."""
    global _GREETING_AUDIO_URL
    if _GREETING_AUDIO_URL:
        return

    greeting = (
        "Hey, this is Aisha from Hamza's team. I'm reaching out because "
        "you recently showed interest in building a freedom business. "
        "Do you have two minutes to chat?"
    )

    audio_bytes = await generate_tts(greeting)
    if audio_bytes:
        audio_dir = "/tmp/phone_agent_audio"
        os.makedirs(audio_dir, exist_ok=True)
        filename = "greeting_default.wav"
        filepath = os.path.join(audio_dir, filename)
        with open(filepath, "wb") as f:
            f.write(audio_bytes)
        _GREETING_AUDIO_URL = f"/audio/{filename}"
        logger.info("Pre-generated greeting audio: %s", _GREETING_AUDIO_URL)
    else:
        logger.warning("Failed to pre-generate greeting audio — will use Speak fallback")


async def _generate_and_store_tts(
    call_sid: str, text: str, request: Request
) -> tuple[str, str]:
    """Generate TTS audio, store it, and return (audio_url, fallback_text).

    Returns:
        Tuple of (absolute_audio_url, plain_text). If TTS fails,
        audio_url will be empty and plain_text is the fallback.
    """
    try:
        audio_bytes = await generate_tts(text)
        if audio_bytes:
            relative_path = await _store_audio_file(call_sid, audio_bytes)
            audio_url = _absolute_audio_url(request, relative_path)
            logger.info(
                "[call:%s] TTS generated %d bytes -> %s",
                call_sid,
                len(audio_bytes),
                audio_url,
            )
            return audio_url, text
    except Exception as exc:
        logger.error("[call:%s] TTS generation failed: %s", call_sid, exc)

    return "", text


def _cleanup_old_audio_files(max_age_hours: int = 24, keep_greeting: bool = True) -> int:
    """Remove audio files older than *max_age_hours* to prevent disk fill.

    Returns:
        Number of files removed.
    """
    audio_dir = "/tmp/phone_agent_audio"
    if not os.path.exists(audio_dir):
        return 0

    now = time.time()
    max_age_seconds = max_age_hours * 3600
    removed = 0
    greeting_name = os.path.basename(_GREETING_AUDIO_URL) if _GREETING_AUDIO_URL else ""

    for filename in os.listdir(audio_dir):
        if keep_greeting and filename == greeting_name:
            continue
        filepath = os.path.join(audio_dir, filename)
        try:
            if os.path.isfile(filepath):
                age = now - os.path.getmtime(filepath)
                if age > max_age_seconds:
                    os.remove(filepath)
                    removed += 1
        except OSError:
            pass

    if removed:
        logger.info("Cleaned up %d old audio files from %s", removed, audio_dir)
    return removed


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
        "available_providers": ["groq", "openai", "anthropic", "deepseek", "xai"],
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
# Vobiz Webhooks  (raw dict parsing — no Pydantic validation for compatibility)
# ---------------------------------------------------------------------------

def _get_field(data: Dict[str, Any], *names: str) -> Any:
    """Get first matching field from dict (case-insensitive)."""
    for name in names:
        if name in data:
            return data[name]
        for k, v in data.items():
            if k.lower() == name.lower():
                return v
    return None


async def _parse_request_body(request: Request) -> Dict[str, Any]:
    """Parse request body as JSON or form data. Returns empty dict on failure.

    Vobiz sends webhooks as form-encoded POST data by default, not JSON.
    This helper tries JSON first, then falls back to form data, then query params.
    """
    data: Dict[str, Any] = dict(request.query_params)

    try:
        json_data = await request.json()
        if isinstance(json_data, dict):
            data.update(json_data)
        return data
    except Exception:
        try:
            form_data = await request.form()
            data.update(dict(form_data))
            return data
        except Exception:
            return data


@app.post("/webhook/vobiz/answer")
@app.get("/webhook/vobiz/answer")
async def webhook_answer(request: Request):
    """Handle 'call answered' event from Vobiz.

    Accepts ANY JSON payload — no Pydantic validation so Vobiz can't 422 us.
    Returns Plivo/Exotel-style XML.
    """
    call_sid = ""
    try:
        data = await _parse_request_body(request)
        call_sid = _get_field(data, "call_sid", "CallSid", "callSid", "request_uuid", "RequestUUID") or ""
        from_number = _get_field(data, "from", "From", "from_number", "FromNumber", "caller_id", "CallerID") or ""
        to_number = _get_field(data, "to", "To", "to_number", "ToNumber", "dialed_number", "DialedNumber") or ""

        if not call_sid:
            logger.info("Vobiz URL test ping on /webhook/vobiz/answer — payload: %s", data)
            return PlainTextResponse(
                _vobiz_xml(text="OK"),
                media_type="application/xml",
            )

        logger.info("[call:%s] Call answered from %s to %s", call_sid, from_number, to_number)

        # --- Demo-mode whitelist guard ---
        # For outbound calls, Vobiz sends our DID in 'from' and the lead in 'to'.
        if DEMO_MODE:
            ok_from, msg_from = can_call(from_number)
            ok_to, msg_to = can_call(to_number)
            if not ok_from and not ok_to:
                logger.warning(
                    "[call:%s] Rejected non-whitelisted caller (from=%s, to=%s) — %s / %s",
                    call_sid,
                    from_number,
                    to_number,
                    msg_from,
                    msg_to,
                )
                return PlainTextResponse(
                    _vobiz_xml(
                        text="Sorry, this number is not authorised for demo calls. "
                        "Please contact the team to be added to the whitelist.",
                        hangup=True,
                    ),
                    media_type="application/xml",
                )

        # Check for existing session (idempotency)
        existing = await _memory.get_session(call_sid)
        if existing is not None:
            logger.info("[call:%s] Session already exists -- returning cached greeting", call_sid)
            if _GREETING_AUDIO_URL:
                # Verify file still exists (tmp may have been cleaned)
                greeting_path = os.path.join("/tmp/phone_agent_audio", os.path.basename(_GREETING_AUDIO_URL))
                if os.path.exists(greeting_path):
                    audio_url = _absolute_audio_url(request, _GREETING_AUDIO_URL)
                    if _is_https_url(audio_url):
                        return PlainTextResponse(
                            _vobiz_xml(audio_url=audio_url),
                            media_type="application/xml",
                        )
                    logger.warning(
                        "[call:%s] Cached greeting audio URL is HTTP (%s) — falling back to <Speak>.",
                        call_sid,
                        audio_url,
                    )
            turns = existing.get("turns", [])
            for turn in turns:
                if turn.get("role") == "assistant":
                    return PlainTextResponse(
                        _vobiz_xml(text=turn["content"]),
                        media_type="application/xml",
                    )

        # --- 1. Create new session ---
        session: Dict[str, Any] = {
            "call_sid": call_sid,
            "lead_phone": from_number,
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

        # --- 2. Return INSTANT greeting (skip slow LLM+TTS to avoid Vobiz timeout) ---
        greeting = (
            "Hey, this is Aisha from Hamza's team. I'm reaching out because "
            "you recently showed interest in building a freedom business. "
            "Do you have two minutes to chat?"
        )
        await _memory.add_turn(call_sid, "assistant", greeting)

        logger.info("[call:%s] Sending greeting (audio=%s)", call_sid, bool(_GREETING_AUDIO_URL))
        record_url = _absolute_audio_url(request, "/webhook/vobiz/recording")

        if _GREETING_AUDIO_URL:
            greeting_path = os.path.join("/tmp/phone_agent_audio", os.path.basename(_GREETING_AUDIO_URL))
            if os.path.exists(greeting_path):
                audio_url = _absolute_audio_url(request, _GREETING_AUDIO_URL)
                if _is_https_url(audio_url):
                    xml = _vobiz_xml(audio_url=audio_url, record_url=record_url)
                    logger.info("[call:%s] Answer XML (Play): %s", call_sid, audio_url)
                    return PlainTextResponse(xml, media_type="application/xml")
                logger.warning(
                    "[call:%s] Greeting audio URL is HTTP (%s) — Vobiz requires HTTPS. "
                    "Falling back to <Speak>.",
                    call_sid,
                    audio_url,
                )

        xml = _vobiz_xml(text=greeting, record_url=record_url)
        logger.info("[call:%s] Answer XML (Speak): %d chars", call_sid, len(greeting))
        return PlainTextResponse(xml, media_type="application/xml")

    except Exception:
        import traceback
        print(f"\n\n[CRASH] answer webhook call_sid={call_sid or 'unknown'}", file=sys.stderr)
        traceback.print_exc()
        logger.exception("[call:%s] UNHANDLED EXCEPTION in answer webhook", call_sid or "unknown")
        return PlainTextResponse(
            _vobiz_xml(
                text="Sorry, we're experiencing a technical issue. Please try again later.",
                hangup=True,
            ),
            media_type="application/xml",
        )


@app.post("/webhook/vobiz/recording")
@app.get("/webhook/vobiz/recording")
async def webhook_recording(request: Request):
    """Handle 'recording completed' event from Vobiz.

    Accepts ANY JSON payload — no Pydantic validation so Vobiz can't 422 us.
    Returns Plivo/Exotel-style XML.
    """
    call_sid = ""
    t0 = time.monotonic()
    try:
        data = await _parse_request_body(request)
        call_sid = _get_field(data, "call_sid", "CallSid", "callSid", "request_uuid", "RequestUUID") or ""

        if not call_sid:
            logger.info("Vobiz URL test ping on /webhook/vobiz/recording — payload: %s", data)
            return PlainTextResponse(
                _vobiz_xml(text="OK"),
                media_type="application/xml",
            )

        logger.info("[call:%s] Recording received", call_sid)

        # --- 1. Get session ---
        session = await _memory.get_session(call_sid)
        if session is None:
            logger.error("[call:%s] No session found for recording — creating fallback", call_sid)
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
            await _memory.save_session(call_sid, session)

        # --- 2. Get user text ---
        logger.info("[call:%s] Recording webhook payload keys: %s", call_sid, list(data.keys()))
        logger.debug("[call:%s] Recording webhook full payload: %s", call_sid, data)

        user_text_raw = _get_field(data, "user_text", "UserText", "transcription", "Transcription", "text", "Text", "speech", "Speech", "message", "Message")
        recording_url = _get_field(data, "recording_url", "RecordingUrl", "recordingUrl", "record_url", "RecordUrl", "recordUrl", "url", "Url", "media_url", "MediaUrl", "audio_url", "AudioUrl")

        user_text = ""
        stt_ms = 0
        if user_text_raw:
            user_text = str(user_text_raw).strip()
            logger.info("[call:%s] Using provided transcription: %r", call_sid, user_text[:80])
        elif recording_url:
            logger.info("[call:%s] Running STT on %s", call_sid, recording_url)
            stt_start = time.monotonic()
            download_headers = None
            if "vobiz" in str(recording_url).lower():
                download_headers = {
                    "X-Auth-ID": get_settings().VOBIZ_AUTH_ID,
                    "X-Auth-Token": get_settings().VOBIZ_AUTH_TOKEN,
                }
                logger.debug("[call:%s] Adding Vobiz auth headers for download", call_sid)
            user_text = await sarvam_stt(str(recording_url), download_headers=download_headers)
            stt_ms = int((time.monotonic() - stt_start) * 1000)
            logger.info("[call:%s] STT result: %r (%dms)", call_sid, user_text[:80] if user_text else "(empty)", stt_ms)
        else:
            logger.warning("[call:%s] No audio URL or text provided", call_sid)
            record_url = _absolute_audio_url(request, "/webhook/vobiz/recording")
            return PlainTextResponse(
                _vobiz_xml(text="Sorry, I didn't catch that. Could you please speak a bit more clearly?", record_url=record_url),
                media_type="application/xml",
            )

        if not user_text:
            repeat_msg = "Sorry, I didn't catch that. Could you please speak a bit more clearly?"
            record_url = _absolute_audio_url(request, "/webhook/vobiz/recording")
            return PlainTextResponse(
                _vobiz_xml(text=repeat_msg, record_url=record_url),
                media_type="application/xml",
            )

        # --- 3. Add user turn ---
        await _memory.add_turn(call_sid, "user", user_text)

        # --- 4. Determine next state ---
        current_state = session.get("state", "opening")
        next_state = determine_next_state(current_state, user_text)
        if next_state != current_state:
            logger.info("[call:%s] State transition: %s --> %s", call_sid, current_state, next_state)
            await _memory.update_state(call_sid, next_state)

        # --- 5. Build system prompt ---
        lead_memory = {
            "call_sid": call_sid,
            "state": next_state,
            "lead_phone": session.get("lead_phone", "unknown"),
        }

        if next_state == "objection":
            obj = detect_objection(user_text)
            if obj:
                logger.info("[call:%s] Detected objection '%s'", call_sid, obj["id"])
                system_prompt = build_objection_prompt(user_text, lead_memory)
            else:
                system_prompt = build_system_prompt(next_state, lead_memory)
        else:
            system_prompt = build_system_prompt(next_state, lead_memory)

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
            error_msg = "Sorry, we seem to be facing a technical issue. Please try again in a moment."
            record_url = _absolute_audio_url(request, "/webhook/vobiz/recording")
            return PlainTextResponse(
                _vobiz_xml(text=error_msg, record_url=record_url),
                media_type="application/xml",
            )

        llm_ms = llm_resp.latency_ms

        ai_text = llm_resp.text or "I'm sorry, I didn't catch that. Could you say that again?"

        # --- 7. Validate response ---
        is_valid, failures = validate_response(ai_text)
        if not is_valid:
            logger.warning(
                "[call:%s] Response validation failed (%s). Using safe fallback.",
                call_sid,
                failures,
            )
            ai_text = "I'm sorry, I didn't understand that. Could you please repeat?"

        # --- 8. Add AI turn ---
        await _memory.add_turn(call_sid, "assistant", ai_text)

        # Update session metadata
        session = await _memory.get_session(call_sid)
        if session:
            session["llm_model"] = llm_resp.model
            session["total_llm_calls"] = session.get("total_llm_calls", 0) + 1
            session["total_tokens_used"] = session.get("total_tokens_used", 0) + llm_resp.tokens_used
            await _memory.save_session(call_sid, session)

        # --- 9. Generate TTS and return audio (with fallback to Speak) ---
        tts_start = time.monotonic()
        record_url = _absolute_audio_url(request, "/webhook/vobiz/recording")
        audio_url, _ = await _generate_and_store_tts(call_sid, ai_text, request)
        tts_ms = int((time.monotonic() - tts_start) * 1000)

        if audio_url and not _is_https_url(audio_url):
            logger.warning(
                "[call:%s] Audio URL is HTTP (%s) — Vobiz requires HTTPS. "
                "Falling back to <Speak>.",
                call_sid,
                audio_url,
            )
            audio_url = ""

        xml = _vobiz_xml(
            text=ai_text if not audio_url else "",
            audio_url=audio_url,
            hangup=(next_state == "ended"),
            record_url=record_url,
        )
        total_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "[call:%s] Latency breakdown: stt=%dms llm=%dms tts=%dms total=%dms | XML=%s chars=%d",
            call_sid,
            stt_ms,
            llm_ms,
            tts_ms,
            total_ms,
            "Play" if audio_url else "Speak",
            len(ai_text),
        )
        return PlainTextResponse(xml, media_type="application/xml")

    except Exception:
        import traceback
        print(f"\n\n[CRASH] recording webhook call_sid={call_sid or 'unknown'}", file=sys.stderr)
        traceback.print_exc()
        logger.exception("[call:%s] UNHANDLED EXCEPTION in recording webhook", call_sid or "unknown")
        return PlainTextResponse(
            _vobiz_xml(
                text="Sorry, we're experiencing a technical issue. Please try again later.",
                hangup=True,
            ),
            media_type="application/xml",
        )


@app.post("/webhook/vobiz/hangup")
@app.get("/webhook/vobiz/hangup")
async def webhook_hangup(request: Request):
    """Handle 'call ended' event from Vobiz.

    Accepts ANY JSON payload — no Pydantic validation so Vobiz can't 422 us.
    """
    call_sid = ""
    try:
        data = await _parse_request_body(request)
        call_sid = _get_field(data, "call_sid", "CallSid", "callSid", "request_uuid", "RequestUUID") or ""
        duration = _get_field(data, "duration_seconds", "Duration", "call_duration") or 0

        if not call_sid:
            logger.info("Vobiz URL test ping on /webhook/vobiz/hangup — payload: %s", data)
            return PlainTextResponse(
                _vobiz_xml(),
                media_type="application/xml",
            )

        logger.info(
            "[call:%s] Call ended. Duration: %ss",
            call_sid,
            duration,
        )

        session = await _memory.get_session(call_sid)
        if session:
            session["duration_seconds"] = duration
            await _memory.save_session(call_sid, session)

        await _memory.end_session(call_sid)
        return PlainTextResponse(
            _vobiz_xml(),
            media_type="application/xml",
        )

    except Exception:
        import traceback
        print(f"\n\n[CRASH] hangup webhook call_sid={call_sid or 'unknown'}", file=sys.stderr)
        traceback.print_exc()
        logger.exception("[call:%s] UNHANDLED EXCEPTION in hangup webhook", call_sid or "unknown")
        return PlainTextResponse(
            _vobiz_xml(),
            media_type="application/xml",
        )


# ---------------------------------------------------------------------------
# Static file serving (for TTS audio files)
# ---------------------------------------------------------------------------

@app.get("/audio/{filename}")
async def serve_audio(filename: str) -> Any:
    """Serve generated TTS audio files."""
    # Path traversal protection
    safe_name = os.path.basename(filename)
    if safe_name != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = os.path.join("/tmp/phone_agent_audio", safe_name)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Audio file not found")

    from fastapi.responses import FileResponse

    return FileResponse(
        filepath,
        media_type="audio/wav",
    )
