"""Explicit chat commands over the shared P14/T7 transaction boundaries.

P14 is a required integration dependency. This module does not emulate missing methods,
open transactions, call public domain mutators, or turn a model proposal into permission.
"""

import json
import re
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID, uuid5

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import PresentationProof
from app.api.schemas.memory import (
    BudgetPreference,
    CategoryPreference,
    MembershipRequest,
    PreferencesUpdate,
    PreferenceValue,
)
from app.api.schemas.sessions import (
    ClarificationIntent,
    MessageRequest,
    MessageResult,
    SessionState,
)
from app.core.errors import ApiFailure
from app.identity.authorization import AuthorizedOwnerContext
from app.memory.service import PreferenceService
from app.sessions.service import SessionService, ShortlistChange, TurnAdmission
from app.sessions.state import SessionContent
from app.shortlist.service import ShortlistService
from app.viewings.confirmation import ConfirmationParticipant

from .intent import Clarification, ReferenceRequest, TextPatch, TurnIntent
from .recalled_values import format_recalled_preferences

PreferenceTarget = Literal["preferences", "budget", "makes", "requirements"]
_SAVE = re.compile(
    r"(?:please\s+)?(?P<verb>remember|save|correct|update)\s+my\s+"
    r"(?P<saved>saved\s+)?(?:current\s+)?"
    r"(?P<target>preferences|budget|makes|soft requirements)"
    r"(?P<suffix>\s+for (?:next time|future searches)|\s+to my current search)?",
    re.I,
)
_ADD = re.compile(r"(?:please\s+)?(?:save|add)\s+(.+?)\s+(?:to|in) my shortlist", re.I)
_REMOVE = re.compile(r"(?:please\s+)?remove\s+(.+?)\s+from my shortlist", re.I)
_QUOTED_VALUE = r'"(?:[^"\\\r\n]|\\["\\/bfnrt]|\\u[0-9a-fA-F]{4})*"'
_VALUE_SEPARATOR = r"(?:\s*,\s*(?:and\s+)?|\s+and\s+)"
_COUNTS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}
_SUPPLIED = re.compile(
    r"(?:please\s+)?(?:explicitly\s+)?(?P<verb>remember|save|correct|update)\s+"
    r"(?:these|my)\s+(?P<saved>saved\s+)?"
    r"(?:(?P<count>one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d{1,2})\s+)?"
    r"soft (?:requirements|preferences)"
    r"(?:\s+for (?:future conversations|future searches|next time))?\s*:\s*"
    r"(?P<values>" + _QUOTED_VALUE + r"(?:" + _VALUE_SEPARATOR + _QUOTED_VALUE + r")*)"
    r"\s*\.?(?:\s+Save these preferences now\.?)?",
    re.I,
)
_HARD_VALUE = re.compile(
    r"\b(?:only|must|required|mandatory|at least|at most|no more than)\b", re.I
)
_NATURAL_SAVE = re.compile(
    r"(?:please\s+)?(?:explicitly\s+)?(?P<verb>remember|save|correct|update)\s+(?P<body>.+)",
    re.I,
)
_SAVE_CANCELLATION = re.compile(
    r"\b(?:if|unless|maybe|perhaps|cancel|discard|undo)\b|"
    r"\b(?:do\s+not|don't|never|without|not\s+to)\s+"
    r"(?:(?:actually|really|permanently)\s+)?"
    r"(?:save|saving|remember|remembering|store|storing|persist|persisting|"
    r"record|recording|update|updating|correct|correcting)\b",
    re.I,
)
_OTHER_SAVE_EFFECT = re.compile(
    r"(?:[.!?;]|\b(?:and|also|then|but)\b)\s*(?:please\s+)?"
    r"(?:book|reserve|schedule|submit|send|add|remove|delete|save|remember|correct|update)\b",
    re.I,
)


