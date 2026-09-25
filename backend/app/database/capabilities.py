"""Explicit functional capability discovery outside the canonical database."""

import sqlite3


def detect_fts5() -> bool:
    """Only SQLite's exact unavailable-module failure permits lexical fallback."""
    probe = sqlite3.connect(":memory:")
    try:
        try:
            probe.execute(
                "CREATE VIRTUAL TABLE capability_probe USING "
                "fts5(value, tokenize='unicode61 remove_diacritics 0')"
            )
        except sqlite3.OperationalError as exc:
            if str(exc) == "no such module: fts5":
                return False
            raise
        probe.execute("INSERT INTO capability_probe VALUES ('verified سيارة 707 café')")
        for term in ("verified", "سيارة", "707", "café"):
            if probe.execute(
                "SELECT count(*) FROM capability_probe WHERE capability_probe MATCH ?", (term,)
            ).fetchone() != (1,):
                raise sqlite3.DatabaseError("FTS5_FUNCTIONAL_PROBE_FAILED")
        probe.execute("INSERT INTO capability_probe(capability_probe) VALUES ('integrity-check')")
        return True
    finally:
        probe.close()


def fts5_registered(db: sqlite3.Connection) -> bool:
    """Read-only admission: never create a probe or attempt to repair the saved store."""
    return any(row[0] == "fts5" for row in db.execute("PRAGMA module_list"))
