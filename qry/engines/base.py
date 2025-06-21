"""Base classes for search engines."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pathlib import Path

from ..core.models import SearchQuery, SearchResult


class SearchEngine(ABC):
    """Abstract base class for all search engines."""
    
    @abstractmethod
    def search(self, query: SearchQuery, search_paths: List[str]) -> List[SearchResult]:
        """Search for files matching the query.
        
        Args:
            query: The search query
            search_paths: List of paths to search in
            
        Returns:
            List of search results
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the name of the search engine."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the search engine is available (dependencies installed, etc.)."""
        pass
