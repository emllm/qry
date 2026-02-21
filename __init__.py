"""Qry - Ultra-fast file search and processing tool."""

__version__ = "0.2.2"

# Import core functionality
from .core.models import SearchQuery, SearchResult, SearchError
from .engines import get_engine, get_default_engine, get_available_engines

# Set up logging
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger(__name__)

# Initialize default engine on import
try:
    default_engine = get_default_engine()
    logger.info(f"Initialized default search engine: {default_engine.get_name()}")
except Exception as e:
    logger.error(f"Failed to initialize default search engine: {e}")
    default_engine = None

def search(query: str, **kwargs) -> list:
    """Perform a search with the default engine.
    
    Args:
        query: Search query string
        **kwargs: Additional search parameters
        
    Returns:
        List of search results
    """
    if not default_engine:
        raise RuntimeError("No search engine available")
        
    search_query = SearchQuery(
        query_text=query,
        file_types=kwargs.get('file_types', []),
        date_range=kwargs.get('date_range'),
        max_results=kwargs.get('max_results', 100),
        include_previews=kwargs.get('include_previews', True)
    )
    
    return default_engine.search(search_query, ['.'])

__all__ = [
    'SearchQuery',
    'SearchResult',
    'SearchError',
    'get_engine',
    'get_default_engine',
    'get_available_engines',
    'search',
]
