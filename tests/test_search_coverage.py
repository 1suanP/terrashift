"""Place search (Photon, mocked) and the data-coverage check (grids mocked)."""
import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

import config
from modules import coverage, global_maps

BACKEND = Path(__file__).resolve().parent.parent / "backend"


@pytest.fixture()
def client():
    sys.path.insert(0, str(BACKEND))
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


def _feature(name, lon, lat, **props):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"name": name, **props}}


PHOTON_KL = {"features": [
    _feature("Kuala Lumpur", 101.694, 3.152, type="city", osm_key="place", osm_value="state", country="Malaysia",
             countrycode="MY", osm_type="R", osm_id=2939672, extent=[101.615, 3.2446, 101.758, 3.0334]),
    # duplicate of the same place (node + boundary): must be removed
    _feature("Kuala Lumpur", 101.695, 3.150, type="city", osm_key="place", osm_value="city", country="Malaysia",
             countrycode="MY", osm_type="N", osm_id=1),
    _feature("Malaysia", 102.266, 4.569, type="country", osm_key="place", osm_value="country", country="Malaysia",
             countrycode="MY", osm_type="R", osm_id=2108121, extent=[98.74, 8.38, 119.47, 0.85]),
    _feature("Fiji", 178.0, -17.8, type="country", osm_key="place", osm_value="country", country="Fiji",
             countrycode="FJ", extent=[176.9, -12.4, -178.2, -21.0]),  # crosses the dateline
]}


def _photon(payload):
    resp = mock.Mock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_search_normalizes_dedupes_and_handles_dateline(client):
    from api.routes import geo
    geo._search_cache.clear()
    with mock.patch.object(geo.requests, "get", return_value=_photon(PHOTON_KL)) as get, \
            mock.patch.object(geo, "_photon_throttle"):
        body = client.get("/api/geo/search?q=kuala lumpur").json()
    names = [(r["name"], r["kind"]) for r in body["results"]]
    assert names == [("Kuala Lumpur", "city"), ("Malaysia", "country"), ("Fiji", "country")]
    kl, my, fj = body["results"]
    assert kl["bbox"] == {"min_lat": 3.0334, "max_lat": 3.2446, "min_lon": 101.615, "max_lon": 101.758}
    assert my["country_code"] == "MY" and my["bbox"]["min_lon"] == 98.74
    assert fj["bbox"] is None  # dateline-crossing extent cannot be one box
    assert "OpenStreetMap" in body["attribution"]
    sent = get.call_args.kwargs
    assert sent["headers"]["User-Agent"].startswith("TerraShift")
    assert ("layer", "city") in sent["params"] and ("lang", "en") in sent["params"]


def test_search_is_cached(client):
    from api.routes import geo
    geo._search_cache.clear()
    with mock.patch.object(geo.requests, "get", return_value=_photon(PHOTON_KL)) as get, \
            mock.patch.object(geo, "_photon_throttle"):
        client.get("/api/geo/search?q=Kuala Lumpur")
        client.get("/api/geo/search?q=kuala   lumpur")
    assert get.call_count == 1


def test_search_no_results_and_validation(client):
    from api.routes import geo
    geo._search_cache.clear()
    with mock.patch.object(geo.requests, "get", return_value=_photon({"features": []})), \
            mock.patch.object(geo, "_photon_throttle"):
        assert client.get("/api/geo/search?q=asdfqwerzxcv").json()["results"] == []
    assert client.get("/api/geo/search?q=a").status_code == 422


def test_search_provider_down_is_502(client):
    from api.routes import geo
    geo._search_cache.clear()
    with mock.patch.object(geo.requests, "get", side_effect=geo.requests.ConnectionError("down")), \
            mock.patch.object(geo, "_photon_throttle"):
        response = client.get("/api/geo/search?q=London")
    assert response.status_code == 502 and "unavailable" in response.json()["detail"]


# ---- coverage ---------------------------------------------------------------------------
def _land_grid():
    """1 degree grid with land only in the box 0..10N, 100..110E."""
    lat = np.arange(-89.5, 90, 1.0)
    lon = np.arange(-179.5, 180, 1.0)
    values = np.full((lat.size, lon.size), np.nan)
    values[np.ix_((lat > 0) & (lat < 10), (lon > 100) & (lon < 110))] = 0.5
    return global_maps.MapGrid(lat=lat, lon=lon, values=values)


def _water_grid():
    g = _land_grid()
    return global_maps.MapGrid(lat=g.lat, lon=g.lon, values=np.where(np.isnan(g.values), 1.0, np.nan))


def _global_grid():
    g = _land_grid()
    return global_maps.MapGrid(lat=g.lat, lon=g.lon, values=np.ones_like(g.values))


@pytest.fixture()
def fake_grids(monkeypatch):
    def load(key, year, month):
        if key.startswith("M2TMNXLND"):
            return _land_grid()
        if key.startswith("M2TMNXOCN"):
            return _water_grid()
        return _global_grid()
    monkeypatch.setattr(global_maps, "load_month", load)


def test_coverage_on_land_and_over_ocean(fake_grids):
    land = coverage.check(point=(5.0, 105.0))["variables"]
    sea = coverage.check(point=(-30.0, -140.0))["variables"]
    assert land["M2TMNXLND/GWETTOP"]["status"] == "available"
    assert land["M2TMNXOCN/TSKINWTR"]["status"] == "no_data_here"
    assert sea["M2TMNXLND/GWETTOP"]["status"] == "no_data_here"
    assert "oceans" in sea["M2TMNXLND/GWETTOP"]["reason"]
    assert sea["M2TMNXOCN/TSKINWTR"]["status"] == "available"
    for v in (land, sea):  # global datasets need no lookup
        assert v["M2TMNXSLV/T2M"]["status"] == "available"
        assert v["GPM_3IMERGM/precipitation"]["status"] == "available"
    assert set(land) == set(config.VARIABLES)


def test_coverage_box_partly_over_land(fake_grids):
    out = coverage.check(box=coverage.Box(-5.0, 3.0, 95.0, 102.0))["variables"]
    assert out["M2TMNXLND/GWETTOP"]["status"] == "available"


def test_coverage_unknown_when_nasa_unreachable(monkeypatch):
    monkeypatch.setattr(global_maps, "load_month", mock.Mock(side_effect=OSError("down")))
    out = coverage.check(point=(5.0, 105.0))["variables"]
    assert out["M2TMNXLND/GWETTOP"]["status"] == "unknown"  # never guessed as available
    assert out["M2TMNXSLV/T2M"]["status"] == "available"


def test_coverage_endpoint_validates_arguments(client, fake_grids):
    assert client.get("/api/maps/coverage?lat=5&lon=105").status_code == 200
    assert client.get("/api/maps/coverage?min_lat=0&max_lat=5&min_lon=100&max_lon=105").status_code == 200
    assert client.get("/api/maps/coverage?lat=5").status_code == 400
    assert client.get("/api/maps/coverage?min_lat=5&max_lat=0&min_lon=100&max_lon=105").status_code == 400
    assert client.get("/api/maps/coverage?lat=95&lon=0").status_code == 422
