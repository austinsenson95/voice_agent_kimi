"""
Voice Pipeline — Sarvam AI Integration

Handles the audio↔text bridge of the phone agent:
    - STT (Speech-to-Text): Caller audio → Hindi/English text
    - TTS (Text-to-Speech): AI response text → audio for caller

Sarvam AI models:
    - saarika:v2 — STT, supports Indian languages (Hindi, Hinglish, English)
    - bulbul:v1 — TTS, natural Indian voice

Both endpoints are async and return quickly enough for real-time voice.
"""

from __future__ import annotations

import base64
import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# STT: Speech-to-Text
# ---------------------------------------------------------------------------

async def sarvam_stt(audio_url: str) -> str:
    """Download audio from URL and transcribe using Sarvam STT (saarika:v2).

    This function performs two HTTP requests:
        1. GET the audio file from the provided URL (Vobiz-hosted)
        2. POST the audio bytes to Sarvam's /speech-to-text endpoint

    Args:
        audio_url: Publicly accessible URL to the audio recording

    Returns:
        Transcribed text (Hindi/English mixed). Empty string on failure
        so the LLM can ask the user to repeat themselves.
    """
    settings = get_settings()
    api_key = settings.SARVAM_API_KEY
    base_url = settings.SARVAM_BASE_URL

    if not api_key:
        logger.error("SARVAM_API_KEY not configured — cannot transcribe audio")
        return ""

    audio_bytes: Optional[bytes] = None

    # --- Step 1: Download audio from Vobiz ---
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            logger.debug("Downloading audio from %s", audio_url)
            audio_resp = await client.get(audio_url)
            audio_resp.raise_for_status()
            audio_bytes = audio_resp.content
            logger.debug("Downloaded %d bytes of audio", len(audio_bytes))
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Failed to download audio: HTTP %d — %s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return ""
    except httpx.TimeoutException:
        logger.error("Timeout downloading audio from %s", audio_url)
        return ""
    except Exception as exc:
        logger.error("Unexpected error downloading audio: %s", exc)
        return ""

    # --- Step 2: Send to Sarvam STT ---
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            # Sarvam expects multipart/form-data with the audio file
            files = {
                "file": ("recording.wav", audio_bytes, "audio/wav"),
            }
            data = {
                "model": "saarika:v2",
                "language_code": settings.AGENT_LANGUAGE,  # e.g. "hi-IN"
                "with_timestamps": "false",
            }
            headers = {
                "api-subscription-key": api_key,
            }

            logger.debug("Sending %d bytes to Sarvam STT", len(audio_bytes))
            resp = await client.post(
                f"{base_url}/speech-to-text",
                headers=headers,
                files=files,
                data=data,
            )
            resp.raise_for_status()
            result = resp.json()

            # Sarvam returns a list of transcripts
            transcripts = result.get("transcript", "")
            if isinstance(transcripts, list) and transcripts:
                text = " ".join(t.get("text", "") for t in transcripts)
            elif isinstance(transcripts, str):
                text = transcripts
            else:
                text = ""

            logger.info("STT result: %r", text[:100])
            return text.strip()

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Sarvam STT API error: HTTP %d — %s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return ""
    except httpx.TimeoutException:
        logger.error("Sarvam STT request timed out")
        return ""
    except Exception as exc:
        logger.error("Unexpected error in Sarvam STT: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# TTS: Text-to-Speech
# ---------------------------------------------------------------------------

async def sarvam_tts(text: str) -> Optional[bytes]:
    """Convert text to speech using Sarvam TTS (bulbul:v1).

    Args:
        text: The AI response text to speak. Keep under 500 chars
              for low latency (Sarvam has a limit per request).

    Returns:
        Raw audio bytes (WAV format) ready to be saved/played, or None
        on failure so the webhook can fall back to returning text.
    """
    settings = get_settings()
    api_key = settings.SARVAM_API_KEY
    base_url = settings.SARVAM_BASE_URL

    if not api_key:
        logger.error("SARVAM_API_KEY not configured — cannot synthesize speech")
        return None

    if not text or not text.strip():
        logger.warning("Empty text passed to TTS — skipping")
        return None

    # Truncate long text to avoid API limits and reduce latency.
    # In production, chunking + streaming would be better for long responses.
    MAX_CHARS = 500
    if len(text) > MAX_CHARS:
        logger.warning(
            "TTS text truncated from %d to %d chars", len(text), MAX_CHARS
        )
        text = text[:MAX_CHARS]

    payload = {
        "inputs": [text],
        "target_language_code": settings.AGENT_LANGUAGE,  # e.g. "hi-IN"
        "speaker": "meera",  # Female Indian voice — natural for coaching
        "model": "bulbul:v1",
        "pitch": 0.0,
        "pace": 1.0,
        "loudness": 1.0,
    }
    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            logger.debug("Sending TTS request for %d chars", len(text))
            resp = await client.post(
                f"{base_url}/text-to-speech",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            result = resp.json()

            # Sarvam returns base64-encoded audio
            audios = result.get("audios", [])
            if audios and len(audios) > 0:
                audio_b64 = audios[0]
                audio_bytes = base64.b64decode(audio_b64)
                logger.debug(
                    "TTS succeeded: %d bytes of audio generated", len(audio_bytes)
                )
                return audio_bytes
            else:
                logger.error("Sarvam TTS returned no audio data")
                return None

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Sarvam TTS API error: HTTP %d — %s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return None
    except httpx.TimeoutException:
        logger.error("Sarvam TTS request timed out")
        return None
    except Exception as exc:
        logger.error("Unexpected error in Sarvam TTS: %s", exc)
        return None
