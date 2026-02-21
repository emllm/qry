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
qry search [query ...] [--type EXT1,EXT2] [--scope PATH] [--depth N]
           [--last-days N] [--limit N] [--output text|json|html]

qry interactive
qry batch <input_file> [--output-file FILE] [--format text|json|csv] [--workers N]
qry version
```

Examples:

```bash
poetry run qry "invoice OR faktura" --scope /data/docs --depth 3
poetry run qry search "report" --type pdf,docx --last-days 7
poetry run qry batch queries.txt --format json --output-file results.json
```

## API usage

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
