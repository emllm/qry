"""Qry - Ultra-fast file search and processing tool."""
from typing import Generator, List, Optional

__version__ = "0.2.9"

# This will be set by __main__.py when the package is run as a script
main = None


def search(
    query_text: str,
    scope: str = ".",
    *,
    mode: str = "filename",
    depth: Optional[int] = None,
    file_types: Optional[List[str]] = None,
    exclude_dirs: Optional[List[str]] = None,
    max_results: int = 10_000_000,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    regex: bool = False,
    sort_by: Optional[str] = None,
) -> List[str]:
    """Search for files and return a list of matching file paths.

    Args:
        query_text: Text to search for.
        scope: Directory to search in (default: current directory).
        mode: Search mode - ``"filename"``, ``"content"``, or ``"both"``.
        depth: Maximum directory depth (None = unlimited).
        file_types: List of extensions to include, e.g. ``["py", "txt"]``.
        exclude_dirs: Directory names to skip. Defaults to the standard set
            (.git, .venv, __pycache__, dist, node_modules, …).
        max_results: Hard cap on returned results.
        min_size: Minimum file size in bytes.
        max_size: Maximum file size in bytes.
        regex: Treat query_text as a regular expression.
        sort_by: Sort results by ``"name"``, ``"size"``, or ``"date"``.

    Returns:
        List of matching file paths.

    Example::

        import qry
        files = qry.search("TODO", scope="./src", mode="content", depth=5)
        big = qry.search("", scope=".", min_size=1024*1024, sort_by="size")
    """
    return list(search_iter(
        query_text, scope,
        mode=mode, depth=depth, file_types=file_types,
        exclude_dirs=exclude_dirs, max_results=max_results,
        min_size=min_size, max_size=max_size, regex=regex,
        sort_by=sort_by,
    ))


def search_iter(
    query_text: str,
    scope: str = ".",
    *,
    mode: str = "filename",
    depth: Optional[int] = None,
    file_types: Optional[List[str]] = None,
    exclude_dirs: Optional[List[str]] = None,
    max_results: int = 10_000_000,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    regex: bool = False,
    sort_by: Optional[str] = None,
) -> Generator[str, None, None]:
    """Like :func:`search` but yields file paths one at a time (memory-efficient).

    Supports ``KeyboardInterrupt`` (Ctrl+C) to stop mid-search.

    Note: when ``sort_by`` is set all results are collected before yielding.

    Example::

        import qry
        for path in qry.search_iter("invoice", scope="/data", mode="content"):
            print(path)
    """
    from qry.core.models import SearchQuery
    from qry.engines import get_default_engine

    kw = {}
    if exclude_dirs is not None:
        kw['exclude_dirs'] = exclude_dirs

    q = SearchQuery(
        query_text=query_text,
        file_types=file_types or [],
        max_depth=depth,
        search_mode=mode,
        max_results=max_results,
        min_size=min_size,
        max_size=max_size,
        use_regex=regex,
        sort_by=sort_by,
        **kw,
    )
    engine = get_default_engine()

    if sort_by:
        results = list(engine.search(q, [scope]))
        key_fn = {
            'name': lambda r: r.file_path.lower(),
            'size': lambda r: r.size,
            'date': lambda r: r.timestamp,
        }.get(sort_by, lambda r: r.file_path.lower())
        results.sort(key=key_fn)
        for r in results:
            yield r.file_path
    elif hasattr(engine, 'search_iter'):
        for result in engine.search_iter(q, [scope]):
            yield result.file_path
    else:
        for result in engine.search(q, [scope]):
            yield result.file_path


__all__ = ['__version__', 'main', 'search', 'search_iter']