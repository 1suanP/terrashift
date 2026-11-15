"""Property 8: bounding box validation and CMR tuple ordering. Validates Requirements 5.1, 5.2, 5.3, 5.5."""
import math

import pytest
from hypothesis import given, strategies as st

from modules.models import BoundingBox

lon = st.floats(min_value=-180, max_value=180, allow_nan=False)
lat = st.floats(min_value=-90, max_value=90, allow_nan=False)


@given(lon, lon, lat, lat)
def test_bounding_box_validity_matches_ordering(a, b, c, d):
    if a < b and c < d:
        box = BoundingBox(a, c, b, d)
        assert box.to_cmr_tuple() == (a, c, b, d)
    else:
        with pytest.raises(ValueError):
            BoundingBox(a, c, b, d)


@given(st.floats(allow_nan=True, allow_infinity=True).filter(lambda x: not math.isfinite(x) or abs(x) > 180))
def test_out_of_range_or_non_finite_longitude_rejected(bad):
    with pytest.raises(ValueError):
        BoundingBox(bad, 0, 10, 10)


@pytest.mark.parametrize("bad", ["10", None, True])
def test_non_numeric_coordinate_rejected(bad):
    with pytest.raises(TypeError):
        BoundingBox(bad, 0, 10, 10)


def test_boundary_values_accepted():
    box = BoundingBox(-180, -90, 180, 90)
    assert box.to_cmr_tuple() == (-180, -90, 180, 90)
