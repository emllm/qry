"""Simple file search engine implementation."""
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional

try:
    import magic  # type: ignore
except ImportError:  # pragma: no cover - depends on optional runtime dependency
    magic = None

from ..core.models import SearchResult, SearchQuery
from .base import SearchEngine
from .fast_search import FastContentSearcher


class SimpleSearchEngine(SearchEngine):
    """Simple file search engine using basic file system operations."""
    
    def __init__(self, max_workers: int = None):
        """Initialize the simple search engine."""
        self.max_workers = max_workers or os.cpu_count()
        self.mime = magic.Magic(mime=True) if magic else None
        self._fast_searcher = FastContentSearcher()
    
    def search(self, query: SearchQuery, search_paths: List[str]) -> List[SearchResult]:
        """Search for files matching the query."""
        results = []
        for path in search_paths:
            if not os.path.exists(path):
                continue
                
            abs_search_path = os.path.abspath(path)
            
            if os.path.isfile(path):
                result = self._process_file(path, query)
                if result and self._matches_query(result, query):
                    results.append(result)
            else:
                for root, dirs, files in os.walk(path):
                    # Check depth if max_depth is specified
                    abs_root = os.path.abspath(root)
                    rel_root = os.path.relpath(abs_root, abs_search_path)
                    
                    if rel_root == '.':
                        depth = 0
                    else:
                        depth = len([p for p in rel_root.split(os.sep) if p and p != '.'])
                        
                    if query.max_depth is not None:
                        # If current directory is at or deeper than max_depth, 
                        # clear dirs so os.walk doesn't descend further
                        if depth >= query.max_depth:
                            dirs[:] = []
                            if depth > query.max_depth:
                                continue
                                
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
            
            # Get MIME type (fallback when python-magic is unavailable)
            if self.mime:
                content_type = self.mime.from_file(file_path)
            else:
                content_type = "application/octet-stream"
            
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
        if query.query_text:
            query_lower = query.query_text.lower()
            
            # Search in filename
            if " or " in query_lower:
                terms = [t.strip() for t in query_lower.split(" or ") if t.strip()]
                filename_match = any(t in result.file_path.lower() for t in terms)
            else:
                filename_match = query_lower in result.file_path.lower()
            
            # If searching content and no filename match, try file content
            if query.search_content:
                if not filename_match:
                    text_match = self._search_in_content(result.file_path, query_lower)
                else:
                    text_match = True
            else:
                text_match = filename_match

            if not text_match:
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
    
    def _search_in_content(self, file_path: str, query_lower: str) -> bool:
        """Search for query text in file content using FastContentSearcher."""
        if " or " in query_lower:
            patterns = [t.strip() for t in query_lower.split(" or ") if t.strip()]
        else:
            patterns = [query_lower]
        return self._fast_searcher.search_file(file_path, patterns, case_sensitive=False)
    
    def get_name(self) -> str:
        """Get the name of the search engine."""
        return "simple"
    
    def is_available(self) -> bool:
        """Check if the search engine is available."""
        return True
