"""
Analysis routes - run statistical trend analysis
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import uuid

# Import existing modules
from modules.pipeline import build_request, run_pipeline
from modules.models import AnalysisRequest, AnalysisResult, BoundingBox, TimeRange
from modules.errors import DataDiscoveryError, DataAccessError, InsufficientDataError
from modules import data_discovery

router = APIRouter()

# In-memory cache for analysis results (in production, use Redis)
analysis_cache: Dict[str, Any] = {}


class AnalysisRunRequest(BaseModel):
    """Request to run analysis"""
    dataset_key: str
    variable_id: str
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    time_range_start: str
    time_range_end: str
    use_anomalies: bool = False
    region_name: str = "Custom region"


class AnalysisRunResponse(BaseModel):
    """Response with analysis ID and, when complete, the full result.

    The result is included so clients need only one request. On serverless hosts
    a follow-up GET may reach a different instance that does not hold the cache.
    """
    analysis_id: str
    status: str
    message: str
    result: Optional["AnalysisResultResponse"] = None


class AnalysisStatus(BaseModel):
    """Status of an analysis"""
    analysis_id: str
    status: str  # "pending", "running", "complete", "error"
    progress: Optional[int] = None
    message: Optional[str] = None


class TrendResult(BaseModel):
    """Statistical trend results"""
    slope: float
    intercept: float
    r_value: float
    p_value: float
    std_err: float
    ci_lower: float
    ci_upper: float


class MannKendallResult(BaseModel):
    """Mann-Kendall test results"""
    trend: str
    h: bool
    p: float
    z: float
    tau: float
    s: float
    var_s: float


class TimeSeriesData(BaseModel):
    """Time series data"""
    timestamps: list
    values: list
    anomalies: Optional[list] = None
    is_anomaly: bool


class AnalysisResultResponse(BaseModel):
    """Complete analysis results"""
    analysis_id: str
    dataset_key: str
    variable_id: str
    variable_name: str
    units: str
    region_name: str
    time_range_start: str
    time_range_end: str
    n_points: int
    significance: str
    linear: TrendResult
    mann_kendall: MannKendallResult
    sens_slope_value: float
    interpretation: str
    time_series: TimeSeriesData


AnalysisRunResponse.model_rebuild()  # resolve the forward reference to AnalysisResultResponse


@router.post("/run", response_model=AnalysisRunResponse)
def run_analysis(request: AnalysisRunRequest, background_tasks: BackgroundTasks):
    # Sync def: FastAPI runs it in a worker thread so the slow NASA download
    # does not block other requests (datasets, variables, health).
    """
    Run full analysis pipeline
    
    Args:
        request: Analysis parameters
        background_tasks: FastAPI background tasks
        
    Returns:
        Analysis ID for tracking progress
    """
    try:
        # Generate unique analysis ID
        analysis_id = str(uuid.uuid4())
        
        # Create bounding box
        bbox = BoundingBox(
            min_lat=request.min_lat,
            max_lat=request.max_lat,
            min_lon=request.min_lon,
            max_lon=request.max_lon
        )
        
        # Build analysis request
        analysis_request = build_request(
            dataset_key=request.dataset_key,
            variable_id=request.variable_id,
            bounds=bbox,
            time_range=(request.time_range_start, request.time_range_end),
            use_anomalies=request.use_anomalies,
            region_name=request.region_name
        )
        
        # Mark as running
        analysis_cache[analysis_id] = {
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "request": request.dict()
        }
        
        # Run pipeline (this can take time, so we'll run synchronously for now)
        # In production, use Celery or background workers
        try:
            # Authenticate with NASA Earthdata first
            data_discovery.authenticate(persist=False)  # never write credentials to ~/.netrc
            
            result = run_pipeline(analysis_request)
            
            # Cache the result
            analysis_cache[analysis_id] = {
                "status": "complete",
                "started_at": analysis_cache[analysis_id]["started_at"],
                "completed_at": datetime.now().isoformat(),
                "request": request.dict(),
                "result": result
            }
            
            return AnalysisRunResponse(
                analysis_id=analysis_id,
                status="complete",
                message="Analysis completed successfully",
                result=_to_response(analysis_id, result),
            )
            
        except InsufficientDataError as e:
            analysis_cache[analysis_id]["status"] = "error"
            analysis_cache[analysis_id]["error"] = str(e)
            raise HTTPException(status_code=400, detail=str(e))
        except DataDiscoveryError as e:
            analysis_cache[analysis_id]["status"] = "error"
            analysis_cache[analysis_id]["error"] = str(e)
            raise HTTPException(status_code=404, detail=str(e))
        except DataAccessError as e:
            analysis_cache[analysis_id]["status"] = "error"
            analysis_cache[analysis_id]["error"] = str(e)
            raise HTTPException(status_code=500, detail=str(e))
            
    except HTTPException:
        raise  # keep the specific status (400 no data, 404 no granules, 500 access) set above
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


@router.get("/status/{analysis_id}", response_model=AnalysisStatus)
async def get_analysis_status(analysis_id: str):
    """
    Get status of an analysis
    
    Args:
        analysis_id: Analysis identifier
        
    Returns:
        Current status of the analysis
    """
    if analysis_id not in analysis_cache:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    cached = analysis_cache[analysis_id]
    
    return AnalysisStatus(
        analysis_id=analysis_id,
        status=cached["status"],
        message=cached.get("error") or "Analysis in progress"
    )


@router.get("/{analysis_id}", response_model=AnalysisResultResponse)
async def get_analysis_result(analysis_id: str):
    """
    Get complete analysis results
    
    Args:
        analysis_id: Analysis identifier
        
    Returns:
        Complete analysis results with trends and time series
    """
    if analysis_id not in analysis_cache:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    cached = analysis_cache[analysis_id]
    
    if cached["status"] == "error":
        raise HTTPException(status_code=400, detail=cached.get("error", "Analysis failed"))
    
    if cached["status"] != "complete":
        raise HTTPException(status_code=202, detail="Analysis still in progress")

    return _to_response(analysis_id, cached["result"])


def _to_response(analysis_id: str, result: AnalysisResult) -> AnalysisResultResponse:
    """Convert a pipeline result into the API response model."""
    series = result.time_series.series
    timestamps = [ts.isoformat() for ts in series.index]
    anomalies = result.time_series.anomalies

    # Convert to response model
    return AnalysisResultResponse(
        analysis_id=analysis_id,
        dataset_key=result.variable_meta.dataset_key,
        variable_id=result.variable_meta.variable_id,
        variable_name=result.variable_meta.long_name,
        units=result.variable_meta.units,
        region_name=result.region_name,
        time_range_start=timestamps[0] if timestamps else "",
        time_range_end=timestamps[-1] if timestamps else "",
        n_points=result.n_points,
        significance=result.significance,
        linear=TrendResult(
            slope=result.linear.slope,
            intercept=result.linear.intercept,
            r_value=result.linear.r_value,
            p_value=result.linear.p_value,
            std_err=result.linear.std_err,
            ci_lower=result.linear.ci_lower,
            ci_upper=result.linear.ci_upper
        ),
        mann_kendall=MannKendallResult(
            trend=result.mann_kendall.trend,
            h=result.mann_kendall.h,
            p=result.mann_kendall.p,
            z=result.mann_kendall.z,
            tau=result.mann_kendall.tau,
            s=result.mann_kendall.s,
            var_s=result.mann_kendall.var_s
        ),
        sens_slope_value=result.sens_slope_value,
        interpretation=result.interpretation,
        time_series=TimeSeriesData(
            timestamps=timestamps,
            values=series.tolist(),
            anomalies=anomalies.tolist() if anomalies is not None else None,
            is_anomaly=result.time_series.is_anomaly
        )
    )


@router.delete("/{analysis_id}")
async def delete_analysis(analysis_id: str):
    """
    Delete cached analysis results
    
    Args:
        analysis_id: Analysis identifier
        
    Returns:
        Confirmation message
    """
    if analysis_id in analysis_cache:
        del analysis_cache[analysis_id]
        return {"message": "Analysis deleted"}
    raise HTTPException(status_code=404, detail="Analysis not found")


@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    return {
        "total_analyses": len(analysis_cache),
        "statuses": {
            "complete": sum(1 for a in analysis_cache.values() if a["status"] == "complete"),
            "running": sum(1 for a in analysis_cache.values() if a["status"] == "running"),
            "error": sum(1 for a in analysis_cache.values() if a["status"] == "error")
        }
    }
