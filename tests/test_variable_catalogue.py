"""Discovery catalogue: only retrievable variables are offered, and no trend is claimed."""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

import config
from modules import data_access as da
from modules import variable_catalogue as cat
from modules.models import BoundingBox, TimeRange

# Wording that would assert a trend before any data has been analyzed.
_CLAIM = re.compile(r"\b(is|are|has been|have been) (increasing|decreasing|rising|falling|warming|drying)\b", re.I)


def test_available_entries_match_pipeline_variables_exactly():
    assert set(cat.AVAILABLE) == set(config.VARIABLES)


def test_unavailable_entries_are_not_analyzable():
    analyzable_ids = {meta.variable_id for meta in config.VARIABLES.values()}
    for entry in cat.UNAVAILABLE:
        assert entry.entry_id not in config.VARIABLES
        assert entry.entry_id not in analyzable_ids
        assert entry.required_datasets, entry.entry_id


def test_catalogue_text_does_not_claim_trends():
    texts = [e.why_trend for e in cat.AVAILABLE.values()]
    texts += [e.why_trend for e in cat.UNAVAILABLE] + [e.plain_language for e in cat.UNAVAILABLE]
    texts += [q.why for q in cat.QUESTIONS]
    for text in texts:
        assert not _CLAIM.search(text), text


def test_questions_are_questions_and_resolve():
    for q in cat.QUESTIONS:
        assert q.question.endswith("?")
        assert q.region_name in config.PRESET_REGIONS


def test_catalogue_rejects_unretrievable_variable(monkeypatch):
    extra = dict(cat.AVAILABLE)
    extra["M2TMNXSLV/NOT_A_VAR"] = next(iter(cat.AVAILABLE.values()))
    monkeypatch.setattr(cat, "AVAILABLE", extra)
    with pytest.raises(Exception, match="cannot retrieve"):
        cat.validate_catalogue()


# ---- data fixes needed by the new MERRA-2 land variables ------------------------------
def _grid(values, fill=None):
    lat = np.array([0.0, 1.0])
    lon = np.array([0.0, 1.0])
    time = pd.date_range("2019-01-01", periods=1, freq="MS")
    arr = xr.DataArray(np.array(values, dtype=np.float32).reshape(1, 2, 2), dims=("time", "lat", "lon"),
                       coords={"time": time, "lat": lat, "lon": lon})
    if fill is not None:
        arr.encoding["_FillValue"] = fill
    return arr


def test_float32_fill_declared_as_float64_is_masked():
    stored = float(np.float32(999999987000000.0))  # what the server actually sends
    arr = _grid([1.0, 2.0, stored, 4.0], fill=999999987000000.0)
    masked = da._mask_fill_values(arr, arr)
    assert int(masked.isnull().sum()) == 1
    assert float(masked.mean()) == pytest.approx(7.0 / 3)


def test_mask_variable_blanks_cells_missing_in_companion(monkeypatch):
    stored = float(np.float32(999999987000000.0))
    top = _grid([0.5, 0.5, 1.0, 1.0])  # 1.0 over "ocean", like GWETTOP
    root = _grid([0.4, 0.4, stored, stored], fill=999999987000000.0)
    ds = xr.Dataset({"GWETTOP": top, "GWETROOT": root})
    monkeypatch.setattr(da.xr, "open_mfdataset", lambda *a, **k: ds)
    out = da.load_granules(["dap4://x"], "GWETTOP", BoundingBox(0.0, 0.0, 1.0, 1.0),
                           TimeRange("2019-01-01", "2019-01-31"), mask_variable="GWETROOT")
    assert float(out["GWETTOP"].mean()) == pytest.approx(0.5)


# ---- API endpoint ---------------------------------------------------------------------
@pytest.fixture()
def client():
    backend = Path(__file__).resolve().parent.parent / "backend"
    sys.path.insert(0, str(backend))
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


def test_catalogue_endpoint_separates_available_from_tested(client):
    body = client.get("/api/discovery/catalogue").json()
    by_status = {}
    for v in body["variables"]:
        by_status.setdefault(v["status"], []).append(v)
    assert len(by_status["available"]) == len(config.VARIABLES)
    assert len(by_status["requires_dataset"]) == len(cat.UNAVAILABLE)
    # No analysis has run in this process, so nothing may report a trend.
    assert all(v["analyses"] == [] for v in body["variables"])
    for v in by_status["available"]:
        assert v["coverage"]["spatial_resolution"] and v["coverage"]["period_start"]
    for v in by_status["requires_dataset"]:
        assert v["required_datasets"]
    assert {c["key"] for c in body["categories"]} == {"climate", "hydrology", "atmosphere", "ocean", "land"}
