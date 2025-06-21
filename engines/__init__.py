"""Search engine implementations and factory."""
from typing import Dict, Type, List, Optional, Tuple

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


def get_engine(name: str, **kwargs) -> Optional[SearchEngine]:
    """Get a search engine by name.
    
    Args:
        name: Name of the engine to get
        **kwargs: Additional arguments to pass to the engine constructor
        
    Returns:
        SearchEngine instance or None if not available
    """
    engines = get_available_engines()
    engine_class = engines.get(name)
    if engine_class:
        return engine_class(**kwargs)
    return None


def get_default_engine() -> SearchEngine:
    """Get the default search engine."""
    engines = get_available_engines()
    
    # Try to return the first available engine
    for name, engine_class in engines.items():
        return engine_class()
    
    # If no engines are available, raise an error
    raise RuntimeError("No search engines available. Please install required dependencies.")
