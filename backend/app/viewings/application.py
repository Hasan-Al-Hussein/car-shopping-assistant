"""UI confirmation over T7; canonical commit precedes any CSV publication work."""

from app.api.schemas.operations import OperationStatus, OperationSucceeded
from app.api.schemas.viewings import BookingReceipt, ConfirmRequest
from app.database.store import StoreError
from app.identity.authorization import AuthorizedOwnerContext, OwnerUnit
from app.leads.projection import CsvProjector, constrain_observation
from app.sessions import repository as sessions
from app.viewings import confirmation_repository as repository
from app.viewings.confirmation import ConfirmationParticipant, TerminalOutcome


class ConfirmationObservationUnavailable(Exception):
    """A proven success survives a later publication/observation failure."""

    def __init__(self, terminal: OperationSucceeded) -> None:
        self.terminal = terminal.model_copy(deep=True)
        super().__init__("CONFIRMATION_OBSERVATION_UNAVAILABLE")


class ViewingApplication:
    def __init__(self, participant: ConfirmationParticipant, *, projector: CsvProjector) -> None:
        self.participant = participant
        self.authorization = participant.authorization
        self.drafts = participant.drafts
        self.projector = projector
        settings = self.authorization.identity.settings
        if (projector.store.path, projector.store.boundary) != (
            settings.store_path, settings.runtime_boundary,
        ):
            raise ValueError("CONFIRMATION_PROJECTOR_STORE_MISMATCH")

    def confirm(
        self, context: AuthorizedOwnerContext, draft_id: str, command: ConfirmRequest,
    ) -> TerminalOutcome:
        draft_id, command = repository.command_copy(draft_id, command)
        participant = self.participant
        terminal = self.authorization.read(
            context,
            lambda unit: participant.lookup_in_unit(
                unit, draft_id=draft_id, command=command, generation=context.generation,
                now=self.authorization.identity.now_text(),
            ),
        )
        if terminal is None:
            prepared = participant.prepare(context, draft_id=draft_id, command=command)

            def write(unit: OwnerUnit) -> TerminalOutcome:
                now = self.authorization.identity.now_text()
                effect = participant.apply_in_unit(
                    unit, draft_id=draft_id, command=command, generation=context.generation,
                    now=now, prepared=prepared,
                )
                transition = effect.transition
                if effect.replayed:
                    if transition is not None:
                        raise StoreError("CONFIRMATION_TRANSITION_INCOMPATIBLE")
                    return effect.terminal
                if transition is None:
                    raise StoreError("CONFIRMATION_TRANSITION_MISSING")
                if (
                    transition.owner_id, transition.draft_id, transition.review_id,
                    transition.operation_key, transition.generation,
                ) != (
                    unit.owner_id, draft_id, command.review_id,
                    command.operation_key, context.generation,
                ):
                    raise StoreError("CONFIRMATION_TRANSITION_INCOMPATIBLE")
                # Actual T7 has accepted at reviewed R, but has not advanced this session.
                row = unit.session(transition.session_id)
                sessions.revision(row, transition.expected_revision)
                participant.resolve_session_in_unit(unit, transition=transition)
                sessions.revision(row, transition.expected_revision)
                row.revision += 1
                sessions.validate_context(unit, row, sessions.content(row))
                sessions.activity(
                    row, now, self.authorization.identity.settings.policy.session_retention_days,
                )
                return effect.terminal

            # A return from the callback is provisional; only this return proves commit.
            terminal = self.authorization.write(context, write)
        if not isinstance(terminal, OperationSucceeded):
            return terminal
        try:
            attempt = self.projector.repair_once()
            observation = self.authorization.read(
                context,
                lambda unit: participant.observe_csv_in_unit(
                    unit, generation=context.generation,
                    now=self.authorization.identity.now_text(),
                ),
            )
            return terminal.model_copy(
                update={"csv": constrain_observation(observation, attempt)}, deep=True,
            )
        except Exception:
            # No canonical retry and no rewriting the immutable terminal. The HTTP
            # boundary can preserve the proven success and its original recovery key.
            raise ConfirmationObservationUnavailable(terminal) from None

    def status(
        self, context: AuthorizedOwnerContext, operation_key: str,
        submitted_generation: str | None,
    ) -> OperationStatus:
        return self.participant.status(
            context, operation_key=operation_key,
            submitted_generation=(
                context.generation if submitted_generation is None else submitted_generation
            ),
        )

    def booking(self, context: AuthorizedOwnerContext, booking_id: str) -> BookingReceipt:
        booking_id = sessions.valid_id(booking_id)

        def read(unit: OwnerUnit) -> BookingReceipt:
            row = unit.booking(booking_id)
            review = unit.review(row.review_id)
            now = self.authorization.identity.now_text()
            terminal = repository.terminal(unit, unit.operation(review.operation_key), now)
            if (
                not isinstance(terminal, OperationSucceeded)
                or terminal.booking.booking_id != booking_id
            ):
                raise StoreError("CONFIRMATION_TERMINAL_INCOMPATIBLE")
            return BookingReceipt.model_validate({
                **terminal.booking.model_dump(mode="json"),
                "lead": terminal.lead.model_dump(mode="json"),
                "csv": self.participant.observe_csv_in_unit(
                    unit, generation=context.generation, now=now,
                ).model_dump(mode="json"),
            })

        return self.authorization.read(context, read)
