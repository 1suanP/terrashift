"""
Configuration routes - datasets, variables, regions, presets
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

# Import existing configuration
import config

router = APIRouter()


class DatasetInfo(BaseModel):
    """Dataset information"""
    key: str
    title: str
    description: str
    short_name: str
    start_date: str
    end_date: str


class VariableInfo(BaseModel):
    """Variable information"""
    variable_id: str
    long_name: str
    short_description: str
    plain_language: str
    units: str
    trend_direction_hint: str
    dataset_key: str


class RegionInfo(BaseModel):
    """Preset region information"""
    name: str
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


class DemoPresetInfo(BaseModel):
    """Demo preset information"""
    name: str
    description: str
    expected_insight: str
    dataset_key: str
    variable_id: str
    region_name: str
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    time_range_start: str
    time_range_end: str
    use_anomalies: bool


@router.get("/datasets", response_model=List[DatasetInfo])
async def get_datasets():
    """
    Get list of available datasets
    
    Returns:
        List of dataset information
    """
    try:
        datasets = []
        for key, dataset in config.DATASETS.items():
            period = config.dataset_period(key)
            datasets.append(DatasetInfo(
                key=key,
                title=dataset.title,
                description=dataset.description,
                short_name=dataset.short_name,
                start_date=period[0].isoformat(),
                end_date=period[1].isoformat()
            ))
        return datasets
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/variables/{dataset_key}", response_model=List[VariableInfo])
async def get_variables(dataset_key: str):
    """
    Get list of variables for a specific dataset
    
    Args:
        dataset_key: Dataset identifier
        
    Returns:
        List of variable information
    """
    try:
        if dataset_key not in config.DATASETS:
            raise HTTPException(status_code=404, detail=f"Dataset '{dataset_key}' not found")
        
        variables = []
        for var_key, var in config.VARIABLES.items():
            if var.dataset_key == dataset_key:
                variables.append(VariableInfo(
                    variable_id=var.variable_id,
                    long_name=var.long_name,
                    short_description=var.short_description,
                    plain_language=var.plain_language,
                    units=var.units,
                    trend_direction_hint=var.trend_direction_hint,
                    dataset_key=var.dataset_key
                ))
        return variables
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/variables", response_model=List[VariableInfo])
async def get_all_variables():
    """
    Get all available variables across all datasets
    
    Returns:
        List of all variable information
    """
    try:
        variables = []
        for var in config.VARIABLES.values():
            variables.append(VariableInfo(
                variable_id=var.variable_id,
                long_name=var.long_name,
                short_description=var.short_description,
                plain_language=var.plain_language,
                units=var.units,
                trend_direction_hint=var.trend_direction_hint,
                dataset_key=var.dataset_key
            ))
        return variables
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/regions", response_model=Dict[str, RegionInfo])
async def get_regions():
    """
    Get preset regions
    
    Returns:
        Dictionary of region name to region bounds
    """
    try:
        regions = {}
        for name, bbox in config.PRESET_REGIONS.items():
            regions[name] = RegionInfo(
                name=name,
                min_lat=bbox.min_lat,
                max_lat=bbox.max_lat,
                min_lon=bbox.min_lon,
                max_lon=bbox.max_lon
            )
        return regions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/presets", response_model=List[DemoPresetInfo])
async def get_demo_presets():
    """
    Get demo presets for quick examples
    
    Returns:
        List of demo preset configurations
    """
    try:
        presets = []
        for preset in config.DEMO_PRESETS:
            # DemoPreset stores bounds, not a name; recover the preset region's name.
            region_name = next(
                (name for name, box in config.PRESET_REGIONS.items() if box == preset.bounds),
                "Selected region",
            )
            presets.append(DemoPresetInfo(
                name=preset.name,
                description=preset.description,
                expected_insight=preset.expected_insight,
                dataset_key=preset.dataset_key,
                variable_id=preset.variable_id,
                region_name=region_name,
                min_lat=preset.bounds.min_lat,
                max_lat=preset.bounds.max_lat,
                min_lon=preset.bounds.min_lon,
                max_lon=preset.bounds.max_lon,
                time_range_start=preset.time_range.start,
                time_range_end=preset.time_range.end,
                use_anomalies=preset.use_anomalies
            ))
        return presets
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/environments")
async def get_environments():
    """
    Get environment categories for guided mode
    
    Returns:
        Dictionary of environment keys to display names
    """
    try:
        return config.ENVIRONMENTS
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/guided-flow/{environment}")
async def get_guided_flow_variables(environment: str):
    """
    Get variable cards for guided mode by environment
    
    Args:
        environment: Environment category key
        
    Returns:
        List of variable cards for the environment
    """
    try:
        if environment not in config.GUIDED_FLOW:
            raise HTTPException(status_code=404, detail=f"Environment '{environment}' not found")
        
        # GUIDED_FLOW maps an environment to a list of "dataset/variable" keys.
        return [
            {
                "key": key,
                "name": config.VARIABLES[key].long_name,
                "description": config.VARIABLES[key].short_description,
                "dataset_key": config.VARIABLES[key].dataset_key,
                "variable_id": config.VARIABLES[key].variable_id
            }
            for key in config.GUIDED_FLOW[environment]
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
