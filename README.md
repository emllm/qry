# qry

[![CI](https://github.com/emllm/qry/actions/workflows/ci.yml/badge.svg)](https://github.com/emllm/qry/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](pyproject.toml)

Ultra-fast file search and metadata extraction tool.

## Features

- Fast filesystem search with optional depth and date filters
- CLI modes: `search`, `interactive`, `batch`, `version`
- HTTP API (FastAPI) for JSON and HTML search responses
- Metadata extraction for matched files (size, timestamps, content type)
- **Streaming results** — Ctrl+C stops search mid-way and outputs what was found so far
- **Smart directory exclusions** — `.git`, `.venv`, `__pycache__`, `dist`, `node_modules` skipped by default
- **YAML and JSON output** — machine-readable output for piping into other tools
- **Python API** — `import qry; qry.search(...)` for use in other applications

## Installation

### Poetry (recommended)

```bash
poetry install --with dev
```

### pip (minimal)

```bash
pip install -r requirements.txt
```

## Quick start

```bash
# search in current directory
poetry run qry "invoice"

# search with scope/depth limit
poetry run qry "README" --scope . --depth 2 --limit 20

# show version and engines
poetry run qry version
```

## CLI usage

```bash
qry search [query ...] [-f] [-c] [--type EXT1,EXT2] [--scope PATH] [--depth N]
           [--last-days N] [--limit N] [--exclude DIR] [--no-exclude]
           [--output yaml|json]

qry interactive
qry batch <input_file> [--output-file FILE] [--format text|json|csv] [--workers N]
qry version
```

Search mode flags:

| Flag | Long form | Searches |
|------|-----------|----------|
| (none) | | filename (default) |
| `-f` | `--filename` | filename only |
| `-c` | `--content` | file contents |
| `-c -f` | `--content --filename` | both (use `--both` alias) |

Output / filtering flags:

| Flag | Description |
|------|-------------|
| `-o yaml` | YAML output (default) |
| `-o json` | JSON output |
| `-e DIR` | Exclude extra directory (repeatable, comma-separated) |
| `--no-exclude` | Disable all default exclusions |
| `-l N` | Limit results (0 = unlimited, default) |
| `-d N` | Max directory depth |

Default excluded directories: `.git` `.venv` `__pycache__` `dist` `node_modules` `.tox` `.mypy_cache`

Examples:

```bash
# search by filename (default)
poetry run qry "invoice"

# search inside file contents — press Ctrl+C to stop early
poetry run qry "def search" -c
poetry run qry "TODO OR FIXME" -c --type py --scope ./src

# JSON output for piping
poetry run qry "invoice" -o json | jq '.results[]'

# exclude extra directories
poetry run qry "config" -e build -e ".cache"

# disable all exclusions (search everything)
poetry run qry "config" --no-exclude

# combine scope/depth/type/date
poetry run qry "invoice OR faktura" --scope /data/docs --depth 3
poetry run qry search "report" --type pdf,docx --last-days 7
poetry run qry batch queries.txt --format json --output-file results.json
```

## Python API

Use `qry` directly from Python — no subprocess needed:

```python
import qry

# Return all matching file paths as a list
files = qry.search("invoice", scope="/data/docs", mode="content", depth=3)

# Stream results one at a time (memory-efficient, supports Ctrl+C)
for path in qry.search_iter("TODO", scope="./src", mode="content"):
    print(path)

# Filename search with type filter
py_files = qry.search("models", scope=".", mode="filename", file_types=["py"])

# Custom exclusions
files = qry.search("config", exclude_dirs=[".git", "build", ".venv"])
```

Parameters for both `qry.search()` and `qry.search_iter()`:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query_text` | str | — | Text to search for |
| `scope` | str | `"."` | Directory to search |
| `mode` | str | `"filename"` | `"filename"`, `"content"`, or `"both"` |
| `depth` | int\|None | `None` | Max directory depth |
| `file_types` | list\|None | `None` | Extensions to include, e.g. `["py","txt"]` |
| `exclude_dirs` | list\|None | `None` | Dir names to skip (None = use defaults) |
| `max_results` | int | unlimited | Hard cap on results |

## HTTP API usage

Run server:

```bash
poetry run qry-api --host 127.0.0.1 --port 8000
```

Main endpoints:

- `GET /api/search`
- `GET /api/search/html`
- `GET /api/engines`
- `GET /api/health`
- OpenAPI docs: `GET /api/docs`

## Development

### Run tests

```bash
poetry run pytest -q
```

### Useful make targets

```bash
make install
make test
make lint
make type-check
make run-api
```

## Project structure

- `qry/cli/` – CLI commands and interactive mode
- `qry/api/` – FastAPI application and routes
- `qry/core/` – core data models
- `qry/engines/` – search engine implementations
- `qry/web/` – HTML renderer/templates integration
- `tests/` – test suite

## Additional docs

- Usage examples: [EXAMPLES.md](EXAMPLES.md)

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)
