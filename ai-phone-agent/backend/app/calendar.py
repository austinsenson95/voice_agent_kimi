"""Cal.com REST API integration for the AI Phone Agent.

Provides async functions to:

* Check availability for a given date / event type.
* Create bookings with caller details.
* Cancel existing bookings by UID.
* Format available slots into natural speech for TTS (text-to-speech).

All network calls use ``httpx.AsyncClient`` with sensible timeouts and
graceful error handling. Timezone handling is hard-coded to **Asia/Kolkata**
(IST, UTC+5:30) since the MVP targets Indian businesses.

Environment variables required::

    CAL_API_KEY         — Cal.com API key
    CAL_EVENT_TYPE_ID   — Numeric event-type ID for the coaching session
    CAL_API_VERSION     — API version prefix (default: "v1")

Usage::

    from app.calendar import check_availability, create_booking, format_slots_for_tts

    slots = await check_availability("2024-01-15")
    speech = format_slots_for_tts(slots)
    # Pass *speech* to the TTS engine.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_CAL_API_KEY = os.getenv("CAL_API_KEY", "")
_CAL_EVENT_TYPE_ID = int(os.getenv("CAL_EVENT_TYPE_ID", "0"))
_CAL_API_VERSION = os.getenv("CAL_API_VERSION", "v1")
_CAL_BASE_URL = os.getenv("CAL_BASE_URL", "https://api.cal.com")

_INDIA_TZ = timezone(timedelta(hours=5, minutes=30))  # Asia/Kolkata


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tomorrow() -> str:
    """Return tomorrow's date in ISO-8601 format (YYYY-MM-DD)."""
    return (datetime.now(_INDIA_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")


def _iso_day_bounds(day_iso: str) -> tuple[str, str]:
    """Return (date_from, date_to) ISO strings for a full day in IST."""
    dt = datetime.strptime(day_iso, "%Y-%m-%d").replace(tzinfo=_INDIA_TZ)
    start = dt.isoformat()
    end = (dt + timedelta(days=1)).isoformat()
    return start, end


def _http_client() -> httpx.AsyncClient:
    """Create a pre-configured ``httpx.AsyncClient`` for Cal.com calls."""
    return httpx.AsyncClient(
        base_url=_CAL_BASE_URL,
        timeout=httpx.Timeout(15.0, connect=5.0),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )


def _extract_slot_times(slots_payload: dict[str, Any]) -> list[str]:
    """Extract available slot start times from a Cal.com availability response.

    Cal.com v1 returns something like::

        {
          "slots": {
            "2024-01-15": [
              {"time": "2024-01-15T10:00:00.000Z"},
              {"time": "2024-01-15T10:30:00.000Z"}
            ]
          }
        }

    We flatten the per-date lists and return ISO-8601 strings.
    """
    results: list[str] = []
    slots_by_date = slots_payload.get("slots") or {}
    if isinstance(slots_by_date, dict):
        for _day, slot_list in slots_by_date.items():
            if isinstance(slot_list, list):
                for slot in slot_list:
                    if isinstance(slot, dict):
                        time_val = slot.get("time")
                        if time_val:
                            results.append(str(time_val))
    elif isinstance(slots_by_date, list):
        # Some API versions return a flat list
        for slot in slots_by_date:
            if isinstance(slot, dict):
                time_val = slot.get("time")
                if time_val:
                    results.append(str(time_val))
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def check_availability(
    date: str | None = None,
    duration: int = 30,
) -> list[str]:
    """Check Cal.com availability for a given date.

    Args:
        date: ISO-8601 date string (YYYY-MM-DD). If ``None``, uses tomorrow.
        duration: Desired session length in minutes (default 30).

    Returns:
        A list of available slot start times in ISO-8601 format.
        Returns an empty list on API errors or when no slots are found.

    Example::

        slots = await check_availability("2024-01-15")
        # ["2024-01-15T04:30:00.000Z", "2024-01-15T05:00:00.000Z", ...]
    """
    if not _CAL_API_KEY or not _CAL_EVENT_TYPE_ID:
        logger.error("Cal.com not configured — CAL_API_KEY or CAL_EVENT_TYPE_ID missing")
        return []

    target_date = date or _tomorrow()
    date_from, date_to = _iso_day_bounds(target_date)

    params = {
        "apiKey": _CAL_API_KEY,
        "eventTypeId": _CAL_EVENT_TYPE_ID,
        "dateFrom": date_from,
        "dateTo": date_to,
        "duration": duration,
    }

    async with _http_client() as client:
        try:
            resp = await client.get(
                f"/api/{_CAL_API_VERSION}/availability",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Cal.com availability HTTP %s: %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return []
        except httpx.RequestError as exc:
            logger.error("Cal.com availability network error: %s", exc)
            return []
        except Exception as exc:
            logger.error("Cal.com availability unexpected error: %s", exc)
            return []

    slots = _extract_slot_times(data)
    logger.info("Found %d available slots for %s", len(slots), target_date)
    return slots


async def create_booking(
    name: str,
    email: str,
    start_time: str,
    phone: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """Create a new booking on Cal.com.

    Args:
        name: Attendee's full name.
        email: Attendee's email address.
        start_time: ISO-8601 datetime with timezone (e.g. ``2024-01-15T10:00:00+05:30``).
        phone: Attendee's phone number (E.164 format preferred).
        notes: Optional notes / questions from the attendee.

    Returns:
        The full JSON response from Cal.com (includes ``uid``, ``bookingUid``,
        confirmation link, etc.). On failure, returns a dict with
        ``{"error": "...", "success": False}``.

    Example::

        result = await create_booking(
            name="Rahul Sharma",
            email="rahul@example.com",
            start_time="2024-01-15T10:00:00+05:30",
            phone="+919999999999",
            notes="Interested in executive coaching",
        )
        # result["bookingUid"] → unique booking ID
        # result["bookingLink"] → confirmation URL
    """
    if not _CAL_API_KEY or not _CAL_EVENT_TYPE_ID:
        logger.error("Cal.com not configured — CAL_API_KEY or CAL_EVENT_TYPE_ID missing")
        return {"error": "Cal.com not configured", "success": False}

    payload = {
        "eventTypeId": _CAL_EVENT_TYPE_ID,
        "start": start_time,
        "timeZone": "Asia/Kolkata",
        "language": "en",
        "responses": {
            "name": name,
            "email": email,
            "phone": phone,
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
                f"/api/{_CAL_API_VERSION}/bookings",
                json=payload,
                headers={"Authorization": f"Bearer {_CAL_API_KEY}"},
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
    """Format a list of ISO-8601 slot times into natural speech for TTS.

    Handles edge cases elegantly:

    * **No slots** → apology + offer to check another day.
    * **One slot** → single-slot phrasing.
    * **Two slots** → "X or Y" phrasing.
    * **Three+ slots** → Oxford-comma list with "and" before the last item.

    All times are converted to **12-hour AM/PM** format in **IST** for the caller.

    Args:
        slots: List of ISO-8601 datetime strings (UTC or offset-aware).

    Returns:
        A natural-language string ready for text-to-speech synthesis.

    Example::

        speech = format_slots_for_tts([
            "2024-01-15T04:30:00.000Z",
            "2024-01-15T08:30:00.000Z",
            "2024-01-15T10:30:00.000Z",
        ])
        # "I have slots at 10:00 AM, 2:00 PM, and 4:00 PM. Which works for you?"
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

    Example::

        ok = await cancel_booking("abc123-def456")
        if ok:
            print("Booking cancelled successfully")
    """
    if not _CAL_API_KEY:
        logger.error("Cal.com not configured — CAL_API_KEY missing")
        return False

    if not booking_uid:
        logger.warning("cancel_booking called with empty booking_uid")
        return False

    payload = {
        "apiKey": _CAL_API_KEY,
        "uid": booking_uid,
        "reason": "Cancelled via AI Phone Agent",
    }

    async with _http_client() as client:
        try:
            resp = await client.post(
                f"/api/{_CAL_API_VERSION}/bookings/{booking_uid}/cancel",
                json=payload,
                headers={"Authorization": f"Bearer {_CAL_API_KEY}"},
            )
            if resp.status_code in (200, 202, 204):
                logger.info("Booking %s cancelled successfully", booking_uid)
                return True
            # Some Cal.com versions return 409/404 for already-cancelled or not-found
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
