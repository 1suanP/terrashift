"""
Unit tests for metadata extraction in globe_data_processor.

Tests the _build_metadata function to ensure it correctly extracts units, 
date ranges, data sources, and statistics from xarray DataArrays.
"""
import numpy as np
import pandas as pd
import pytest
import xarray as xr

from modules.globe_data_processor import _build_metadata


class TestMetadataExtraction:
    """Test suite for metadata extraction functionality."""
    
    def test_extract_units_from_attributes(self):
        """Test that units are extracted from xarray attributes."""
        # Create data with units attribute
        data = xr.DataArray(
            np.random.randn(10, 10),
            dims=['lat', 'lon'],
            coords={'lat': np.linspace(-90, 90, 10), 'lon': np.linspace(-180, 180, 10)},
            attrs={'units': 'K'}
        )
        
        metadata = _build_metadata(data, 'temperature', data.values)
        
        assert metadata['units'] == 'K'
    
    def test_default_units_for_temperature(self):
        """Test that temperature defaults to 'K' when units not in attributes."""
        data = xr.DataArray(
            np.random.randn(10, 10),
            dims=['lat', 'lon'],
            coords={'lat': np.linspace(-90, 90, 10), 'lon': np.linspace(-180, 180, 10)}
        )
        
        metadata = _build_metadata(data, 'temperature', data.values)
        
        assert metadata['units'] == 'K'
    
    def test_default_units_for_precipitation(self):
        """Test that precipitation defaults to 'mm/day' when units not in attributes."""
        data = xr.DataArray(
            np.random.randn(10, 10),
            dims=['lat', 'lon'],
            coords={'lat': np.linspace(-90, 90, 10), 'lon': np.linspace(-180, 180, 10)}
        )
        
        metadata = _build_metadata(data, 'precipitation', data.values)
        
        assert metadata['units'] == 'mm/day'
    
    def test_default_units_for_aerosol(self):
        """Test that aerosol defaults to '1' (unitless) when units not in attributes."""
        data = xr.DataArray(
            np.random.randn(10, 10),
            dims=['lat', 'lon'],
            coords={'lat': np.linspace(-90, 90, 10), 'lon': np.linspace(-180, 180, 10)}
        )
        
        metadata = _build_metadata(data, 'aerosol', data.values)
        
        assert metadata['units'] == '1'
    
    def test_extract_single_date(self):
        """Test extracting date from single time coordinate."""
        time = pd.Timestamp('2020-01-15')
        data = xr.DataArray(
            np.random.randn(10, 10),
            dims=['lat', 'lon'],
            coords={
                'lat': np.linspace(-90, 90, 10),
                'lon': np.linspace(-180, 180, 10),
                'time': time
            },
            attrs={'units': 'K'}
        )
        
        metadata = _build_metadata(data, 'temperature', data.values)
        
        assert metadata['startDate'] == '2020-01-15'
        assert metadata['endDate'] == '2020-01-15'
    
    def test_extract_date_range(self):
        """Test extracting date range from time dimension with multiple values."""
        times = pd.date_range('2020-01-01', '2020-12-31', freq='ME')  # ME = Month End
        
        # Create a 3D array with time dimension
        data = xr.DataArray(
            np.random.randn(len(times), 10, 10),
            dims=['time', 'lat', 'lon'],
            coords={
                'time': times,
                'lat': np.linspace(-90, 90, 10),
                'lon': np.linspace(-180, 180, 10)
            },
            attrs={'units': 'K'}
        )
        
        # Test with the full time array (even though we'd typically use a time slice)
        metadata = _build_metadata(data, 'temperature', data.values[0])
        
        assert metadata['startDate'] == '2020-01-31'  # First month end
        assert metadata['endDate'] == '2020-12-31'
    
    def test_missing_time_coordinate(self):
        """Test handling of missing time coordinate."""
        data = xr.DataArray(
            np.random.randn(10, 10),
            dims=['lat', 'lon'],
            coords={'lat': np.linspace(-90, 90, 10), 'lon': np.linspace(-180, 180, 10)}
        )
        
        metadata = _build_metadata(data, 'temperature', data.values)
        
        assert metadata['startDate'] == 'unknown'
        assert metadata['endDate'] == 'unknown'
    
    def test_nasa_merra2_source_for_temperature(self):
        """Test that temperature data is correctly mapped to NASA MERRA-2 source."""
        data = xr.DataArray(
            np.random.randn(10, 10),
            dims=['lat', 'lon'],
            coords={'lat': np.linspace(-90, 90, 10), 'lon': np.linspace(-180, 180, 10)}
        )
        
        metadata = _build_metadata(data, 'temperature', data.values)
        
        assert metadata['source'] == 'NASA MERRA-2'
    
    def test_nasa_merra2_source_for_aerosol(self):
        """Test that aerosol data is correctly mapped to NASA MERRA-2 source."""
        data = xr.DataArray(
            np.random.randn(10, 10),
            dims=['lat', 'lon'],
            coords={'lat': np.linspace(-90, 90, 10), 'lon': np.linspace(-180, 180, 10)}
        )
        
        metadata = _build_metadata(data, 'aerosol', data.values)
        
        assert metadata['source'] == 'NASA MERRA-2'
    
    def test_nasa_gpm_imerg_source_for_precipitation(self):
        """Test that precipitation data is correctly mapped to NASA GPM IMERG source."""
        data = xr.DataArray(
            np.random.randn(10, 10),
            dims=['lat', 'lon'],
            coords={'lat': np.linspace(-90, 90, 10), 'lon': np.linspace(-180, 180, 10)}
        )
        
        metadata = _build_metadata(data, 'precipitation', data.values)
        
        assert metadata['source'] == 'NASA GPM IMERG'
    
    def test_source_from_attributes_overrides_default(self):
        """Test that source attribute in data overrides default layer_type mapping."""
        data = xr.DataArray(
            np.random.randn(10, 10),
            dims=['lat', 'lon'],
            coords={'lat': np.linspace(-90, 90, 10), 'lon': np.linspace(-180, 180, 10)},
            attrs={'source': 'Custom Data Source'}
        )
        
        metadata = _build_metadata(data, 'temperature', data.values)
        
        assert metadata['source'] == 'Custom Data Source'
    
    def test_statistics_calculation(self):
        """Test that min, max, and mean statistics are calculated correctly."""
        values = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
        data = xr.DataArray(
            values,
            dims=['lat', 'lon'],
            coords={'lat': [10, 20, 30], 'lon': [100, 110, 120]}
        )
        
        metadata = _build_metadata(data, 'temperature', values)
        
        assert metadata['min'] == 1.0
        assert metadata['max'] == 9.0
        assert metadata['mean'] == 5.0
    
    def test_statistics_with_nan_values(self):
        """Test that statistics correctly handle NaN values."""
        values = np.array([[1.0, np.nan, 3.0], [4.0, 5.0, np.nan], [7.0, 8.0, 9.0]])
        data = xr.DataArray(
            values,
            dims=['lat', 'lon'],
            coords={'lat': [10, 20, 30], 'lon': [100, 110, 120]}
        )
        
        metadata = _build_metadata(data, 'temperature', values)
        
        assert metadata['min'] == 1.0
        assert metadata['max'] == 9.0
        # Mean of [1, 3, 4, 5, 7, 8, 9] = 37/7 ≈ 5.29
        assert abs(metadata['mean'] - 5.285714285714286) < 0.0001
    
    def test_statistics_with_all_nan_values(self):
        """Test that statistics handle all-NaN arrays gracefully."""
        values = np.full((3, 3), np.nan)
        data = xr.DataArray(
            values,
            dims=['lat', 'lon'],
            coords={'lat': [10, 20, 30], 'lon': [100, 110, 120]}
        )
        
        metadata = _build_metadata(data, 'temperature', values)
        
        assert np.isnan(metadata['min'])
        assert np.isnan(metadata['max'])
        assert np.isnan(metadata['mean'])
    
    def test_metadata_structure_completeness(self):
        """Test that all required metadata fields are present."""
        data = xr.DataArray(
            np.random.randn(10, 10),
            dims=['lat', 'lon'],
            coords={
                'lat': np.linspace(-90, 90, 10),
                'lon': np.linspace(-180, 180, 10),
                'time': pd.Timestamp('2020-06-15')
            },
            attrs={'units': 'K'}
        )
        
        metadata = _build_metadata(data, 'temperature', data.values)
        
        # Check all required fields are present
        required_fields = ['units', 'startDate', 'endDate', 'source', 'min', 'max', 'mean']
        for field in required_fields:
            assert field in metadata, f"Missing required field: {field}"
    
    def test_date_format_is_iso_8601(self):
        """Test that dates are formatted in ISO 8601 format (YYYY-MM-DD)."""
        time = pd.Timestamp('2020-03-15')
        data = xr.DataArray(
            np.random.randn(10, 10),
            dims=['lat', 'lon'],
            coords={
                'lat': np.linspace(-90, 90, 10),
                'lon': np.linspace(-180, 180, 10),
                'time': time
            }
        )
        
        metadata = _build_metadata(data, 'temperature', data.values)
        
        # Check format is YYYY-MM-DD
        assert len(metadata['startDate']) == 10
        assert metadata['startDate'][4] == '-'
        assert metadata['startDate'][7] == '-'
        
        # Verify it's a valid date
        pd.Timestamp(metadata['startDate'])  # Should not raise
