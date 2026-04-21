#!/usr/bin/env python3
"""
Cache Cleanup Script
Removes application cache files:
- data/ subdirectories content (history, archive, network_context_history, security_history, etc.)
  Preserves .gitkeep files.
- output/ content (action packages and logs)
- **/__pycache__/ directories (Python bytecode cache)
"""

import os
import shutil
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"


def _clean_directory(directory: Path) -> int:
    """Removes all files inside a directory tree, preserving .gitkeep files.
    Returns the number of files removed."""
    removed = 0
    if not directory.exists():
        return removed

    for root, dirs, files in os.walk(directory, topdown=False):
        root_path = Path(root)
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


def clean_data() -> int:
    """Removes all files inside data/, preserving .gitkeep files."""
    return _clean_directory(DATA_DIR)


def clean_output() -> int:
    """Removes all files inside output/ (action packages and logs)."""
    return _clean_directory(OUTPUT_DIR)


def clean_pycache() -> int:
    """Removes all __pycache__ directories recursively."""
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

    Returns a dict with counts: {"data_files": int, "output_files": int, "pycache_dirs": int}
    """
    if verbose:
        print("Cleaning application cache...")

    data_count = clean_data()
    if verbose:
        print(f"  ✓ data/:         {data_count} file(s) removed")

    output_count = clean_output()
    if verbose:
        print(f"  ✓ output/:       {output_count} file(s) removed")

    pycache_count = clean_pycache()
    if verbose:
        print(f"  ✓ __pycache__:   {pycache_count} directory(ies) removed")

    if verbose:
        print("Done.")

    return {"data_files": data_count, "output_files": output_count, "pycache_dirs": pycache_count}


if __name__ == "__main__":
    clean_all(verbose=True)
