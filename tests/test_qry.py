"""Tests for qry search functionality."""
import os
import tempfile
import textwrap

import pytest


def test_import():
    """Verify the main package can be imported."""
    import qry
    assert hasattr(qry, '__version__')
    assert hasattr(qry, 'search')
    assert hasattr(qry, 'search_iter')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_tree(tmp_path):
    """Create a small file tree for testing."""
    (tmp_path / "hello.py").write_text("# hello world\ndef search(): pass\n")
    (tmp_path / "readme.md").write_text("# README\nSome docs here\n")
    (tmp_path / "big.bin").write_bytes(b"\x00" * 2048)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_text("deep file content with search keyword\n")
    (sub / "notes.py").write_text("# notes\nimport os\n")
    hidden = tmp_path / ".git"
    hidden.mkdir()
    (hidden / "config").write_text("git config\n")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "mod.cpython-313.pyc").write_bytes(b"\x00" * 100)
    return tmp_path


# ---------------------------------------------------------------------------
# Python API tests
# ---------------------------------------------------------------------------

class TestSearch:
    def test_filename_search(self, sample_tree):
        import qry
        results = qry.search("hello", scope=str(sample_tree), mode="filename")
        assert any("hello.py" in r for r in results)

    def test_content_search(self, sample_tree):
        import qry
        results = qry.search("search", scope=str(sample_tree), mode="content")
        assert any("hello.py" in r for r in results)
        assert any("deep.txt" in r for r in results)

    def test_depth_limit(self, sample_tree):
        import qry
        results = qry.search("", scope=str(sample_tree), depth=0)
        # depth 0 = only files in the root of sample_tree
        for r in results:
            rel = os.path.relpath(r, str(sample_tree))
            assert os.sep not in rel, f"depth=0 should not include subdirs: {rel}"

    def test_file_types(self, sample_tree):
        import qry
        results = qry.search("", scope=str(sample_tree), file_types=["py"])
        assert all(r.endswith(".py") for r in results)
        assert len(results) >= 2  # hello.py + notes.py

    def test_exclude_dirs(self, sample_tree):
        import qry
        results = qry.search("", scope=str(sample_tree))
        paths_str = " ".join(results)
        assert ".git" not in paths_str
        assert "__pycache__" not in paths_str

    def test_no_exclude(self, sample_tree):
        import qry
        results = qry.search("", scope=str(sample_tree), exclude_dirs=[])
        paths_str = " ".join(results)
        assert ".git" in paths_str or "__pycache__" in paths_str

    def test_min_size(self, sample_tree):
        import qry
        results = qry.search("", scope=str(sample_tree), min_size=1024)
        assert any("big.bin" in r for r in results)
        assert not any("hello.py" in r for r in results)

    def test_max_size(self, sample_tree):
        import qry
        results = qry.search("", scope=str(sample_tree), max_size=100)
        assert not any("big.bin" in r for r in results)

    def test_regex_filename(self, sample_tree):
        import qry
        results = qry.search(r"\.py$", scope=str(sample_tree), regex=True)
        assert all(r.endswith(".py") for r in results)

    def test_regex_content(self, sample_tree):
        import qry
        results = qry.search(r"def \w+\(\)", scope=str(sample_tree), mode="content", regex=True)
        assert any("hello.py" in r for r in results)

    def test_sort_by_name(self, sample_tree):
        import qry
        results = qry.search("", scope=str(sample_tree), sort_by="name")
        assert results == sorted(results, key=lambda x: x.lower())

    def test_sort_by_size(self, sample_tree):
        import qry
        results = qry.search("", scope=str(sample_tree), sort_by="size")
        sizes = [os.path.getsize(r) for r in results]
        assert sizes == sorted(sizes)

    def test_search_iter(self, sample_tree):
        import qry
        gen = qry.search_iter("", scope=str(sample_tree))
        results = list(gen)
        assert len(results) > 0

    def test_or_query(self, sample_tree):
        import qry
        results = qry.search("hello or readme", scope=str(sample_tree), mode="filename")
        names = [os.path.basename(r) for r in results]
        assert "hello.py" in names
        assert "readme.md" in names


# ---------------------------------------------------------------------------
# Engine internals
# ---------------------------------------------------------------------------

class TestSimpleEngine:
    def test_content_snippet(self, sample_tree):
        from qry.engines.simple import SimpleSearchEngine
        snippet = SimpleSearchEngine.get_content_snippet(
            str(sample_tree / "hello.py"), "search"
        )
        assert snippet is not None
        assert "search" in snippet

    def test_content_snippet_regex(self, sample_tree):
        from qry.engines.simple import SimpleSearchEngine
        snippet = SimpleSearchEngine.get_content_snippet(
            str(sample_tree / "hello.py"), r"def \w+", use_regex=True
        )
        assert snippet is not None
        assert "def" in snippet

    def test_content_snippet_not_found(self, sample_tree):
        from qry.engines.simple import SimpleSearchEngine
        snippet = SimpleSearchEngine.get_content_snippet(
            str(sample_tree / "hello.py"), "nonexistent_xyz_42"
        )
        assert snippet is None


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

class TestParseSize:
    def test_bytes(self):
        from qry.cli.commands import _parse_size
        assert _parse_size("100") == 100
        assert _parse_size("100b") == 100

    def test_kilobytes(self):
        from qry.cli.commands import _parse_size
        assert _parse_size("1k") == 1024
        assert _parse_size("10KB") == 10240

    def test_megabytes(self):
        from qry.cli.commands import _parse_size
        assert _parse_size("1m") == 1024 ** 2
        assert _parse_size("5MB") == 5 * 1024 ** 2

    def test_gigabytes(self):
        from qry.cli.commands import _parse_size
        assert _parse_size("1G") == 1024 ** 3
        assert _parse_size("2gb") == 2 * 1024 ** 3
