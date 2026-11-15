"""Properties 4 and 13: significance classification and interpretation content.

Validates Requirements 17.1-17.4, 18.1-18.4.
"""
import math
import re

import pytest
from hypothesis import given, strategies as st

import config
from modules.models import LinearTrendResult, MannKendallResult
from modules.trend_analysis import classify_significance, interpret_trend

slopes = st.floats(-1e3, 1e3, allow_nan=False)


@given(st.floats(0, 1), slopes, st.floats(0.001, 0.999))
def test_classification_consistent(p, slope, alpha):
    out = classify_significance(p, slope, alpha)
    if p >= alpha or slope == 0:
        assert out == "none"
    elif slope > 0:
        assert out == "increasing"
    else:
        assert out == "decreasing"


def test_classification_edges():
    assert classify_significance(float("nan"), 1.0) == "none"
    assert classify_significance(0.01, float("nan")) == "none"
    assert classify_significance(0.05, 1.0, 0.05) == "none"
    for args in [(-0.1, 1.0), (1.1, 1.0), (0.5, 1.0, float("nan")), (0.5, 1.0, 0.0), (0.5, 1.0, 1.0)]:
        with pytest.raises(ValueError):
            classify_significance(*args)


def lin(slope, p=0.001):
    return LinearTrendResult(slope, 0.0, 0.9, p, 0.01, slope - 0.02, slope + 0.02)


def mk(trend, slope, h=True):
    return MannKendallResult(trend, h, 0.001 if h else 0.5, 3.0, 0.5, 100.0, 50.0, slope, 0.0)


META = config.VARIABLES["M2TMNXSLV/T2M"]
JARGON = ["p-value", "tau", "null hypothesis", "coefficient"]


@given(st.floats(1e-4, 500), st.sampled_from([1, -1]), st.text("abcdefghij ", min_size=1, max_size=60).filter(lambda s: s.strip()))
def test_interpretation_content(rate, sign, region):
    slope = sign * rate
    trend = "increasing" if sign > 0 else "decreasing"
    text = interpret_trend(lin(slope), mk(trend, slope), META, region)
    assert region in text and META.units in text and "per year" in text
    assert trend in text and "statistically significant" in text
    assert "linear regression" in text and "Mann-Kendall" in text
    assert len(text) <= 400
    assert 1 <= len(re.findall(r"[.!?](?:\s|$)", text)) <= 3
    assert not any(j in text.lower() for j in JARGON)
    assert "e+" not in text and "e-" not in text


def test_rate_rounded_to_two_significant_figures(temp_meta):
    text = interpret_trend(lin(0.0234567), mk("increasing", 0.02), temp_meta, "Peru")
    assert "0.023 " in text
    text = interpret_trend(lin(1234.0), mk("increasing", 1234.0), temp_meta, "Peru")
    assert "1200 " in text


def test_not_significant_and_disagreement(temp_meta):
    text = interpret_trend(lin(0.5, p=0.4), mk("no trend", 0.4, h=False), temp_meta, "Peru")
    assert "not statistically significant" in text
    text = interpret_trend(lin(0.5), mk("decreasing", -0.4), temp_meta, "Peru")
    assert "disagree" in text and "not statistically significant" in text
    text = interpret_trend(lin(0.0), mk("no trend", 0.0, h=False), temp_meta, "Peru")
    assert "not changing" in text


def test_missing_inputs_rejected(temp_meta):
    with pytest.raises(ValueError):
        interpret_trend(None, mk("increasing", 1.0), temp_meta, "Peru")
    with pytest.raises(ValueError):
        interpret_trend(lin(1.0), None, temp_meta, "Peru")
    with pytest.raises(ValueError):
        interpret_trend(lin(1.0), mk("increasing", 1.0), temp_meta, "  ")
    with pytest.raises(ValueError):
        interpret_trend(lin(1.0), mk("increasing", 1.0), None, "Peru")
