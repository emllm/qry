"""Fast file content search algorithms with benchmarks.

Implements and compares:
- str.find (baseline)
- Boyer-Moore-Horspool
- Knuth-Morris-Pratt (KMP)
- Aho-Corasick (multi-pattern)
- mmap + re (memory-mapped regex)
- Whoosh full-text index (if available)
"""
import mmap
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Algorithm implementations
# ---------------------------------------------------------------------------

def _build_bmh_table(pattern: bytes) -> Dict[int, int]:
    m = len(pattern)
    table = {b: m for b in range(256)}
    for i in range(m - 1):
        table[pattern[i]] = m - 1 - i
    return table


def bmh_search(text: bytes, pattern: bytes) -> List[int]:
    """Boyer-Moore-Horspool – O(n/m) average."""
    n, m = len(text), len(pattern)
    if m == 0 or m > n:
        return []
    table = _build_bmh_table(pattern)
    positions = []
    i = m - 1
    while i < n:
        j = m - 1
        k = i
        while j >= 0 and text[k] == pattern[j]:
            j -= 1
            k -= 1
        if j == -1:
            positions.append(k + 1)
        i += table[text[i]]
    return positions


def _build_kmp_table(pattern: bytes) -> List[int]:
    m = len(pattern)
    table = [0] * m
    j = 0
    for i in range(1, m):
        while j > 0 and pattern[i] != pattern[j]:
            j = table[j - 1]
        if pattern[i] == pattern[j]:
            j += 1
        table[i] = j
    return table


def kmp_search(text: bytes, pattern: bytes) -> List[int]:
    """Knuth-Morris-Pratt – O(n+m)."""
    n, m = len(text), len(pattern)
    if m == 0:
        return []
    table = _build_kmp_table(pattern)
    positions = []
    j = 0
    for i in range(n):
        while j > 0 and text[i] != pattern[j]:
            j = table[j - 1]
        if text[i] == pattern[j]:
            j += 1
        if j == m:
            positions.append(i - m + 1)
            j = table[j - 1]
    return positions


class AhoCorasick:
    """Aho-Corasick automaton for multi-pattern search – O(n + total_matches)."""

    def __init__(self, patterns: List[bytes]):
        self.goto: List[Dict[int, int]] = [{}]
        self.fail: List[int] = [0]
        self.output: List[List[bytes]] = [[]]
        self._build(patterns)

    def _build(self, patterns: List[bytes]):
        for pat in patterns:
            cur = 0
            for ch in pat:
                if ch not in self.goto[cur]:
                    self.goto[cur][ch] = len(self.goto)
                    self.goto.append({})
                    self.fail.append(0)
                    self.output.append([])
                cur = self.goto[cur][ch]
            self.output[cur].append(pat)

        queue = list(self.goto[0].values())
        while queue:
            r = queue.pop(0)
            for ch, s in self.goto[r].items():
                queue.append(s)
                state = self.fail[r]
                while state and ch not in self.goto[state]:
                    state = self.fail[state]
                self.fail[s] = self.goto[state].get(ch, 0)
                if self.fail[s] == s:
                    self.fail[s] = 0
                self.output[s] = self.output[s] + self.output[self.fail[s]]

    def search(self, text: bytes) -> List[Tuple[int, bytes]]:
        cur = 0
        results = []
        for i, ch in enumerate(text):
            while cur and ch not in self.goto[cur]:
                cur = self.fail[cur]
            cur = self.goto[cur].get(ch, 0)
            for pat in self.output[cur]:
                results.append((i - len(pat) + 1, pat))
        return results


def mmap_regex_search(file_path: str, pattern: str) -> List[int]:
    """Memory-mapped file search using compiled regex – avoids full read."""
    compiled = re.compile(pattern.encode(), re.IGNORECASE)
    positions = []
    try:
        with open(file_path, 'rb') as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                for m in compiled.finditer(mm):
                    positions.append(m.start())
    except (ValueError, OSError):
        pass
    return positions


