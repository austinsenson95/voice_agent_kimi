"""FastAPI route definitions for the AI Phone Agent integrations.

These routers are designed to be **included** into the main FastAPI app::

    from fastapi import FastAPI
    from app.routes import calendar_router, whatsapp_router, battle_card_router, objections_router

    app = FastAPI()
    app.include_router(calendar_router)
    app.include_router(whatsapp_router)
    app.include_router(battle_card_router)
    app.include_router(objections_router)

Each router is self-contained and maps to the integration modules in
:mod:`app.calendar`, :mod:`app.whatsapp`, :mod:`app.battle_card`,
and :mod:`app.objections`.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.calendar import check_availability, create_booking, cancel_booking
from app.whatsapp import (
    send_followup,
    send_booking_confirmation,
    send_callback_offer,
    send_human_connecting,
)
from app.battle_card import BattleCard, get_default_card
from app.objections import (
    detect_objection,
    get_objection_response,
    should_escalate,
    get_all_objections,
)
from app.config import can_call  # TODO: gate outbound dispatch with can_call(phone) — reject with 403 if False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CheckAvailabilityRequest(BaseModel):
    """POST /api/calendar/check request body."""

    date: str | None = Field(
        default=None,
        description="ISO-8601 date (YYYY-MM-DD). Uses tomorrow if omitted.",
        examples=["2024-01-15"],
    )


class CheckAvailabilityResponse(BaseModel):
    """POST /api/calendar/check response body."""

    slots: list[str] = Field(
        default_factory=list,
        description="List of available slot start times in ISO-8601 format.",
    )
    formatted_for_tts: str = Field(
        default="",
        description="Natural-language version of the slots for TTS.",
    )
    requested_date: str | None = Field(default=None)


class BookRequest(BaseModel):
    """POST /api/calendar/book request body."""

    name: str = Field(..., min_length=1, description="Attendee full name")
    email: str = Field(..., min_length=3, description="Attendee email address")
    start_time: str = Field(
        ...,
        description="ISO-8601 datetime with timezone, e.g. 2024-01-15T10:00:00+05:30",
    )
    phone: str = Field(default="", description="Phone number in E.164 format")
    notes: str = Field(default="", description="Optional notes from the attendee")


class BookResponse(BaseModel):
    """POST /api/calendar/book response body."""

    success: bool
    booking_uid: str | None = None
    booking_link: str | None = None
    start_time: str | None = None
    attendee_name: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class CancelRequest(BaseModel):
    """POST /api/calendar/cancel request body."""

    booking_uid: str = Field(..., description="The Cal.com booking UID to cancel")


class WhatsAppFollowupRequest(BaseModel):
    """POST /api/whatsapp/followup request body."""

    phone: str = Field(..., description="Recipient phone number (E.164)")
    name: str = Field(default="there", description="Recipient first name")
    booking_link: str = Field(default="", description="Override calendar link")


class WhatsAppBookingConfirmRequest(BaseModel):
    """POST /api/whatsapp/booking-confirm request body."""

    phone: str = Field(..., description="Recipient phone number")
    name: str = Field(..., description="Recipient first name")
    date: str = Field(..., description="Human-readable date string")
    time: str = Field(..., description="Human-readable time string")


class WhatsAppCallbackRequest(BaseModel):
    """POST /api/whatsapp/callback-offer request body."""

    phone: str = Field(..., description="Recipient phone number")
    name: str = Field(..., description="Recipient first name")


class WhatsAppHumanConnectRequest(BaseModel):
    """POST /api/whatsapp/human-connect request body."""

    phone: str = Field(..., description="Recipient phone number")
    name: str = Field(..., description="Recipient first name")


class WhatsAppGenericResponse(BaseModel):
    """Generic WhatsApp send response."""

    success: bool
    message_id: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class BattleCardUpdateRequest(BaseModel):
    """PUT /api/battle-card request body."""

    business_name: str | None = None
    business_owner: str | None = None
    service_description: str | None = None
    pricing_range: str | None = None
    session_duration: str | None = None
    ideal_client: str | None = None
    unique_selling_prop: str | None = None
    testimonial_1: str | None = None
    testimonial_2: str | None = None
    website: str | None = None
    calendar_link: str | None = None
    whatsapp_number: str | None = None


class ObjectionDetectRequest(BaseModel):
    """POST /api/objections/detect request body."""

    user_text: str = Field(..., min_length=1, description="Caller text to analyse")


# ---------------------------------------------------------------------------
# Router instances
# ---------------------------------------------------------------------------

calendar_router = APIRouter(prefix="/api/calendar", tags=["calendar"])
whatsapp_router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])
battle_card_router = APIRouter(prefix="/api/battle-card", tags=["battle-card"])
objections_router = APIRouter(prefix="/api/objections", tags=["objections"])


# ---------------------------------------------------------------------------
# Calendar routes
# ---------------------------------------------------------------------------


@calendar_router.post("/check", response_model=CheckAvailabilityResponse)
async def api_calendar_check(body: CheckAvailabilityRequest) -> dict[str, Any]:
    """Check Cal.com availability for a given date.

    Returns available time slots in ISO-8601 format plus a TTS-friendly
    natural-language string.
    """
    from app.calendar import format_slots_for_tts

    slots = await check_availability(date=body.date)
    speech = format_slots_for_tts(slots)
    return {
        "slots": slots,
        "formatted_for_tts": speech,
        "requested_date": body.date,
    }


@calendar_router.post("/book", response_model=BookResponse)
async def api_calendar_book(body: BookRequest) -> dict[str, Any]:
    """Create a new Cal.com booking."""
    result = await create_booking(
        name=body.name,
        email=body.email,
        start_time=body.start_time,
        phone=body.phone,
        notes=body.notes,
    )
    if not result.get("success"):
        raise HTTPException(status_code=422, detail=result.get("error", "Booking failed"))

    # Normalise the Cal.com response into a stable schema
    return {
        "success": True,
        "booking_uid": result.get("uid") or result.get("bookingUid"),
        "booking_link": result.get("bookingLink") or result.get("metadata", {}).get("videoCallUrl"),
        "start_time": result.get("startTime"),
        "attendee_name": body.name,
        "raw": result,
    }


@calendar_router.post("/cancel")
async def api_calendar_cancel(body: CancelRequest) -> dict[str, bool]:
    """Cancel an existing Cal.com booking by UID."""
    ok = await cancel_booking(body.booking_uid)
    if not ok:
        raise HTTPException(status_code=400, detail="Cancellation failed — booking may not exist")
    return {"success": True}


# ---------------------------------------------------------------------------
# WhatsApp routes
# ---------------------------------------------------------------------------


@whatsapp_router.post("/followup", response_model=WhatsAppGenericResponse)
async def api_whatsapp_followup(body: WhatsAppFollowupRequest) -> dict[str, Any]:
    """Send a personalised follow-up message after a call ends."""
    result = await send_followup(
        phone=body.phone,
        name=body.name,
        booking_link=body.booking_link,
    )
    return {
        "success": result.get("success", False),
        "message_id": result.get("messages", [{}])[0].get("id"),
        "raw": result,
    }


@whatsapp_router.post("/booking-confirm", response_model=WhatsAppGenericResponse)
async def api_whatsapp_booking_confirm(
    body: WhatsAppBookingConfirmRequest,
) -> dict[str, Any]:
    """Send a booking confirmation message with date, time, and session details."""
    result = await send_booking_confirmation(
        phone=body.phone,
        name=body.name,
        date=body.date,
        time=body.time,
    )
    return {
        "success": result.get("success", False),
        "message_id": result.get("messages", [{}])[0].get("id"),
        "raw": result,
    }


@whatsapp_router.post("/callback-offer", response_model=WhatsAppGenericResponse)
async def api_whatsapp_callback_offer(body: WhatsAppCallbackRequest) -> dict[str, Any]:
    """Send a 'sorry I missed you' callback offer message."""
    result = await send_callback_offer(phone=body.phone, name=body.name)
    return {
        "success": result.get("success", False),
        "message_id": result.get("messages", [{}])[0].get("id"),
        "raw": result,
    }


@whatsapp_router.post("/human-connect", response_model=WhatsAppGenericResponse)
async def api_whatsapp_human_connect(
    body: WhatsAppHumanConnectRequest,
) -> dict[str, Any]:
    """Notify the caller that a human agent will call them back."""
    result = await send_human_connecting(phone=body.phone, name=body.name)
    return {
        "success": result.get("success", False),
        "message_id": result.get("messages", [{}])[0].get("id"),
        "raw": result,
    }


# ---------------------------------------------------------------------------
# Battle card routes
# ---------------------------------------------------------------------------


@battle_card_router.get("")
async def api_battle_card_get() -> dict[str, str]:
    """Return the current battle card configuration.

    Includes all business context settings loaded from environment variables.
    """
    card = get_default_card()
    return card.to_dict()


@battle_card_router.put("")
async def api_battle_card_put(body: BattleCardUpdateRequest) -> dict[str, str]:
    """Update battle card configuration fields.

    Only fields provided in the request body are updated. Changes are
    applied in-memory to the singleton instance (does **not** persist to
    env vars or disk in this MVP).
    """
    card = get_default_card()
    updates = body.model_dump(exclude_unset=True)

    field_map = {
        "business_name": "business_name",
        "business_owner": "business_owner",
        "service_description": "service_description",
        "pricing_range": "pricing_range",
        "session_duration": "session_duration",
        "ideal_client": "ideal_client",
        "unique_selling_prop": "unique_selling_prop",
        "testimonial_1": "testimonial_1",
        "testimonial_2": "testimonial_2",
        "website": "website",
        "calendar_link": "calendar_link",
        "whatsapp_number": "whatsapp_number",
    }

    for req_field, attr_name in field_map.items():
        if req_field in updates and updates[req_field] is not None:
            setattr(card, attr_name, updates[req_field])
            logger.info("BattleCard updated — %s = %s", req_field, updates[req_field])

    return card.to_dict()


# ---------------------------------------------------------------------------
# Objections routes
# ---------------------------------------------------------------------------


@objections_router.get("")
async def api_objections_list() -> list[dict[str, Any]]:
    """Return the full objection library for dashboard display."""
    return get_all_objections()


@objections_router.post("/detect")
async def api_objections_detect(body: ObjectionDetectRequest) -> dict[str, Any]:
    """Detect an objection in caller text and return the response.

    Uses the business context from the current battle card for template
    substitution in the response text.
    """
    card = get_default_card()
    obj = detect_objection(body.user_text)
    if obj is None:
        return {
            "detected": False,
            "objection_id": None,
            "response": None,
            "escalate_to_human": False,
        }

    response_text = get_objection_response(obj["id"], card._context)
    escalate = should_escalate(obj["id"])

    return {
        "detected": True,
        "objection_id": obj["id"],
        "response": response_text,
        "follow_up": obj.get("follow_up"),
        "escalate_to_human": escalate,
    }
