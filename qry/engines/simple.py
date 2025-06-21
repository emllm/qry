"""Simple file search engine implementation."""
import os
import re
import magic
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

from ..core.models import SearchResult, SearchQuery
from .base import SearchEngine


class SimpleSearchEngine(SearchEngine):
    """Simple file search engine using basic file system operations."""
    
    def __init__(self, max_workers: int = None):
        """Initialize the simple search engine."""
        self.max_workers = max_workers or os.cpu_count()
        self.mime = magic.Magic(mime=True)
    
    def search(self, query: SearchQuery, search_paths: List[str]) -> List[SearchResult]:
        """Search for files matching the query."""
        results = []
        for path in search_paths:
            if not os.path.exists(path):
                continue
                
            if os.path.isfile(path):
                result = self._process_file(path, query)
                if result and self._matches_query(result, query):
                    results.append(result)
            else:
                for root, _, files in os.walk(path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        result = self._process_file(file_path, query)
                        if result and self._matches_query(result, query):
                            results.append(result)
                            if len(results) >= query.max_results:
                                return results
        return results
    
    def _process_file(
        self, 
        file_path: str, 
        query: SearchQuery
    ) -> Optional[SearchResult]:
        """Process a single file and return a SearchResult if it matches the query."""
        try:
            stat = os.stat(file_path)
            file_type = Path(file_path).suffix.lower()
            
            # Get MIME type
            content_type = self.mime.from_file(file_path)
            
            return SearchResult(
                file_path=file_path,
                file_type=file_type,
                content_type=content_type,
                data={},
                metadata={
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime),
                    'created': datetime.fromtimestamp(stat.st_ctime)
                },
                timestamp=datetime.fromtimestamp(stat.st_mtime),
                size=stat.st_size
            )
        except Exception:
            return None
    
    def _matches_query(self, result: SearchResult, query: SearchQuery) -> bool:
        """Check if a result matches the query."""
        # Basic filename matching
        if query.query_text and query.query_text.lower() not in result.file_path.lower():
            return False
            
        # File type filtering
        if query.file_types and result.file_type.lstrip('.') not in query.file_types:
            return False
            
        # Date range filtering
        if query.date_range:
            start_date, end_date = query.date_range
            if result.timestamp < start_date or result.timestamp > end_date:
                return False
                
        return True
    
    def get_name(self) -> str:
        """Get the name of the search engine."""
        return "simple"
    
    def is_available(self) -> bool:
        """Check if the search engine is available."""
        try:
            import magic
            return True
        except ImportError:
            return False
