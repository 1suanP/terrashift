"""
Data routes - search and load NASA data
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

# Import existing modules
from modules import data_discovery, data_access
from modules.errors import DataDiscoveryError, DataAccessError
from modules.models import BoundingBox, TimeRange

router = APIRouter()


class SearchRequest(BaseModel):
    """Request for searching NASA granules"""
    dataset_short_name: str
    time_range_start: str
    time_range_end: str
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


class SearchResponse(BaseModel):
    """Response with search results"""
    granule_count: int
    opendap_urls: List[str]
    message: str


class LoadRequest(BaseModel):
    """Request for loading data"""
    opendap_urls: List[str]
    variable_id: str
    time_range_start: str
    time_range_end: str
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


class LoadResponse(BaseModel):
    """Response with loaded data summary"""
    success: bool
    points_count: int
    time_steps: int
    message: str


@router.post("/search", response_model=SearchResponse)
async def search_granules(request: SearchRequest):
    """
    Search for NASA data granules
    
    Args:
        request: Search parameters (dataset, time range, bounding box)
        
    Returns:
        SearchResponse with granule count and OPeNDAP URLs
    """
    try:
        # Authenticate first
        try:
            data_discovery.authenticate()
        except DataDiscoveryError as e:
            raise HTTPException(
                status_code=401,
                detail=f"Authentication failed: {str(e)}"
            )
        
        # Create bounding box and time range
        bbox = BoundingBox(
            min_lat=request.min_lat,
            max_lat=request.max_lat,
            min_lon=request.min_lon,
            max_lon=request.max_lon
        )
        
        time_range = TimeRange(
            start=request.time_range_start,
            end=request.time_range_end
        )
        
        # Search for granules
        granules = data_discovery.search_granules(
            short_name=request.dataset_short_name,
            temporal=(time_range.start, time_range.end),
            bounding_box=bbox.to_cmr_tuple()
        )
        
        if not granules:
            return SearchResponse(
                granule_count=0,
                opendap_urls=[],
                message=f"No data found for {request.dataset_short_name} in specified region and time period"
            )
        
        # Extract OPeNDAP URLs
        opendap_urls = data_discovery.get_opendap_urls(granules)
        
        return SearchResponse(
            granule_count=len(granules),
            opendap_urls=opendap_urls,
            message=f"Found {len(granules)} granules with {len(opendap_urls)} OPeNDAP URLs"
        )
        
    except DataDiscoveryError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@router.post("/load", response_model=LoadResponse)
async def load_data(request: LoadRequest):
    """
    Load data from OPeNDAP URLs and compute regional average
    
    Args:
        request: Load parameters (URLs, variable, time range, bounding box)
        
    Returns:
        LoadResponse with data summary
    """
    try:
        # Create models
        bbox = BoundingBox(
            min_lat=request.min_lat,
            max_lat=request.max_lat,
            min_lon=request.min_lon,
            max_lon=request.max_lon
        )
        
        time_range = TimeRange(
            start=request.time_range_start,
            end=request.time_range_end
        )
        
        # Load granules
        dataset = data_access.load_granules(
            opendap_urls=request.opendap_urls,
            variable_id=request.variable_id,
            time_range=time_range,
            bounding_box=bbox
        )
        
        # This endpoint just validates loading works
        # Actual regional average computation happens in analysis endpoint
        time_steps = len(dataset.time) if hasattr(dataset, 'time') else 0
        
        return LoadResponse(
            success=True,
            points_count=0,  # Would need to compute grid size
            time_steps=time_steps,
            message=f"Successfully loaded data with {time_steps} time steps"
        )
        
    except DataAccessError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Load error: {str(e)}")


@router.get("/health")
async def data_health():
    """Health check for data services"""
    return {"status": "ok", "service": "data"}
