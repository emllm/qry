"""API routes for the qry service."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta

from ..core.models import SearchQuery, SearchResult
from ..engines import get_engine, get_available_engines
from ..web.renderer import HTMLRenderer

router = APIRouter()


@router.get("/search", response_model=List[dict])
async def search(
    q: str = Query(..., description="Search query"),
    types: Optional[str] = Query(None, description="Comma-separated list of file types to filter by"),
    limit: int = Query(100, description="Maximum number of results to return"),
    last_days: Optional[int] = Query(None, description="Filter by last N days"),
    engine: str = Query("default", description="Search engine to use"),
) -> List[dict]:
    """Search for files."""
    # Parse date range if provided
    date_range = None
    if last_days:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=last_days)
        date_range = (start_date, end_date)
    
    # Parse file types
    file_types = types.split(",") if types else []
    
    # Get the appropriate search engine
    search_engine = get_engine(engine) if engine != "default" else get_engine()
    if not search_engine:
        raise HTTPException(status_code=400, detail=f"Unsupported search engine: {engine}")
    
    # Build and execute the query
    query = SearchQuery(
        query_text=q,
        file_types=file_types,
        date_range=date_range,
        max_results=limit
    )
    
    try:
        results = search_engine.search(query, ['.'])  # Search in current directory
        return [result.dict() for result in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/html", response_class=HTMLResponse)
async def search_html(
    q: str = Query(..., description="Search query"),
    types: Optional[str] = Query(None, description="Comma-separated list of file types to filter by"),
    limit: int = Query(100, description="Maximum number of results to return"),
    last_days: Optional[int] = Query(None, description="Filter by last N days"),
    engine: str = Query("default", description="Search engine to use"),
) -> str:
    """Search for files and return results as HTML."""
    # First get the JSON results
    results = await search(q, types, limit, last_days, engine)
    
    # Convert to SearchResult objects
    search_results = [SearchResult(**r) for r in results]
    
    # Create a search query for the renderer
    query = SearchQuery(
        query_text=q,
        file_types=types.split(",") if types else [],
        max_results=limit
    )
    
    # Render to HTML
    renderer = HTMLRenderer()
    return renderer.render_search_results(search_results, query)


@router.get("/engines", response_model=List[dict])
async def list_engines() -> List[dict]:
    """List available search engines."""
    engines = get_available_engines()
    return [
        {
            "name": name,
            "description": engine.__doc__ or "",
            "available": engine().is_available()
        }
        for name, engine in engines.items()
    ]


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
