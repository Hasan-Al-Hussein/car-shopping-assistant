"""Generate versioned API contract without opening a database or provider."""

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "backend"))

from app.api.schemas.routes import create_contract_app


def main() -> None:
    schema = create_contract_app().openapi()
    target = PROJECT / "contracts" / "v1" / "openapi.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Generated {target}: {len(schema['paths'])} paths; no runtime service invoked."
    )


if __name__ == "__main__":
    main()