def str_find_search(text: bytes, pattern: bytes) -> List[int]:
    """Baseline: built-in str.find loop (CPython C implementation)."""
    positions = []
    start = 0
    while True:
        idx = text.find(pattern, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + 1
    return positions


# ---------------------------------------------------------------------------
# High-level file searcher using the best algorithm
# ---------------------------------------------------------------------------

class FastContentSearcher:
    """Search file contents using the fastest available algorithm.

    Algorithm selection:
    - Single pattern, small files  → str.find (CPython C, very fast)
    - Single pattern, large files  → mmap + regex (no full read)
    - Multiple patterns            → Aho-Corasick
    """

    def search_file(
        self,
        file_path: str,
        patterns: List[str],
        case_sensitive: bool = False,
    ) -> bool:
        """Return True if any pattern is found in the file."""
        if not patterns:
            return True
        try:
            size = os.path.getsize(file_path)
        except OSError:
            return False

        if len(patterns) > 1:
            return self._aho_corasick_file(file_path, patterns, case_sensitive)
        elif size > 4 * 1024 * 1024:  # > 4 MB → mmap
            return bool(mmap_regex_search(file_path, re.escape(patterns[0])))
        else:
            return self._str_find_file(file_path, patterns[0], case_sensitive)

    def _str_find_file(self, file_path: str, pattern: str, case_sensitive: bool) -> bool:
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            needle = pattern.encode('utf-8', errors='ignore')
            if not case_sensitive:
                return needle.lower() in data.lower()
            return needle in data
        except OSError:
            return False

    def _aho_corasick_file(self, file_path: str, patterns: List[str], case_sensitive: bool) -> bool:
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            if not case_sensitive:
                data = data.lower()
            needles = [p.lower().encode() if not case_sensitive else p.encode() for p in patterns]
            ac = AhoCorasick(needles)
            return bool(ac.search(data))
        except OSError:
            return False


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

def run_benchmark(
    search_dir: str,
    pattern: str,
    max_files: int = 200,
) -> None:
    """Compare all algorithms on real files in search_dir."""
    files: List[str] = []
    for root, _, fnames in os.walk(search_dir):
        for fname in fnames:
            fp = os.path.join(root, fname)
            try:
                if os.path.getsize(fp) < 10 * 1024 * 1024:  # skip >10 MB
                    files.append(fp)
            except OSError:
                pass
        if len(files) >= max_files:
            break
    files = files[:max_files]

    pat_bytes = pattern.lower().encode()

    algorithms: List[Tuple[str, object]] = [
        ("str.find (baseline)", lambda t, p: str_find_search(t, p)),
        ("Boyer-Moore-Horspool", lambda t, p: bmh_search(t, p)),
        ("KMP", lambda t, p: kmp_search(t, p)),
    ]

    print(f"\n{'='*60}")
    print(f"Benchmark: pattern='{pattern}', files={len(files)}")
    print(f"{'='*60}")
    print(f"{'Algorithm':<28} {'Time (s)':>10} {'Matches':>10}")
    print(f"{'-'*28} {'-'*10} {'-'*10}")

    # Pre-read files to avoid I/O bias
    corpus: List[bytes] = []
    for fp in files:
        try:
            with open(fp, 'rb') as f:
                corpus.append(f.read().lower())
        except OSError:
            corpus.append(b'')

    for name, algo in algorithms:
        t0 = time.perf_counter()
        total_matches = 0
        for data in corpus:
            total_matches += len(algo(data, pat_bytes))
        elapsed = time.perf_counter() - t0
        print(f"{name:<28} {elapsed:>10.4f} {total_matches:>10}")

    # mmap (reads files itself)
    pat_re = re.escape(pattern)
    t0 = time.perf_counter()
    mmap_matches = sum(len(mmap_regex_search(fp, pat_re)) for fp in files)
    mmap_elapsed = time.perf_counter() - t0
    print(f"{'mmap + regex':<28} {mmap_elapsed:>10.4f} {mmap_matches:>10}")

    # Aho-Corasick (multi-pattern, single pattern here for fair comparison)
    ac = AhoCorasick([pat_bytes])
    t0 = time.perf_counter()
    ac_matches = sum(len(ac.search(data)) for data in corpus)
    ac_elapsed = time.perf_counter() - t0
    print(f"{'Aho-Corasick':<28} {ac_elapsed:>10.4f} {ac_matches:>10}")

    # Whoosh (optional)
    try:
        _benchmark_whoosh(files, pattern)
    except ImportError:
        print(f"{'Whoosh':<28} {'not installed':>10}")

    print(f"{'='*60}\n")


def _benchmark_whoosh(files: List[str], pattern: str) -> None:
    import tempfile
    from whoosh.fields import ID, TEXT, Schema
    from whoosh.index import create_in
    from whoosh.qparser import QueryParser

    schema = Schema(path=ID(stored=True), content=TEXT)
    tmpdir = tempfile.mkdtemp()
    ix = create_in(tmpdir, schema)
    writer = ix.writer()
    for fp in files:
        try:
            with open(fp, 'r', errors='ignore') as f:
                writer.add_document(path=fp, content=f.read())
        except OSError:
            pass
    t_index = time.perf_counter()
    writer.commit()
    t_index = time.perf_counter() - t_index

    t0 = time.perf_counter()
    with ix.searcher() as searcher:
        q = QueryParser("content", ix.schema).parse(pattern)
        results = searcher.search(q, limit=None)
        count = len(results)
    elapsed = time.perf_counter() - t0
    print(f"{'Whoosh (query only)':<28} {elapsed:>10.4f} {count:>10}  (index built in {t_index:.2f}s)")


if __name__ == "__main__":
    import sys
    search_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    pattern = sys.argv[2] if len(sys.argv) > 2 else "def "
    run_benchmark(search_dir, pattern)
