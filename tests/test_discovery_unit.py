"""Unit tests for data discovery, plus Property 22 (credentials never leak).

Validates Requirements 7.2, 7.5, 7.6, 8.2, 8.3, 8.4, 8.5, 33.3.
"""
import logging
from types import SimpleNamespace
from unittest import mock

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from modules import data_discovery as dd
from modules.errors import DataDiscoveryError
from tests.conftest import make_granule

BBOX = (-124.5, 32.5, -114.0, 42.0)
TEMPORAL = ("2001-01-01", "2002-01-01")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    monkeypatch.setattr(dd, "_netrc_path", lambda: tmp_path / ".netrc")


# ---- authentication -----------------------------------------------------------
def test_missing_credentials_raises_with_guidance():
    with pytest.raises(DataDiscoveryError, match="Earthdata Login"):
        dd.authenticate()
    assert dd.validate_credentials() is False


def test_env_credentials_authenticate(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "someone")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "hunter2-secret")
    with mock.patch.object(dd.earthaccess, "login", return_value=SimpleNamespace(authenticated=True)) as login:
        auth = dd.authenticate()
    login.assert_called_once_with(strategy="environment", persist=True)
    assert auth.authenticated
    assert dd.validate_credentials() is True


def test_rejected_credentials(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "someone")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "wrong-password-xyz")
    with mock.patch.object(dd.earthaccess, "login", return_value=SimpleNamespace(authenticated=False)):
        with pytest.raises(DataDiscoveryError, match="rejected"):
            dd.authenticate()


def test_unreachable_service(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "someone")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "pw-abcdef")
    with mock.patch.object(dd.earthaccess, "login", side_effect=ConnectionError("boom")):
        with pytest.raises(DataDiscoveryError, match="could not be reached"):
            dd.authenticate()


def test_auth_timeout(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "someone")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "pw-abcdef")
    monkeypatch.setattr(dd, "AUTH_TIMEOUT_SECONDS", 0.05)
    import time

    with mock.patch.object(dd.earthaccess, "login", side_effect=lambda **kw: time.sleep(0.5)):
        with pytest.raises(DataDiscoveryError, match="could not be reached"):
            dd.authenticate()


# ---- search -------------------------------------------------------------------
@pytest.mark.parametrize(
    "short_name,temporal,bbox",
    [
        ("", TEMPORAL, BBOX),
        ("GPM_3IMERGM", ("2002-01-01", "2001-01-01"), BBOX),
        ("GPM_3IMERGM", TEMPORAL, (-200, 0, 10, 10)),
        ("GPM_3IMERGM", TEMPORAL, (0, -95, 10, 10)),
        ("GPM_3IMERGM", ("bad", "2001-01-01"), BBOX),
    ],
)
def test_search_invalid_args_never_call_cmr(short_name, temporal, bbox):
    with mock.patch.object(dd.earthaccess, "search_data") as search:
        with pytest.raises(DataDiscoveryError):
            dd.search_granules(short_name, temporal, bbox)
    search.assert_not_called()


def test_search_returns_granules():
    granules = [make_granule(("https://x/a", "OPeNDAP"))]
    with mock.patch.object(dd.earthaccess, "search_data", return_value=granules) as search:
        out = dd.search_granules("GPM_3IMERGM", TEMPORAL, BBOX, version="07")
    assert out == granules
    kwargs = search.call_args.kwargs
    assert kwargs["short_name"] == "GPM_3IMERGM" and kwargs["version"] == "07"
    assert kwargs["bounding_box"] == BBOX and kwargs["temporal"] == TEMPORAL


def test_search_empty_result_message_has_parameters():
    with mock.patch.object(dd.earthaccess, "search_data", return_value=[]):
        with pytest.raises(DataDiscoveryError) as err:
            dd.search_granules("GPM_3IMERGM", TEMPORAL, BBOX)
    msg = str(err.value)
    assert "GPM_3IMERGM" in msg and "2001-01-01" in msg and "2002-01-01" in msg and "available period" in msg


def test_search_service_error_and_auth_error():
    with mock.patch.object(dd.earthaccess, "search_data", side_effect=RuntimeError("cmr exploded")):
        with pytest.raises(DataDiscoveryError, match="service error"):
            dd.search_granules("GPM_3IMERGM", TEMPORAL, BBOX)
    with mock.patch.object(dd.earthaccess, "search_data", side_effect=RuntimeError("401 Unauthorized")):
        with pytest.raises(DataDiscoveryError, match="Authentication failed"):
            dd.search_granules("GPM_3IMERGM", TEMPORAL, BBOX)


def test_search_timeout(monkeypatch):
    import time

    monkeypatch.setattr(dd, "SEARCH_TIMEOUT_SECONDS", 0.05)
    with mock.patch.object(dd.earthaccess, "search_data", side_effect=lambda **kw: time.sleep(0.5)):
        with pytest.raises(DataDiscoveryError, match="timed out"):
            dd.search_granules("GPM_3IMERGM", TEMPORAL, BBOX)


def test_get_opendap_urls_fixture(mock_granules):
    assert dd.get_opendap_urls(mock_granules) == [
        "dap4://opendap.earthdata.nasa.gov/collections/C1/granules/a",
        "dap4://opendap.earthdata.nasa.gov/collections/C1/granules/c",
    ]
    assert dd.get_opendap_urls([mock_granules[1]]) == []


# ---- Property 22: credentials never appear in logs or error text --------------
secret = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=8, max_size=20)


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(user=secret, password=secret, failure=st.sampled_from(["reject", "unreachable", "unauth-exc"]))
def test_credentials_never_leak(user, password, failure, caplog):
    import os

    os.environ["EARTHDATA_USERNAME"] = f"user-{user}"
    os.environ["EARTHDATA_PASSWORD"] = f"pw-{password}"
    try:
        if failure == "reject":
            patch = mock.patch.object(dd.earthaccess, "login", return_value=SimpleNamespace(authenticated=False))
        elif failure == "unreachable":
            patch = mock.patch.object(dd.earthaccess, "login", side_effect=ConnectionError(f"pw-{password} refused"))
        else:
            patch = mock.patch.object(dd.earthaccess, "login", side_effect=RuntimeError(f"401 for user-{user}/pw-{password}"))
        with caplog.at_level(logging.DEBUG), patch:
            with pytest.raises(DataDiscoveryError) as err:
                dd.authenticate()
        text = str(err.value) + repr(err.value) + caplog.text
        assert f"pw-{password}" not in text
        assert f"user-{user}" not in text
    finally:
        os.environ.pop("EARTHDATA_USERNAME", None)
        os.environ.pop("EARTHDATA_PASSWORD", None)