def _natural_values(text: str, patch: TextPatch) -> tuple[str, ...] | None:
    """Check buyer authorization and literal values; the model supplies their meaning."""
    matched = _NATURAL_SAVE.fullmatch(text)
    if matched is None:
        return None
    body = matched.group("body")
    if re.match(r"(?:what|when|which|whether|how)\b", body, re.I):
        return None
    if _SAVE_CANCELLATION.search(body) or _OTHER_SAVE_EFFECT.search(body):
        return None
    # A buyer may explicitly distinguish a preference from a required filter.
    strength_text = re.sub(
        r"\bnot\s+(?:a\s+)?(?:hard|required|mandatory)(?:\s+(?:filter|requirement))?\b",
        "",
        body,
        flags=re.I,
    )
    if re.search(r"\bhard\b", strength_text, re.I) or _HARD_VALUE.search(strength_text):
        return None
    values: list[str] = []
    for proposed in patch.values:
        value = re.search(r"(?<!\w)" + re.escape(proposed) + r"(?!\w)", patch.quote, re.I)
        if value is None:
            return None
        values.append(value.group())
    # Quoted/count-bearing lists retain their complete-list proof rather than
    # allowing this flexible path to save a model-selected subset.
    quoted = re.findall(_QUOTED_VALUE, body)
    if quoted:
        try:
            if [json.loads(value) for value in quoted] != values:
                return None
        except ValueError:
            return None
    counted = re.search(
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d{1,2})"
        r"\s+(?:soft\s+)?(?:preferences|requirements)\b",
        body,
        re.I,
    )
    if counted:
        count = counted.group(1).casefold()
        if (_COUNTS[count] if count in _COUNTS else int(count)) != len(values):
            return None
    return tuple(values)


class ActionClarification(Exception):
    def __init__(self, question: str) -> None:
        self.problem = Clarification("preference_scope", question)
        super().__init__(question)


@dataclass(frozen=True)
class RequestedActions:
    preference_target: PreferenceTarget | None = None
    preference_intent: Literal["remember", "correct"] = "remember"
    reference: ReferenceRequest | None = None
    desired_membership: bool | None = None
    supplied_requirements: tuple[str, ...] | None = None


@dataclass(frozen=True)
class PreparedActions:
    """Trusted in-process command snapshot; never deserialize this from model/client data."""

    message_id: str
    client_message_id: str
    session_id: str
    preference: PreferencesUpdate | None
    membership: ShortlistChange | None


def _supplied_requirements(admission: TurnAdmission, intent: TurnIntent) -> RequestedActions | None:
    """Validate new durable values against the complete buyer command and typed proposal.

    These are independent durable values, not a retagged search transition. Current
    criteria are never changed or used as substitutes for omitted/new buyer values.
    """
    text = admission.request.text.strip()
    matched = _SUPPLIED.fullmatch(text)
    natural = _NATURAL_SAVE.fullmatch(text) if matched is None and intent.patches else None
    if matched is None and natural is None:
        return None
    problem = "Tell me the soft preferences you want to save; no changes were made."
    if set(intent.deferred) != {"preferences"} or intent.references or len(intent.patches) != 1:
        raise ActionClarification(problem)
    pending = admission.session.pending_intent
    if isinstance(pending, ClarificationIntent) and pending.purpose == "listing_reference":
        raise ActionClarification(pending.question)
    patch = intent.patches[0]
    if (
        not isinstance(patch, TextPatch)
        or patch.field != "soft_preferences"
        or patch.operation not in {"add", "replace"}
        or patch.quote not in admission.request.text
    ):
        raise ActionClarification(problem)
    if matched is not None:
        literals = re.findall(_QUOTED_VALUE, matched.group("values"))
        try:
            values = tuple(json.loads(literal) for literal in literals)
        except ValueError:
            raise ActionClarification(problem) from None
        if list(values) != patch.values or any(literal not in patch.quote for literal in literals):
            raise ActionClarification(problem)
        count = matched.group("count")
        if count is not None and (
            _COUNTS[count.casefold()] if count.casefold() in _COUNTS else int(count)
        ) != len(values):
            raise ActionClarification(problem)
        command, names_saved = matched.group("verb"), matched.group("saved") is not None
    else:
        assert natural is not None
        natural_values = _natural_values(text, patch)
        if natural_values is None:
            raise ActionClarification(problem)
        values = natural_values
        command = natural.group("verb")
        names_saved = re.search(r"\bsaved\b", natural.group("body"), re.I) is not None
    if (
        not 1 <= len(values) <= 12
        or any(
            not value.strip() or len(value) > 200 or _HARD_VALUE.search(value) for value in values
        )
        or len({value.casefold() for value in values}) != len(values)
    ):
        raise ActionClarification(problem)
    correcting = command.casefold() in {"correct", "update"}
    if names_saved and not correcting:
        raise ActionClarification("To replace saved values, explicitly ask to correct them.")
    existing = next(
        (
            entry.preference
            for entry in admission.session.recalled_preferences.entries
            if entry.preference.key == "requirements"
        ),
        None,
    )
    if existing is not None and (
        existing.strength == "hard" or (existing.value != list(values) and not correcting)
    ):
        raise ActionClarification(
            "Review the existing saved requirements first. Explicitly correct a saved soft list "
            "to replace it; this request cannot silently overwrite other saved requirements."
        )
    return RequestedActions(
        preference_target="requirements",
        preference_intent="correct" if correcting else "remember",
        supplied_requirements=values,
    )


