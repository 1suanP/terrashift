"""
Geocoding routes: place search (autocomplete) and reverse geocoding of clicked points.

Both providers are non-U.S.-Government services built on OpenStreetMap data (ODbL),
so every response carries an attribution string the UI must show.

* Search uses Photon (https://photon.komoot.io, by komoot). It is built for
  search-as-you-type; the public server asks for a "reasonable" number of requests.
  We debounce in the browser, cache here, and space requests >= 0.35 s apart.
* Reverse geocoding uses Nominatim. Its policy allows at most 1 request/s, requires an
  identifying User-Agent, and forbids autocomplete, so Nominatim is never used for
  typing-time search. https://operations.osmfoundation.org/policies/nominatim/

All calls go through this backend (one place to cache, throttle, and switch provider).
"""
import threading
import time
from collections import OrderedDict
from functools import lru_cache
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
PHOTON_URL = "https://photon.komoot.io/api/"
USER_AGENT = "TerraShift/3.0 (NASA Space Apps student project; local development)"
ATTRIBUTION = "Place names \u00a9 OpenStreetMap contributors (ODbL), via Nominatim"
SEARCH_ATTRIBUTION = "Search by Photon (komoot) \u00b7 \u00a9 OpenStreetMap contributors (ODbL)"

# Places, not shops or bus stops (Photon "layer" filter)
PHOTON_LAYERS = ("country", "state", "county", "city", "district", "locality", "other")


class _Throttle:
    """Keep at least ``gap`` seconds between calls to one provider (across threads)."""

    def __init__(self, gap: float) -> None:
        self.gap = gap
        self._lock = threading.Lock()
        self._last = 0.0

    def __call__(self) -> None:
        with self._lock:
            wait = self.gap - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()


_throttle = _Throttle(1.1)  # Nominatim: max 1 request per second
_photon_throttle = _Throttle(0.35)


def _pick(address: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        if address.get(key):
            return address[key]
    return None


@lru_cache(maxsize=2048)
def _reverse_cached(lat: float, lon: float) -> Dict[str, Any]:
    _throttle()
    response = requests.get(
        NOMINATIM_URL,
        params={"format": "jsonv2", "lat": lat, "lon": lon, "zoom": 10, "accept-language": "en"},
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    if "error" in data:  # open ocean or unnamed area
        return {"found": False}
    address = data.get("address", {})
    return {
        "found": True,
        "place": _pick(address, "city", "town", "village", "hamlet", "municipality", "county", "state_district"),
        "region": _pick(address, "state", "province", "region", "county"),
        "country": address.get("country"),
        "country_code": (address.get("country_code") or "").upper() or None,
        "display_name": data.get("display_name"),
    }


# --------------------------------------------------------------------------- search
_KIND = {
    "country": "country", "state": "state", "county": "region", "city": "city",
    "district": "district", "locality": "place", "other": "place",
}
_REGION_VALUES = {"region", "island", "archipelago", "peninsula", "desert", "mountain_range", "forest", "bay", "sea", "strait"}

_search_cache: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
_search_lock = threading.Lock()
SEARCH_CACHE_SIZE = 1000


def _box_from_extent(extent: Optional[List[float]]) -> Optional[Dict[str, float]]:
    """Photon extent is [west, north, east, south]. None if missing or crossing the dateline."""
    if not extent or len(extent) != 4:
        return None
    west, north, east, south = (float(v) for v in extent)
    if not (west < east and south < north):
        return None
    return {"min_lat": south, "max_lat": north, "min_lon": west, "max_lon": east}


def _normalize(feature: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    props = feature.get("properties", {})
    coords = (feature.get("geometry") or {}).get("coordinates") or []
    name = props.get("name")
    if not name or len(coords) != 2:
        return None
    lon, lat = float(coords[0]), float(coords[1])
    kind = _KIND.get(props.get("type", ""), "place")
    if props.get("osm_value") in _REGION_VALUES:
        kind = "region"
    if props.get("osm_value") == "country" or props.get("type") == "country":
        kind = "country"
    parts = [props.get("city") if props.get("city") != name else None, props.get("county") if kind in ("city", "district", "place") else None,
             props.get("state") if props.get("state") != name else None, props.get("country") if props.get("country") != name else None]
    return {
        "name": name,
        "subtitle": ", ".join(p for p in parts if p),
        "kind": kind,
        "category": (props.get("osm_value") or "").replace("_", " "),
        "lat": lat,
        "lon": lon,
        "bbox": _box_from_extent(props.get("extent")),
        "country": props.get("country"),
        "country_code": (props.get("countrycode") or "").upper() or None,
        "state": props.get("state"),
        "osm_id": f"{props.get('osm_type', '')}{props.get('osm_id', '')}",
    }


def _photon_search(query: str, limit: int) -> List[Dict[str, Any]]:
    key = f"{query.casefold()}|{limit}"
    with _search_lock:
        if key in _search_cache:
            _search_cache.move_to_end(key)
            return _search_cache[key]
    _photon_throttle()
    params: List[tuple] = [("q", query), ("limit", limit + 4), ("lang", "en")]
    params += [("layer", layer) for layer in PHOTON_LAYERS]
    response = requests.get(PHOTON_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=8)
    response.raise_for_status()
    results: List[Dict[str, Any]] = []
    for feature in response.json().get("features", []):
        item = _normalize(feature)
        if not item:
            continue
        # The same place often appears several times (node + boundary): same name and
        # country within ~25 km counts as one. (Distance, not rounding, so 3.150 and
        # 3.152 are not split across a rounding boundary.)
        if any(
            r["name"].casefold() == item["name"].casefold() and r["country"] == item["country"]
            and abs(r["lat"] - item["lat"]) < 0.25 and abs(r["lon"] - item["lon"]) < 0.25
            for r in results
        ):
            continue
        results.append(item)
        if len(results) >= limit:
            break
    with _search_lock:
        _search_cache[key] = results
        if len(_search_cache) > SEARCH_CACHE_SIZE:
            _search_cache.popitem(last=False)
    return results


@router.get("/search")
def search_places(
    q: str = Query(..., min_length=2, max_length=120),
    limit: int = Query(6, ge=1, le=10),
) -> Dict[str, Any]:
    """Places matching ``q`` (countries, states, cities, regions, natural features)."""
    query = " ".join(q.split())
    try:
        results = _photon_search(query, limit)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Place search is unavailable right now ({type(exc).__name__}).") from None
    return {"query": query, "results": results, "attribution": SEARCH_ATTRIBUTION}


@router.get("/reverse")
def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> Dict[str, Any]:
    """Nearest named place for a point. Coordinates are rounded to ~1 km for caching."""
    try:
        result = _reverse_cached(round(lat, 2), round(lon, 2))
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Place lookup is unavailable right now ({type(exc).__name__}).") from None
    return {**result, "lat": lat, "lon": lon, "attribution": ATTRIBUTION}
