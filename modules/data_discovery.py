"""NASA Earthdata Login authentication and CMR granule search (via ``earthaccess``).

Credentials are read only from environment variables or a ``.netrc`` file. Their
values are never logged, included in exception messages, or returned.
"""
from __future__ import annotations

import logging
import math
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import date
from pathlib import Path
from typing import Any

import earthaccess

from modules.errors import DataDiscoveryError

logger = logging.getLogger(__name__)

AUTH_TIMEOUT_SECONDS = 30
SEARCH_TIMEOUT_SECONDS = 30
MAX_GRANULES = 2000

_SETUP_HINT = (
    "Set EARTHDATA_USERNAME and EARTHDATA_PASSWORD (for example in a .env file) or create a "
    "~/.netrc entry. You can create a free Earthdata Login account at "
    "https://urs.earthdata.nasa.gov/users/new."
)


def _netrc_path() -> Path:
    return Path(os.path.expanduser("~")) / ".netrc"


def _has_env_credentials() -> bool:
    return bool(os.environ.get("EARTHDATA_USERNAME")) and bool(os.environ.get("EARTHDATA_PASSWORD"))


def _has_netrc_credentials() -> bool:
    path = _netrc_path()
    if not path.is_file():
        return False
    try:
        import netrc

        entry = netrc.netrc(str(path)).authenticators("urs.earthdata.nasa.gov")
    except Exception:  # unreadable or malformed .netrc -> treat as absent
        return False
    return bool(entry and entry[0] and entry[2])


def validate_credentials() -> bool:
    """Return True if credentials are available locally. Makes no network request."""
    return _has_env_credentials() or _has_netrc_credentials()


def _run_with_timeout(func, timeout: float):
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(func)
    try:
        return future.result(timeout=timeout)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _looks_like_auth_failure(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return any(t in text for t in ("401", "403", "unauthor", "credential", "forbidden", "invalid user", "login"))


def authenticate(strategy: str = "environment", persist: bool = True):
    """Authenticate with Earthdata Login and return the ``earthaccess`` auth object.

    ``strategy`` is ``"environment"`` (default) or ``"netrc"``. If environment credentials
    are absent but a ``.netrc`` exists, the netrc strategy is used instead.
    Raises ``DataDiscoveryError`` for missing, rejected, or unreachable cases.
    """
    if strategy == "environment" and not _has_env_credentials():
        if _has_netrc_credentials():
            strategy = "netrc"
        else:
            raise DataDiscoveryError("Earthdata Login credentials were not found. " + _SETUP_HINT)
    elif strategy == "netrc" and not _has_netrc_credentials():
        if _has_env_credentials():
            strategy = "environment"
        else:
            raise DataDiscoveryError("Earthdata Login credentials were not found. " + _SETUP_HINT)

    try:
        auth = _run_with_timeout(lambda: earthaccess.login(strategy=strategy, persist=persist), AUTH_TIMEOUT_SECONDS)
    except FutureTimeout as exc:
        raise DataDiscoveryError(
            f"Earthdata Login could not be reached within {AUTH_TIMEOUT_SECONDS} seconds. "
            "Check your connection and try again."
        ) from exc
    except Exception as exc:
        if _looks_like_auth_failure(exc):
            raise DataDiscoveryError(
                "Earthdata Login rejected the supplied credentials. Check your username and password."
            ) from None
        raise DataDiscoveryError(
            "Earthdata Login service could not be reached. Check your connection and try again."
        ) from None

    if not getattr(auth, "authenticated", False):
        raise DataDiscoveryError(
            "Earthdata Login rejected the supplied credentials. Check your username and password."
        )
    return auth


def _validate_search_args(short_name: Any, temporal: Any, bounding_box: Any) -> None:
    if not isinstance(short_name, str) or not short_name.strip() or len(short_name) > 100:
        raise DataDiscoveryError("short_name must be a non-empty string of at most 100 characters.")
    try:
        start, end = temporal
        start_d, end_d = date.fromisoformat(start), date.fromisoformat(end)
    except (TypeError, ValueError) as exc:
        raise DataDiscoveryError("temporal must be a (start, end) pair of ISO dates (YYYY-MM-DD).") from exc
    if start_d > end_d:
        raise DataDiscoveryError(f"temporal start ({start}) is after end ({end}).")
    try:
        west, south, east, north = bounding_box
        values = [west, south, east, north]
    except (TypeError, ValueError) as exc:
        raise DataDiscoveryError("bounding_box must be (west, south, east, north).") from exc
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values):
        raise DataDiscoveryError("bounding_box values must be finite numbers.")
    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise DataDiscoveryError("bounding_box longitude must be within -180 to 180.")
    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise DataDiscoveryError("bounding_box latitude must be within -90 to 90.")
    if south > north:
        raise DataDiscoveryError("bounding_box south must not be greater than north.")


def search_granules(
    short_name: str,
    temporal: tuple[str, str],
    bounding_box: tuple[float, float, float, float],
    version: str | None = None,
) -> list:
    """Search NASA CMR for granules. Raises ``DataDiscoveryError`` on any failure or empty result."""
    _validate_search_args(short_name, temporal, bounding_box)

    kwargs: dict[str, Any] = {
        "short_name": short_name,
        "temporal": tuple(temporal),
        "bounding_box": tuple(bounding_box),
        "count": MAX_GRANULES,
    }
    if version:
        kwargs["version"] = version

    try:
        granules = _run_with_timeout(lambda: earthaccess.search_data(**kwargs), SEARCH_TIMEOUT_SECONDS)
    except FutureTimeout as exc:
        raise DataDiscoveryError(
            f"The CMR search timed out after {SEARCH_TIMEOUT_SECONDS} seconds. Please try again."
        ) from exc
    except Exception as exc:
        if _looks_like_auth_failure(exc):
            raise DataDiscoveryError(
                "Authentication failed during the CMR search. Please verify your Earthdata credentials."
            ) from None
        raise DataDiscoveryError("The CMR search failed because of a service error. Please try again.") from None

    granules = list(granules or [])[:MAX_GRANULES]
    if not granules:
        raise DataDiscoveryError(
            f"No granules were found for {short_name} with time range {temporal[0]} to {temporal[1]} "
            f"and bounding box {tuple(bounding_box)}. Check the time range against the dataset's "
            "available period."
        )
    return granules


def _related_urls(granule: Any) -> list[dict]:
    try:
        urls = granule["umm"]["RelatedUrls"]
    except (KeyError, TypeError):
        return []
    return urls if isinstance(urls, list) else []


def get_opendap_urls(granules: list) -> list[str]:
    """Return one ``dap4://`` OPeNDAP URL per granule that exposes one, preserving order."""
    result: list[str] = []
    for granule in granules or []:
        for entry in _related_urls(granule):
            description = str(entry.get("Description", "") or "")
            url = entry.get("URL")
            if "OPENDAP" in description.upper() and isinstance(url, str) and url:
                if url.startswith("https://"):
                    url = "dap4://" + url[len("https://"):]
                elif url.startswith("http://"):
                    url = "dap4://" + url[len("http://"):]
                result.append(url)
                break  # at most one URL per granule
    return result
