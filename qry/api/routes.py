"""API routes for the qry service."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from qry.core.models import SearchQuery, SearchResult
from qry.engines import get_available_engines, get_engine
from qry.web.renderer import HTMLRenderer

router = APIRouter()


@router.get("/search", response_model=List[dict])
async def search(
    q: str = Query(..., description="Search query"),
    types: Optional[str] = Query(
        None,
        description="Comma-separated list of file types to filter by",
    ),
    limit: int = Query(100, ge=1, le=10_000, description="Maximum number of results"),
    last_days: Optional[int] = Query(None, ge=1, description="Filter by last N days"),
    engine: str = Query("default", description="Search engine to use"),
) -> List[dict]:
    """Search for files and return JSON-serializable results."""
    date_range = None
    if last_days is not None:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=last_days)
        date_range = (start_date, end_date)

    file_types = types.split(",") if types else []
    search_engine = get_engine(engine)
    if search_engine is None:
        raise HTTPException(status_code=400, detail=f"Unsupported search engine: {engine}")

    query = SearchQuery(
        query_text=q,
        file_types=file_types,
        date_range=date_range,
        max_results=limit,
    )

    try:
        results = search_engine.search(query, ["."])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return [result.to_dict() for result in results]


@router.get("/search/html", response_class=HTMLResponse)
async def search_html(
    q: str = Query(..., description="Search query"),
    types: Optional[str] = Query(
        None,
        description="Comma-separated list of file types to filter by",
    ),
    limit: int = Query(100, ge=1, le=10_000, description="Maximum number of results"),
    last_days: Optional[int] = Query(None, ge=1, description="Filter by last N days"),
    engine: str = Query("default", description="Search engine to use"),
) -> str:
    """Search for files and return rendered HTML."""
    raw_results = await search(q=q, types=types, limit=limit, last_days=last_days, engine=engine)

    search_results: List[SearchResult] = []
    for item in raw_results:
        hydrated = dict(item)
        timestamp = hydrated.get("timestamp")
        if isinstance(timestamp, str):
            hydrated["timestamp"] = datetime.fromisoformat(timestamp)
        search_results.append(SearchResult(**hydrated))

    query = SearchQuery(query_text=q, file_types=types.split(",") if types else [], max_results=limit)
    return HTMLRenderer().render_search_results(search_results, query)


@router.get("/engines", response_model=List[dict])
async def list_engines() -> List[dict]:
    """List available search engines."""
    return [
        {"name": name, "description": engine.__doc__ or "", "available": engine().is_available()}
        for name, engine in get_available_engines().items()
    ]


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
