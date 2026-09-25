"""Exercise actual composed services; only offline interpretation is scripted."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import Any
from uuid import uuid4

from app.api.schemas.common import InventoryRef
from app.api.schemas.identity import IdentityBootstrapRequest, RecognizedIdentity
from app.api.schemas.sessions import (
    ClarificationIntent,
    ClarificationReply,
    ExplicitConfirmation,
    MessageRequest,
    MessageResult,
    SessionCreateRequest,
)
from app.assistant.budget import TurnBudget
from app.assistant.packet import minimize_text
from app.core.diagnostics import ProviderMetricSlot
from app.core.errors import ApiFailure
from app.identity.authorization import AuthorizedOwnerContext
from app.identity.credentials import decode_token
from app.runtime_app import ApplicationComposition

from .diagnostics import provider_metric_metadata
from .effects import digest, snapshot
from .judging import combined, judge
from .observations import project
from .schema import Corpus, Step, StepResult
from .transports import ScriptedTransport


@dataclass
class Actor:
    context: AuthorizedOwnerContext
    session_id: str
    first_session_id: str
    last_request: MessageRequest | None = None
    last_result_sha256: str | None = None


class ServiceDriver:
    def __init__(
        self,
        composition: ApplicationComposition,
        corpus: Corpus,
        oracle: dict[str, Any],
        scripted: ScriptedTransport | None,
    ) -> None:
        self.composition, self.corpus, self.oracle, self.scripted = (
            composition,
            corpus,
            oracle,
            scripted,
        )

    async def read[T](self, operation: Callable[[], T]) -> T:
        deadline = monotonic() + 5
        # An assistant timeout may leave its original service call running. Wait for
        # that call to settle before observing it; never replay or replace the call.
        # Waiting consumes the existing five-second observation budget.
        while self.composition.worker.pending:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise ApiFailure("STORE_BUSY")
            await asyncio.sleep(min(0.01, remaining))
        return await self.composition.worker.run(operation, deadline_at=deadline)

    async def actor(self) -> Actor:
        def create() -> Actor:
            comp = self.composition
            outcome = comp.identity.bootstrap(
                IdentityBootstrapRequest(
                    notice_version="DEMO-POLICY-1",
                    notice_acknowledged=True,
                ),
                None,
            )
            if outcome.cookie is None or not isinstance(outcome.identity, RecognizedIdentity):
                raise ValueError("EVALUATION_IDENTITY_UNAVAILABLE")
            context = comp.authorization.authorize_write(
                decode_token(outcome.cookie),
                outcome.identity.context_id,
                outcome.identity.csrf_token,
            )
            current = comp.sessions.create(
                context, SessionCreateRequest(client_action_id=str(uuid4()))
            )
            return Actor(context, current.session_id, current.session_id)

        return await self.read(create)

    async def perform(self, actor: Actor, step: Step, index: int) -> StepResult:
        comp = self.composition
        started = monotonic()
        # Construct the adversarial actor before the observed operation boundary.
        acting_context = (
            (await self.actor()).context if step.kind == "foreign_owner" else actor.context
        )
        owner_id = await self.read(
            lambda: comp.authorization.read(actor.context, lambda unit: unit.owner_id)
        )
        before = await self.read(lambda: snapshot(comp.store, owner_id))
        current = await self.read(lambda: comp.sessions.get(actor.context, actor.session_id))
        result: MessageResult | None = None
        error: str | None = None
        request_id = str(uuid4())
        slot = ProviderMetricSlot(request_id)
        budget = TurnBudget(
            comp.settings.timeouts, monotonic() + comp.settings.timeouts.operation_seconds
        )
        if self.scripted is not None:
            self.scripted.step = step if step.kind == "message" else None
        try:
            if step.kind == "new_session":
                created = await self.read(
                    lambda: comp.sessions.create(
                        actor.context,
                        SessionCreateRequest(client_action_id=str(uuid4())),
                    )
                )
                actor.session_id = created.session_id
                actor.last_request = None
                actor.last_result_sha256 = None
            else:
                if step.kind == "replay":
                    if actor.last_request is None:
                        raise ValueError("NO_ORIGINAL_REQUEST_TO_REPLAY")
                    request = actor.last_request
                else:
                    echo = (
                        ClarificationReply(
                            intent_id=current.pending_intent.intent_id,
                            created_revision=current.pending_intent.created_revision,
                        )
                        if isinstance(current.pending_intent, ClarificationIntent)
                        else None
                    )
                    selected = (
                        None
                        if step.select_source_id is None
                        else InventoryRef(
                            namespace=self.corpus.namespace,
                            snapshot_id=self.corpus.snapshot_id,
                            source_id=step.select_source_id,
                        )
                    )
                    confirmation = None
                    if step.kind == "confirm":
                        if current.current_draft_id is None:
                            raise ValueError("NO_CURRENT_REVIEW")
                        draft = await self.read(
                            lambda: comp.drafts.get(actor.context, current.current_draft_id or "")
                        )
                        review = draft.review
                        if review is None:
                            raise ValueError("NO_CURRENT_REVIEW")
                        confirmation = ExplicitConfirmation(
                            draft_id=review.draft_id,
                            review_id=review.review_id,
                            expected_draft_revision=review.draft_revision,
                            operation_key=review.operation_key,
                            rules_version=review.rules_version,
                            store_generation=review.store_generation,
                            confirmation="confirm_simulated_viewing",
                        )
                    request = MessageRequest(
                        client_message_id=str(uuid4()),
                        expected_revision=current.revision,
                        text=step.text or "Confirm this reviewed simulated viewing",
                        clarification_reply=echo,
                        selected_ref=selected,
                        explicit_confirmation=confirmation,
                    )
                    actor.last_request = request
                # This runner admits only a fresh disposable instance and never seeds contacts.
                result = await comp.assistant.run(
                    acting_context,
                    actor.session_id,
                    request,
                    request_state={"request_id": request_id, "provider_metric_slot": slot},
                    budget=budget,
                )
        except ApiFailure as failure:
            error = failure.code
        finally:
            if self.scripted is not None:
                self.scripted.step = None
        current = await self.read(lambda: comp.sessions.get(actor.context, actor.session_id))
        after = await self.read(lambda: snapshot(comp.store, owner_id))
        observed = project(
            result,
            current,
            before=before,
            after=after,
            oracle=self.oracle,
            namespace=self.corpus.namespace,
            snapshot=self.corpus.snapshot_id,
            step=step,
            error=error,
        )
        observed["new_session"] = actor.session_id != actor.first_session_id
        observed["provider_attempts"] = budget.provider_attempts
        observed["tool_invocations"] = budget.tool_invocations
        if result is not None:
            receipt_sha256 = digest(result.model_dump(mode="json", exclude={"current_revision"}))
            if step.kind == "replay":
                observed["replay_receipt_matches"] = receipt_sha256 == actor.last_result_sha256
                observed["original_receipt_sha256"] = actor.last_result_sha256
            observed["receipt_sha256"] = receipt_sha256
            actor.last_result_sha256 = receipt_sha256
        metric = slot.close(request_id)
        observed["provider_diagnostic"] = provider_metric_metadata(metric)
        assertions = [judge(item, observed) for item in step.assertions]
        return StepResult(
            index=index,
            kind=step.kind,
            synthetic_input=minimize_text(step.text),
            verdict=combined([item.verdict for item in assertions]),
            observed=observed,
            assertions=assertions,
            elapsed_ms=(monotonic() - started) * 1000,
            provider_attempts=budget.provider_attempts,
            tool_invocations=budget.tool_invocations,
            usage={} if metric is None else metric.usage.model_dump(),
            safe_error=error,
        )
