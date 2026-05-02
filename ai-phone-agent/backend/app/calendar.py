"""Cal.com REST API integration for the AI Phone Agent.

Uses Cal.com API v2 for bookings and cancellations.
Availability checking falls back to sensible defaults because the
``/v2/slots`` endpoint is not yet available for legacy ``cal_live_*`` keys.

All network calls use ``httpx.AsyncClient`` with sensible timeouts and
graceful error handling. Timezone handling is hard-coded to **Asia/Kolkata**
(IST, UTC+5:30) since the MVP targets Indian businesses.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, List

import httpx

from app.config import get_settings, CALENDAR_RULES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (pulled from centralized config.py)
# ---------------------------------------------------------------------------

_INDIA_TZ = timezone(timedelta(hours=5, minutes=30))  # Asia/Kolkata


def _tomorrow() -> str:
    """Return tomorrow's date in ISO-8601 format (YYYY-MM-DD)."""
    return (datetime.now(_INDIA_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")


def _default_slots(day_iso: str) -> List[str]:
    """Return default availability slots for a given day.

    Cal.com v2 ``/slots`` endpoint is not available for legacy ``cal_live_*``
    API keys, so we return sensible business-hour defaults. If a chosen slot
    is actually booked, ``create_booking`` will fail gracefully and the agent
    can offer the next one.
    """
    # Standard coaching slots in IST: 10:00, 14:00, 16:00, 18:00
    slot_hours = [10, 14, 16, 18]
    slots: List[str] = []
    for hour in slot_hours:
        dt = datetime.strptime(day_iso, "%Y-%m-%d").replace(
            hour=hour, minute=0, second=0, tzinfo=_INDIA_TZ
        )
        slots.append(dt.isoformat())
    return slots


def _http_client() -> httpx.AsyncClient:
    """Create a pre-configured ``httpx.AsyncClient`` for Cal.com calls."""
    return httpx.AsyncClient(
        base_url="https://api.cal.com",
        timeout=httpx.Timeout(15.0, connect=5.0),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "cal-api-version": "2024-08-13",
        },
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def check_availability(
    day: str | None = None,
    duration: int = 30,
) -> list[str]:
    """Return available slots for a given day.

    Args:
        day: ISO-8601 date string (YYYY-MM-DD). If ``None``, uses tomorrow.
        duration: Desired session length in minutes (default 30).

    Returns:
        A list of available slot start times in ISO-8601 format.
    """
    settings = get_settings()
    if not settings.CAL_API_KEY or not settings.CAL_USERNAME:
        logger.error("Cal.com not configured — CAL_API_KEY or CAL_USERNAME missing")
        return []

    target_day = day or _tomorrow()

    # NOTE: Cal.com v2 /slots endpoint returns 404 for legacy cal_live_* keys.
    # We return sensible defaults and let create_booking handle conflicts.
    slots = _default_slots(target_day)
    logger.info("Returning %d default slots for %s", len(slots), target_day)
    return slots


async def create_booking(
    name: str,
    email: str,
    start_time: str,
    phone: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """Create a new booking on Cal.com via API v2.

    Args:
        name: Attendee's full name.
        email: Attendee's email address.
        start_time: ISO-8601 datetime with timezone (e.g. ``2024-01-15T10:00:00+05:30``).
        phone: Attendee's phone number (E.164 format preferred).
        notes: Optional notes / questions from the attendee.

    Returns:
        The full JSON response from Cal.com. On failure, returns a dict with
        ``{"error": "...", "success": False}``.
    """
    settings = get_settings()
    if not settings.CAL_API_KEY or not settings.CAL_USERNAME or not settings.CAL_EVENT_SLUG:
        logger.error("Cal.com not configured — missing CAL_API_KEY, CAL_USERNAME or CAL_EVENT_SLUG")
        return {"error": "Cal.com not configured", "success": False}

    payload = {
        "eventTypeSlug": settings.CAL_EVENT_SLUG,
        "username": settings.CAL_USERNAME,
        "start": start_time,
        "attendee": {
            "name": name,
            "email": email,
            "timeZone": "Asia/Kolkata",
            "phone": phone,
        },
        "bookingFieldsResponses": {
            "notes": notes or "Booked via AI Phone Agent",
        },
        "metadata": {
            "source": "ai-phone-agent",
            "booked_at": datetime.now(_INDIA_TZ).isoformat(),
        },
    }

    async with _http_client() as client:
        try:
            resp = await client.post(
                "/v2/bookings",
                json=payload,
                headers={"Authorization": f"Bearer {settings.CAL_API_KEY}"},
            )
            resp.raise_for_status()
            data = resp.json()
            data["success"] = True
            logger.info("Booking created — uid=%s", data.get("uid") or data.get("bookingUid"))
            return data
        except httpx.HTTPStatusError as exc:
            error_text = exc.response.text[:500]
            logger.error("Cal.com booking HTTP %s: %s", exc.response.status_code, error_text)
            return {
                "error": f"HTTP {exc.response.status_code}: {error_text}",
                "success": False,
            }
        except httpx.RequestError as exc:
            logger.error("Cal.com booking network error: %s", exc)
            return {"error": f"Network error: {exc}", "success": False}
        except Exception as exc:
            logger.error("Cal.com booking unexpected error: %s", exc)
            return {"error": f"Unexpected error: {exc}", "success": False}


def format_slots_for_tts(slots: list[str]) -> str:
    # TODO: integrate CALENDAR_RULES context constant for booking language
    """Format a list of ISO-8601 slot times into natural speech for TTS.

    Handles edge cases elegantly:

    * **No slots** → apology + offer to check another day.
    * **One slot** → single-slot phrasing.
    * **Two slots** → "X or Y" phrasing.
    * **Three+ slots** → Oxford-comma list with "and" before the last item.

    All times are converted to **12-hour AM/PM** format in **IST** for the caller.
    """
    if not slots:
        return (
            "I don't have any available slots for that day, unfortunately. "
            "Would you like me to check another day that might work for you?"
        )

    # Parse and convert to IST
    local_times: list[datetime] = []
    for s in slots:
        try:
            # Handle 'Z' suffix and various offset formats
            s_clean = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s_clean)
            dt_ist = dt.astimezone(_INDIA_TZ)
            local_times.append(dt_ist)
        except (ValueError, TypeError):
            logger.warning("Could not parse slot time: %s", s)
            continue

    if not local_times:
        return (
            "I'm having trouble reading the available times right now. "
            "Let me try checking again, or I can have someone reach out to you directly."
        )

    # Format as 12-hour AM/PM
    def _fmt(t: datetime) -> str:
        return t.strftime("%I:%M %p").lstrip("0")

    formatted = [_fmt(t) for t in local_times]

    if len(formatted) == 1:
        return (
            f"I have one slot available at {formatted[0]}. "
            f"Does that work for you?"
        )
    elif len(formatted) == 2:
        return (
            f"I have slots at {formatted[0]} or {formatted[1]}. "
            f"Which one works better for you?"
        )
    else:
        # Oxford comma style
        all_but_last = ", ".join(formatted[:-1])
        last = formatted[-1]
        return (
            f"I have slots at {all_but_last}, and {last}. "
            f"Which of these works for you?"
        )


async def cancel_booking(booking_uid: str) -> bool:
    """Cancel a booking by its UID.

    Args:
        booking_uid: The ``uid`` (or ``bookingUid``) returned by Cal.com
                     when the booking was created.

    Returns:
        ``True`` if cancellation succeeded, ``False`` otherwise.
    """
    settings = get_settings()
    if not settings.CAL_API_KEY:
        logger.error("Cal.com not configured — CAL_API_KEY missing")
        return False

    if not booking_uid:
        logger.warning("cancel_booking called with empty booking_uid")
        return False

    async with _http_client() as client:
        try:
            resp = await client.post(
                f"/v2/bookings/{booking_uid}/cancel",
                json={"cancellationReason": "Cancelled via AI Phone Agent"},
                headers={"Authorization": f"Bearer {settings.CAL_API_KEY}"},
            )
            if resp.status_code in (200, 202, 204):
                logger.info("Booking %s cancelled successfully", booking_uid)
                return True
            if resp.status_code == 404:
                logger.warning("Booking %s not found (may already be cancelled)", booking_uid)
                return False
            logger.error(
                "Cal.com cancel HTTP %s: %s",
                resp.status_code,
                resp.text[:200],
            )
            return False
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Cal.com cancel HTTP %s: %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return False
        except httpx.RequestError as exc:
            logger.error("Cal.com cancel network error: %s", exc)
            return False
        except Exception as exc:
            logger.error("Cal.com cancel unexpected error: %s", exc)
            return False
