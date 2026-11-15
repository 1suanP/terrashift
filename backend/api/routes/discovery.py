"""
Variable discovery routes - searchable catalogue and trend-investigation questions
"""
from typing import Any, Dict, List

from fastapi import APIRouter

import config
from modules import variable_catalogue as cat
from api.routes.analysis import analysis_cache

router = APIRouter()


def _suggestion(s: cat.DatasetSuggestion) -> Dict[str, str]:
    return {"short_name": s.short_name, "title": s.title, "archive": s.archive, "period": s.period, "note": s.note}


def _completed_analyses() -> Dict[str, List[Dict[str, Any]]]:
    """Analyses finished in this backend session, grouped by 'dataset/variable'."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for analysis_id, cached in list(analysis_cache.items()):
        if cached.get("status") != "complete" or "result" not in cached:
            continue
        req, res = cached["request"], cached["result"]
        grouped.setdefault(f"{req['dataset_key']}/{req['variable_id']}", []).append({
            "analysis_id": analysis_id,
            "region_name": res.region_name,
            "time_range_start": req["time_range_start"],
            "time_range_end": req["time_range_end"],
            "significance": res.significance,
            "linear_p_value": res.linear.p_value,
            "mann_kendall_p": res.mann_kendall.p,
            "slope_per_year": res.linear.slope,
            "units": res.variable_meta.units,
            "n_points": res.n_points,
            "completed_at": cached.get("completed_at"),
        })
    return grouped


@router.get("/catalogue")
def get_catalogue() -> Dict[str, Any]:
    """Every variable the app knows about, whether it can be analyzed, and suggested questions."""
    analyses = _completed_analyses()
    variables: List[Dict[str, Any]] = []

    for key, entry in cat.AVAILABLE.items():
        meta = config.VARIABLES[key]
        dataset = config.DATASETS[meta.dataset_key]
        start, end = config.dataset_period(meta.dataset_key)
        variables.append({
            "id": key,
            "status": "available",
            "common_name": entry.common_name,
            "scientific_name": meta.long_name,
            "variable_id": meta.variable_id,
            "dataset_key": meta.dataset_key,
            "dataset_title": dataset.title,
            "categories": list(entry.categories),
            "level": entry.level,
            "short_description": meta.short_description,
            "plain_language": meta.plain_language,
            "units": meta.units,
            "trend_direction_hint": meta.trend_direction_hint,
            "why_trend": entry.why_trend,
            "keywords": list(entry.keywords),
            "coverage": {
                **cat.DATASET_COVERAGE[meta.dataset_key],
                "period_start": start.isoformat(),
                "period_end": "present" if dataset.period_end == "present" else end.isoformat(),
                "load_seconds_per_year": cat.LOAD_SECONDS_PER_YEAR[meta.dataset_key],
            },
            "other_datasets": [_suggestion(s) for s in entry.other_datasets],
            "analyses": analyses.get(key, []),
        })

    for entry in cat.UNAVAILABLE:
        closest = None
        if entry.closest_available:
            closest = {"id": entry.closest_available, "common_name": cat.AVAILABLE[entry.closest_available].common_name}
        variables.append({
            "id": entry.entry_id,
            "status": "requires_dataset",
            "common_name": entry.common_name,
            "scientific_name": entry.scientific_name,
            "categories": list(entry.categories),
            "level": entry.level,
            "short_description": entry.description,
            "plain_language": entry.plain_language,
            "units": entry.typical_units,
            "why_trend": entry.why_trend,
            "reason_unavailable": entry.reason_unavailable,
            "required_datasets": [_suggestion(s) for s in entry.required_datasets],
            "closest_available": closest,
            "keywords": list(entry.keywords),
            "analyses": [],
        })

    questions = []
    for index, q in enumerate(cat.QUESTIONS):
        box = config.PRESET_REGIONS[q.region_name]
        questions.append({
            "id": index,
            "question": q.question,
            "why": q.why,
            "variable_key": q.variable_key or cat.unavailable_by_id(q.unavailable_id).closest_available,
            "unavailable_id": q.unavailable_id,
            "region": {
                "name": q.region_name,
                "min_lat": box.min_lat, "max_lat": box.max_lat,
                "min_lon": box.min_lon, "max_lon": box.max_lon,
            },
            "start_year": q.start_year,
            "end_year": q.end_year,
        })

    return {
        "categories": [{"key": k, "label": label, "description": desc} for k, (label, desc) in cat.CATEGORIES.items()],
        "levels": [{"key": k, "label": label} for k, label in cat.LEVELS.items()],
        "alpha": config.ALPHA,
        "variables": variables,
        "questions": questions,
    }
