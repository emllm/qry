"""Command-line interface commands for qry."""
import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, TextIO

from qry import __version__
from qry.core.models import SearchQuery
from qry.engines import get_default_engine, get_available_engines
from qry.cli.interactive import run_interactive
from qry.cli.batch import run_batch


class CLICommands:
    """Handle command-line interface commands."""
    
    def __init__(self, engine=None) -> None:
        """Initialize the CLI commands handler.
        
        Args:
            engine: Optional search engine instance to use
        """
        self.engine = engine or get_default_engine()
        self.available_engines = get_available_engines()
    
    def search_command(self, args: argparse.Namespace) -> int:
        """Handle the search command.
        
        Args:
            args: Command line arguments
            
        Returns:
            int: Exit code (0 for success)
        """
        query = self._build_search_query(args)
        results = self.engine.search(query, ['.'])  # Search in current directory
        
        # Format and print results
        for i, result in enumerate(results, 1):
            print(f"{i}. {result.file_path} ({result.content_type}, {result.size} bytes)")
        
        return 0
    
    def _build_search_query(self, args: argparse.Namespace) -> SearchQuery:
        """Build a SearchQuery from command-line arguments.
        
        Args:
            args: Command line arguments
            
        Returns:
            SearchQuery: Configured search query
        """
        date_range = None
        if args.last_days:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=args.last_days)
            date_range = (start_date, end_date)
        
        file_types = args.type.split(',') if args.type else []
        
        return SearchQuery(
            query_text=' '.join(args.query) if args.query else "",
            file_types=file_types,
            date_range=date_range,
            max_results=args.limit,
            include_previews=not args.no_preview
        )
    
    def version_command(self, args: argparse.Namespace) -> int:
        """Handle the version command.
        
        Args:
            args: Command line arguments
            
        Returns:
            int: Always returns 0 (success)
        """
        print(f"qry version {__version__}")
        print(f"Available engines: {', '.join(self.available_engines.keys())}")
        return 0
        
    def interactive_command(self, args: argparse.Namespace) -> int:
        """Start interactive mode.
        
        Args:
            args: Command line arguments
            
        Returns:
            int: Exit code from interactive mode
        """
        return run_interactive(self.engine)
        
    def batch_command(self, args: argparse.Namespace) -> int:
        """Process search queries in batch mode.
        
        Args:
            args: Command line arguments
            
        Returns:
            int: Exit code (0 for success)
        """
        input_file = args.input_file
        if not os.path.isfile(input_file):
            print(f"Error: Input file not found: {input_file}", file=sys.stderr)
            return 1
            
        return run_batch(
            input_file=input_file,
            output_file=args.output_file,
            output_format=args.format,
            engine_name=args.engine,
            max_workers=args.workers
        )
        print(f"qry version {__version__}")
        print(f"Using engine: {self.engine.get_name()}")


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="qry - Ultra-fast file search and metadata extraction tool"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Common arguments
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--engine",
        help="Search engine to use (default: auto-detect)",
        choices=get_available_engines().keys(),
    )
    
    # Search command
    search_parser = subparsers.add_parser(
        "search", 
        help="Search for files",
        parents=[common_parser]
    )
    search_parser.add_argument("query", nargs="*", help="Search query")
    search_parser.add_argument(
        "--type",
        "-t",
        help="Filter by file type (comma-separated)",
    )
    search_parser.add_argument(
        "--last-days",
        "-d",
        type=int,
        help="Filter by last N days",
    )
    search_parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=100,
        help="Maximum number of results (default: 100)",
    )
    search_parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Disable preview generation",
    )
    search_parser.add_argument(
        "--output",
        "-o",
        help="Output format (text, json, html)",
        choices=["text", "json", "html"],
        default="text",
    )
    
    # Interactive command
    interactive_parser = subparsers.add_parser(
        "interactive",
        aliases=["i", "shell"],
        help="Start interactive mode",
        parents=[common_parser]
    )
    
    # Batch command
    batch_parser = subparsers.add_parser(
        "batch",
        help="Process search queries in batch mode",
        parents=[common_parser]
    )
    batch_parser.add_argument(
        "input_file",
        help="File containing search queries (one per line)",
    )
    batch_parser.add_argument(
        "--output-file",
        "-o",
        help="Output file (default: print to stdout)",
    )
    batch_parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "csv"],
        default="text",
        help="Output format (default: text)",
    )
    batch_parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=4,
        help="Number of worker threads (default: 4)",
    )
    
    # Version command
    subparsers.add_parser("version", help="Show version information")
    
    # Help command
    help_parser = subparsers.add_parser("help", help="Show help")
    help_parser.add_argument("command", nargs="?", help="Command to show help for")
    
    return parser


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    parsed_args = parser.parse_args(args)
    
    if not parsed_args.command or parsed_args.command == "help":
        if hasattr(parsed_args, 'command') and parsed_args.command:
            # Show help for a specific command
            parser.parse_args([parsed_args.command, "--help"])
        else:
            # Show general help
            parser.print_help()
        return 0
    
    # Get the specified engine if provided
    engine = None
    if hasattr(parsed_args, 'engine') and parsed_args.engine:
        engine = get_engine(parsed_args.engine)
    
    commands = CLICommands(engine)
    
    try:
        if parsed_args.command == "search":
            return commands.search_command(parsed_args)
        elif parsed_args.command in ("interactive", "i", "shell"):
            return commands.interactive_command(parsed_args)
        elif parsed_args.command == "batch":
            return commands.batch_command(parsed_args)
        elif parsed_args.command == "version":
            return commands.version_command(parsed_args)
        else:
            print(f"Unknown command: {parsed_args.command}", file=sys.stderr)
            return 1
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if hasattr(parsed_args, 'debug') and parsed_args.debug:
            import traceback
            traceback.print_exc()
        return 1
