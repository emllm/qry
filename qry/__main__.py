#!/usr/bin/env python3
"""
Qry - Ultra-fast file search and processing tool.

This module provides the entry point for the 'python -m qry' command.
"""

import sys
from qry.cli.commands import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
