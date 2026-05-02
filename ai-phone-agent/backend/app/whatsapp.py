"""Chat Mitra WhatsApp Business API integration for the AI Phone Agent.

Provides async functions to send personalised WhatsApp messages at key
touch-points in the caller journey:

* **Follow-up** — after a call ends, with booking link.
* **Booking confirmation** — with date, time, and session details.
* **Callback offer** — "sorry I missed you" with re-engagement.
* **Human connecting** — notify that a human agent will call back soon.

All messages are warm and personal (not corporate) and written for an
Indian coaching / consulting business context.

Environment variables required::

    CHATMITRA_API_KEY    — API key for Chat Mitra
    CHATMITRA_PHONE_ID   — Registered WhatsApp phone number ID
    CHATMITRA_BASE_URL   — API base URL (default: https://api.chatmitra.com/v1)

    # Personalisation
    BUSINESS_NAME        — Display name of the business
    BUSINESS_OWNER       — Name of the founder / lead coach
    SESSION_DURATION     — e.g. "45 minutes"
    CALENDAR_LINK        — Booking URL (used in follow-up)
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

from app.config import WHATSAPP_PERSONA  # TODO: integrate into message builders

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_CHATMITRA_API_KEY = os.getenv("CHATMITRA_API_KEY", "")
_CHATMITRA_PHONE_ID = os.getenv("CHATMITRA_PHONE_ID", "")
_CHATMITRA_BASE_URL = os.getenv("CHATMITRA_BASE_URL", "https://api.chatmitra.com/v1")

_BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Your Coaching Business")
_BUSINESS_OWNER = os.getenv("BUSINESS_OWNER", "Your Name")
_SESSION_DURATION = os.getenv("SESSION_DURATION", "45 minutes")
_CALENDAR_LINK = os.getenv("CALENDAR_LINK", "")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _http_client() -> httpx.AsyncClient:
    """Create a pre-configured ``httpx.AsyncClient`` for Chat Mitra calls."""
    return httpx.AsyncClient(
        base_url=_CHATMITRA_BASE_URL,
        timeout=httpx.Timeout(15.0, connect=5.0),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {_CHATMITRA_API_KEY}",
        },
    )


def _normalize_phone(phone: str) -> str:
    """Normalise a phone number to E.164 format.

    * Strip whitespace, dashes, and leading ``+`` for validation.
    * Ensure it starts with ``+``.
    * Default to the input if already well-formed.
    """
    cleaned = phone.strip().replace(" ", "").replace("-", "")
    if not cleaned.startswith("+"):
        # Assume Indian number if no country code
        if cleaned.startswith("0"):
            cleaned = "+91" + cleaned[1:]
        elif cleaned.startswith("91") and len(cleaned) >= 10:
            cleaned = "+" + cleaned
        else:
            cleaned = "+91" + cleaned
    return cleaned


async def _send_message(
    phone: str,
    body: str,
    message_type: str = "text",
) -> dict[str, Any]:
    """Low-level helper to send a WhatsApp message via Chat Mitra.

    Args:
        phone: Recipient phone number (E.164 preferred).
        body: Message text content.
        message_type: Chat Mitra message type (default ``text``).

    Returns:
        Parsed JSON response on success, or ``{"error": "...", "success": False}``
        on failure.
    """
    if not _CHATMITRA_API_KEY or not _CHATMITRA_PHONE_ID:
        logger.error("Chat Mitra not configured — CHATMITRA_API_KEY or CHATMITRA_PHONE_ID missing")
        return {"error": "Chat Mitra not configured", "success": False}

    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": _normalize_phone(phone),
        "type": message_type,
        "text": {"body": body},
    }

    async with _http_client() as client:
        try:
            resp = await client.post(
                f"/{_CHATMITRA_PHONE_ID}/messages",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            data["success"] = True
            logger.info(
                "WhatsApp message sent to %s — type=%s, mid=%s",
                phone[-4:],
                message_type,
                data.get("messages", [{}])[0].get("id", "?"),
            )
            return data
        except httpx.HTTPStatusError as exc:
            error_text = exc.response.text[:500]
            logger.error(
                "Chat Mitra HTTP %s: %s",
                exc.response.status_code,
                error_text,
            )
            return {
                "error": f"HTTP {exc.response.status_code}: {error_text}",
                "success": False,
            }
        except httpx.RequestError as exc:
            logger.error("Chat Mitra network error: %s", exc)
            return {"error": f"Network error: {exc}", "success": False}
        except Exception as exc:
            logger.error("Chat Mitra unexpected error: %s", exc)
            return {"error": f"Unexpected error: {exc}", "success": False}


# ---------------------------------------------------------------------------
# Public API — high-level message builders
# ---------------------------------------------------------------------------


async def send_followup(
    phone: str,
    name: str = "there",
    booking_link: str = "",
) -> dict[str, Any]:
    # TODO: integrate WHATSAPP_PERSONA context constant for tone/templates
    """Send a personalised follow-up message after a call ends.

    The message includes the business name, a warm closing, and an
    optional booking link so the recipient can schedule at their convenience.

    Args:
        phone: Recipient's WhatsApp number (E.164 format preferred).
        name: Recipient's first name (default ``"there"``).
        booking_link: Override the default calendar link (optional).

    Returns:
        Chat Mitra API response dict.

    Example::

        result = await send_followup(
            phone="+919999999999",
            name="Rahul",
        )
    """
    link = booking_link or _CALENDAR_LINK or "our booking page"
    body = (
        f"Hi {name}! 👋\n\n"
        f"It was great speaking with you. This is {_BUSINESS_OWNER}'s assistant "
        f"from {_BUSINESS_NAME}.\n\n"
        f"If you'd like to take the next step, you can book a {_SESSION_DURATION} "
        f"session here:\n{link}\n\n"
        f"Feel free to reply here on WhatsApp if you have any questions. "
        f"We're here to help! 😊\n\n"
        f"Warm regards,\n"
        f"Team {_BUSINESS_NAME}"
    )
    return await _send_message(phone, body)


async def send_booking_confirmation(
    phone: str,
    name: str,
    date: str,
    time: str,
) -> dict[str, Any]:
    """Send a booking confirmation message with session details.

    Args:
        phone: Recipient's WhatsApp number.
        name: Recipient's first name.
        date: Human-readable date (e.g. ``"Monday, 15th January"``).
        time: Human-readable time (e.g. ``"10:00 AM"``).

    Returns:
        Chat Mitra API response dict.

    Example::

        result = await send_booking_confirmation(
            phone="+919999999999",
            name="Rahul",
            date="Monday, 15th January",
            time="10:00 AM IST",
        )
    """
    body = (
        f"Hi {name}! ✅\n\n"
        f"Your session with {_BUSINESS_OWNER} is confirmed!\n\n"
        f"📅 *Date:* {date}\n"
        f"🕐 *Time:* {time}\n"
        f"⏱️ *Duration:* {_SESSION_DURATION}\n\n"
        f"We'll send you a calendar invite shortly with the video call link. "
        f"If you need to reschedule, just reply here or call us back.\n\n"
        f"Looking forward to speaking with you! 🙏\n\n"
        f"— Team {_BUSINESS_NAME}"
    )
    return await _send_message(phone, body)


async def send_callback_offer(
    phone: str,
    name: str,
) -> dict[str, Any]:
    """Send a "sorry I missed you" message offering callback slots.

    Used when the human handoff fails, the call drops, or the caller
    couldn't be reached after multiple attempts.

    Args:
        phone: Recipient's WhatsApp number.
        name: Recipient's first name.

    Returns:
        Chat Mitra API response dict.

    Example::

        result = await send_callback_offer(
            phone="+919999999999",
            name="Rahul",
        )
    """
    body = (
        f"Hi {name}, apologies for missing you earlier! 😔\n\n"
        f"This is {_BUSINESS_OWNER}'s assistant from {_BUSINESS_NAME}. "
        f"I'd love to connect with you and understand how we can help.\n\n"
        f"Would you prefer that I call you back? Just reply with a time that works:\n"
        f"• Morning (9 AM - 12 PM)\n"
        f"• Afternoon (12 PM - 4 PM)\n"
        f"• Evening (4 PM - 7 PM)\n\n"
        f"Or feel free to book directly here:\n"
        f"{_CALENDAR_LINK}\n\n"
        f"Talk soon! 🙏"
    )
    return await _send_message(phone, body)


async def send_human_connecting(
    phone: str,
    name: str,
) -> dict[str, Any]:
    """Notify the caller that a human agent will call them back.

    Sets clear expectations (within 2 business hours) so the caller
    isn't left hanging.

    Args:
        phone: Recipient's WhatsApp number.
        name: Recipient's first name.

    Returns:
        Chat Mitra API response dict.

    Example::

        result = await send_human_connecting(
            phone="+919999999999",
            name="Rahul",
        )
    """
    body = (
        f"Hi {name}! 👋\n\n"
        f"I've connected you with {_BUSINESS_OWNER}'s team. "
        f"A human agent will call you back *within the next 2 hours*.\n\n"
        f"If your matter is urgent, feel free to call us directly or reply here "
        f"on WhatsApp — we monitor this closely.\n\n"
        f"Thank you for your patience! 🙏\n\n"
        f"— {_BUSINESS_NAME}"
    )
    return await _send_message(phone, body)


async def send_custom_message(
    phone: str,
    body: str,
) -> dict[str, Any]:
    """Send an arbitrary WhatsApp message (escape hatch for custom use-cases).

    Args:
        phone: Recipient's WhatsApp number.
        body: Raw message text.

    Returns:
        Chat Mitra API response dict.
    """
    return await _send_message(phone, body)
