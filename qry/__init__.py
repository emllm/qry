"""Qry - Ultra-fast file search and processing tool."""
from typing import Generator, List, Optional

__version__ = "0.2.4"

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

    Returns:
        List of matching file paths.

    Example::

        import qry
        files = qry.search("TODO", scope="./src", mode="content", depth=5)
    """
    return list(search_iter(
        query_text, scope,
        mode=mode, depth=depth, file_types=file_types,
        exclude_dirs=exclude_dirs, max_results=max_results,
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
) -> Generator[str, None, None]:
    """Like :func:`search` but yields file paths one at a time (memory-efficient).

    Supports ``KeyboardInterrupt`` (Ctrl+C) to stop mid-search.

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
        **kw,
    )
    engine = get_default_engine()
    if hasattr(engine, 'search_iter'):
        for result in engine.search_iter(q, [scope]):
            yield result.file_path
    else:
        for result in engine.search(q, [scope]):
            yield result.file_path


__all__ = ['__version__', 'main', 'search', 'search_iter']