def requested_actions(admission: TurnAdmission, intent: TurnIntent) -> RequestedActions | None:
    """Accept complete explicit commands; unsupported compound requests have no effects.

    Current-value commands and explicitly supplied new durable values have separate
    validation. Neither a search nor a model proposal alone authorizes saving.
    """
    domains = set(intent.deferred)
    if not domains.intersection({"preferences", "shortlist"}):
        return None
    if (
        admission.status != "accepted"
        or admission.ticket is None
        or domains - {"preferences", "shortlist"}
        or intent.problem is not None
        or intent.scope in {"hypothetical", "unclear"}
    ):
        raise ActionClarification(
            "First settle any changed criteria or other action. Then explicitly ask to save "
            "your current preferences or add/remove a specific car from your shortlist."
        )
    pending, reply = admission.session.pending_intent, admission.request.clarification_reply
    if pending.kind != "none" and not (
        isinstance(pending, ClarificationIntent)
        and pending.purpose in {"action_intent", "listing_reference"}
        and reply is not None
        and (reply.intent_id, reply.created_revision)
        == (pending.intent_id, pending.created_revision)
    ):
        raise ActionClarification("Complete the current question or viewing review first.")
    supplied = _supplied_requirements(admission, intent)
    if supplied is not None:
        return supplied
    if intent.patches:
        raise ActionClarification(
            "Tell me the new soft preferences to save, or first "
            "settle changed search criteria before asking to remember the current values."
        )
    target: PreferenceTarget | None = None
    preference_intent: Literal["remember", "correct"] = "remember"
    reference = None
    desired = None
    parts = re.split(
        r"\s+and\s+(?=(?:please\s+)?(?:remember|save|correct|update|add|remove)\b)",
        admission.request.text.strip().rstrip(".!?"),
        flags=re.I,
    )
    if not 1 <= len(parts) <= 2:
        raise ActionClarification("Please make one explicit request for each saved collection.")
    for part in parts:
        save = _SAVE.fullmatch(part.strip())
        add, remove = _ADD.fullmatch(part.strip()), _REMOVE.fullmatch(part.strip())
        if save is not None and target is None:
            named = save.group("target").casefold()
            if named not in {"preferences", "budget", "makes", "soft requirements"}:
                raise ApiFailure("INTERNAL_ERROR")
            # Literal narrowing keeps this pure command grammar distinct from model values.
            if named == "budget":
                target = "budget"
            elif named == "makes":
                target = "makes"
            elif named == "soft requirements":
                target = "requirements"
            else:
                target = "preferences"
            if save.group("verb").casefold() in {"correct", "update"}:
                if (save.group("suffix") or "").casefold() != " to my current search":
                    raise ActionClarification(
                        "Say explicitly that saved preferences should be updated "
                        "to your current search."
                    )
                preference_intent = "correct"
            elif save.group("saved") is not None:
                raise ActionClarification(
                    "Saved values and current search choices are distinct. Name the current value "
                    "to remember or explicitly correct saved preferences to your current search."
                )
        elif (add is not None or remove is not None) and reference is None:
            match = add if add is not None else remove
            assert match is not None
            phrase = match.group(1)
            if len(intent.references) != 1 or intent.references[0].quote != phrase:
                raise ActionClarification("Identify the exact car you want to add or remove.")
            reference = intent.references[0]
            desired = add is not None
        else:
            raise ActionClarification(
                "Please name the current budget, makes or soft requirements to remember, "
                "or ask to add/remove an exact car from your shortlist. No change was made."
            )
    parsed = ({"preferences"} if target is not None else set()) | (
        {"shortlist"} if reference is not None else set()
    )
    if parsed != domains or (reference is None and intent.references):
        raise ActionClarification(
            "Please separate or clarify the requested changes; none were applied."
        )
    if (
        isinstance(pending, ClarificationIntent)
        and pending.purpose == "listing_reference"
        and reference is None
    ):
        raise ActionClarification(pending.question)
    return RequestedActions(target, preference_intent, reference, desired)


