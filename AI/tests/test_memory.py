from app.memory import safe_user_memory, sanitize_memory_updates
from app.schemas import UserMemory


def test_sanitize_memory_updates_drops_malformed_entries():
    raw = [
        {"key": "favorite_food", "value": "Japanese"},
        {"key": "", "value": "ignored"},
        {"value": "no key here"},
        {"key": "budget", "value": 120},
    ]
    result = sanitize_memory_updates(raw)
    assert len(result) == 2
    assert result[0].key == "favorite_food"
    assert result[1].value == 120


def test_sanitize_memory_updates_handles_empty_list():
    assert sanitize_memory_updates([]) == []
    assert sanitize_memory_updates(None) == []


def test_user_memory_budget_parses_free_text_with_currency():
    # The AI sometimes proposes a budget memory_update with the currency baked
    # into the string (e.g. "5000 BDT") rather than a clean number — this must
    # be parsed, not rejected, since a strict float field crashing the whole
    # /chat request over this was a real production bug.
    assert UserMemory(budget="5000 BDT").budget == 5000.0
    assert UserMemory(budget="$1,200.50").budget == 1200.50
    assert UserMemory(budget=100).budget == 100.0
    assert UserMemory(budget=None).budget is None


def test_user_memory_budget_falls_back_to_none_when_unparseable():
    assert UserMemory(budget="flexible, no real limit").budget is None


def test_safe_user_memory_drops_invalid_field_instead_of_raising():
    # General safety net beyond the budget validator: any field that still
    # fails validation (e.g. the AI proposing a number for a string field) is
    # dropped rather than crashing the whole memory merge — and therefore the
    # whole /chat request — over one bad AI-proposed value.
    memory = safe_user_memory({"favorite_food": "Italian", "partner_name": 12345})
    assert memory.favorite_food == "Italian"
    assert memory.partner_name is None
