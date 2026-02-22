"""Performance benchmarks for qry search.

Run with: pytest tests/bench/test_performance.py -v
Or: python tests/bench/test_performance.py
"""
import os
import tempfile
import time
import timeit
from pathlib import Path
from datetime import datetime, timedelta

import qry
from qry.engines.simple import SimpleSearchEngine
from qry.core.models import SearchQuery


def create_test_files(temp_dir: str, num_files: int = 1000) -> None:
    """Create test files for benchmarking."""
    # Create directory structure
    dirs = [
        "src/core",
        "src/utils", 
        "tests/unit",
        "tests/integration",
        "docs",
        "build/dist",
        "cache/data",
    ]
    
    for d in dirs:
        os.makedirs(os.path.join(temp_dir, d), exist_ok=True)
    
    # Create files
    extensions = [".py", ".txt", ".md", ".json", ".yaml", ".js"]
    for i in range(num_files):
        subdir = dirs[i % len(dirs)]
        ext = extensions[i % len(extensions)]
        filename = os.path.join(temp_dir, subdir, f"file_{i}{ext}")
        with open(filename, 'w') as f:
            if ext == ".py":
                f.write(f"# Test file {i}\ndef test_{i}():\n    pass\n")
            elif ext == ".txt":
                f.write(f"Test content {i} with some searchable text\n")
            else:
                f.write(f'{{"id": {i}, "name": "test_{i}"}}\n')
    
    # Create some large files for mmap testing
    large_file = os.path.join(temp_dir, "src/core/large.bin")
    with open(large_file, 'wb') as f:
        f.write(b'x' * (10 * 1024 * 1024))  # 10MB


class BenchmarkResults:
    """Store and display benchmark results."""
    def __init__(self):
        self.results = {}
    
    def record(self, name: str, value: float, unit: str = "ms"):
        self.results[name] = {"value": value, "unit": unit}
    
    def display(self):
        print("\n" + "="*60)
        print("BENCHMARK RESULTS")
        print("="*60)
        for name, data in sorted(self.results.items()):
            print(f"{name:40} {data['value']:10.2f} {data['unit']}")
        print("="*60)


def benchmark_filename_search(temp_dir: str) -> BenchmarkResults:
    """Benchmark filename search performance."""
    results = BenchmarkResults()
    
    # Test 1: Basic filename search
    start = time.perf_counter()
    files = qry.search("file_", scope=temp_dir, mode="filename")
    elapsed = (time.perf_counter() - start) * 1000
    results.record("filename_search_1k_files", elapsed, "ms")
    print(f"Filename search (1k files): {elapsed:.2f}ms, found {len(files)}")
    
    # Test 2: With depth limit
    start = time.perf_counter()
    files = qry.search("file_", scope=temp_dir, mode="filename", depth=1)
    elapsed = (time.perf_counter() - start) * 1000
    results.record("filename_search_depth_1", elapsed, "ms")
    print(f"Filename search (depth=1): {elapsed:.2f}ms, found {len(files)}")
    
    # Test 3: With file type filter
    start = time.perf_counter()
    files = qry.search("file_", scope=temp_dir, mode="filename", file_types=["py"])
    elapsed = (time.perf_counter() - start) * 1000
    results.record("filename_search_py_only", elapsed, "ms")
    print(f"Filename search (.py only): {elapsed:.2f}ms, found {len(files)}")
    
    return results


def benchmark_date_filtering(temp_dir: str) -> BenchmarkResults:
    """Benchmark date-based filtering."""
    results = BenchmarkResults()
    
    # Test with date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    query = SearchQuery(
        query_text="file_",
        file_types=[],
        date_range=(start_date, end_date),
        max_results=10000,
    )
    
    engine = SimpleSearchEngine(max_workers=1, use_cache=True)
    
    start = time.perf_counter()
    search_results = engine.search(query, [temp_dir])
    elapsed = (time.perf_counter() - start) * 1000
    results.record("date_filter_7_days", elapsed, "ms")
    print(f"Date filtering (7 days): {elapsed:.2f}ms, found {len(search_results)}")
    
    return results


def benchmark_caching(temp_dir: str) -> BenchmarkResults:
    """Benchmark caching effectiveness."""
    results = BenchmarkResults()
    
    # Import the cached function directly
    from qry.engines.simple import _cached_stat
    
    engine = SimpleSearchEngine(max_workers=1, use_cache=True)
    query = SearchQuery(
        query_text="file_",
        file_types=[],
        max_results=10000,
    )
    
    # First run (cold cache)
    _cached_stat.cache_clear()  # Clear cache
    start = time.perf_counter()
    engine.search(query, [temp_dir])
    cold_time = (time.perf_counter() - start) * 1000
    results.record("search_cold_cache", cold_time, "ms")
    print(f"Search (cold cache): {cold_time:.2f}ms")
    
    # Second run (warm cache)
    start = time.perf_counter()
    engine.search(query, [temp_dir])
    warm_time = (time.perf_counter() - start) * 1000
    results.record("search_warm_cache", warm_time, "ms")
    print(f"Search (warm cache): {warm_time:.2f}ms")
    
    if cold_time > 0:
        speedup = cold_time / warm_time if warm_time > 0 else 1
        results.record("cache_speedup", speedup, "x")
        print(f"Cache speedup: {speedup:.2f}x")
    
    return results


