#!/usr/bin/env python3
"""
Cache Cleanup Script
Removes application cache files:
- data/ subdirectories content (history, archive, network_context_history, security_history, etc.)
  Preserves .gitkeep files.
- **/__pycache__/ directories (Python bytecode cache)
"""

import os
import shutil
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def clean_data() -> int:
    """Removes all files and subdirectories inside data/, preserving .gitkeep files.
    Returns the number of items removed."""
    removed = 0
    if not DATA_DIR.exists():
        return removed

    for root, dirs, files in os.walk(DATA_DIR, topdown=False):
        root_path = Path(root)
        # Remove files (except .gitkeep)
        for fname in files:
            if fname == ".gitkeep":
                continue
            target = root_path / fname
            try:
                target.unlink()
                removed += 1
            except OSError as e:
                print(f"  Warning: could not remove {target}: {e}")

    return removed


def clean_pycache() -> int:
    """Removes all __pycache__ directories recursively. Returns the number of directories removed."""
    removed = 0
    for dirpath, dirnames, _ in os.walk(BASE_DIR):
        for dirname in dirnames:
            if dirname == "__pycache__":
                target = Path(dirpath) / dirname
                try:
                    shutil.rmtree(target)
                    removed += 1
                except OSError as e:
                    print(f"  Warning: could not remove {target}: {e}")
    return removed


def clean_all(verbose: bool = True) -> dict:
    """
    Runs the full cache cleanup.

    Returns a dict with counts: {"data_files": int, "pycache_dirs": int}
    """
    if verbose:
        print("Cleaning application cache...")

    data_count = clean_data()
    if verbose:
        print(f"  ✓ data/:         {data_count} file(s) removed")

    pycache_count = clean_pycache()
    if verbose:
        print(f"  ✓ __pycache__:   {pycache_count} directory(ies) removed")

    if verbose:
        print("Done.")

    return {"data_files": data_count, "pycache_dirs": pycache_count}


if __name__ == "__main__":
    clean_all(verbose=True)
