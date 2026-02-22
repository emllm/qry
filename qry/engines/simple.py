"""Simple file search engine implementation."""
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple
from functools import lru_cache

try:
    import magic  # type: ignore
except ImportError:  # pragma: no cover - depends on optional runtime dependency
    magic = None

from ..core.models import SearchResult, SearchQuery
from .base import SearchEngine
from .fast_search import FastContentSearcher


# Cache for file stat results - avoids repeated filesystem calls
@lru_cache(maxsize=10000)
def _cached_stat(file_path: str) -> Optional[os.stat_result]:
    """Cached version of os.stat to avoid repeated filesystem calls."""
    try:
        return os.stat(file_path)
    except OSError:
        return None


# Regex pattern cache
_regex_cache: Dict[str, re.Pattern] = {}


def _get_cached_regex(pattern: str, flags: int = re.IGNORECASE) -> re.Pattern:
    """Get or create a cached compiled regex pattern."""
    cache_key = (pattern, flags)
    if cache_key not in _regex_cache:
        try:
            _regex_cache[cache_key] = re.compile(pattern, flags)
        except re.error:
            _regex_cache[cache_key] = re.compile(re.escape(pattern), flags)
    return _regex_cache[cache_key]


class SimpleSearchEngine(SearchEngine):
    """Simple file search engine using basic file system operations."""
    
    def __init__(self, max_workers: int = None, use_cache: bool = True):
        """Initialize the simple search engine.
        
        Args:
            max_workers: Maximum number of worker threads for parallel processing
            use_cache: Whether to use caching for file metadata
        """
        self.max_workers = max_workers or min(8, (os.cpu_count() or 4))
        self.use_cache = use_cache
        self.mime = magic.Magic(mime=True) if magic else None
        self._fast_searcher = FastContentSearcher()
        # Date range for early directory pruning
        self._date_range: Optional[Tuple[datetime, datetime]] = None
    
    def search(self, query: SearchQuery, search_paths: List[str]) -> List[SearchResult]:
        """Search for files matching the query. Returns full list."""
        return list(self.search_iter(query, search_paths))

    def search_iter(self, query: SearchQuery, search_paths: List[str]) -> Generator[SearchResult, None, None]:
        """Yield matching SearchResult objects one at a time (supports Ctrl+C)."""
        exclude = set(getattr(query, 'exclude_dirs', []))
        count = 0
        
        # Store date range for early directory pruning
        self._date_range = getattr(query, 'date_range', None)
        
        # If we have date range and can use parallel processing, use it
        if self._date_range and self.max_workers > 1:
            # Use parallel processing for date-filtered searches
            yield from self._search_parallel(query, search_paths, exclude, count)
            return
        
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
                    
                    # Early date-based directory pruning
                    if self._date_range:
                        dirs[:] = self._filter_dirs_by_date(root, dirs, self._date_range)

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
    
    def _search_parallel(
        self, 
        query: SearchQuery, 
        search_paths: List[str], 
        exclude: set,
        initial_count: int
    ) -> Generator[SearchResult, None, None]:
        """Parallel directory search with date-based filtering."""
        count = initial_count
        
        # First, collect all directories to search
        all_dirs: List[Tuple[str, int]] = []  # (directory_path, depth)
        
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
                    dirs[:] = [d for d in dirs if d not in exclude]
                    
                    # Early date-based directory pruning
                    if self._date_range:
                        dirs[:] = self._filter_dirs_by_date(root, dirs, self._date_range)
                    
                    abs_root = os.path.abspath(root)
                    rel_root = os.path.relpath(abs_root, abs_search_path)
                    
                    if rel_root == '.':
                        depth = 0
                    else:
                        depth = len([p for p in rel_root.split(os.sep) if p and p != '.'])
                    
                    if query.max_depth is not None and depth >= query.max_depth:
                        dirs[:] = []
                        if depth > query.max_depth:
                            continue
                    
                    all_dirs.append((root, depth))
        
        # Process files in directories in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for dir_path, depth in all_dirs:
                if query.max_depth is not None and depth > query.max_depth:
                    continue
                try:
                    files = os.listdir(dir_path)
                except OSError:
                    continue
                future = executor.submit(self._process_directory, dir_path, files, query)
                futures[future] = dir_path
            
            for future in as_completed(futures):
                if count >= query.max_results:
                    executor.shutdown(wait=False)
                    break
                try:
                    results = future.result()
                    for result in results:
                        if self._matches_query(result, query):
                            yield result
                            count += 1
                            if count >= query.max_results:
                                break
                except Exception:
                    pass
    
    def _process_directory(
        self, 
        dir_path: str, 
        files: List[str], 
        query: SearchQuery
    ) -> List[SearchResult]:
        """Process all files in a directory (for parallel execution)."""
        results = []
        for file in files:
            file_path = os.path.join(dir_path, file)
            result = self._process_file(file_path, query)
            if result:
                results.append(result)
        return results
    
    def _filter_dirs_by_date(
        self, 
        parent_dir: str, 
        dirs: List[str],
        date_range: Optional[Tuple[datetime, datetime]]
    ) -> List[str]:
        """Filter directories by date based on directory name (e.g., 2024-01-15)."""
        if not date_range:
            return dirs
        
        start_date, end_date = date_range
        filtered = []
        
        for d in dirs:
            dir_path = os.path.join(parent_dir, d)
            # Try to parse directory name as date
            parsed_date = self._parse_dir_date(d)
            if parsed_date is not None:
                # Directory has date in name - check if it's in range
                if parsed_date < start_date or parsed_date > end_date:
                    # Skip entire directory tree if date is outside range
                    continue
            filtered.append(d)
        
        return filtered
    
    def _parse_dir_date(self, dir_name: str) -> Optional[datetime]:
        """Try to parse a directory name as a date."""
        # Common date formats in directory names
        date_formats = [
            "%Y-%m-%d", "%Y%m%d", "%d-%m-%Y", "%m-%d-%Y",
            "%Y_%m_%d", "%Y%m", "%Y", "%B_%Y", "%b_%Y",
        ]
        
        # Try to extract date from directory name
        # Remove common prefixes/suffixes
        cleaned = dir_name.strip()
        
        for fmt in date_formats:
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        
        # Try to find a date pattern in the name
        date_pattern = re.compile(r'(\d{4})[-_]?(\d{2})?[-_]?(\d{2})?')
        match = date_pattern.search(cleaned)
        if match:
            try:
                year = int(match.group(1))
                month = int(match.group(2)) if match.group(2) else 1
                day = int(match.group(3)) if match.group(3) else 1
                return datetime(year, month, day)
            except ValueError:
                pass
        
        return None
    
    def _process_file(
        self, 
        file_path: str, 
        query: SearchQuery
    ) -> Optional[SearchResult]:
        """Process a single file and return a SearchResult if it matches the query."""
        try:
            # Use cached stat if enabled
            if self.use_cache:
                stat = _cached_stat(file_path)
            else:
                stat = os.stat(file_path)
            
            if stat is None:
                return None
                
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
                rx = _get_cached_regex(query.query_text, re.IGNORECASE)
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
        rx = _get_cached_regex(pattern, re.IGNORECASE)
        try:
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
                rx = _get_cached_regex(query_text, re.IGNORECASE)
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
