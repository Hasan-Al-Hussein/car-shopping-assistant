"""Explicit local entrypoint: use the configured backend Python environment."""

import sys
from pathlib import Path


def main() -> None:
    # The repository intentionally uses uv package=false; this script works from
    # another current directory without installing or copying the backend package.
    backend = str(Path(__file__).resolve().parent / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from app.runtime_app import main as serve

    serve()


if __name__ == "__main__":
    main()
