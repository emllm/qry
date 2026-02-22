"""Simple file search engine implementation."""
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Callable, Dict, Generator, List, Optional, Tuple
from functools import lru_cache

try:
    import magic  # type: ignore
except ImportError:  # pragma: no cover - depends on optional runtime dependency
    magic = None

from ..core.models import SearchResult, SearchQuery
from .base import SearchEngine
from .fast_search import FastContentSearcher


# Priority levels for directory search ordering
class Priority(IntEnum):
    """Priority levels for directory search ordering.
    
    Higher priority directories are searched first, allowing
    developers to find relevant results faster.
    """
    # High priority - source code and important config
    SOURCE = 100      # src/, source/, lib/
    PROJECT = 90      # project-specific: tests/, docs/, scripts/
    CONFIG = 80       # config files: config/, .*/, etc.
    
    # Medium priority - common development directories
    MAIN = 70         # main/, app/, core/
    MODULES = 60      # modules/, components/, packages/
    UTILS = 50        # utils/, helpers/, tools/
    
    # Low priority - build and output directories
    BUILD = 40        # build/, dist/, out/, target/
    CACHE = 30        # cache/, .cache/, __pycache__/, node_modules/
    TEMP = 20         # temp/, tmp/, .tmp/
    GENERATED = 10    # generated/, compiled/, bin/
    
    # Exclude - directories to skip
    EXCLUDED = 0      # .git/, .venv/, etc.


# Priority patterns - regex patterns mapped to priorities
PRIORITY_PATTERNS = [
    # High priority - source code
    (r'(^|/)src($|/)', Priority.SOURCE),
    (r'(^|/)source($|/)', Priority.SOURCE),
    (r'(^|/)lib($|/)', Priority.SOURCE),
    (r'(^|/)code($|/)', Priority.SOURCE),
    
    # Project-specific high priority
    (r'(^|/)tests?($|/)', Priority.PROJECT),
    (r'(^|/)test($|/)', Priority.PROJECT),
    (r'(^|/)docs?($|/)', Priority.PROJECT),
    (r'(^|/)scripts($|/)', Priority.PROJECT),
    (r'(^|/)examples?($|/)', Priority.PROJECT),
    
    # Config files
    (r'(^|/)\.config($|/)', Priority.CONFIG),
    (r'(^|/)config($|/)', Priority.CONFIG),
    (r'(^|/)settings($|/)', Priority.CONFIG),
    
    # Medium priority - main app directories
    (r'(^|/)main($|/)', Priority.MAIN),
    (r'(^|/)app($|/)', Priority.MAIN),
    (r'(^|/)core($|/)', Priority.MAIN),
    (r'(^|/)server($|/)', Priority.MAIN),
    (r'(^|/)client($|/)', Priority.MAIN),
    
    # Modules
    (r'(^|/)modules?($|/)', Priority.MODULES),
    (r'(^|/)components?($|/)', Priority.MODULES),
    (r'(^|/)packages?($|/)', Priority.MODULES),
    (r'(^|/)plugins?($|/)', Priority.MODULES),
    (r'(^|/)extensions?($|/)', Priority.MODULES),
    
    # Utils
    (r'(^|/)utils($|/)', Priority.UTILS),
    (r'(^|/)helpers($|/)', Priority.UTILS),
    (r'(^|/)tools($|/)', Priority.UTILS),
    (r'(^|/)lib($|/)', Priority.UTILS),
    
    # Low priority - build directories
    (r'(^|/)build($|/)', Priority.BUILD),
    (r'(^|/)dist($|/)', Priority.BUILD),
    (r'(^|/)out($|/)', Priority.BUILD),
    (r'(^|/)target($|/)', Priority.BUILD),
    (r'(^|/)release($|/)', Priority.BUILD),
    (r'(^|/)debug($|/)', Priority.BUILD),
    
    # Cache directories (very low)
    (r'(^|/)cache($|/)', Priority.CACHE),
    (r'(^|/)__pycache__($|/)', Priority.CACHE),
    (r'(^|/)node_modules($|/)', Priority.CACHE),
    (r'(^|/).pytest_cache($|/)', Priority.CACHE),
    (r'(^|/).tox($|/)', Priority.CACHE),
    
    # Temp directories
    (r'(^|/)temp($|/)', Priority.TEMP),
    (r'(^|/)tmp($|/)', Priority.TEMP),
    (r'(^|/).tmp($|/)', Priority.TEMP),
    
    # Generated directories
    (r'(^|/)generated($|/)', Priority.GENERATED),
    (r'(^|/)compiled($|/)', Priority.GENERATED),
    (r'(^|/)bin($|/)', Priority.GENERATED),
    (r'(^|/)obj($|/)', Priority.GENERATED),
    
    # Excluded (lowest priority - searched last)
    (r'(^|/).git($|/)', Priority.EXCLUDED),
    (r'(^|/).svn($|/)', Priority.EXCLUDED),
    (r'(^|/).hg($|/)', Priority.EXCLUDED),
    (r'(^|/).venv($|/)', Priority.EXCLUDED),
    (r'(^|/)venv($|/)', Priority.EXCLUDED),
    (r'(^|/)env($|/)', Priority.EXCLUDED),
    (r'(^|/).idea($|/)', Priority.EXCLUDED),
    (r'(^|/).vscode($|/)', Priority.EXCLUDED),
]


