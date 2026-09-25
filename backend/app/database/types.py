"""Storage representations that preserve SQLite ordering semantics."""

import re
from datetime import UTC, datetime
from typing import Annotated

from sqlalchemy import String
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import TypeDecorator

_UTC_INPUT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)")


class UTCText(TypeDecorator[str]):
    """Normalize wire-compatible UTC fractions before lexicographic SQL comparison."""

    impl = String(27)
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or _UTC_INPUT.fullmatch(value) is None:
            raise ValueError("STORAGE_REQUIRES_UTC_INSTANT")
        parsed = datetime.fromisoformat(value).astimezone(UTC)
        return parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")


UtcStored = Annotated[str, mapped_column(UTCText())]


def utc_check(column: str) -> str:
    # Trusted schema column name only. Fraction-free strftime avoids millisecond rounding.
    digit = "[0-9]"
    pattern = (
        f"{digit * 4}-{digit * 2}-{digit * 2}T{digit * 2}:{digit * 2}:{digit * 2}.{digit * 6}Z"
    )
    return (
        f"{column} IS NULL OR (length({column}) = 27 AND {column} GLOB '{pattern}' "
        f"AND substr({column},1,4) >= '0001' "
        f"AND substr({column},12,2) BETWEEN '00' AND '23' "
        f"AND substr({column},15,2) BETWEEN '00' AND '59' "
        f"AND substr({column},18,2) BETWEEN '00' AND '59' "
        f"AND strftime('%Y-%m-%dT%H:%M:%S',substr({column},1,19)||'Z') IS NOT NULL "
        f"AND strftime('%Y-%m-%dT%H:%M:%S',substr({column},1,19)||'Z') = substr({column},1,19))"
    )
