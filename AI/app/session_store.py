"""
In-memory conversation memory, keyed by session_id.

This is what lets /chat behave like an actual chatbot instead of a stateless
completion endpoint: the backend can send only {session_id, message} and Alfred
still knows what was said before. The backend can still send its own memory/
history each call (e.g. to inject data it owns, like a partner's name pulled
from a profile DB) — anything it sends is merged on top of what's stored here.

Single-process, in-memory by design: this service runs as one process today
and nothing else needs to share this state. If that changes, swap the dict
below for Redis behind the same three methods.
"""
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional

from app.memory import safe_user_memory
from app.schemas import Location, MemoryUpdate, UserMemory

MAX_TURNS = 20            # trim stored history to the last N turns
SESSION_TTL_SECONDS = 2 * 60 * 60  # evict sessions idle for 2+ hours
EVICTION_INTERVAL_SECONDS = 60     # only sweep for expired sessions this often,
                                    # not on every single request


@dataclass
class SessionState:
    history: List[Dict[str, str]] = field(default_factory=list)
    memory: UserMemory = field(default_factory=UserMemory)
    location: Optional[Location] = None
    # Free-form slots remembered across turns for sub-flows that need more than
    # location/memory — e.g. travel's origin/destination/dates, coach's topic.
    # Keeps SessionState from growing a new named field per intent.
    slots: Dict[str, Any] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.monotonic)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, SessionState] = {}
        self._lock = Lock()
        self._last_eviction = time.monotonic()

    def _evict_expired_if_due(self) -> None:
        """Full scan is O(n) over all live sessions — only pay for it once per
        EVICTION_INTERVAL_SECONDS instead of on every single request."""
        now = time.monotonic()
        if now - self._last_eviction < EVICTION_INTERVAL_SECONDS:
            return
        self._last_eviction = now
        expired = [sid for sid, s in self._sessions.items() if now - s.updated_at > SESSION_TTL_SECONDS]
        for sid in expired:
            del self._sessions[sid]

    def get(self, session_id: str) -> Optional[SessionState]:
        with self._lock:
            self._evict_expired_if_due()
            return self._sessions.get(session_id)

    def append_turn(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            state = self._sessions.setdefault(session_id, SessionState())
            state.history.append({"role": role, "content": content})
            state.history = state.history[-MAX_TURNS:]
            state.updated_at = time.monotonic()

    def merge_memory(self, session_id: str, updates: List[MemoryUpdate]) -> UserMemory:
        with self._lock:
            state = self._sessions.setdefault(session_id, SessionState())
            if updates:
                merged = state.memory.model_dump()
                for u in updates:
                    merged[u.key] = u.value
                state.memory = safe_user_memory(merged)
            state.updated_at = time.monotonic()
            return state.memory

    def set_location(self, session_id: str, city: str) -> None:
        """Remembers the last city/place mentioned in this session, so a later
        turn like "just suggest a restaurant" can still route to a real search
        without the caller resending location every request."""
        with self._lock:
            state = self._sessions.setdefault(session_id, SessionState())
            state.location = Location(city=city)
            state.updated_at = time.monotonic()

    def update_slots(self, session_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Merges non-null values into this session's remembered slots (e.g.
        travel's origin/destination/dates, coach's topic) and returns the
        merged result. Only non-None values overwrite — a later turn that
        doesn't mention "destination" shouldn't erase one given earlier."""
        with self._lock:
            state = self._sessions.setdefault(session_id, SessionState())
            for key, value in updates.items():
                if value is not None:
                    state.slots[key] = value
            state.updated_at = time.monotonic()
            return dict(state.slots)


_store_singleton: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = SessionStore()
    return _store_singleton


def reset_session_store_for_tests() -> None:
    global _store_singleton
    _store_singleton = None
