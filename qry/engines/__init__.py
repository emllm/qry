"""Search engine implementations and factory."""
from typing import Dict, Optional, Type

from .base import SearchEngine
from .simple import SimpleSearchEngine

# Register all available engines here
ENGINES = {
    'simple': SimpleSearchEngine,
    # Add more engines here as they are implemented
}


def get_available_engines() -> Dict[str, Type[SearchEngine]]:
    """Get a dictionary of available search engines."""
    return {
        name: engine
        for name, engine in ENGINES.items()
        if engine().is_available()
    }


def get_engine(name: Optional[str] = None, **kwargs) -> Optional[SearchEngine]:
    """Get a search engine by name.
    
    Args:
        name: Name of the engine to get
        **kwargs: Additional arguments to pass to the engine constructor
        
    Returns:
        SearchEngine instance or None if not available
    """
    engines = get_available_engines()

    if not name or name == "default":
        for engine_class in engines.values():
            return engine_class(**kwargs)
        return None

    engine_class = engines.get(name)
    if engine_class:
        return engine_class(**kwargs)
    return None


def get_default_engine() -> SearchEngine:
    """Get the default search engine."""
    engine = get_engine()
    if engine is not None:
        return engine
    
    # If no engines are available, raise an error
    raise RuntimeError("No search engines available. Please install required dependencies.")


__all__ = [
    'get_available_engines',
    'get_default_engine',
    'get_engine',
    'SearchEngine',
]
