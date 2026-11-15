"""Deployment settings: CORS origins from the environment, and no credentials on disk."""
import importlib
import sys
from pathlib import Path
from unittest import mock

import pytest

BACKEND = Path(__file__).resolve().parent.parent / "backend"


def _client(monkeypatch, origins: str | None):
    if origins is None:
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("ALLOWED_ORIGINS", origins)
    sys.path.insert(0, str(BACKEND))
    import api.main
    importlib.reload(api.main)  # CORS origins are read at import time
    from fastapi.testclient import TestClient
    return TestClient(api.main.app)


def _preflight(client, origin):
    return client.options(
        "/api/discovery/catalogue",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )


def test_deployed_frontend_is_allowed(monkeypatch):
    client = _client(monkeypatch, " https://terrashift-ptsw.vercel.app/ , https://example.org")
    for origin in ("https://terrashift-ptsw.vercel.app", "https://example.org", "http://localhost:5173"):
        assert _preflight(client, origin).headers.get("access-control-allow-origin") == origin


def test_unknown_sites_are_not_allowed(monkeypatch):
    client = _client(monkeypatch, "https://terrashift-ptsw.vercel.app")
    assert "access-control-allow-origin" not in _preflight(client, "https://evil.example").headers


def test_without_setting_only_local_origins(monkeypatch):
    client = _client(monkeypatch, None)
    assert "access-control-allow-origin" not in _preflight(client, "https://terrashift-ptsw.vercel.app").headers
    assert _preflight(client, "http://localhost:5173").headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.parametrize("path,body", [
    ("/api/analysis/run", {
        "dataset_key": "M2TMNXSLV", "variable_id": "T2M", "min_lat": 2.6, "max_lat": 3.6,
        "min_lon": 101.2, "max_lon": 102.2, "time_range_start": "2023-01-01",
        "time_range_end": "2023-12-31", "use_anomalies": True, "region_name": "KL",
    }),
])
def test_login_never_persists_credentials(monkeypatch, path, body):
    client = _client(monkeypatch, None)
    from api.routes import analysis
    with mock.patch.object(analysis.data_discovery, "authenticate") as auth, \
            mock.patch.object(analysis, "run_pipeline", side_effect=analysis.InsufficientDataError("stop")):
        client.post(path, json=body)
    assert auth.call_args.kwargs == {"persist": False}
