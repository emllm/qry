## [Unreleased]

### Added
- Streaming search via `search_iter()` — results yielded one at a time, Ctrl+C stops mid-search and outputs partial YAML/JSON
- `--exclude DIR` / `-e DIR` flag — add extra directories to skip (repeatable, comma-separated)
- `--no-exclude` flag — disable all default directory exclusions
- Default exclusions: `.git`, `.venv`, `__pycache__`, `dist`, `node_modules`, `.tox`, `.mypy_cache`
- `--output json` flag — JSON output in addition to YAML
- Public Python API: `qry.search()` and `qry.search_iter()` — importable functions for use in other applications
- `excluded` field in YAML/JSON output showing active exclusion list

### Changed
- Default result limit changed from 100 to unlimited (use `-l N` to cap)
- Output format changed from plain text to YAML (default) or JSON (`-o json`)
- `search_command` now streams results through generator instead of collecting all first

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


