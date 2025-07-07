"""Server module for the Nomos FastAPI application."""

import os
from pathlib import Path


def run_server(config_path: Path, port: int = 8000, workers: int = 1) -> None:
    """Run the Nomos FastAPI server using uvicorn."""
    try:
        import uvicorn
    except ImportError:
        raise ImportError("Not installed in server mode. Install with 'pip install nomos[serve]'")

    os.environ["CONFIG_PATH"] = str(config_path)
    uvicorn.run("nomos.api.app:app", host="0.0.0.0", port=port, workers=workers)


__all__ = ["run_server"]
