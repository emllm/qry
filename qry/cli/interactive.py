"""Interactive command-line interface for qry."""
import os
import sys
import cmd
import shlex
from typing import List, Optional, Dict, Any
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter, PathCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style

from ..core.models import SearchQuery
from ..engines import get_default_engine, get_available_engines
from ..web.renderer import HTMLRenderer


class InteractiveCLI(cmd.Cmd):
    """Interactive command-line interface for qry."""
    
    prompt = 'qry> '
    doc_header = 'Available commands (type help <command>):'
    ruler = '-' * 80
    
    def __init__(self, engine=None):
        """Initialize the interactive CLI."""
        super().__init__()
        self.engine = engine or get_default_engine()
        self.available_engines = get_available_engines()
        self.current_engine = self.engine.get_name()
        self.current_dir = str(Path.cwd())
        self.history_file = os.path.expanduser('~/.qry_history')
        self.session = self._create_session()
        self.renderer = HTMLRenderer()
        
        # Command history and completion
        self.commands = [
            'search', 'set', 'engine', 'cd', 'pwd', 'ls', 'clear', 'exit', 'help'
        ]
        self.search_options = [
            '--type', '--last-days', '--limit', '--output', '--no-preview'
        ]
        self.set_commands = [
            'engine', 'output', 'limit', 'preview'
        ]
        
        # Current search context
        self.last_results = []
        self.current_page = 0
        self.page_size = 10
    
    def _create_session(self):
        """Create a prompt session with history and completion."""
        # Ensure history file exists
        Path(self.history_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Define completion
        commands = WordCompleter(self.commands, ignore_case=True)
        
        return PromptSession(
            history=FileHistory(self.history_file),
            completer=commands,
            auto_suggest=AutoSuggestFromHistory(),
            style=Style.from_dict({
                'prompt': '#ff0066',
                'bottom-toolbar': 'bg:#222222 #ffffff',
            })
        )
    
    def cmdloop(self, intro=None):
        """Override cmdloop to use prompt_toolkit."""
        print("\nQRY Interactive Mode")
        print("Type 'help' for a list of commands, 'exit' to quit\n")
        
        while True:
            try:
                # Get input with prompt_toolkit
                try:
                    text = self.session.prompt(
                        f"qry({self.current_engine}) {self.current_dir}> "
                    ).strip()
                except EOFError:
                    break  # Ctrl-D
                
                if not text:
                    continue
                
                # Special case for 'exit'
                if text.lower() in ('exit', 'quit'):
                    break
                    
                # Process the command
                self.onecmd(text)
                
            except KeyboardInterrupt:
                print("^C")
            except Exception as e:
                print(f"Error: {e}")
    
    def emptyline(self):
        """Do nothing on empty input."""
        pass
    
    def default(self, line):
        """Handle unknown commands as search queries."""
        if line.startswith('!'):
            # Execute shell command
            os.system(line[1:])
        else:
            # Treat as search query
            self.do_search(line)
    
    def do_search(self, arg):
        """
        Search for files.
        
        Usage: search [query] [options]
        
        Options:
          --type TYPE1,TYPE2  Filter by file type
          --last-days DAYS   Filter by last N days
          --limit N          Maximum number of results (default: 10)
          --output FORMAT    Output format (text, json, html)
          --no-preview       Disable preview generation
        """
        try:
            # Parse arguments
            args = self._parse_search_args(arg)
            
            # Build search query
            query = SearchQuery(
                query_text=args.get('query', ''),
                file_types=args.get('types', []),
                max_results=args.get('limit', 10),
                include_previews=not args.get('no_preview', False)
            )
            
            # Execute search
            print(f"Searching for: {query.query_text}")
            results = self.engine.search(query, [self.current_dir])
            self.last_results = results
            
            # Display results
            output_format = args.get('output', 'text')
            self._display_results(results, output_format)
            
        except Exception as e:
            print(f"Error: {e}")
    
    def _parse_search_args(self, arg_str: str) -> Dict[str, Any]:
        """Parse search command arguments."""
        args = {'query': '', 'types': [], 'limit': 10, 'output': 'text', 'no_preview': False}
        
        # Split arguments while handling quoted strings
        try:
            parts = shlex.split(arg_str)
        except ValueError as e:
            print(f"Error parsing arguments: {e}")
            return args
        
        i = 0
        query_parts = []
        
        while i < len(parts):
            part = parts[i]
            
            if part == '--type':
                if i + 1 < len(parts):
                    args['types'] = parts[i+1].split(',')
                    i += 2
                else:
                    print("Error: --type requires a value")
                    break
            elif part == '--last-days':
                if i + 1 < len(parts):
                    try:
                        args['last_days'] = int(parts[i+1])
                        i += 2
                    except ValueError:
                        print("Error: --last-days requires a number")
                        break
                else:
                    print("Error: --last-days requires a value")
                    break
            elif part == '--limit':
                if i + 1 < len(parts):
                    try:
                        args['limit'] = int(parts[i+1])
                        i += 2
                    except ValueError:
                        print("Error: --limit requires a number")
                        break
                else:
                    print("Error: --limit requires a value")
                    break
            elif part == '--output':
                if i + 1 < len(parts) and parts[i+1] in ('text', 'json', 'html'):
                    args['output'] = parts[i+1]
                    i += 2
                else:
                    print("Error: --output requires one of: text, json, html")
                    break
            elif part == '--no-preview':
                args['no_preview'] = True
                i += 1
            else:
                query_parts.append(part)
                i += 1
        
        args['query'] = ' '.join(query_parts)
        return args
    
    def _display_results(self, results: List[Any], output_format: str = 'text'):
        """Display search results in the specified format."""
        if not results:
            print("No results found.")
            return
        
        if output_format == 'json':
            import json
            print(json.dumps([r.dict() for r in results], indent=2))
        elif output_format == 'html':
            query = SearchQuery(query_text="")
            html = self.renderer.render_search_results(results, query)
            output_file = "search_results.html"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"Results saved to {output_file}")
        else:  # text
            for i, result in enumerate(results, 1):
                print(f"{i}. {result.file_path}")
                if hasattr(result, 'metadata') and result.metadata:
                    for k, v in result.metadata.items():
                        print(f"   {k}: {v}")
    
    def do_set(self, arg):
        """
        Set configuration options.
        
        Usage: set <option> <value>
        
        Options:
          engine <name>    Set the search engine
          output <format>  Set default output format (text, json, html)
          limit <number>   Set default result limit
          preview <on|off> Toggle preview generation
        """
        args = arg.split()
        if len(args) < 2:
            print("Usage: set <option> <value>")
            return
            
        option = args[0].lower()
        value = ' '.join(args[1:])
        
        if option == 'engine':
            if value in self.available_engines:
                self.engine = self.available_engines[value]()
                self.current_engine = value
                print(f"Engine set to: {value}")
            else:
                print(f"Unknown engine: {value}. Available engines: {', '.join(self.available_engines.keys())}")
        elif option == 'output':
            if value in ('text', 'json', 'html'):
                print(f"Output format set to: {value}")
            else:
                print("Invalid output format. Must be one of: text, json, html")
        elif option == 'limit':
            try:
                limit = int(value)
                if limit > 0:
                    print(f"Result limit set to: {limit}")
                else:
                    print("Limit must be greater than 0")
            except ValueError:
                print("Invalid limit. Must be a number.")
        elif option == 'preview':
            if value.lower() in ('on', 'off'):
                print(f"Preview generation turned {value}")
            else:
                print("Invalid value. Use 'on' or 'off'.")
        else:
            print(f"Unknown option: {option}")
    
    def do_engine(self, arg):
        """List available search engines or set the current engine."""
        if not arg:
            print("Available search engines:")
            for name, engine in self.available_engines.items():
                status = " (current)" if name == self.current_engine else ""
                print(f"  {name}{status}")
        else:
            self.do_set(f"engine {arg}")
    
    def do_cd(self, arg):
        """Change the current working directory."""
        try:
            if not arg:
                new_dir = os.path.expanduser('~')
            else:
                new_dir = os.path.abspath(os.path.join(self.current_dir, arg))
            
            if os.path.isdir(new_dir):
                os.chdir(new_dir)
                self.current_dir = os.getcwd()
                print(f"Current directory: {self.current_dir}")
            else:
                print(f"Directory not found: {new_dir}")
        except Exception as e:
            print(f"Error: {e}")
    
    def do_pwd(self, arg):
        """Print the current working directory."""
        print(self.current_dir)
    
    def do_ls(self, arg):
        """List directory contents."""
        try:
            path = os.path.join(self.current_dir, arg) if arg else self.current_dir
            for item in sorted(os.listdir(path)):
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    print(f"{item}/")
                else:
                    print(item)
        except Exception as e:
            print(f"Error: {e}")
    
    def do_clear(self, arg):
        """Clear the screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def do_exit(self, arg):
        """Exit the interactive shell."""
        print("Goodbye!")
        return True
    
    def help_search(self):
        """Show help for the search command."""
        print("\n".join([
            "search [query] [options]",
            "",
            "Search for files matching the query.",
            "",
            "Options:",
            "  --type TYPE1,TYPE2  Filter by file type",
            "  --last-days DAYS   Filter by last N days",
            "  --limit N          Maximum number of results (default: 10)",
            "  --output FORMAT    Output format (text, json, html)",
            "  --no-preview       Disable preview generation",
            "",
            "Examples:",
            "  search invoice --type pdf --last-days 30",
            '  search "report" --output html'
        ]))


def run_interactive(engine=None):
    """Run the interactive command-line interface."""
    try:
        cli = InteractiveCLI(engine)
        cli.cmdloop()
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0
