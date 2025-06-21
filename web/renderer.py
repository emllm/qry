"""HTML rendering for search results."""
from typing import List, Dict, Any
import os
from datetime import datetime

from ..core.models import SearchResult, SearchQuery


class HTMLRenderer:
    """Renders search results as HTML."""
    
    def __init__(self, template_dir: str = None):
        """Initialize the HTML renderer.
        
        Args:
            template_dir: Directory containing HTML templates
        """
        self.template_dir = template_dir or os.path.join(
            os.path.dirname(__file__), 'templates'
        )
    
    def render_search_results(
        self, 
        results: List[SearchResult], 
        query: SearchQuery,
        title: str = "Search Results"
    ) -> str:
        """Render search results as HTML.
        
        Args:
            results: List of search results
            query: The search query
            title: Page title
            
        Returns:
            Rendered HTML as string
        """
        # Load the base template
        base_template = self._load_template('base.html')
        
        # Generate results HTML
        results_html = []
        for result in results:
            results_html.append(self._render_result_item(result))
        
        # Format the page
        html = base_template.format(
            title=title,
            query=query.query_text,
            results_count=len(results),
            results='\n'.join(results_html),
            now=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            version="0.2.0"
        )
        
        return html
    
    def _render_result_item(self, result: SearchResult) -> str:
        """Render a single search result item."""
        return f"""
        <div class="bg-white rounded-lg shadow-md p-4 mb-4">
            <div class="flex items-center justify-between">
                <h3 class="text-lg font-semibold text-blue-600">
                    <a href="file://{result.file_path}" class="hover:underline">
                        {os.path.basename(result.file_path)}
                    </a>
                </h3>
                <span class="text-sm text-gray-500">
                    {self._format_file_size(result.size)}
                </span>
            </div>
            
            <div class="mt-2 text-sm text-gray-600">
                <p class="truncate">{result.file_path}</p>
                <p class="mt-1">
                    <span class="text-gray-700">Type:</span> {result.content_type}
                    <span class="mx-2">•</span>
                    <span class="text-gray-700">Modified:</span> {result.timestamp.strftime('%Y-%m-%d %H:%M')}
                </p>
            </div>
            
            {self._render_metadata_preview(result.metadata)}
        </div>
        """
    
    def _render_metadata_preview(self, metadata: Dict[str, Any]) -> str:
        """Render a preview of file metadata."""
        if not metadata:
            return ""
            
        preview_items = []
        for key, value in metadata.items():
            if isinstance(value, dict):
                value = ", ".join(f"{k}: {v}" for k, v in value.items())
            preview_items.append(f"<strong>{key}:</strong> {value}")
            
        if not preview_items:
            return ""
            
        return f"""
        <div class="mt-3 p-3 bg-gray-50 rounded text-sm">
            <h4 class="font-semibold mb-1">Metadata:</h4>
            <div class="grid grid-cols-2 gap-1">
                {"</div><div>".join(preview_items[:8])}
            </div>
        </div>
        """
    
    def _load_template(self, template_name: str) -> str:
        """Load an HTML template."""
        template_path = os.path.join(self.template_dir, template_name)
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            # Fallback to default template
            if template_name == 'base.html':
                return """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{title}</title>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
                </head>
                <body class="bg-gray-100 p-8">
                    <div class="max-w-4xl mx-auto">
                        <h1 class="text-3xl font-bold mb-6">{title}</h1>
                        <div class="mb-6">
                            <p class="text-gray-600">Found {results_count} results for: <span class="font-semibold">{query}</span></p>
                        </div>
                        <div class="space-y-4">
                            {results}
                        </div>
                        <div class="mt-8 text-center text-sm text-gray-500">
                            <p>Generated on {now} • Qry v{version}</p>
                        </div>
                    </div>
                </body>
                </html>
                """
            return ""
    
    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        """Format file size in a human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
