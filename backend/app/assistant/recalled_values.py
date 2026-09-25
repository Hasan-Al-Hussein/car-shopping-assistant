"""Bounded plain-text presentation of owned preference records, never search authority."""

import json
import re
from datetime import datetime

from app.api.schemas.inventory import BudgetRange, SearchCriteria
from app.api.schemas.memory import BudgetPreference, PreferenceRecord

from .output_policy import safe_assistant_text

_CATEGORY_LIMIT = 3
_LABELS = {
    "budget": "cash budget",
    "makes": "makes",
    "use_cases": "intended uses",
    "requirements": "requirements",
}


def is_recall_question(text: str) -> bool:
    """A complete read-only question; the word 'remember' alone never selects this path."""
    return re.fullmatch(
        r"\s*(?:what (?:preferences|requirements) do you remember(?: about me)?|"
        r"what are my saved (?:preferences|requirements)|"
        r"what (?:requirements|preferences) did I ask you to remember in my "
        r"(?:earlier|previous) conversation\?\s*tell me the saved values)\s*[?.!]?\s*",
        text,
        re.I,
    ) is not None


def _money(minor_units: int) -> str:
    whole, fraction = divmod(minor_units, 100)
    return f"{whole:,}.{fraction:02d}"


def _budget(value: BudgetRange) -> str:
    if value.currency != "AED":
        if value.minimum is not None and value.maximum is not None:
            bounds = f"{value.minimum:,} to {value.maximum:,}"
        elif value.minimum is not None:
            bounds = f"at least {value.minimum:,}"
        else:
            assert value.maximum is not None
            bounds = f"at most {value.maximum:,}"
        return f"{value.currency} {bounds} minor units (cash; display scale not established)"
    if value.minimum is not None and value.maximum is not None:
        amount = f"{_money(value.minimum)} to {_money(value.maximum)}"
    elif value.minimum is not None:
        amount = f"at least {_money(value.minimum)}"
    else:
        assert value.maximum is not None
        amount = f"at most {_money(value.maximum)}"
    return f"{value.currency} {amount} total cash"


def format_recalled_preferences(
    record: PreferenceRecord,
    *,
    session_id: str,
    criteria: SearchCriteria,
    now: str,
) -> str:
    """Show retained values and their limits without inventing prior conversations.

    The caller obtains this record from the owned PreferenceService.recall boundary.
    Existing entries include their own origin/expiry; this is not transcript retrieval.
    Output is plain text. A client must render it as text, not executable markup.
    """
    record = PreferenceRecord.model_validate(record.model_dump(mode="json"))
    criteria = SearchCriteria.model_validate(criteria.model_dump(mode="json"))
    instant = datetime.fromisoformat(now)
    if instant.tzinfo is None:
        raise ValueError("RECALL_TIME_REQUIRES_TIMEZONE")
    overrides = set()
    if criteria.filters.budget is not None:
        overrides.add("budget")
    if criteria.filters.makes:
        overrides.add("makes")
    if criteria.soft_preferences:
        overrides.add("requirements")
    lines = []
    for entry in record.entries:
        if datetime.fromisoformat(entry.expires_at) <= instant:
            continue
        preference = entry.preference
        if isinstance(preference, BudgetPreference):
            if preference.value is None:
                continue
            value = _budget(preference.value)
        else:
            shown = preference.value[:_CATEGORY_LIMIT]
            value = ", ".join(
                json.dumps(safe_assistant_text(item), ensure_ascii=False) for item in shown
            )
            remaining = len(preference.value) - len(shown)
            if remaining:
                value += f"; {remaining} additional saved values remain in your preference record"
        origin = "another session" if entry.source_session_id != session_id else "this session"
        strength = "hard requirement" if preference.strength == "hard" else "soft preference"
        text = f"You saved {_LABELS[preference.key]} in {origin} ({strength}): {value}."
        if entry.applicability == "requires_reconfirmation":
            text += " This value needs your reconfirmation before it is relied on."
        if preference.key in overrides and not (
            preference.key == "requirements" and preference.strength == "hard"
        ):
            text += " Your explicit current choice takes precedence in this session."
        lines.append(text)
    if not lines:
        lines.append("No current saved preferences are available. You can state new criteria.")
    if record.collection_mode == "disabled":
        lines.append("Preference saving is paused; retained values are shown only for review.")
    lines.append(
        "These saved values have not changed your current search or saved new preferences."
    )
    return "\n".join(lines)
