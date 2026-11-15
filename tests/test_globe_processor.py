"""
Unit tests for globe_data_processor module.

Tests the contour generation and GeoJSON transformation for 3D globe visualization.
"""
import numpy as np
import pytest
import xarray as xr

from modules.globe_data_processor import process_for_globe


def test_process_for_globe_basic():
    """Test basic contour generation from xarray data."""
    # Create simple synthetic data
    lat = np.linspace(-90, 90, 50)
    lon = np.linspace(-180, 180, 100)
    lon_grid, lat_grid = np.meshgrid(lon, lat)
    
    # Create a temperature pattern (warmer at equator)
    temp = 288 + 15 * np.cos(np.radians(lat_grid))
    
    data = xr.DataArray(
        temp,
        dims=['lat', 'lon'],
        coords={'lat': lat, 'lon': lon},
        attrs={'units': 'K', 'source': 'test'}
    )
    
    result = process_for_globe(data, 'temperature', num_contours=5)
    
    # Check structure
    assert result['type'] == 'FeatureCollection'
    assert 'features' in result
    assert 'metadata' in result
    assert 'colorScale' in result
    
    # Check metadata
    assert result['metadata']['units'] == 'K'
    assert result['metadata']['source'] == 'test'
    assert 'min' in result['metadata']
    assert 'max' in result['metadata']
    assert 'mean' in result['metadata']
    
    # Check color scale
    assert 'min' in result['colorScale']
    assert 'max' in result['colorScale']
    assert 'colors' in result['colorScale']
    assert 'stops' in result['colorScale']


def test_process_for_globe_all_nan():
    """Test handling of all-NaN data."""
    lat = np.linspace(-90, 90, 20)
    lon = np.linspace(-180, 180, 40)
    
    data = xr.DataArray(
        np.full((20, 40), np.nan),
        dims=['lat', 'lon'],
        coords={'lat': lat, 'lon': lon}
    )
    
    result = process_for_globe(data, 'temperature')
    
    # Should return empty FeatureCollection
    assert result['type'] == 'FeatureCollection'
    assert result['features'] == []
    assert 'metadata' in result


def test_process_for_globe_single_value():
    """Test handling of single-value (no variation) data."""
    lat = np.linspace(-90, 90, 20)
    lon = np.linspace(-180, 180, 40)
    
    data = xr.DataArray(
        np.full((20, 40), 288.0),
        dims=['lat', 'lon'],
        coords={'lat': lat, 'lon': lon}
    )
    
    result = process_for_globe(data, 'temperature')
    
    # Should return empty FeatureCollection (no contours for single value)
    assert result['type'] == 'FeatureCollection'
    assert result['features'] == []


def test_process_for_globe_invalid_type():
    """Test TypeError for invalid data type."""
    with pytest.raises(TypeError, match="data must be an xr.DataArray"):
        process_for_globe([1, 2, 3], 'temperature')


def test_process_for_globe_missing_dimensions():
    """Test ValueError for missing lat/lon dimensions."""
    data = xr.DataArray(
        np.random.randn(10, 10),
        dims=['x', 'y'],
        coords={'x': np.arange(10), 'y': np.arange(10)}
    )
    
    with pytest.raises(ValueError, match="must have 'lat' or 'latitude' dimension"):
        process_for_globe(data, 'temperature')


def test_process_for_globe_invalid_layer_type():
    """Test ValueError for invalid layer_type."""
    lat = np.linspace(-90, 90, 20)
    lon = np.linspace(-180, 180, 40)
    
    data = xr.DataArray(
        np.random.randn(20, 40),
        dims=['lat', 'lon'],
        coords={'lat': lat, 'lon': lon}
    )
    
    with pytest.raises(ValueError, match="layer_type must be one of"):
        process_for_globe(data, 'invalid_type')


def test_process_for_globe_invalid_num_contours():
    """Test ValueError for num_contours < 2."""
    lat = np.linspace(-90, 90, 20)
    lon = np.linspace(-180, 180, 40)
    
    data = xr.DataArray(
        np.random.randn(20, 40),
        dims=['lat', 'lon'],
        coords={'lat': lat, 'lon': lon}
    )
    
    with pytest.raises(ValueError, match="num_contours must be at least 2"):
        process_for_globe(data, 'temperature', num_contours=1)


def test_process_for_globe_invalid_smooth_sigma():
    """Test ValueError for negative smooth_sigma."""
    lat = np.linspace(-90, 90, 20)
    lon = np.linspace(-180, 180, 40)
    
    data = xr.DataArray(
        np.random.randn(20, 40),
        dims=['lat', 'lon'],
        coords={'lat': lat, 'lon': lon}
    )
    
    with pytest.raises(ValueError, match="smooth_sigma must be non-negative"):
        process_for_globe(data, 'temperature', smooth_sigma=-1.0)


def test_process_for_globe_empty_data():
    """Test ValueError for empty data."""
    data = xr.DataArray(
        np.array([]).reshape(0, 0),
        dims=['lat', 'lon'],
        coords={'lat': np.array([]), 'lon': np.array([])}
    )
    
    with pytest.raises(ValueError, match="data is empty"):
        process_for_globe(data, 'temperature')


