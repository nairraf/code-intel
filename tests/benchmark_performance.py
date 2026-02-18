import asyncio
import time
import sys
import os
import sqlite3
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

# Import our implementation modules
from src.server import refresh_index_impl, search_code_impl, get_stats_impl
from src.config import CACHE_DB_PATH

async def run_benchmark_cycle(label: str):
    print(f"\n--- Starting Benchmark: {label} ---")
    start_total = time.time()

    # 1. Full Index Sync
    print("Step 1: Full Sync (force_full_scan=True)...")
    start = time.time()
    sync_result = await refresh_index_impl(root_path=".", force_full_scan=True)
    duration_sync = time.time() - start
    print(f"   Sync took: {duration_sync:.2f}s")
    # print(sync_result)

    # 2. Search Tests
    print("Step 2: Search Tests...")
    queries = ["VectorStore implementation", "fastmcp server core", "sqlite cache logic"]
    start = time.time()
    for q in queries:
        await search_code_impl(q, root_path=".")
    duration_search = time.time() - start
    print(f"   Searching {len(queries)} terms took: {duration_search:.2f}s")

    # 3. Stats Validation
    print("Step 3: Stats Validation...")
    start = time.time()
    await get_stats_impl(root_path=".")
    duration_stats = time.time() - start
    print(f"   Stats retrieval took: {duration_stats:.2f}s")

    total_duration = time.time() - start_total
    print(f"--- {label} Total Time: {total_duration:.2f}s ---")
    return {
        "sync": duration_sync,
        "search": duration_search,
        "stats": duration_stats,
        "total": total_duration
    }

def clear_cache():
    if Path(CACHE_DB_PATH).exists():
        print(f"Clearing cache at: {CACHE_DB_PATH}")
        os.remove(CACHE_DB_PATH)
    else:
        print("No cache found to clear.")

async def main():
    # Cold Run (Clear cache first)
    clear_cache()
    run1 = await run_benchmark_cycle("COLD RUN (Cache Misses)")

    # Hot Run (Cache should be populated)
    run2 = await run_benchmark_cycle("HOT RUN (Cache Hits)")

    # Comparison
    print("\n" + "="*40)
    print("BENCHMARK COMPARISON RESULTS")
    print("="*40)
    print(f"{'Metric':<15} | {'Cold (s)':<10} | {'Hot (s)':<10} | {'Speedup':<10}")
    print("-" * 55)
    
    for metric in ["sync", "search", "stats", "total"]:
        cold = run1[metric]
        hot = run2[metric]
        speedup = cold / hot if hot > 0 else float('inf')
        print(f"{metric.capitalize():<15} | {cold:<10.2f} | {hot:<10.2f} | {speedup:<10.1f}x")
    print("="*40)

if __name__ == "__main__":
    asyncio.run(main())
