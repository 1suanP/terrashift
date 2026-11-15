"""Globe map, geocoding, and fixed config routes (no network: NASA and OSM are mocked)."""
import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

from modules import global_maps

BACKEND = Path(__file__).resolve().parent.parent / "backend"


@pytest.fixture()
def client():
    sys.path.insert(0, str(BACKEND))
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


def _grid():
    lat = np.array([-0.25, 0.25])
    lon = np.array([-0.5, 0.0, 0.5])
    values = np.array([[1.0, np.nan, 3.0], [4.0, 5.0, 6.0]])  # rows south -> north
    return global_maps.MapGrid(lat=lat, lon=lon, values=values)


def test_grid_payload_is_row_major_south_to_north_with_nulls():
    p = global_maps.grid_payload(_grid())
    assert (p["lat_count"], p["lon_count"]) == (2, 3)
    assert p["lat_start"] == -0.25 and p["lat_step"] == 0.5 and p["lon_step"] == 0.5
    assert p["values"] == [1.0, None, 3.0, 4.0, 5.0, 6.0]
    assert (p["min"], p["max"]) == (1.0, 6.0)


def test_load_month_reads_nasa_once_then_uses_disk_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(global_maps, "CACHE_DIR", tmp_path)
    key = "GPM_3IMERGM/precipitation"
    monkeypatch.setattr(global_maps, "available_months", lambda k, y: {1: "dap4://granule"})
    reader = mock.Mock(return_value=_grid())
    monkeypatch.setattr(global_maps, "_read_granule", reader)
    first = global_maps.load_month(key, 2023, 1)
    second = global_maps.load_month(key, 2023, 1)
    assert reader.call_count == 1
    np.testing.assert_allclose(first.values, second.values)


def test_unpublished_month_is_reported_not_invented(tmp_path, monkeypatch):
    monkeypatch.setattr(global_maps, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(global_maps, "available_months", lambda k, y: {1: "dap4://granule"})
    with pytest.raises(global_maps.DataDiscoveryError, match="not published"):
        global_maps.load_month("GPM_3IMERGM/precipitation", 2023, 7)


def test_year_with_nothing_published_has_no_months(monkeypatch):
    global_maps._months_cache.clear()

    def no_granules(*args, **kwargs):
        raise global_maps.DataDiscoveryError("No granules were found for GPM_3IMERGM ...")

    monkeypatch.setattr(global_maps.data_discovery, "search_granules", no_granules)
    assert global_maps.available_months("GPM_3IMERGM/precipitation", 2024) == {}
    global_maps._months_cache.clear()


def test_map_layers_endpoint_lists_only_real_layers(client):
    body = client.get("/api/maps/layers").json()
    assert [l["key"] for l in body["layers"]] == list(global_maps.MAP_LAYERS)


def test_unknown_map_layer_is_404(client):
    assert client.get("/api/maps/M2TMNXSLV/PS?year=2020&month=1").status_code == 404


def _fake_response(payload):
    resp = mock.Mock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_reverse_geocode_found_and_ocean(client):
    from api.routes import geo
    geo._reverse_cached.cache_clear()
    city = {"display_name": "Manaus, Amazonas, Brazil",
            "address": {"city": "Manaus", "state": "Amazonas", "country": "Brazil", "country_code": "br"}}
    with mock.patch.object(geo.requests, "get", return_value=_fake_response(city)) as get, \
            mock.patch.object(geo, "_throttle"):
        body = client.get("/api/geo/reverse?lat=-3.1&lon=-60").json()
        assert body["found"] and body["place"] == "Manaus" and body["country_code"] == "BR"
        assert "OpenStreetMap" in body["attribution"]
        assert get.call_args.kwargs["headers"]["User-Agent"]
    with mock.patch.object(geo.requests, "get", return_value=_fake_response({"error": "Unable to geocode"})), \
            mock.patch.object(geo, "_throttle"):
        assert client.get("/api/geo/reverse?lat=0&lon=-140").json()["found"] is False


def test_reverse_geocode_rejects_bad_coordinates(client):
    assert client.get("/api/geo/reverse?lat=95&lon=0").status_code == 422


def test_demo_presets_endpoint_works(client):
    response = client.get("/api/config/presets")
    assert response.status_code == 200
    presets = response.json()
    assert {p["region_name"] for p in presets} >= {"California", "Amazon Basin"}
    assert all(p["min_lat"] < p["max_lat"] for p in presets)


def test_guided_flow_endpoint_works(client):
    response = client.get("/api/config/guided-flow/water_cycle")
    assert response.status_code == 200
    assert response.json()[0]["key"] == "GPM_3IMERGM/precipitation"
