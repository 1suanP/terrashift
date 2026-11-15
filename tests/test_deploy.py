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


def test_without_setting_local_and_live_site_allowed(monkeypatch):
    client = _client(monkeypatch, None)
    for origin in ("http://localhost:5173", "https://terrashift-ptsw.vercel.app"):
        assert _preflight(client, origin).headers.get("access-control-allow-origin") == origin
    assert "access-control-allow-origin" not in _preflight(client, "https://other.vercel.app").headers


def test_run_returns_the_result_in_one_request(monkeypatch):
    """Serverless instances do not share memory, so the client must not need a second GET."""
    import numpy as np
    import pandas as pd
    import config
    from modules.trend_analysis import analyze

    client = _client(monkeypatch, None)
    from api.routes import analysis
    idx = pd.date_range("2020-01-01", periods=36, freq="MS")
    series = pd.Series(np.linspace(25, 27, 36) + np.sin(np.arange(36)), index=idx)
    result = analyze(series, config.get_variable_meta("M2TMNXSLV", "T2M"), "KL", use_anomalies=True)
    with mock.patch.object(analysis.data_discovery, "authenticate"), \
            mock.patch.object(analysis, "run_pipeline", return_value=result):
        body = client.post("/api/analysis/run", json={
            "dataset_key": "M2TMNXSLV", "variable_id": "T2M", "min_lat": 2.6, "max_lat": 3.6,
            "min_lon": 101.2, "max_lon": 102.2, "time_range_start": "2020-01-01",
            "time_range_end": "2022-12-31", "use_anomalies": True, "region_name": "KL",
        }).json()
    analysis.analysis_cache.pop(body["analysis_id"], None)  # keep other tests' session state clean
    assert body["status"] == "complete"
    assert body["result"]["n_points"] == 36
    assert len(body["result"]["time_series"]["timestamps"]) == 36


def test_cache_goes_to_tmp_on_serverless(monkeypatch):
    from modules import global_maps
    monkeypatch.delenv("TERRASHIFT_CACHE_DIR", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    assert str(global_maps._default_cache_dir()).startswith("/tmp/")
    monkeypatch.delenv("VERCEL")
    assert global_maps._default_cache_dir().parts[-3:] == ("backend", "cache", "maps")


def test_vercel_entrypoint_exposes_the_app():
    import server
    assert server.app.title == "TerraShift API"


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
