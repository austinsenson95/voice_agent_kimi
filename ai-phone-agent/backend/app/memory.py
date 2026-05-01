"""
Session Memory — Redis-backed with in-memory fallback

Every active phone call gets a "session" stored as a JSON dict.
The session tracks: conversation state, turn history, metadata.

Storage strategy:
    - Production: Redis (with 24h TTL for auto-cleanup of abandoned calls)
    - Local dev:  in-memory dict (no Redis needed, data lost on restart)

Redis keys:
    session:{call_sid}  →  JSON-serialized CallSession dict
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.schemas import Turn

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-memory fallback (for local testing without Redis)
# ---------------------------------------------------------------------------

class _InMemoryStore:
    """Simple dict-based store that mirrors Redis semantics.

    Used when REDIS_URL is not set — perfect for local development
    or running unit tests without a Redis dependency.
    """

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}

    async def get(self, key: str) -> Optional[str]:
        entry = self._data.get(key)
        if entry is None:
            return None
        # Simple TTL check
        if "expires_at" in entry:
            if datetime.now(timezone.utc).timestamp() > entry["expires_at"]:
                del self._data[key]
                return None
        return entry.get("value")

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        entry: Dict[str, Any] = {"value": value}
        if ex:
            entry["expires_at"] = datetime.now(timezone.utc).timestamp() + ex
        self._data[key] = entry

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def keys(self, pattern: str) -> List[str]:
        # Simple prefix matching (no glob)
        prefix = pattern.replace("*", "")
        return [k for k in self._data.keys() if k.startswith(prefix)]


# ---------------------------------------------------------------------------
# SessionMemory class
# ---------------------------------------------------------------------------

class SessionMemory:
    """Manages phone call sessions with Redis (production) or in-memory (dev).

    Usage:
        memory = SessionMemory()
        await memory.save_session("CA123", {"call_sid": "CA123", ...})
        session = await memory.get_session("CA123")
        await memory.add_turn("CA123", "user", "Hello")
        turns = await memory.get_turns("CA123", last_n=5)
    """

    def __init__(self) -> None:
        settings = get_settings()
        redis_url = settings.REDIS_URL
        self._ttl = settings.SESSION_TTL_SECONDS

        if redis_url:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._using_redis = True
                logger.info("SessionMemory using Redis at %s", redis_url)
            except Exception as exc:
                logger.warning(
                    "Failed to connect to Redis (%s). Falling back to in-memory.",
                    exc,
                )
                self._redis = _InMemoryStore()
                self._using_redis = False
        else:
            self._redis = _InMemoryStore()
            self._using_redis = False
            logger.info("REDIS_URL not set — using in-memory session store")

    def _key(self, call_sid: str) -> str:
        """Build the Redis key for a session."""
        return f"session:{call_sid}"

    async def get_session(self, call_sid: str) -> Optional[Dict[str, Any]]:
        """Fetch a session by call_sid.

        Returns:
            Session dict or None if not found/expired.
        """
        try:
            raw = await self._redis.get(self._key(call_sid))
            if raw is None:
                return None
            if isinstance(raw, str):
                return json.loads(raw)
            # In-memory fallback returns dict directly
            return raw
        except Exception as exc:
            logger.error("Error reading session %s: %s", call_sid, exc)
            return None

    async def save_session(
        self, call_sid: str, session: Dict[str, Any]
    ) -> None:
        """Save (or update) a session with TTL.

        The TTL ensures abandoned calls are cleaned up automatically
        after 24 hours — no manual garbage collection needed.
        """
        try:
            session["updated_at"] = datetime.now(timezone.utc).isoformat()
            raw = json.dumps(session, default=str)
            await self._redis.set(self._key(call_sid), raw, ex=self._ttl)
        except Exception as exc:
            logger.error("Error saving session %s: %s", call_sid, exc)

    async def add_turn(
        self, call_sid: str, role: str, content: str
    ) -> None:
        """Append a conversation turn to the session's history.

        This is the primary way conversation history grows. Each user
        message and each AI response becomes a Turn in the list.
        """
        session = await self.get_session(call_sid)
        if session is None:
            logger.warning(
                "Cannot add turn — session %s not found", call_sid
            )
            return

        turns = session.get("turns", [])
        turn = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        turns.append(turn)
        session["turns"] = turns
        await self.save_session(call_sid, session)

    async def get_turns(
        self, call_sid: str, last_n: int = 10
    ) -> List[Dict[str, str]]:
        """Get the most recent N conversation turns.

        We only return the last N turns to keep the LLM prompt size
        manageable and latency low. For very long calls, older context
        is summarized or dropped.

        Returns:
            List of {"role": "user|assistant", "content": "..."} dicts
        """
        session = await self.get_session(call_sid)
        if session is None:
            return []

        turns = session.get("turns", [])
        # Return only role/content — timestamp is internal metadata
        recent = turns[-last_n:] if len(turns) > last_n else turns
        return [{"role": t["role"], "content": t["content"]} for t in recent]

    async def end_session(self, call_sid: str) -> None:
        """Mark a session as ended and set a short TTL for cleanup.

        After a call hangs up, we keep the session around briefly
        (for analytics/dashboard) then let it expire.
        """
        session = await self.get_session(call_sid)
        if session is None:
            return

        session["state"] = "ended"
        session["ended_at"] = datetime.now(timezone.utc).isoformat()
        try:
            raw = json.dumps(session, default=str)
            # Shorter TTL after hangup — 1 hour is enough for post-call processing
            await self._redis.set(self._key(call_sid), raw, ex=3600)
        except Exception as exc:
            logger.error("Error ending session %s: %s", call_sid, exc)

    async def list_active_sessions(self) -> List[Dict[str, Any]]:
        """List all currently active (not ended) sessions.

        Used by the /health endpoint and dashboard to show active calls.
        """
        active = []
        try:
            if self._using_redis:
                # Scan for session:* keys
                cursor = 0
                while True:
                    cursor, keys = await self._redis.scan(
                        cursor=cursor, match="session:*", count=100
                    )
                    for key in keys:
                        raw = await self._redis.get(key)
                        if raw:
                            session = json.loads(raw) if isinstance(raw, str) else raw
                            if session.get("state") != "ended":
                                active.append(session)
                    if cursor == 0:
                        break
            else:
                # In-memory fallback
                for key in self._redis.keys("session:*"):
                    raw = await self._redis.get(key)
                    if raw:
                        session = json.loads(raw) if isinstance(raw, str) else raw
                        if session.get("state") != "ended":
                            active.append(session)
        except Exception as exc:
            logger.error("Error listing active sessions: %s", exc)

        return active

    async def update_state(self, call_sid: str, new_state: str) -> None:
        """Update just the conversation state of a session.

        This is separate from save_session() because state transitions
        happen frequently and we want a lightweight operation.
        """
        session = await self.get_session(call_sid)
        if session is None:
            return
        session["state"] = new_state
        await self.save_session(call_sid, session)
