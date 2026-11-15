"""Entry point for hosts that import the API as one module (e.g. Vercel's Python runtime).

The FastAPI app lives in backend/api/main.py and imports its routes as ``api.routes``,
so both the project root and backend/ need to be importable.
Local development is unchanged: ``cd backend && uvicorn api.main:app``.
"""
import os
import sys
from pathlib import Path

# Serverless hosts only allow writing to /tmp; libraries that keep small files in $HOME
# (e.g. earthaccess) must not fail on a read-only home directory.
home = os.environ.get("HOME", "")
if not home or not os.access(home, os.W_OK):
    os.environ["HOME"] = "/tmp"

ROOT = Path(__file__).resolve().parent
for path in (ROOT, ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from api.main import app  # noqa: E402

__all__ = ["app"]
