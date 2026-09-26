"""Deliberately excluded from normal test_*.py discovery; invoked by F-03 proof only."""

from tests.support.harness import new_clock


def test_intentional_clock_assertion_failure() -> None:
    clock = new_clock()
    before = clock.now()
    clock.advance(60)
    assert clock.now() == before, "F03_INTENTIONAL_ASSERTION_FAILURE"
