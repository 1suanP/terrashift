"""Unit tests for TimeRange validation and Config validation (Requirements 6, 23-26, 34)."""
import dataclasses
from datetime import date

import pytest

import config
from modules.errors import ConfigError
from modules.models import AnalysisRequest, BoundingBox, TimeRange


# ---- TimeRange ----------------------------------------------------------------
def test_time_range_equal_dates_ok():
    assert TimeRange("2020-01-01", "2020-01-01").start == "2020-01-01"


def test_time_range_reversed_rejected():
    with pytest.raises(ValueError, match="earlier than or equal"):
        TimeRange("2021-01-01", "2020-01-01")


@pytest.mark.parametrize("start,end", [("nope", "2020-01-01"), ("2020-01-01", "2020-13-40"), ("", "2020-01-01")])
def test_time_range_invalid_strings(start, end):
    with pytest.raises(ValueError):
        TimeRange(start, end)


def test_time_range_non_string_rejected():
    with pytest.raises(ValueError, match="start"):
        TimeRange(None, "2020-01-01")  # type: ignore[arg-type]


# ---- validate_request ---------------------------------------------------------
TODAY = date(2026, 11, 13)


def test_validate_request_accepts_valid():
    config.validate_request("GPM_3IMERGM", "precipitation", TimeRange("2000-06-01", "2020-12-31"), TODAY)


@pytest.mark.parametrize("key", ["gpm_3imergm", "UNKNOWN", "", None, 5])
def test_validate_request_bad_dataset(key):
    with pytest.raises(ValueError, match="dataset_key"):
        config.validate_request(key, "precipitation", TimeRange("2001-01-01", "2002-01-01"), TODAY)


@pytest.mark.parametrize("var", ["Precipitation", "T2M", "", None])
def test_validate_request_bad_variable(var):
    with pytest.raises(ValueError, match="variable_id"):
        config.validate_request("GPM_3IMERGM", var, TimeRange("2001-01-01", "2002-01-01"), TODAY)


def test_validate_request_outside_period_mentions_period():
    with pytest.raises(ValueError, match="2000-06-01"):
        config.validate_request("GPM_3IMERGM", "precipitation", TimeRange("1999-01-01", "2002-01-01"), TODAY)
    with pytest.raises(ValueError, match="2026-11-13"):
        config.validate_request("GPM_3IMERGM", "precipitation", TimeRange("2001-01-01", "2030-01-01"), TODAY)


# ---- Config content -----------------------------------------------------------
def test_expected_datasets_and_variables_present():
    assert config.DATASETS["GPM_3IMERGM"].version == "07"
    assert config.DATASETS["GPM_3IMERGM"].provider == "GES_DISC"
    assert date.fromisoformat(config.DATASETS["GPM_3IMERGM"].period_start) <= date(2000, 6, 1)
    assert date.fromisoformat(config.DATASETS["M2TMNXSLV"].period_start) <= date(1980, 1, 1)
    for var in ("T2M", "TS", "QV2M", "PS", "SLP", "U10M", "V10M"):
        assert f"M2TMNXSLV/{var}" in config.VARIABLES
    assert "M2TMNXLND/PRECTOTLAND" in config.VARIABLES
    assert config.VARIABLES["GPM_3IMERGM/precipitation"].units == "mm/day"


def test_demo_presets_cover_precip_and_atmosphere():
    kinds = {(p.dataset_key, p.variable_id) for p in config.DEMO_PRESETS}
    assert ("GPM_3IMERGM", "precipitation") in kinds
    assert any(ds == "M2TMNXSLV" for ds, _ in kinds)


def test_demo_presets_build_valid_requests():
    for p in config.DEMO_PRESETS:
        AnalysisRequest(p.dataset_key, p.variable_id, p.bounds, p.time_range, p.use_anomalies)
        config.validate_request(p.dataset_key, p.variable_id, p.time_range)


def test_variable_text_limits():
    for key, meta in config.VARIABLES.items():
        assert 1 <= len(meta.short_description) <= 150, key
        assert 200 <= len(meta.plain_language) <= 300, key
        assert "\n" not in meta.plain_language, key
        assert 1 <= len(meta.trend_direction_hint) <= 80, key


def test_every_variable_in_guided_flow_resolves():
    for env, keys in config.GUIDED_FLOW.items():
        assert env in config.ENVIRONMENTS
        assert all(k in config.VARIABLES for k in keys)


# ---- validate_config error paths ----------------------------------------------
def test_missing_variable_entry_detected():
    variables = {k: v for k, v in config.VARIABLES.items() if k != "M2TMNXSLV/T2M"}
    with pytest.raises(ConfigError, match="T2M"):
        config.validate_config(variables=variables)


def test_unknown_guided_flow_variable_detected():
    with pytest.raises(ConfigError, match="unknown variable"):
        config.validate_config(guided_flow={"atmosphere": ["M2TMNXSLV/NOPE"]})


def test_unknown_environment_category_detected():
    meta = dataclasses.replace(config.VARIABLES["M2TMNXSLV/T2M"], category="nope")
    with pytest.raises(ConfigError, match="category"):
        config.validate_config(variables={**config.VARIABLES, "M2TMNXSLV/T2M": meta})


def test_overlong_description_detected():
    meta = dataclasses.replace(config.VARIABLES["M2TMNXSLV/T2M"], short_description="x" * 151)
    with pytest.raises(ConfigError, match="short_description"):
        config.validate_config(variables={**config.VARIABLES, "M2TMNXSLV/T2M": meta})


def test_empty_description_detected():
    meta = dataclasses.replace(config.VARIABLES["M2TMNXSLV/T2M"], trend_direction_hint="")
    with pytest.raises(ConfigError, match="trend_direction_hint"):
        config.validate_config(variables={**config.VARIABLES, "M2TMNXSLV/T2M": meta})


def test_demo_preset_outside_period_detected():
    bad = dataclasses.replace(config.DEMO_PRESETS[0], time_range=TimeRange("1990-01-01", "1991-01-01"))
    with pytest.raises(ConfigError, match="invalid"):
        config.validate_config(demo_presets=[bad])


def test_bad_alpha_and_colors_detected():
    with pytest.raises(ConfigError):
        config.validate_config(alpha=1.5)
    with pytest.raises(ConfigError):
        config.validate_config(colors={"increasing": "green", "decreasing": "#c62828", "none": "#757575"})
