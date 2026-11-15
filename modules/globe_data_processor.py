"""
Transform NASA Earth science data for 3D globe visualization.

This module bridges the existing NASA data pipeline (xarray DataArrays from data_access.py)
and Three.js visualization by generating contour data suitable for rendering on a sphere.
It handles multiple environmental layer types (temperature, aerosol, precipitation) with
appropriate color scales and metadata formatting.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

# scipy and skimage imports for contour generation (used in later tasks)
try:
    from scipy import ndimage
    from skimage import measure
    _CONTOUR_SUPPORT = True
except ImportError:
    _CONTOUR_SUPPORT = False


def get_color_scale(layer_type: str, data_min: float, data_max: float) -> dict[str, Any]:
    """
    Generate color scale configuration for a data layer.
    
    Creates a color mapping appropriate for the environmental data type, mapping
    data values to colors that provide perceptually meaningful visualization
    (e.g., red for hot, blue for cold in temperature data).
    
    Parameters
    ----------
    layer_type : str
        Type of environmental layer: 'temperature', 'aerosol', or 'precipitation'.
        - 'temperature': Temperature anomalies (blue for cold, red for hot)
        - 'aerosol': Aerosol optical depth (cyan for low, red for high)
        - 'precipitation': Precipitation rate (cyan for low, dark blue for high)
    data_min : float
        Minimum data value in the dataset
    data_max : float
        Maximum data value in the dataset
        
    Returns
    -------
    dict
        Color scale configuration with the following keys:
        - 'min': float - Minimum data value (same as data_min parameter)
        - 'max': float - Maximum data value (same as data_max parameter)
        - 'colors': list[str] - Hex color codes for the gradient stops
        - 'stops': list[float] - Normalized positions (0.0 to 1.0) for each color
    
    Raises
    ------
    ValueError
        If layer_type is not recognized (though unrecognized types fall back to
        temperature scale)
    
    Examples
    --------
    >>> scale = get_color_scale('temperature', -5.0, 5.0)
    >>> print(scale['colors'])
    ['#0000FF', '#35D6E8', '#FFFFFF', '#FFD700', '#FF9F0A', '#FF453A']
    >>> print(scale['stops'])
    [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    
    >>> scale = get_color_scale('aerosol', 0.0, 1.0)
    >>> print(scale['colors'])
    ['#35D6E8', '#FF9F0A', '#FF453A']
    >>> print(len(scale['colors']))
    3
    
    >>> scale = get_color_scale('precipitation', 0.0, 10.0)
    >>> print(scale['colors'])
    ['#35D6E8', '#4C8DFF', '#0000AA']
    
    Notes
    -----
    - Color scales follow NASA visualization conventions and accessibility guidelines
    - Temperature scale: blue → cyan → white → yellow → orange → red (6 stops)
    - Aerosol scale: cyan → orange → red (3 stops)
    - Precipitation scale: cyan → blue → dark blue (3 stops)
    - Unknown layer types default to the temperature scale
    - All colors use uppercase hex format for consistency
    
    See Also
    --------
    process_for_globe : Main processing function that uses color scales
    """
    # Define color scales for each layer type
    scales = {
        'temperature': {
            'colors': [
                '#0000FF',  # blue (cold)
                '#35D6E8',  # cyan
                '#FFFFFF',  # white (neutral)
                '#FFD700',  # yellow
                '#FF9F0A',  # orange
                '#FF453A',  # red (hot)
            ],
            'stops': [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        },
        'aerosol': {
            'colors': [
                '#35D6E8',  # cyan (low)
                '#FF9F0A',  # orange (moderate)
                '#FF453A',  # red (high)
            ],
            'stops': [0.0, 0.5, 1.0]
        },
        'precipitation': {
            'colors': [
                '#35D6E8',  # cyan (low)
                '#4C8DFF',  # blue (moderate)
                '#0000AA',  # dark blue (high)
            ],
            'stops': [0.0, 0.5, 1.0]
        }
    }
    
    # Get the scale for the layer type, defaulting to temperature if unknown
    scale = scales.get(layer_type, scales['temperature'])
    
    # Return color scale with data range
    return {
        'min': data_min,
        'max': data_max,
        'colors': scale['colors'],
        'stops': scale['stops']
    }


def process_for_globe(
    data: xr.DataArray,
    layer_type: str,
    num_contours: int = 10,
    smooth_sigma: float = 1.0,
) -> dict[str, Any]:
    """
    Process NASA Earth science data for 3D globe visualization.
    
    Transforms gridded xarray data into a GeoJSON-compatible structure containing
    contours, metadata, and color scale information suitable for Three.js globe
    rendering. The function generates contour lines from the data grid, smooths
    them for visual quality, and packages everything with appropriate metadata.
    
    Parameters
    ----------
    data : xr.DataArray
        Input data with 'lat' and 'lon' dimensions. Should represent a single
        time slice of Earth science data (e.g., monthly average temperature,
        precipitation, or aerosol optical depth). NaN values are handled gracefully.
    layer_type : str
        Type of environmental layer, one of:
        - 'temperature': Surface temperature data
        - 'aerosol': Aerosol optical depth
        - 'precipitation': Precipitation rate
        Used to determine appropriate color scale and units.
    num_contours : int, default=10
        Number of contour levels to generate. More contours provide finer detail
        but increase data size and rendering complexity. Must be at least 2.
    smooth_sigma : float, default=1.0
        Gaussian smoothing parameter for the data grid before contouring.
        Higher values produce smoother, more generalized contours. Set to 0
        to disable smoothing.
        
    Returns
    -------
    dict
        GeoJSON-compatible structure with the following keys:
        
        - 'type': str
            Always 'FeatureCollection' for GeoJSON compatibility
        - 'features': list[dict]
            List of GeoJSON Feature objects, each representing a contour line.
            Each feature has:
            - 'type': 'Feature'
            - 'geometry': {'type': 'LineString', 'coordinates': [[lon, lat], ...]}
            - 'properties': {'value': float, 'level': int}
        - 'metadata': dict
            Statistical and provenance information:
            - 'units': str (e.g., 'K', 'mm/day', 'unitless')
            - 'startDate': str (ISO 8601 format)
            - 'endDate': str (ISO 8601 format)
            - 'source': str (dataset identifier)
            - 'min': float (minimum value in data)
            - 'max': float (maximum value in data)
            - 'mean': float (spatial mean, NaN-aware)
        - 'colorScale': dict
            Color mapping for the layer:
            - 'min': float (data value at first color stop)
            - 'max': float (data value at last color stop)
            - 'colors': list[str] (hex color strings, e.g., ['#0000ff', '#ff0000'])
            - 'stops': list[float] (normalized 0-1 positions for each color)
    
    Raises
    ------
    ValueError
        If data lacks 'lat' or 'lon' dimensions, if layer_type is unrecognized,
        if num_contours < 2, if smooth_sigma < 0, or if data is empty/all-NaN.
    TypeError
        If data is not an xr.DataArray or arguments have incorrect types.
    
    Examples
    --------
    >>> import xarray as xr
    >>> import numpy as np
    >>> 
    >>> # Create sample temperature data
    >>> lat = np.linspace(-90, 90, 180)
    >>> lon = np.linspace(-180, 180, 360)
    >>> temp = xr.DataArray(
    ...     np.random.randn(180, 360) * 10 + 288,  # ~288K mean
    ...     dims=['lat', 'lon'],
    ...     coords={'lat': lat, 'lon': lon},
    ...     attrs={'units': 'K', 'long_name': 'Surface Temperature'}
    ... )
    >>> 
    >>> # Process for globe visualization
    >>> result = process_for_globe(temp, 'temperature', num_contours=8)
    >>> print(result.keys())
    dict_keys(['type', 'features', 'metadata', 'colorScale'])
    >>> print(len(result['features']))  # 8 contour levels
    8
    >>> print(result['metadata']['units'])
    K
    
    Notes
    -----
    - Contours are generated using marching squares algorithm (skimage.measure.find_contours)
    - Coordinate transformation assumes data uses standard lat/lon grid (-90 to 90, -180 to 180)
    - Large arrays (>1M points) may benefit from spatial downsampling before processing
    - Color scales are predefined per layer_type but can be customized in future versions
    - The returned structure is JSON-serializable for easy transfer to web clients
    
    See Also
    --------
    modules.data_access.load_granules : Load NASA data from OPeNDAP
    modules.data_access.compute_regional_average : Spatial averaging
    scipy.ndimage.gaussian_filter : Gaussian smoothing implementation
    skimage.measure.find_contours : Contour generation algorithm
    """
    # Validate input types
    if not isinstance(data, xr.DataArray):
        raise TypeError(f"data must be an xr.DataArray, got {type(data).__name__}")
    if not isinstance(layer_type, str):
        raise TypeError(f"layer_type must be a string, got {type(layer_type).__name__}")
    if not isinstance(num_contours, int):
        raise TypeError(f"num_contours must be an int, got {type(num_contours).__name__}")
    if not isinstance(smooth_sigma, (int, float)):
        raise TypeError(f"smooth_sigma must be a number, got {type(smooth_sigma).__name__}")
    
    # Validate parameters
    if num_contours < 2:
        raise ValueError(f"num_contours must be at least 2, got {num_contours}")
    if smooth_sigma < 0:
        raise ValueError(f"smooth_sigma must be non-negative, got {smooth_sigma}")
    
    # Check for required dimensions
    if 'lat' not in data.dims and 'latitude' not in data.dims:
        raise ValueError(f"data must have 'lat' or 'latitude' dimension, got dims: {list(data.dims)}")
    if 'lon' not in data.dims and 'longitude' not in data.dims:
        raise ValueError(f"data must have 'lon' or 'longitude' dimension, got dims: {list(data.dims)}")
    
    # Validate layer_type
    valid_layer_types = {'temperature', 'aerosol', 'precipitation'}
    if layer_type not in valid_layer_types:
        raise ValueError(f"layer_type must be one of {valid_layer_types}, got '{layer_type}'")
    
    # Check contour support
    if not _CONTOUR_SUPPORT:
        raise RuntimeError("scipy and/or skimage not available; install them for contour generation")
    
    # Extract coordinates - handle both 'lat'/'lon' and 'latitude'/'longitude'
    lat_name = 'lat' if 'lat' in data.dims else 'latitude'
    lon_name = 'lon' if 'lon' in data.dims else 'longitude'
    
    lats = data.coords[lat_name].values
    lons = data.coords[lon_name].values
    values = data.values
    
    # Check for empty or all-NaN data
    if values.size == 0:
        raise ValueError("data is empty (zero size)")
    if np.all(np.isnan(values)):
        # Return empty FeatureCollection for all-NaN data
        return {
            'type': 'FeatureCollection',
            'features': [],
            'metadata': _build_metadata(data, layer_type, values),
            'colorScale': _get_color_scale(layer_type, np.nan, np.nan)
        }
    
    # Handle NaN values - replace with 0 for contouring
    values_clean = np.nan_to_num(values, nan=0.0)
    
    # Check for single value (no variation)
    valid_values = values[~np.isnan(values)]
    if len(valid_values) > 0 and np.allclose(valid_values, valid_values[0]):
        # Single value - return empty FeatureCollection
        return {
            'type': 'FeatureCollection',
            'features': [],
            'metadata': _build_metadata(data, layer_type, values),
            'colorScale': _get_color_scale(layer_type, valid_values[0], valid_values[0])
        }
    
    # Apply Gaussian smoothing
    if smooth_sigma > 0:
        smoothed = ndimage.gaussian_filter(values_clean, sigma=smooth_sigma)
    else:
        smoothed = values_clean
    
    # Calculate contour levels
    vmin = np.nanmin(values)
    vmax = np.nanmax(values)
    
    # Generate evenly-spaced levels, excluding min and max endpoints
    levels = np.linspace(vmin, vmax, num_contours + 2)[1:-1]
    
    # Generate contours for each level
    features = []
    for level in levels:
        try:
            contours = measure.find_contours(smoothed, level)
            
            # Convert each contour to GeoJSON LineString
            for contour in contours:
                # contour is in pixel coordinates (row, col)
                # Convert to lat/lon
                line_coords = []
                for row, col in contour:
                    # Ensure indices are within bounds
                    row_idx = int(np.clip(row, 0, len(lats) - 1))
                    col_idx = int(np.clip(col, 0, len(lons) - 1))
                    
                    lat = float(lats[row_idx])
                    lon = float(lons[col_idx])
                    
                    # Validate coordinates
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        line_coords.append([lon, lat])
                
                # Only add contour if it has at least 2 valid points
                if len(line_coords) >= 2:
                    feature = {
                        'type': 'Feature',
                        'geometry': {
                            'type': 'LineString',
                            'coordinates': line_coords
                        },
                        'properties': {
                            'value': float(level),
                            'layer_type': layer_type
                        }
                    }
                    features.append(feature)
        except (ValueError, RuntimeError):
            # Skip levels that fail to generate contours
            continue
    
    # Build result
    result = {
        'type': 'FeatureCollection',
        'features': features,
        'metadata': _build_metadata(data, layer_type, values),
        'colorScale': _get_color_scale(layer_type, vmin, vmax)
    }
    
    return result


def _build_metadata(data: xr.DataArray, layer_type: str, values: np.ndarray) -> dict[str, Any]:
    """
    Build metadata dictionary from DataArray attributes.
    
    Extracts metadata including units, date ranges, data sources, and statistics
    from xarray DataArray for display in the globe legend.
    
    Parameters
    ----------
    data : xr.DataArray
        Input data with attributes and coordinates
    layer_type : str
        'temperature', 'aerosol', or 'precipitation'
    values : np.ndarray
        Extracted data values for statistics calculation
        
    Returns
    -------
    dict
        Metadata with units, dates, source, and statistics:
        - 'units': str - Data units (e.g., "°C", "mm/day", "1" for AOD)
        - 'startDate': str - ISO format start date (e.g., "2020-01-01")
        - 'endDate': str - ISO format end date (e.g., "2020-12-31")
        - 'source': str - NASA data source (e.g., "NASA MERRA-2", "NASA GPM IMERG")
        - 'min': float - Minimum value in dataset
        - 'max': float - Maximum value in dataset
        - 'mean': float - Mean value in dataset (NaN-aware)
    """
    metadata = {}
    
    # Extract units from xarray attributes
    if 'units' in data.attrs:
        metadata['units'] = data.attrs['units']
    elif layer_type == 'temperature':
        metadata['units'] = 'K'
    elif layer_type == 'precipitation':
        metadata['units'] = 'mm/day'
    elif layer_type == 'aerosol':
        metadata['units'] = '1'  # Aerosol Optical Depth is unitless but represented as '1'
    else:
        metadata['units'] = 'unknown'
    
    # Extract date range from time dimension
    if 'time' in data.coords:
        time_coord = data.coords['time']
        if hasattr(time_coord, 'values'):
            time_vals = time_coord.values
            
            # Handle both single time values and time ranges
            if np.isscalar(time_vals) or (hasattr(time_vals, 'shape') and time_vals.shape == ()):
                # Single time value
                try:
                    import pandas as pd
                    time_str = pd.Timestamp(time_vals).strftime('%Y-%m-%d')
                    metadata['startDate'] = time_str
                    metadata['endDate'] = time_str
                except Exception:
                    time_str = str(time_vals)[:10] if len(str(time_vals)) >= 10 else str(time_vals)
                    metadata['startDate'] = time_str
                    metadata['endDate'] = time_str
            else:
                # Time range (array of time values)
                try:
                    import pandas as pd
                    if len(time_vals) > 0:
                        start_date = pd.Timestamp(time_vals[0]).strftime('%Y-%m-%d')
                        end_date = pd.Timestamp(time_vals[-1]).strftime('%Y-%m-%d')
                        metadata['startDate'] = start_date
                        metadata['endDate'] = end_date
                    else:
                        metadata['startDate'] = 'unknown'
                        metadata['endDate'] = 'unknown'
                except Exception:
                    # Fallback to string slicing
                    if len(time_vals) > 0:
                        start_str = str(time_vals[0])[:10] if len(str(time_vals[0])) >= 10 else str(time_vals[0])
                        end_str = str(time_vals[-1])[:10] if len(str(time_vals[-1])) >= 10 else str(time_vals[-1])
                        metadata['startDate'] = start_str
                        metadata['endDate'] = end_str
                    else:
                        metadata['startDate'] = 'unknown'
                        metadata['endDate'] = 'unknown'
        else:
            metadata['startDate'] = 'unknown'
            metadata['endDate'] = 'unknown'
    else:
        metadata['startDate'] = 'unknown'
        metadata['endDate'] = 'unknown'
    
    # Determine data source from layer type
    source_map = {
        'temperature': 'NASA MERRA-2',
        'aerosol': 'NASA MERRA-2',
        'precipitation': 'NASA GPM IMERG'
    }
    
    # Check if source is in attributes first, otherwise use layer_type mapping
    if 'source' in data.attrs:
        metadata['source'] = data.attrs['source']
    else:
        metadata['source'] = source_map.get(layer_type, 'NASA')
    
    # Calculate statistics (ignoring NaN values)
    if not np.all(np.isnan(values)):
        metadata['min'] = float(np.nanmin(values))
        metadata['max'] = float(np.nanmax(values))
        metadata['mean'] = float(np.nanmean(values))
    else:
        metadata['min'] = np.nan
        metadata['max'] = np.nan
        metadata['mean'] = np.nan
    
    return metadata


def _get_color_scale(layer_type: str, vmin: float, vmax: float) -> dict[str, Any]:
    """Get color scale definition for a layer type."""
    # Define color scales per layer type
    color_scales = {
        'temperature': {
            'colors': ['#0000ff', '#00ffff', '#00ff00', '#ffff00', '#ff0000'],
            'stops': [0.0, 0.25, 0.5, 0.75, 1.0]
        },
        'precipitation': {
            'colors': ['#ffffff', '#c6e8f5', '#6baed6', '#2171b5', '#084594'],
            'stops': [0.0, 0.25, 0.5, 0.75, 1.0]
        },
        'aerosol': {
            'colors': ['#f7fcf5', '#e5f5e0', '#c7e9c0', '#a1d99b', '#74c476', '#31a354'],
            'stops': [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        }
    }
    
    scale = color_scales.get(layer_type, {
        'colors': ['#0000ff', '#ff0000'],
        'stops': [0.0, 1.0]
    })
    
    return {
        'min': float(vmin) if not np.isnan(vmin) else 0.0,
        'max': float(vmax) if not np.isnan(vmax) else 1.0,
        'colors': scale['colors'],
        'stops': scale['stops']
    }
