"""Batch processing for qry.

This module provides functionality for processing multiple search queries in batch mode,
supporting parallel execution and multiple output formats.
"""

import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, TextIO

from tqdm import tqdm  # type: ignore

from ..core.models import SearchQuery, SearchResult
from ..engines import get_engine, get_default_engine


class BatchProcessor:
    """Process multiple search queries in batch mode."""

    def __init__(
        self,
        engine=None,
        output_format: str = 'text',
        output_file: Optional[str] = None,
        max_workers: int = 4,
        search_paths: Optional[List[str]] = None,
    ) -> None:
        """Initialize the batch processor.

        Args:
            engine: Search engine instance to use
            output_format: Output format (text, json, csv)
            output_file: Optional output file path
            max_workers: Maximum number of worker threads
            search_paths: Paths to search in for each query
        """
        self.engine = engine or get_default_engine()
        self.output_format = output_format
        self.output_file = output_file
        self.max_workers = max_workers
        self.search_paths = search_paths or ['.']
        self.results: List[Dict[str, Any]] = []

    def process_file(self, input_file: str) -> int:
        """Process queries from a file.

        Args:
            input_file: Path to input file

        Returns:
            int: Number of queries processed
        """
        with open(input_file, 'r', encoding='utf-8') as f:
            queries = [line.strip() for line in f if line.strip()]

        return self.process_queries(queries)

    def process_queries(self, queries: List[str]) -> int:
        """Process a list of search queries.
        
        Args:
            queries: List of search query strings
            
        Returns:
            int: Number of queries processed
        """
        total_queries = len(queries)
        if total_queries == 0:
            print("No queries to process.", file=sys.stderr)
            return 0
        
        # Prepare output
        output_file = None
        if self.output_file:
            output_file = open(self.output_file, 'w', encoding='utf-8')
            if self.output_format == 'json':
                output_file.write('[')
            elif self.output_format == 'csv':
                writer = csv.writer(output_file)
                # Write CSV header
                writer.writerow(['query', 'file_path', 'score', 'file_type', 'size', 'modified'])
        
        try:
            # Process queries in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._process_single_query, query): i
                    for i, query in enumerate(queries)
                }
                
                # Set up progress bar
                with tqdm(total=len(queries), desc="Processing queries") as pbar:
                    for future in as_completed(futures):
                        query_idx = futures[future]
                        query = queries[query_idx]
                        
                        try:
                            results = future.result()
                            self._write_results(
                                query,
                                results,
                                output_file,
                                query_idx,
                                total_queries
                            )
                        except Exception as e:
                            print(
                                f"\nError processing query '{query}': {e}",
                                file=sys.stderr
                            )
                        pbar.update(1)
            
            # Close JSON array if needed
            if output_file and self.output_format == 'json':
                output_file.write('\n]')
            
            return total_queries
            
        finally:
            if output_file:
                output_file.close()
    
    def _process_single_query(self, query: str) -> List[SearchResult]:
        """Process a single search query.

        Args:
            query: Search query string

        Returns:
            List[SearchResult]: Search results
        """
        search_query = SearchQuery(query_text=query)
        return self.engine.search(search_query, self.search_paths)
    
    def _write_results(
        self,
        query: str,
        results: List[SearchResult],
        output_file: Optional[TextIO],
        query_idx: int,
        total_queries: int
    ) -> None:
        """Write results in the specified format."""
        if not output_file:
            self._print_results(query, results)
            return
        
        # Convert results to dicts
        result_dicts = [
            {
                'query': query,
                'file_path': str(r.file_path),
                'score': r.score,
                'file_type': r.file_type,
                'size': r.size,
                'modified': r.modified.isoformat() if r.modified else None,
                'metadata': r.metadata
            }
            for r in results
        ]
        
        if self.output_format == 'json':
            # Add comma between JSON objects
            if query_idx > 0:
                output_file.write(',')
            json.dump(result_dicts, output_file, indent=2)
            
        elif self.output_format == 'csv':
            writer = csv.writer(output_file)
            for r in result_dicts:
                writer.writerow([
                    r['query'],
                    r['file_path'],
                    r['score'],
                    r['file_type'],
                    r['size'],
                    r['modified']
                ])
        else:  # text
            output_file.write(f"\nResults for: {query}\n")
            output_file.write("-" * 80 + "\n")
            for i, r in enumerate(result_dicts, 1):
                output_file.write(
                    f"{i}. {r['file_path']} (score: {r['score']:.2f})\n"
                )
            output_file.write("\n")
    
    def _print_results(self, query: str, results: List[SearchResult]):
        """Print results to console."""
        print(f"\nResults for: {query}")
        print("-" * 80)
        
        if not results:
            print("No results found.")
            return
            
        for i, result in enumerate(results, 1):
            print(f"{i}. {result.file_path} (score: {result.score:.2f})")
            if hasattr(result, 'metadata') and result.metadata:
                for k, v in result.metadata.items():
                    print(f"   {k}: {v}")


def run_batch(
    input_file: str,
    output_file: Optional[str] = None,
    output_format: str = 'text',
    engine_name: Optional[str] = None,
    max_workers: int = 4
) -> int:
    """Run batch processing.
    
    Args:
        input_file: Path to input file with queries (one per line)
        output_file: Optional path to output file
        output_format: Output format (text, json, csv)
        engine_name: Name of search engine to use
        max_workers: Maximum number of worker threads
        
    Returns:
        int: Exit code (0 for success)
    """
    try:
        # Get the specified engine or default
        engine = get_engine(engine_name) if engine_name else get_default_engine()
        
        # Create and run processor
        processor = BatchProcessor(
            engine=engine,
            output_format=output_format,
            output_file=output_file,
            max_workers=max_workers
        )
        
        # Process the input file
        count = processor.process_file(input_file)
        
        # Print summary
        if not output_file:
            print(f"\nProcessed {count} queries.")
        else:
            print(f"\nProcessed {count} queries. Results saved to {output_file}")
            
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