def benchmark_parallel_search(temp_dir: str) -> BenchmarkResults:
    """Benchmark parallel vs sequential search."""
    results = BenchmarkResults()
    
    query = SearchQuery(
        query_text="file_",
        file_types=[],
        max_results=10000,
    )
    
    # Sequential
    engine_seq = SimpleSearchEngine(max_workers=1, use_cache=False)
    start = time.perf_counter()
    engine_seq.search(query, [temp_dir])
    seq_time = (time.perf_counter() - start) * 1000
    results.record("search_sequential", seq_time, "ms")
    print(f"Sequential search: {seq_time:.2f}ms")
    
    # Parallel (4 workers)
    engine_par = SimpleSearchEngine(max_workers=4, use_cache=False)
    start = time.perf_counter()
    engine_par.search(query, [temp_dir])
    par_time = (time.perf_counter() - start) * 1000
    results.record("search_parallel_4w", par_time, "ms")
    print(f"Parallel search (4w): {par_time:.2f}ms")
    
    if seq_time > 0:
        speedup = seq_time / par_time if par_time > 0 else 1
        results.record("parallel_speedup", speedup, "x")
        print(f"Parallel speedup: {speedup:.2f}x")
    
    return results


def benchmark_large_file_mmap(temp_dir: str) -> BenchmarkResults:
    """Benchmark mmap vs regular file reading."""
    results = BenchmarkResults()
    
    large_file = os.path.join(temp_dir, "src/core/large.bin")
    
    # Regular read
    start = time.perf_counter()
    with open(large_file, 'rb') as f:
        data = f.read()
        found = b'test' in data
    read_time = (time.perf_counter() - start) * 1000
    results.record("file_read_10MB", read_time, "ms")
    print(f"Regular read (10MB): {read_time:.2f}ms")
    
    # mmap read
    import mmap
    start = time.perf_counter()
    with open(large_file, 'rb') as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            pos = mm.find(b'test')
    mmap_time = (time.perf_counter() - start) * 1000
    results.record("mmap_read_10MB", mmap_time, "ms")
    print(f"MMAP read (10MB): {mmap_time:.2f}ms")
    
    if read_time > 0:
        speedup = read_time / mmap_time if mmap_time > 0 else 1
        results.record("mmap_speedup", speedup, "x")
        print(f"MMAP speedup: {speedup:.2f}x")
    
    return results


def benchmark_iter_vs_list(temp_dir: str) -> BenchmarkResults:
    """Benchmark iterator vs list return."""
    results = BenchmarkResults()
    
    # List return
    start = time.perf_counter()
    files = qry.search("file_", scope=temp_dir, mode="filename")
    list_time = (time.perf_counter() - start) * 1000
    results.record("search_list_return", list_time, "ms")
    print(f"Search (list return): {list_time:.2f}ms, {len(files)} files")
    
    # Iterator return  
    start = time.perf_counter()
    count = 0
    for f in qry.search_iter("file_", scope=temp_dir, mode="filename"):
        count += 1
    iter_time = (time.perf_counter() - start) * 1000
    results.record("search_iter_return", iter_time, "ms")
    print(f"Search (iter return): {iter_time:.2f}ms, {count} files")
    
    return results


def run_all_benchmarks():
    """Run all benchmarks."""
    print("Creating test files...")
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Test directory: {temp_dir}")
        create_test_files(temp_dir)
        
        all_results = BenchmarkResults()
        
        print("\n" + "="*60)
        print("RUNNING BENCHMARKS")
        print("="*60)
        
        print("\n--- Filename Search ---")
        all_results.results.update(benchmark_filename_search(temp_dir).results)
        
        print("\n--- Date Filtering ---")
        all_results.results.update(benchmark_date_filtering(temp_dir).results)
        
        print("\n--- Caching ---")
        all_results.results.update(benchmark_caching(temp_dir).results)
        
        print("\n--- Parallel Search ---")
        all_results.results.update(benchmark_parallel_search(temp_dir).results)
        
        print("\n--- Large File (mmap) ---")
        all_results.results.update(benchmark_large_file_mmap(temp_dir).results)
        
        print("\n--- Iterator vs List ---")
        all_results.results.update(benchmark_iter_vs_list(temp_dir).results)
        
        all_results.display()
        
        return all_results


if __name__ == "__main__":
    run_all_benchmarks()
