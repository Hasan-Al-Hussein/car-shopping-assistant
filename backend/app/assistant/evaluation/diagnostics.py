"""Bounded exception metadata; never serialize messages, source lines or locals."""

import builtins
import re
from pathlib import Path
from typing import Any

from pydantic import JsonValue, ValidationError

from app.core.diagnostics import ProviderMetric
from app.core.errors import ERRORS, ApiFailure


def provider_metric_metadata(
    metric: ProviderMetric | None,
) -> dict[str, JsonValue] | None:
    """Last completed invocation only; absent is distinct from successful metadata."""
    if metric is None:
        return None
    return {
        "code": metric.code,
        "failure_phase": metric.failure_phase,
        "http_status": metric.http_status,
    }


def safe_exception(error: Exception, project: Path) -> dict[str, Any]:
    kind = type(error)
    name = kind.__name__
    category = (
        name
        if getattr(builtins, name, None) is kind
        else "ApiFailure"
        if kind is ApiFailure
        else "ValidationError"
        if kind is ValidationError
        else "OtherException"
    )
    frames = []
    trace = error.__traceback__
    root = project.resolve()
    while trace is not None:
        code = trace.tb_frame.f_code
        try:
            relative = Path(code.co_filename).resolve().relative_to(root).as_posix()
        except (OSError, ValueError):
            relative = ""
        if relative.startswith(("backend/app/", "backend/tests/", "scripts/evaluation/")):
            function = code.co_name
            named = re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,99}|<module>|<lambda>", function)
            frames.append(
                {
                    "file": relative,
                    "function": function if named else "other",
                    "line": trace.tb_lineno,
                }
            )
        trace = trace.tb_next
    result: dict[str, Any] = {"exception_type": category, "repository_frames": frames[-16:]}
    if kind is ApiFailure:
        assert isinstance(error, ApiFailure)
        result["error_code"] = error.code if error.code in ERRORS else "INTERNAL_ERROR"
    return result