# Compile priority patterns once
_priority_rx = [(re.compile(p), pri) for p, pri in PRIORITY_PATTERNS]


def _get_directory_priority(dir_path: str) -> Priority:
    """Get priority for a directory based on its path.
    
    Args:
        dir_path: The directory path to evaluate
        
    Returns:
        Priority level (higher = searched first)
    """
    for rx, priority in _priority_rx:
        if rx.search(dir_path):
            return priority
    return Priority.MAIN  # Default priority


# Callback type for priority progress
PriorityCallback = Optional[Callable[[str, int, int, List[str]], None]]


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
    
    def __init__(
        self, 
        max_workers: int = None, 
        use_cache: bool = True,
        priority_mode: bool = False,
        priority_callback: PriorityCallback = None,
        incremental_timeout: float = 1.0
    ):
        """Initialize the simple search engine.
        
        Args:
            max_workers: Maximum number of worker threads for parallel processing
            use_cache: Whether to use caching for file metadata
            priority_mode: If True, search directories by priority (high to low)
            priority_callback: Callback function(priority_name, current, total, results) 
                            called when switching to new priority level
            incremental_timeout: Seconds to wait before showing progress (default: 1.0)
        """
        self.max_workers = max_workers or min(8, (os.cpu_count() or 4))
        self.use_cache = use_cache
        self.priority_mode = priority_mode
        self.priority_callback = priority_callback
        self.incremental_timeout = incremental_timeout
        self.mime = magic.Magic(mime=True) if magic else None
        self._fast_searcher = FastContentSearcher()
        # Date range for early directory pruning
        self._date_range: Optional[Tuple[datetime, datetime]] = None
    
    def search(self, query: SearchQuery, search_paths: List[str]) -> List[SearchResult]:
        """Search for files matching the query. Returns full list."""
        return list(self.search_iter(query, search_paths))

    def search_iter(self, query: SearchQuery, search_paths: List[str]) -> Generator[SearchResult, None, None]:
        """Yield matching SearchResult objects one at a time (supports Ctrl+C)."""
        # Use priority-based search if enabled
        if self.priority_mode:
            yield from self._search_by_priority(query, search_paths)
            return
        
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
    
    def _search_incremental(
        self, 
        query: SearchQuery, 
        search_paths: List[str]
    ) -> Generator[SearchResult, None, None]:
        """Incremental search with timeout-based fallback.
        
        This mode:
        1. Searches high-priority directories first
        2. Shows results immediately as they're found
        3. If no results after timeout, automatically expands search to lower priorities
        4. This ensures user finds what they're looking for quickly
        
        Args:
            query: The search query
            search_paths: List of paths to search
            
        Yields:
            SearchResult objects as they're found
        """
        import time
        import threading
        
        exclude = set(getattr(query, 'exclude_dirs', []))
        self._date_range = getattr(query, 'date_range', None)
        
        # Priority levels to search in order (high to low)
        priority_order = [
            Priority.SOURCE, Priority.PROJECT, Priority.CONFIG,
            Priority.MAIN, Priority.MODULES, Priority.UTILS,
            Priority.BUILD, Priority.CACHE, Priority.TEMP, 
            Priority.GENERATED, Priority.EXCLUDED
        ]
        
        # Track which priorities we've searched
        searched_priorities: set = set()
        found_results = False
        start_time = time.time()
        
        # Use a queue to collect results from background search
        import queue
        results_queue: queue.Queue = queue.Queue()
        stop_search = threading.Event()
        
        def background_search(priorities_to_search: List[Priority]):
            """Background thread for searching given priorities."""
            try:
                for priority in priorities_to_search:
                    if stop_search.is_set():
                        break
                        
                    dirs_at_priority = self._collect_dirs_for_priority(
                        search_paths, exclude, priority
                    )
                    
                    for dir_path, depth in dirs_at_priority:
                        if stop_search.is_set():
                            break
                        try:
                            files = os.listdir(dir_path)
                        except OSError:
                            continue
                        
                        for file in files:
                            if stop_search.is_set():
                                break
                            file_path = os.path.join(dir_path, file)
                            result = self._process_file(file_path, query)
                            if result and self._matches_query(result, query):
                                results_queue.put(result)
            finally:
                results_queue.put(None)  # Sentinel to signal completion
        
        # Start with highest priority
        current_priority_idx = 0
        
        while current_priority_idx < len(priority_order):
            priorities_to_search = [priority_order[current_priority_idx]]
            searched_priorities.add(priority_order[current_priority_idx])
            
            # Start background search
            search_thread = threading.Thread(
                target=background_search, 
                args=(priorities_to_search,),
                daemon=True
            )
            search_thread.start()
            
            # Collect results with timeout
            timeout = self.incremental_timeout
            results_in_batch = []
            last_result_time = time.time()
            
            while True:
                try:
                    result = results_queue.get(timeout=0.1)
                    if result is None:
                        # Search completed for this priority
                        break
                    found_results = True
                    last_result_time = time.time()
                    results_in_batch.append(result)
                    yield result
                    
                    # Check if we should wait longer for more results
                    if time.time() - last_result_time > timeout:
                        # No new results for timeout period
                        break
                        
                except queue.Empty:
                    # Timeout - check if we should expand search
                    if not found_results and time.time() - start_time > timeout:
                        # No results yet, expand to next priority
                        break
                    if time.time() - last_result_time > timeout:
                        # Had results but no new ones, continue checking
                        break
            
            # Stop current search and expand if no results
            stop_search.set()
            search_thread.join(timeout=0.5)
            stop_search.clear()
            
            # If we found results, we can stop early (user found what they want)
            if results_in_batch and self.priority_callback:
                # User got results, but we can continue in background if they want more
                pass
            
            # Move to next priority level
            current_priority_idx += 1
            
            # Reset timeout for subsequent searches
            start_time = time.time()
            
            # If user wants more results, continue to lower priorities
        
        # After all priorities, do one final sweep for any remaining results
        while True:
            try:
                result = results_queue.get_nowait()
                if result is None:
                    break
                yield result
            except queue.Empty:
                break
    
    def _collect_dirs_for_priority(
        self,
        search_paths: List[str],
        exclude: set,
        target_priority: Priority
    ) -> List[Tuple[str, int]]:
        """Collect all directories matching a specific priority."""
        result_dirs = []
        
        for path in search_paths:
            if not os.path.exists(path):
                continue
            
            abs_search_path = os.path.abspath(path)
            
            if os.path.isfile(path):
                continue
            
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in exclude]
                
                if self._date_range:
                    dirs[:] = self._filter_dirs_by_date(root, dirs, self._date_range)
                
                abs_root = os.path.abspath(root)
                rel_root = os.path.relpath(abs_root, abs_search_path)
                
                depth = 0 if rel_root == '.' else len([p for p in rel_root.split(os.sep) if p and p != '.'])
                
                priority = _get_directory_priority(rel_root)
                if priority == target_priority:
                    result_dirs.append((root, depth))
                
                # Continue walking to find all matching dirs
                if priority > target_priority:
                    # Still descending, keep going
                    pass
                    
        return result_dirs
    
    def _search_by_priority(
        self, 
        query: SearchQuery, 
        search_paths: List[str]
    ) -> Generator[SearchResult, None, None]:
        """Search directories by priority - high priority first.
        
        This mode organizes directories by importance (source code first, 
        cache/temp last) and yields results as each priority level completes.
        
        Args:
            query: The search query
            search_paths: List of paths to search
            
        Yields:
            SearchResult objects sorted by directory priority
        """
        exclude = set(getattr(query, 'exclude_dirs', []))
        
        # Store date range for early directory pruning
        self._date_range = getattr(query, 'date_range', None)
        
        # Collect all directories with their priorities
        all_dirs_by_priority: Dict[Priority, List[Tuple[str, int]]] = {}
        
        for path in search_paths:
            if not os.path.exists(path):
                continue
            
            abs_search_path = os.path.abspath(path)
            
            if os.path.isfile(path):
                result = self._process_file(path, query)
                if result and self._matches_query(result, query):
                    yield result
                continue
            
            # Walk directory tree and collect all directories
            for root, dirs, files in os.walk(path):
                # Prune excluded directories
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
                
                if query.max_depth is not None and depth > query.max_depth:
                    continue
                
                # Get priority for this directory
                priority = _get_directory_priority(rel_root)
                
                if priority not in all_dirs_by_priority:
                    all_dirs_by_priority[priority] = []
                all_dirs_by_priority[priority].append((root, depth))
        
        # Sort priorities from high to low
        sorted_priorities = sorted(all_dirs_by_priority.keys(), reverse=True)
        total_priorities = len(sorted_priorities)
        
        # Search each priority level
        for idx, priority in enumerate(sorted_priorities):
            priority_name = priority.name if hasattr(priority, 'name') else str(priority)
            dirs = all_dirs_by_priority[priority]
            
            priority_results = []
            
            # Search all directories at this priority level
            for dir_path, depth in dirs:
                if query.max_depth is not None and depth > query.max_depth:
                    continue
                    
                try:
                    files = os.listdir(dir_path)
                except OSError:
                    continue
                
                for file in files:
                    file_path = os.path.join(dir_path, file)
                    result = self._process_file(file_path, query)
                    if result and self._matches_query(result, query):
                        priority_results.append(result)
            
            # Emit results from this priority level
            for result in priority_results:
                yield result
            
            # Call progress callback if provided
            if self.priority_callback:
                result_paths = [r.file_path for r in priority_results]
                self.priority_callback(
                    priority_name, 
                    idx + 1, 
                    total_priorities, 
                    result_paths
                )
    
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
        """Check if a result matches the query.
        
        Order of checks is optimized for performance:
        1. File type (dict lookup - fastest)
        2. Size filtering (stat cache - O(1))
        3. Date range (stat cache - O(1))
        4. Filename match (string compare - fast)
        5. Content search (I/O bound - SLOWEST, check LAST)
        """
        # 1. File type filtering (FASTEST - dict lookup)
        if query.file_types and result.file_type.lstrip('.') not in query.file_types:
            return False
        
        # 2. Size filtering (stat cache - O(1))
        if query.min_size is not None and result.size < query.min_size:
            return False
        if query.max_size is not None and result.size > query.max_size:
            return False
            
        # 3. Date range filtering (stat cache - O(1))
        if query.date_range:
            start_date, end_date = query.date_range
            if result.timestamp < start_date or result.timestamp > end_date:
                return False

        # 4. Filename/text matching (string compare - fast)
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
            
            # 5. Content search (SLOWEST - I/O bound, check LAST)
            if mode == "content":
                # For content-only mode, skip filename check
                match = self._search_in_content(result.file_path, query, query_lower)
            elif mode == "both":
                # Check filename first, only do content search if filename doesn't match
                match = filename_match or self._search_in_content(result.file_path, query, query_lower)
            else:  # filename (default)
                match = filename_match

            if not match:
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
