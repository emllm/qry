"""Core data models for the qry application."""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Union


@dataclass
class SearchResult:
    """Represents a search result with metadata."""
    file_path: str
    file_type: str
    content_type: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: datetime
    size: int
    hash: str = None


@dataclass
class SearchQuery:
    """Represents a search query with various filtering options."""
    query_text: str
    file_types: List[str]
    date_range: Tuple[datetime, datetime] = None
    content_types: List[str] = None
    output_format: str = "html"
    include_previews: bool = True
    max_results: int = 1000


class SearchError(Exception):
    """Base exception for search-related errors."""
    pass
