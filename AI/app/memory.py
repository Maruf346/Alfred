"""
Memory is owned entirely by the backend. This module only formats memory
for prompt injection and validates memory_update suggestions the AI proposes
back — it never reads or writes any persistent store itself.
"""
import logging
from typing import Any, Dict, List

from pydantic import ValidationError

from app.schemas import MemoryUpdate, UserMemory

logger = logging.getLogger("alfred.memory")

# Keys the AI is allowed to suggest updates for. Anything outside this set
# still gets returned, but is flagged, since it's the backend's schema to own.
KNOWN_MEMORY_KEYS = {
    "name",
    "budget",
    "favorite_food",
    "favorite_activity",
    "relationship_status",
    "partner_name",
    "anniversary",
}


def sanitize_memory_updates(raw_updates: List[Dict[str, Any]]) -> List[MemoryUpdate]:
    cleaned: List[MemoryUpdate] = []
    for item in raw_updates or []:
        key = item.get("key")
        if not key or "value" not in item:
            continue
        cleaned.append(MemoryUpdate(key=key, value=item["value"]))
    return cleaned


def safe_user_memory(fields: Dict[str, Any]) -> UserMemory:
    """Builds a UserMemory from a raw dict, tolerating individual fields that
    fail validation (the AI can propose an arbitrarily-typed memory_update
    value) by dropping just the offending field and retrying, rather than
    letting one bad value raise and crash the entire /chat request."""
    try:
        return UserMemory(**fields)
    except ValidationError as exc:
        bad_keys = {str(err["loc"][0]) for err in exc.errors() if err.get("loc")}
        logger.warning("Dropping invalid memory fields %s: %s", bad_keys, exc)
        cleaned = {k: v for k, v in fields.items() if k not in bad_keys}
        return UserMemory(**cleaned)
