"""Simple file search engine implementation."""
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Generator, List, Optional

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
        """Search for files matching the query. Returns full list."""
        return list(self.search_iter(query, search_paths))

    def search_iter(self, query: SearchQuery, search_paths: List[str]) -> Generator[SearchResult, None, None]:
        """Yield matching SearchResult objects one at a time (supports Ctrl+C)."""
        exclude = set(getattr(query, 'exclude_dirs', []))
        count = 0
        for path in search_paths:
            if not os.path.exists(path):
                continue
                
            abs_search_path = os.path.abspath(path)
            
            if os.path.isfile(path):
                result = self._process_file(path, query)
                if result and self._matches_query(result, query):
                    yield result
                    count += 1
                    if count >= query.max_results:
                        return
            else:
                for root, dirs, files in os.walk(path):
                    # Prune excluded directories in-place
                    dirs[:] = [d for d in dirs if d not in exclude]

                    # Check depth if max_depth is specified
                    abs_root = os.path.abspath(root)
                    rel_root = os.path.relpath(abs_root, abs_search_path)
                    
                    if rel_root == '.':
                        depth = 0
                    else:
                        depth = len([p for p in rel_root.split(os.sep) if p and p != '.'])
                        
                    if query.max_depth is not None:
                        if depth >= query.max_depth:
                            dirs[:] = []
                            if depth > query.max_depth:
                                continue
                                
                    for file in files:
                        file_path = os.path.join(root, file)
                        result = self._process_file(file_path, query)
                        if result and self._matches_query(result, query):
                            yield result
                            count += 1
                            if count >= query.max_results:
                                return
    
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
        # Size filtering
        if query.min_size is not None and result.size < query.min_size:
            return False
        if query.max_size is not None and result.size > query.max_size:
            return False

        # Text / regex matching
        if query.query_text:
            query_lower = query.query_text.lower()

            if query.use_regex:
                try:
                    rx = re.compile(query.query_text, re.IGNORECASE)
                except re.error:
                    rx = re.compile(re.escape(query.query_text), re.IGNORECASE)
                filename_match = bool(rx.search(result.file_path))
            elif " or " in query_lower:
                terms = [t.strip() for t in query_lower.split(" or ") if t.strip()]
                filename_match = any(t in result.file_path.lower() for t in terms)
            else:
                filename_match = query_lower in result.file_path.lower()
            
            mode = getattr(query, 'search_mode', 'filename')
            if mode == "content":
                match = self._search_in_content(result.file_path, query, query_lower)
            elif mode == "both":
                match = filename_match or self._search_in_content(result.file_path, query, query_lower)
            else:  # filename (default)
                match = filename_match

            if not match:
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
    
    def _search_in_content(self, file_path: str, query: SearchQuery, query_lower: str) -> bool:
        """Search for query text in file content."""
        if query.use_regex:
            return self._regex_search_file(file_path, query.query_text)
        if " or " in query_lower:
            patterns = [t.strip() for t in query_lower.split(" or ") if t.strip()]
        else:
            patterns = [query_lower]
        return self._fast_searcher.search_file(file_path, patterns, case_sensitive=False)

    @staticmethod
    def _regex_search_file(file_path: str, pattern: str) -> bool:
        """Search file content with a regex pattern."""
        try:
            rx = re.compile(pattern, re.IGNORECASE)
            with open(file_path, 'r', errors='ignore') as f:
                for line in f:
                    if rx.search(line):
                        return True
        except (OSError, IOError):
            pass
        return False

    @staticmethod
    def get_content_snippet(file_path: str, query_text: str, context_lines: int = 1, use_regex: bool = False) -> Optional[str]:
        """Return first matching line with context for content search preview."""
        try:
            if use_regex:
                try:
                    rx = re.compile(query_text, re.IGNORECASE)
                except re.error:
                    rx = re.compile(re.escape(query_text), re.IGNORECASE)
            else:
                rx = None
            q_lower = query_text.lower()
            terms = [t.strip() for t in q_lower.split(" or ") if t.strip()] if " or " in q_lower else [q_lower]
            lines = []
            with open(file_path, 'r', errors='ignore') as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                hit = rx.search(line) if rx else any(t in line.lower() for t in terms)
                if hit:
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    snippet_lines = []
                    for j in range(start, end):
                        prefix = "»" if j == i else " "
                        snippet_lines.append(f"{prefix} {j + 1}: {lines[j].rstrip()}")
                    return "\n".join(snippet_lines)
        except (OSError, IOError):
            pass
        return None
    
    def get_name(self) -> str:
        """Get the name of the search engine."""
        return "simple"
    
    def is_available(self) -> bool:
        """Check if the search engine is available."""
        return True
