"""Core data models for the qry application."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


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
    hash: Optional[str] = None
    score: float = 1.0

    @property
    def modified(self) -> datetime:
        """Return modification timestamp (compatibility helper)."""
        return self.timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to a JSON-friendly dictionary."""
        return {
            "file_path": self.file_path,
            "file_type": self.file_type,
            "content_type": self.content_type,
            "data": self._serialize_value(self.data),
            "metadata": self._serialize_value(self.metadata),
            "timestamp": self.timestamp.isoformat(),
            "size": self.size,
            "hash": self.hash,
            "score": self.score,
        }

    def dict(self) -> Dict[str, Any]:
        """Compatibility alias for code expecting a pydantic-style API."""
        return self.to_dict()

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {k: SearchResult._serialize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [SearchResult._serialize_value(v) for v in value]
        return value


@dataclass
class SearchQuery:
    """Represents a search query with various filtering options."""
    query_text: str
    file_types: List[str] = field(default_factory=list)
    date_range: Optional[Tuple[datetime, datetime]] = None
    content_types: List[str] = field(default_factory=list)
    output_format: str = "html"
    include_previews: bool = True
    max_results: int = 1000
    max_depth: Optional[int] = None


class SearchError(Exception):
    """Base exception for search-related errors."""
    pass
