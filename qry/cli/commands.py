"""Command-line interface commands for qry."""
import argparse
import json as _json
import os
import re
import sys
from datetime import datetime, timedelta
from typing import List, Optional

import yaml

from qry import __version__
from qry.core.models import SearchQuery
from qry.engines import get_default_engine, get_available_engines, get_engine
from qry.engines.simple import SimpleSearchEngine
from qry.cli.interactive import run_interactive
from qry.cli.batch import run_batch

_SIZE_UNITS = {'b': 1, 'k': 1024, 'kb': 1024, 'm': 1024**2, 'mb': 1024**2, 'g': 1024**3, 'gb': 1024**3}

# Human-readable date ranges
_DATE_RANGE_ALIASES = {
    'today': 0,
    'yesterday': 1,
    'lastday': 1,
    'last day': 1,
    '2days': 2,
    '3days': 3,
    '5days': 5,
    'week': 7,
    'lastweek': 7,
    'last week': 7,
    '2weeks': 14,
    '2 weeks': 14,
    'month': 30,
    'lastmonth': 30,
    'last month': 30,
    '2months': 60,
    '2 months': 60,
    '3months': 90,
    '3 months': 90,
    'quarter': 90,
    'year': 365,
    'lastyear': 365,
    'last year': 365,
    '2years': 730,
}


def _parse_size(value: str) -> int:
    """Parse human-readable size string like '10MB', '500k', '1G' to bytes."""
    value = value.strip().lower()
    for suffix, mult in sorted(_SIZE_UNITS.items(), key=lambda x: -len(x[0])):
        if value.endswith(suffix):
            return int(float(value[:-len(suffix)]) * mult)
    return int(value)


