## [Unreleased]

### Added
- **Streaming search** via `search_iter()` — results yielded one at a time, Ctrl+C stops mid-search and outputs partial YAML/JSON
- **Directory exclusions** — `--exclude DIR` / `-e DIR` flag (repeatable, comma-separated); `--no-exclude` to disable defaults
- Default exclusions: `.git`, `.venv`, `__pycache__`, `dist`, `node_modules`, `.tox`, `.mypy_cache`
- **Output formats** — `--output yaml` (default), `--output json`, `--output paths` (one path per line, pipe-friendly)
- **Python API** — `qry.search()` and `qry.search_iter()` importable functions for use in other applications
- **Regex search** — `--regex` / `-r` flag treats query as a regular expression (filenames and content)
- **Size filtering** — `--min-size SIZE` / `--max-size SIZE` with human-readable units (1k, 10MB, 1G)
- **Sort results** — `--sort name|size|date` for ordered output
- **Content preview** — `--preview` / `-p` shows matching line with context for content search (`-c`)
- `scope` field in output shows glob depth pattern (`/path/*/*/*`)
- `depth` field shows actual result depth range
- `excluded` field shows active exclusion list

### Changed
- Default result limit changed from 100 to unlimited (use `-l N` to cap)
- Output format changed from plain text to structured YAML/JSON
- Search engine uses generator (`search_iter`) internally for streaming
- Python API extended with `min_size`, `max_size`, `regex`, `sort_by` parameters

### Fixed
- Search results were never printed (only scope/depth summary was shown)

## [0.2.4] - 2026-02-21

### Summary

feat(docs): deep code analysis engine with 4 supporting modules

### Docs

- docs: update README

### Build

- update pyproject.toml

### Other

- update qry/cli/commands.py
- update qry/core/models.py
- update qry/engines/simple.py


## [0.2.3] - 2026-02-21

### Summary

refactor(goal): deep code analysis engine with 6 supporting modules

### Docs

- docs: update README

### Build

- update pyproject.toml

### Config

- config: update goal.yaml

### Other

- update qry/api/app.py
- update qry/cli/commands.py
- update qry/core/models.py
- update qry/engines/simple.py


## [0.2.2] - 2026-02-21

### Summary

feat(goal): deep code analysis engine with 7 supporting modules

### Test

- update tests/test_qry.py

### Config

- config: update goal.yaml