def _preference_changes(session: SessionState, target: PreferenceTarget) -> list[PreferenceValue]:
    criteria = session.criteria
    if target == "preferences" and (
        criteria.query
        or any(
            value
            for key, value in criteria.filters.model_dump().items()
            if key not in {"budget", "makes"}
        )
    ):
        raise ActionClarification(
            "Name the current budget, makes or soft requirements to save. Other search criteria "
            "cannot be silently omitted from a request to save all preferences."
        )
    changes: list[PreferenceValue] = []
    if target in {"preferences", "budget"} and criteria.filters.budget is not None:
        changes.append(
            BudgetPreference(key="budget", value=criteria.filters.budget, strength="hard")
        )
    if target in {"preferences", "makes"} and criteria.filters.makes:
        changes.append(
            CategoryPreference(key="makes", value=criteria.filters.makes, strength="hard")
        )
    if target in {"preferences", "requirements"} and criteria.soft_preferences:
        changes.append(
            CategoryPreference(key="requirements", value=criteria.soft_preferences, strength="soft")
        )
    if not changes:
        raise ActionClarification(
            "State the preference for this search before asking to remember it."
        )
    return changes


class ActionBridge:
    def __init__(
        self,
        sessions: SessionService,
        *,
        preferences: PreferenceService | None,
        shortlist: ShortlistService | None,
        confirmation: ConfirmationParticipant | None,
    ) -> None:
        self.sessions, self.preferences = sessions, preferences
        self.shortlist, self.confirmation = shortlist, confirmation

    def prepare(
        self,
        context: AuthorizedOwnerContext,
        admission: TurnAdmission,
        requested: RequestedActions,
        resolved_ref: InventoryRef | None,
    ) -> PreparedActions:
        if admission.status != "accepted" or admission.ticket is None:
            raise ApiFailure("UNSUPPORTED_STATE")
        preference = None
        if requested.preference_target is not None:
            if self.preferences is None:
                raise ApiFailure("UNSUPPORTED_STATE")
            preference = PreferencesUpdate(
                expected_revision=admission.session.recalled_preferences.revision,
                session_id=admission.session.session_id,
                client_action_id=str(uuid5(UUID(admission.message_id), "preferences:v1")),
                scope="durable",
                intent=requested.preference_intent,
                changes=(
                    _preference_changes(admission.session, requested.preference_target)
                    if requested.supplied_requirements is None
                    else [
                        CategoryPreference(
                            key="requirements",
                            value=list(requested.supplied_requirements),
                            strength="soft",
                        )
                    ]
                ),
            )
            preference = PreferencesUpdate.model_validate(preference.model_dump(mode="json"))
        membership = None
        if requested.reference is not None:
            if self.shortlist is None:
                raise ApiFailure("UNSUPPORTED_STATE")
            if resolved_ref is None or requested.desired_membership is None:
                raise ApiFailure("VALIDATION_ERROR")
            # Owned observational read, not desired-ref preparation or a guessed revision.
            current = self.shortlist.get(context, page_size=1)
            membership = ShortlistChange(
                ref=InventoryRef.model_validate(resolved_ref.model_dump(mode="json")),
                command=MembershipRequest(
                    client_action_id=str(uuid5(UUID(admission.message_id), "shortlist:v1")),
                    expected_revision=current.revision,
                ),
                desired=requested.desired_membership,
            )
        elif resolved_ref is not None:
            raise ApiFailure("VALIDATION_ERROR")
        return PreparedActions(
            admission.message_id,
            admission.request.client_message_id,
            admission.session.session_id,
            preference,
            membership,
        )

    def complete(
        self,
        context: AuthorizedOwnerContext,
        admission: TurnAdmission,
        plan: PreparedActions,
        result: MessageResult,
        *,
        update: SessionContent | None = None,
        presentation: PresentationProof | None = None,
        selection: InventoryRef | None = None,
    ) -> MessageResult:
        if plan.preference is None and plan.membership is None:
            raise ApiFailure("VALIDATION_ERROR")
        if (
            admission.ticket is None
            or (plan.message_id, plan.client_message_id, plan.session_id)
            != (
                admission.message_id,
                admission.request.client_message_id,
                admission.session.session_id,
            )
            or (result.client_message_id, result.session_id, result.turn_revision)
            != (
                admission.request.client_message_id,
                admission.session.session_id,
                admission.session.revision,
            )
        ):
            raise ApiFailure("VALIDATION_ERROR")
        if any(
            action["state"] != "not_requested" for action in result.actions.model_dump().values()
        ):
            raise ApiFailure("VALIDATION_ERROR")
        # P14 supplies actual outcomes AND acknowledgement before persisting the receipt.
        # Never patch the returned text/result or swallow an unknown/commit failure here.
        return self.sessions.complete_action(
            context,
            admission.ticket,
            result,
            preference=plan.preference,
            membership=plan.membership,
            preference_service=self.preferences,
            shortlist_service=self.shortlist,
            update=update,
            presentation=presentation,
            selection=selection,
        )

    def confirm(
        self, context: AuthorizedOwnerContext, session_id: str, request: MessageRequest
    ) -> MessageResult:
        if self.confirmation is None or request.explicit_confirmation is None:
            raise ApiFailure("UNSUPPORTED_STATE")
        # The real P14 wrapper validates combinations, projects ConfirmRequest, preserves
        # reviewed R, invokes T7 and stores exactly one message/session advancement.
        copied = MessageRequest.model_validate(request.model_dump(mode="json"))
        return self.sessions.confirm_turn(
            context, session_id, copied, participant=self.confirmation
        )

    def recall(self, context: AuthorizedOwnerContext, session: SessionState) -> str:
        # Partial read/confirmation compositions can still present the owned admission
        # snapshot. They cannot refresh or write preference records without the service.
        record = (
            session.recalled_preferences
            if self.preferences is None
            else self.preferences.recall(
                context,
                keys=("budget", "makes", "use_cases", "requirements"),
                current_keys=(),
            )
        )
        authorization = (
            self.sessions.authorization
            if self.preferences is None
            else self.preferences.authorization
        )
        return format_recalled_preferences(
            record,
            session_id=session.session_id,
            criteria=session.criteria,
            now=authorization.identity.now_text(),
        )


class ActionPort(Protocol):
    """Bounded async facade; production composition delegates to the concrete bridge."""

    async def prepare_actions(
        self,
        context: AuthorizedOwnerContext,
        admission: TurnAdmission,
        requested: RequestedActions,
        resolved_ref: InventoryRef | None,
    ) -> PreparedActions: ...

    async def complete_actions(
        self,
        context: AuthorizedOwnerContext,
        admission: TurnAdmission,
        plan: PreparedActions,
        result: MessageResult,
        *,
        update: SessionContent | None = None,
    ) -> MessageResult: ...

    async def confirm_turn(
        self,
        context: AuthorizedOwnerContext,
        session_id: str,
        request: MessageRequest,
    ) -> MessageResult: ...

    async def recall_preferences(
        self,
        context: AuthorizedOwnerContext,
        session: SessionState,
    ) -> str: ...
