"""
Integration test for metadata extraction in process_for_globe.

This test validates that the metadata extraction is properly integrated
into the globe data processing pipeline and produces the expected output structure.
"""
import numpy as np
import pandas as pd
import pytest
import xarray as xr

from modules.globe_data_processor import process_for_globe


class TestMetadataIntegration:
    """Integration tests for metadata in globe processing pipeline."""
    
    def test_process_for_globe_includes_metadata(self):
        """Test that process_for_globe output includes metadata."""
        # Create sample data
        data = xr.DataArray(
            np.random.randn(20, 40) * 10 + 288,
            dims=['lat', 'lon'],
            coords={
                'lat': np.linspace(-90, 90, 20),
                'lon': np.linspace(-180, 180, 40),
                'time': pd.Timestamp('2020-06-15')
            },
            attrs={'units': 'K'}
        )
        
        result = process_for_globe(data, 'temperature', num_contours=5)
        
        # Verify top-level structure
        assert 'type' in result
        assert 'features' in result
        assert 'metadata' in result
        assert 'colorScale' in result
        
        # Verify metadata structure
        metadata = result['metadata']
        assert 'units' in metadata
        assert 'startDate' in metadata
        assert 'endDate' in metadata
        assert 'source' in metadata
        assert 'min' in metadata
        assert 'max' in metadata
        assert 'mean' in metadata
    
    def test_temperature_layer_metadata(self):
        """Test metadata for temperature layer."""
        data = xr.DataArray(
            np.random.randn(20, 40) * 10 + 288,
            dims=['lat', 'lon'],
            coords={
                'lat': np.linspace(-90, 90, 20),
                'lon': np.linspace(-180, 180, 40),
                'time': pd.Timestamp('2020-06-15')
            },
            attrs={'units': 'K'}
        )
        
        result = process_for_globe(data, 'temperature')
        metadata = result['metadata']
        
        assert metadata['units'] == 'K'
        assert metadata['source'] == 'NASA MERRA-2'
        assert metadata['startDate'] == '2020-06-15'
        assert metadata['endDate'] == '2020-06-15'
        assert isinstance(metadata['min'], float)
        assert isinstance(metadata['max'], float)
        assert isinstance(metadata['mean'], float)
    
    def test_precipitation_layer_metadata(self):
        """Test metadata for precipitation layer."""
        data = xr.DataArray(
            np.random.rand(20, 40) * 20,
            dims=['lat', 'lon'],
            coords={
                'lat': np.linspace(-90, 90, 20),
                'lon': np.linspace(-180, 180, 40),
                'time': pd.Timestamp('2021-03-10')
            }
        )
        
        result = process_for_globe(data, 'precipitation')
        metadata = result['metadata']
        
        assert metadata['units'] == 'mm/day'
        assert metadata['source'] == 'NASA GPM IMERG'
        assert metadata['startDate'] == '2021-03-10'
    
    def test_aerosol_layer_metadata(self):
        """Test metadata for aerosol layer."""
        data = xr.DataArray(
            np.random.rand(20, 40) * 0.5,
            dims=['lat', 'lon'],
            coords={
                'lat': np.linspace(-90, 90, 20),
                'lon': np.linspace(-180, 180, 40),
                'time': pd.Timestamp('2019-08-22')
            }
        )
        
        result = process_for_globe(data, 'aerosol')
        metadata = result['metadata']
        
        assert metadata['units'] == '1'  # Unitless AOD
        assert metadata['source'] == 'NASA MERRA-2'
        assert metadata['startDate'] == '2019-08-22'
    
    def test_metadata_statistics_accuracy(self):
        """Test that statistics are calculated accurately."""
        # Create data with known values
        values = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
        data = xr.DataArray(
            values,
            dims=['lat', 'lon'],
            coords={
                'lat': [10, 20, 30],
                'lon': [100, 110, 120],
                'time': pd.Timestamp('2020-01-01')
            }
        )
        
        result = process_for_globe(data, 'temperature', num_contours=3)
        metadata = result['metadata']
        
        assert metadata['min'] == 1.0
        assert metadata['max'] == 9.0
        assert metadata['mean'] == 5.0
    
    def test_color_scale_uses_metadata_min_max(self):
        """Test that colorScale uses the same min/max as metadata."""
        data = xr.DataArray(
            np.random.randn(20, 40) * 10 + 288,
            dims=['lat', 'lon'],
            coords={
                'lat': np.linspace(-90, 90, 20),
                'lon': np.linspace(-180, 180, 40)
            }
        )
        
        result = process_for_globe(data, 'temperature')
        
        # Color scale should use the same min/max as statistics
        assert abs(result['colorScale']['min'] - result['metadata']['min']) < 0.001
        assert abs(result['colorScale']['max'] - result['metadata']['max']) < 0.001
    
    def test_metadata_with_custom_source_attribute(self):
        """Test that custom source attribute overrides default."""
        data = xr.DataArray(
            np.random.randn(20, 40),
            dims=['lat', 'lon'],
            coords={
                'lat': np.linspace(-90, 90, 20),
                'lon': np.linspace(-180, 180, 40)
            },
            attrs={'source': 'Custom Climate Model v2.0'}
        )
        
        result = process_for_globe(data, 'temperature')
        metadata = result['metadata']
        
        assert metadata['source'] == 'Custom Climate Model v2.0'