def _parse_date_range(value: str) -> Optional[int]:
    """Parse human-readable date range like 'last week', 'month', 'yesterday'.
    
    Returns:
        Number of days as integer, or None if not recognized
    """
    value = value.strip().lower().replace('_', ' ')
    
    # Check direct aliases
    if value in _DATE_RANGE_ALIASES:
        return _DATE_RANGE_ALIASES[value]
    
    # Try parsing "last N days/weeks/months"
    import re
    patterns = [
        r'last\s+(\d+)\s+days?',
        r'last\s+(\d+)\s+weeks?',
        r'last\s+(\d+)\s+months?',
        r'last\s+(\d+)\s+years?',
        r'(\d+)\s+days?',
        r'(\d+)\s+weeks?',
        r'(\d+)\s+months?',
        r'(\d+)\s+years?',
    ]
    
    for pattern in patterns:
        match = re.match(pattern, value)
        if match:
            num = int(match.group(1))
            if 'week' in pattern:
                return num * 7
            elif 'month' in pattern:
                return num * 30
            elif 'year' in pattern:
                return num * 365
            else:
                return num
    
    return None


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
        import time
        
        query = self._build_search_query(args)
        search_paths = [args.scope]
        base_path = os.path.abspath(search_paths[0])
        output_fmt = getattr(args, 'output', 'yaml')
        mode_labels = {"filename": "filename", "content": "file content", "both": "filename + content"}
        search_type = mode_labels.get(query.search_mode, 'filename')

        collected = []
        collected_results = []
        interrupted = False
        show_preview = getattr(args, 'preview', False) and query.search_mode in ('content', 'both')
        
        # Progress tracking for large searches
        start_time = time.time()
        last_progress_time = start_time
        progress_interval = 2.0  # Show progress every 2 seconds
        files_scanned = 0
        
        try:
            iterator = (
                self.engine.search_iter(query, search_paths)
                if hasattr(self.engine, 'search_iter')
                else iter(self.engine.search(query, search_paths))
            )
            for result in iterator:
                collected.append(result.file_path)
                if show_preview or query.sort_by:
                    collected_results.append(result)
                files_scanned += 1
                
                # Show incremental progress for long searches
                current_time = time.time()
                if current_time - last_progress_time > progress_interval:
                    elapsed = current_time - start_time
                    print(f"# Scanning... {files_scanned} matches, {elapsed:.1f}s elapsed", file=sys.stderr)
                    # Show first few results early for user feedback
                    if len(collected) <= 10:
                        for p in collected[-3:]:
                            print(f"  -> {p}", file=sys.stderr)
                    last_progress_time = current_time
                    
        except KeyboardInterrupt:
            interrupted = True

        # Sort results if requested
        if query.sort_by and collected_results:
            sort_key = {
                'name': lambda r: r.file_path.lower(),
                'size': lambda r: r.size,
                'date': lambda r: r.timestamp,
            }.get(query.sort_by, lambda r: r.file_path.lower())
            collected_results.sort(key=sort_key)
            collected = [r.file_path for r in collected_results]

        # --output paths: one path per line, pipe-friendly
        if output_fmt == 'paths':
            for p in collected:
                print(p)
            if interrupted:
                print("# interrupted by user (Ctrl+C)", file=sys.stderr)
            return 0

        # Build scope_pattern: base_path + /*/* … showing depth spread of results
        if collected:
            depths = set()
            for p in collected:
                abs_p = os.path.abspath(p)
                try:
                    rel = os.path.relpath(abs_p, base_path)
                    parts = [x for x in rel.split(os.sep) if x and x != '.']
                    depths.add(len(parts))
                except ValueError:
                    depths.add(0)
            min_d, max_d = min(depths), max(depths)
            scope_pattern = base_path + (('/' + '/'.join(['*'] * max_d)) if max_d else '')
        else:
            scope_pattern = base_path
            min_d = max_d = 0

        depth_info = (f"{min_d} to {max_d}" if min_d != max_d else str(max_d)) + " level(s)"

        meta = {
            'scope': scope_pattern,
            'depth': depth_info,
            'query': query.query_text or None,
            'search_type': search_type,
            'depth_limit': query.max_depth,
            'excluded': query.exclude_dirs if query.exclude_dirs else None,
            'interrupted': True if interrupted else None,
            'total': len(collected),
            'results': collected if not show_preview else None,
            'matches': [
                {'path': r.file_path, 'snippet': SimpleSearchEngine.get_content_snippet(r.file_path, query.query_text, use_regex=query.use_regex)}
                for r in collected_results
            ] if show_preview else None,
        }
        meta = {k: v for k, v in meta.items() if v is not None}

        if output_fmt == 'json':
            print(_json.dumps(meta, ensure_ascii=False, indent=2))
        else:
            print(yaml.dump(meta, default_flow_style=False, allow_unicode=True, sort_keys=False))

        if interrupted:
            print("# interrupted by user (Ctrl+C)", file=sys.stderr)

        return 0
    
    def _build_search_query(self, args: argparse.Namespace) -> SearchQuery:
        """Build a SearchQuery from command-line arguments.
        
        Args:
            args: Command line arguments
            
        Returns:
            SearchQuery: Configured search query
        """
        # Handle date range - multiple options can be combined
        date_range = None
        end_date = None
        start_date = None
        
        # --last-days takes precedence
        if getattr(args, 'last_days', None):
            end_date = datetime.now()
            start_date = end_date - timedelta(days=args.last_days)
        elif getattr(args, 'last', None):
            # Parse human-readable date range like "week", "month", "yesterday"
            days = _parse_date_range(args.last)
            if days is not None:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
        else:
            # Check for --after-date and --before-date
            after_date_str = getattr(args, 'after_date', None)
            before_date_str = getattr(args, 'before_date', None)
            
            if after_date_str:
                try:
                    start_date = datetime.strptime(after_date_str, "%Y-%m-%d")
                except ValueError:
                    pass
            
            if before_date_str:
                try:
                    end_date = datetime.strptime(before_date_str, "%Y-%m-%d")
                    # Set to end of day
                    end_date = end_date.replace(hour=23, minute=59, second=59)
                except ValueError:
                    pass
        
        if start_date or end_date:
            # Default to now if only start date is specified
            if end_date is None:
                end_date = datetime.now()
            # Default to epoch if only end date is specified  
            if start_date is None:
                start_date = datetime(1970, 1, 1)
            date_range = (start_date, end_date)
        
        file_types = args.type.split(',') if args.type else []
        
        if getattr(args, 'content', False):
            search_mode = "content"
        elif getattr(args, 'filename', False):
            search_mode = "filename"
        else:
            search_mode = "filename"

        exclude_dirs = list(SearchQuery.__dataclass_fields__['exclude_dirs'].default_factory())
        if getattr(args, 'exclude', None):
            for e in args.exclude:
                for part in e.split(','):
                    part = part.strip()
                    if part and part not in exclude_dirs:
                        exclude_dirs.append(part)
        if getattr(args, 'no_exclude', False):
            exclude_dirs = []

        min_size = _parse_size(args.min_size) if getattr(args, 'min_size', None) else None
        max_size = _parse_size(args.max_size) if getattr(args, 'max_size', None) else None
        use_regex = getattr(args, 'regex', False)
        sort_by = getattr(args, 'sort', None)

        return SearchQuery(
            query_text=' '.join(args.query) if args.query else "",
            file_types=file_types,
            date_range=date_range,
            max_results=args.limit if args.limit > 0 else 10_000_000,
            include_previews=not args.no_preview,
            max_depth=args.depth,
            search_mode=search_mode,
            exclude_dirs=exclude_dirs,
            min_size=min_size,
            max_size=max_size,
            use_regex=use_regex,
            sort_by=sort_by,
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
        "--scope",
        "-s",
        "--path",
        "-p",
        default=".",
        help="Search scope directory (default: current directory)",
    )
    search_parser.add_argument(
        "--depth",
        "-d",
        type=int,
        help="Maximum depth to search",
    )
    search_parser.add_argument(
        "--last-days",
        type=int,
        help="Filter by last N days (or use --last for human-readable: today, yesterday, week, month, year)",
    )
    search_parser.add_argument(
        "--last",
        help="Human-readable date range: 'today', 'yesterday', 'week', 'month', 'year', '2weeks', '3months', etc.",
    )
    search_parser.add_argument(
        "--after-date",
        help="Filter by files modified after date (YYYY-MM-DD)",
    )
    search_parser.add_argument(
        "--before-date",
        help="Filter by files modified before date (YYYY-MM-DD)",
    )
    search_parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=4,
        help="Number of worker threads for parallel search (default: 4)",
    )
    search_parser.add_argument(
        "--filename",
        "-f",
        action="store_true",
        help="Search by filename (default behaviour)",
    )
    search_parser.add_argument(
        "--content",
        "-c",
        action="store_true",
        help="Search in file contents",
    )
    search_parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=0,
        help="Maximum number of results (default: 0 = unlimited)",
    )
    search_parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Disable preview generation",
    )
    search_parser.add_argument(
        "--min-size",
        metavar="SIZE",
        help="Minimum file size (e.g. 1k, 10MB, 1G)",
    )
    search_parser.add_argument(
        "--max-size",
        metavar="SIZE",
        help="Maximum file size (e.g. 100k, 5MB)",
    )
    search_parser.add_argument(
        "--regex",
        "-r",
        action="store_true",
        help="Treat query as a regular expression",
    )
    search_parser.add_argument(
        "--sort",
        choices=["name", "size", "date"],
        help="Sort results by name, size, or date",
    )
    search_parser.add_argument(
        "--preview",
        "-P",
        action="store_true",
        help="Show content snippet with line number for -c matches",
    )
    search_parser.add_argument(
        "--exclude",
        "-e",
        action="append",
        metavar="DIR",
        help="Exclude directory name(s), comma-separated. Can be repeated. Default excludes: .git .venv __pycache__ dist node_modules",
    )
    search_parser.add_argument(
        "--no-exclude",
        action="store_true",
        help="Disable all default directory exclusions",
    )
    search_parser.add_argument(
        "--output",
        "-o",
        help="Output format (yaml, json, paths)",
        choices=["yaml", "json", "paths"],
        default="yaml",
    )
    
    # Interactive command
    subparsers.add_parser(
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
    help_parser.add_argument("topic", nargs="?", help="Command to show help for")
    
    return parser


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    
    if args is None:
        args = sys.argv[1:]
        
    # If the first argument is not a known command, assume it's a search query or search flags
    known_commands = {"search", "interactive", "i", "shell", "batch", "version", "help"}
    if args and args[0] not in known_commands:
        args = ["search"] + args
        
    parsed_args = parser.parse_args(args)
    
    if not parsed_args.command:
        parser.print_help()
        return 0

    if parsed_args.command == "help":
        if getattr(parsed_args, "topic", None):
            parser.parse_args([parsed_args.topic, "--help"])
        else:
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