def test_process_for_globe_feature_structure():
    """Test that generated features have correct GeoJSON structure."""
    lat = np.linspace(-90, 90, 30)
    lon = np.linspace(-180, 180, 60)
    lon_grid, lat_grid = np.meshgrid(lon, lat)
    
    # Create clear gradient to ensure contours are generated
    precip = 5 + 3 * np.sin(np.radians(lat_grid))
    
    data = xr.DataArray(
        precip,
        dims=['lat', 'lon'],
        coords={'lat': lat, 'lon': lon}
    )
    
    result = process_for_globe(data, 'precipitation', num_contours=3)
    
    # Should have at least some features
    if len(result['features']) > 0:
        feature = result['features'][0]
        
        # Check Feature structure
        assert feature['type'] == 'Feature'
        assert 'geometry' in feature
        assert 'properties' in feature
        
        # Check geometry
        assert feature['geometry']['type'] == 'LineString'
        assert 'coordinates' in feature['geometry']
        coords = feature['geometry']['coordinates']
        assert len(coords) >= 2
        
        # Check coordinate format [lon, lat]
        for coord in coords:
            assert len(coord) == 2
            lon_val, lat_val = coord
            assert -180 <= lon_val <= 180
            assert -90 <= lat_val <= 90
        
        # Check properties
        assert 'value' in feature['properties']
        assert 'layer_type' in feature['properties']
        assert feature['properties']['layer_type'] == 'precipitation'


def test_process_for_globe_alternative_coord_names():
    """Test handling of 'latitude'/'longitude' dimension names."""
    latitude = np.linspace(-90, 90, 20)
    longitude = np.linspace(-180, 180, 40)
    lon_grid, lat_grid = np.meshgrid(longitude, latitude)
    
    temp = 288 + 10 * np.cos(np.radians(lat_grid))
    
    data = xr.DataArray(
        temp,
        dims=['latitude', 'longitude'],
        coords={'latitude': latitude, 'longitude': longitude}
    )
    
    result = process_for_globe(data, 'temperature')
    
    assert result['type'] == 'FeatureCollection'
    assert 'features' in result


def test_process_for_globe_with_nans():
    """Test handling of partial NaN data."""
    lat = np.linspace(-90, 90, 30)
    lon = np.linspace(-180, 180, 60)
    lon_grid, lat_grid = np.meshgrid(lon, lat)
    
    temp = 288 + 10 * np.cos(np.radians(lat_grid))
    # Add some NaN values
    temp[5:10, 10:20] = np.nan
    
    data = xr.DataArray(
        temp,
        dims=['lat', 'lon'],
        coords={'lat': lat, 'lon': lon}
    )
    
    result = process_for_globe(data, 'temperature')
    
    # Should still work and produce features
    assert result['type'] == 'FeatureCollection'
    assert 'features' in result
    # Metadata should ignore NaN values
    assert np.isfinite(result['metadata']['min'])
    assert np.isfinite(result['metadata']['max'])


def test_process_for_globe_no_smoothing():
    """Test contour generation with smoothing disabled."""
    lat = np.linspace(-90, 90, 20)
    lon = np.linspace(-180, 180, 40)
    lon_grid, lat_grid = np.meshgrid(lon, lat)
    
    temp = 288 + 10 * np.cos(np.radians(lat_grid))
    
    data = xr.DataArray(
        temp,
        dims=['lat', 'lon'],
        coords={'lat': lat, 'lon': lon}
    )
    
    result = process_for_globe(data, 'temperature', smooth_sigma=0.0)
    
    assert result['type'] == 'FeatureCollection'
    assert 'features' in result


def test_process_for_globe_layer_types():
    """Test all supported layer types."""
    lat = np.linspace(-90, 90, 20)
    lon = np.linspace(-180, 180, 40)
    lon_grid, lat_grid = np.meshgrid(lon, lat)
    
    # Test each layer type
    for layer_type in ['temperature', 'precipitation', 'aerosol']:
        values = 10 + 5 * np.cos(np.radians(lat_grid))
        
        data = xr.DataArray(
            values,
            dims=['lat', 'lon'],
            coords={'lat': lat, 'lon': lon}
        )
        
        result = process_for_globe(data, layer_type)
        
        assert result['type'] == 'FeatureCollection'
        assert 'colorScale' in result
        assert len(result['colorScale']['colors']) > 0
        assert len(result['colorScale']['stops']) > 0


