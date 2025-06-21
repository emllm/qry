"""Qry - Ultra-fast file search and processing tool."""

import argparse
import sys
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Any, Dict, Union

# Import core components
from qry.core.models import SearchQuery, SearchResult, ContentType, FileType
from qry.engines import get_default_engine, get_available_engines, SearchEngine
from qry.cli.commands import CLICommands, create_parser
from qry.cli.interactive import run_interactive
from qry.cli.batch import run_batch

# ===============================================
# MAIN ENTRY POINT
# ===============================================

def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI.
    
    Args:
        args: Command line arguments (defaults to sys.argv[1:])
        
    Returns:
        int: Exit code (0 for success, non-zero for errors)
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)
    
    # Handle version flag
    if hasattr(parsed_args, 'version') and parsed_args.version:
        from qry import __version__
        print(f"qry version {__version__}")
        return 0
    
    # Initialize CLI commands handler
    cli = CLICommands()
    
    # Route to appropriate command handler
    if hasattr(parsed_args, 'command'):
        if parsed_args.command == 'search':
            return cli.search_command(parsed_args)
        elif parsed_args.command == 'interactive':
            return run_interactive()
        elif parsed_args.command == 'batch':
            return run_batch(parsed_args)
    
    # If no command was matched, show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
