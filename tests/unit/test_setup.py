#!/usr/bin/env python3
"""Verify that all required dependencies are installed correctly."""

import sys


def test_imports():
    """Test that all required packages can be imported."""
    required_packages = {
        'pydantic': 'Pydantic',
        'fastapi': 'FastAPI',
        'uvicorn': 'Uvicorn',
        'pytest': 'Pytest',
        'hypothesis': 'Hypothesis'
    }
    
    failed = []
    
    for package, name in required_packages.items():
        try:
            __import__(package)
            print(f"[OK] {name} imported successfully")
        except ImportError as e:
            print(f"[FAIL] Failed to import {name}: {e}")
            failed.append(name)
    
    if failed:
        print(f"\n[FAIL] Failed to import: {', '.join(failed)}")
        return False
    
    print("\n[OK] All dependencies are installed correctly!")
    return True


if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
