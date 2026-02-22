## [0.2.11] - 2026-02-22

### Summary

feat(tests): test module improvements

### Test

- update tests/bench/test_performance.py


## [0.2.10] - 2026-02-22

### Summary

feat(docs): deep code analysis engine with 2 supporting modules

### Docs

- docs: update README

### Other

- update qry/engines/simple.py


## [0.2.9] - 2026-02-22

### Summary

feat(priority): Priority-based search with incremental results and timeout fallback

### Priority-based Search
- Added `Priority` enum with 11 levels (SOURCE=100 to EXCLUDED=0)
- Directories categorized: src/ (100), tests/ (90), config/ (80), main/ (70), etc.
- Searches important directories first, cache/temp directories last

### Incremental Search
- Added `incremental_timeout` parameter (default: 1.0 second)
- Shows results immediately as they're found
- If no results after timeout, automatically expands to lower priority directories
- Ensures users find what they're looking for quickly

### New Parameters
- `priority_mode` - Enable priority-based search
- `priority_callback` - Callback for priority level changes
- `incremental_timeout` - Seconds to wait before expanding search

### Other

- update qry/engines/simple.py


## [0.2.8] - 2026-02-22

### Summary

perf(search): Major performance optimizations - caching, parallel processing, date-based directory pruning

### Performance Improvements
- **File stat caching** - Added `@lru_cache` for `os.stat()` calls to avoid repeated filesystem operations
- **Regex pattern caching** - Compiled regex patterns are cached to avoid recompilation
- **Parallel directory processing** - Added `ThreadPoolExecutor` for concurrent file processing in multiple directories
- **Date-based directory pruning** - Directories with date patterns in names (e.g., `2024-01-15`) are skipped early if outside the date range

### New CLI Options
- `--after-date YYYY-MM-DD` - Filter files modified after a specific date
- `--before-date YYYY-MM-DD` - Filter files modified before a specific date
- `-w N` / `--workers N` - Number of worker threads for parallel search (default: 4)

### Other

- build: update Makefile
- update qry/cli/commands.py
- update qry/engines/simple.py


## [0.2.7] - 2026-02-21

### Summary

feat(docs): deep code analysis engine with 4 supporting modules

### Docs

- docs: update EXAMPLES.md
- docs: update README

### Build

- update pyproject.toml

### Other

- update qry/__init__.py


## [0.2.5] - 2026-02-21

### Added
- **Streaming search** via `search_iter()` — results yielded one at a time, Ctrl+C stops mid-search and outputs partial YAML/JSON
- **Directory exclusions** — `--exclude DIR` / `-e DIR` flag (repeatable, comma-separated); `--no-exclude` to disable defaults
- Default exclusions: `.git`, `.venv`, `__pycache__`, `dist`, `node_modules`, `.tox`, `.mypy_cache`
- **Output formats** — `--output yaml` (default), `--output json`, `--output paths` (one path per line, pipe-friendly)
- **Python API** — `qry.search()` and `qry.search_iter()` importable functions for use in other applications
- **Regex search** — `--regex` / `-r` flag treats query as a regular expression (filenames and content)
- **Size filtering** — `--min-size SIZE` / `--max-size SIZE` with human-readable units (1k, 10MB, 1G)
- **Sort results** — `--sort name|size|date` for ordered output
- **Content preview** — `--preview` / `-P` shows matching line with context for content search (`-c`)
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
- Version synced between `pyproject.toml` and `qry/__init__.py`

### Tests
- Test suite expanded from 2 to 22 tests covering: Python API, content search, regex, size filtering, sort, exclusions, snippets, `_parse_size`

### Docs
- `README.md` rewritten with full CLI reference, flag tables, Python API with parameter docs
- `EXAMPLES.md` rewritten from scratch — all examples use real, working `qry` commands
- `CHANGELOG.md` updated with all changes

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