def test_get_color_scale_temperature():
    """Test temperature color scale generation."""
    from modules.globe_data_processor import get_color_scale
    
    scale = get_color_scale('temperature', -5.0, 5.0)
    
    # Check structure
    assert 'min' in scale
    assert 'max' in scale
    assert 'colors' in scale
    assert 'stops' in scale
    
    # Check values
    assert scale['min'] == -5.0
    assert scale['max'] == 5.0
    
    # Check temperature colors (6 stops)
    assert len(scale['colors']) == 6
    assert len(scale['stops']) == 6
    
    # Check specific colors
    assert scale['colors'][0] == '#0000FF'  # blue (cold)
    assert scale['colors'][1] == '#35D6E8'  # cyan
    assert scale['colors'][2] == '#FFFFFF'  # white (neutral)
    assert scale['colors'][3] == '#FFD700'  # yellow
    assert scale['colors'][4] == '#FF9F0A'  # orange
    assert scale['colors'][5] == '#FF453A'  # red (hot)
    
    # Check stops
    assert scale['stops'] == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]


def test_get_color_scale_aerosol():
    """Test aerosol color scale generation."""
    from modules.globe_data_processor import get_color_scale
    
    scale = get_color_scale('aerosol', 0.0, 1.0)
    
    # Check structure
    assert scale['min'] == 0.0
    assert scale['max'] == 1.0
    
    # Check aerosol colors (3 stops)
    assert len(scale['colors']) == 3
    assert len(scale['stops']) == 3
    
    # Check specific colors
    assert scale['colors'][0] == '#35D6E8'  # cyan (low)
    assert scale['colors'][1] == '#FF9F0A'  # orange (moderate)
    assert scale['colors'][2] == '#FF453A'  # red (high)
    
    # Check stops
    assert scale['stops'] == [0.0, 0.5, 1.0]


def test_get_color_scale_precipitation():
    """Test precipitation color scale generation."""
    from modules.globe_data_processor import get_color_scale
    
    scale = get_color_scale('precipitation', 0.0, 10.0)
    
    # Check structure
    assert scale['min'] == 0.0
    assert scale['max'] == 10.0
    
    # Check precipitation colors (3 stops)
    assert len(scale['colors']) == 3
    assert len(scale['stops']) == 3
    
    # Check specific colors
    assert scale['colors'][0] == '#35D6E8'  # cyan (low)
    assert scale['colors'][1] == '#4C8DFF'  # blue (moderate)
    assert scale['colors'][2] == '#0000AA'  # dark blue (high)
    
    # Check stops
    assert scale['stops'] == [0.0, 0.5, 1.0]


def test_get_color_scale_unknown_type():
    """Test that unknown layer types fall back to temperature scale."""
    from modules.globe_data_processor import get_color_scale
    
    scale = get_color_scale('unknown_type', -10.0, 10.0)
    
    # Should default to temperature scale
    assert scale['min'] == -10.0
    assert scale['max'] == 10.0
    assert len(scale['colors']) == 6  # temperature has 6 colors
    assert scale['colors'][0] == '#0000FF'  # blue (temperature scale)


def test_get_color_scale_negative_range():
    """Test color scale with negative data range."""
    from modules.globe_data_processor import get_color_scale
    
    scale = get_color_scale('temperature', -15.0, -5.0)
    
    assert scale['min'] == -15.0
    assert scale['max'] == -5.0
    assert len(scale['colors']) == 6


def test_get_color_scale_large_range():
    """Test color scale with large data range."""
    from modules.globe_data_processor import get_color_scale
    
    scale = get_color_scale('precipitation', 0.0, 1000.0)
    
    assert scale['min'] == 0.0
    assert scale['max'] == 1000.0
    assert len(scale['colors']) == 3


def test_get_color_scale_single_value():
    """Test color scale where min equals max."""
    from modules.globe_data_processor import get_color_scale
    
    scale = get_color_scale('temperature', 288.0, 288.0)
    
    assert scale['min'] == 288.0
    assert scale['max'] == 288.0
    # Should still return valid color scale structure
    assert len(scale['colors']) > 0
    assert len(scale['stops']) > 0


def test_get_color_scale_all_layer_types():
    """Test that all three layer types produce valid scales."""
    from modules.globe_data_processor import get_color_scale
    
    layer_types = ['temperature', 'aerosol', 'precipitation']
    
    for layer_type in layer_types:
        scale = get_color_scale(layer_type, 0.0, 100.0)
        
        # All should have required fields
        assert 'min' in scale
        assert 'max' in scale
        assert 'colors' in scale
        assert 'stops' in scale
        
        # Colors and stops should match in length
        assert len(scale['colors']) == len(scale['stops'])
        
        # Stops should be normalized 0-1
        assert scale['stops'][0] == 0.0
        assert scale['stops'][-1] == 1.0
        
        # All stops should be in ascending order
        for i in range(len(scale['stops']) - 1):
            assert scale['stops'][i] < scale['stops'][i + 1]


def test_get_color_scale_hex_format():
    """Test that all colors are in uppercase hex format."""
    from modules.globe_data_processor import get_color_scale
    
    scale = get_color_scale('temperature', 0.0, 100.0)
    
    for color in scale['colors']:
        # Check hex format
        assert color.startswith('#')
        assert len(color) == 7
        # Check uppercase
        assert color == color.upper()
        # Check valid hex
        int(color[1:], 16)  # Should not raise ValueError
