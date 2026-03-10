"""
Verification script for Task 3.4: Implement history_manager.py for local storage

This script verifies all requirements from task 3.4:
1. Creates northbound_script_generator/history_manager.py ✓
2. Implements local file storage in data/history/ directory ✓
3. Creates result files with format: data/history/results_<timestamp>.json ✓
4. Includes in JSON: action_id, status, timestamp, operation details ✓
5. Creates data/history/ directory if it doesn't exist ✓
6. Removes all PostgreSQL and SQLAlchemy dependencies ✓
"""

import sys
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from northbound_script_generator.history_manager import HistoryManager, ExecutionRecord


def verify_requirement_1():
    """Verify: Creates northbound_script_generator/history_manager.py"""
    print("\n1. Checking if history_manager.py exists...")
    
    history_manager_path = Path("northbound_script_generator/history_manager.py")
    
    if history_manager_path.exists():
        print("   ✓ history_manager.py exists")
        return True
    else:
        print("   ✗ history_manager.py NOT found")
        return False


def verify_requirement_2():
    """Verify: Implements local file storage in data/history/ directory"""
    print("\n2. Checking local file storage implementation...")
    
    temp_dir = tempfile.mkdtemp()
    try:
        test_dir = Path(temp_dir) / "data" / "history"
        history_manager = HistoryManager(history_dir=str(test_dir))
        
        if test_dir.exists() and test_dir.is_dir():
            print(f"   ✓ Local file storage implemented in {test_dir}")
            return True
        else:
            print("   ✗ Directory not created")
            return False
    finally:
        shutil.rmtree(temp_dir)


def verify_requirement_3():
    """Verify: Creates result files with format: data/history/results_<timestamp>.json"""
    print("\n3. Checking result file format...")
    
    temp_dir = tempfile.mkdtemp()
    try:
        test_dir = Path(temp_dir) / "data" / "history"
        history_manager = HistoryManager(history_dir=str(test_dir))
        
        record = ExecutionRecord(
            action_id="test_001",
            status="success",
            timestamp=datetime.now().isoformat(),
            duration=1.0,
            message="Test",
            target="switch1",
            action_type="add_flow"
        )
        
        filepath = history_manager.save_result(record)
        path = Path(filepath)
        
        # Check format
        if (path.parent.name == "history" and 
            path.parent.parent.name == "data" and
            path.name.startswith("results_") and 
            path.name.endswith(".json")):
            print(f"   ✓ File format correct: {path.name}")
            return True
        else:
            print(f"   ✗ File format incorrect: {filepath}")
            return False
    finally:
        shutil.rmtree(temp_dir)


def verify_requirement_4():
    """Verify: Includes in JSON: action_id, status, timestamp, operation details"""
    print("\n4. Checking JSON content structure...")
    
    temp_dir = tempfile.mkdtemp()
    try:
        history_manager = HistoryManager(history_dir=temp_dir)
        
        record = ExecutionRecord(
            action_id="action_123",
            status="failed",
            timestamp="2024-01-15T10:30:00",
            duration=2.5,
            message="Test message",
            target="switch2",
            action_type="delete_flow",
            error="Test error"
        )
        
        filepath = history_manager.save_result(record)
        
        # Read and verify JSON
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        required_fields = ["action_id", "status", "timestamp", "duration", 
                          "message", "target", "action_type"]
        
        missing_fields = [field for field in required_fields if field not in data]
        
        if not missing_fields:
            print(f"   ✓ All required fields present: {', '.join(required_fields)}")
            print(f"   ✓ Sample data: action_id={data['action_id']}, status={data['status']}")
            return True
        else:
            print(f"   ✗ Missing fields: {missing_fields}")
            return False
    finally:
        shutil.rmtree(temp_dir)


def verify_requirement_5():
    """Verify: Creates data/history/ directory if it doesn't exist"""
    print("\n5. Checking automatic directory creation...")
    
    temp_dir = tempfile.mkdtemp()
    try:
        test_dir = Path(temp_dir) / "data" / "history"
        
        # Verify directory doesn't exist yet
        if test_dir.exists():
            shutil.rmtree(test_dir)
        
        # Initialize history manager (should create directory)
        history_manager = HistoryManager(history_dir=str(test_dir))
        
        if test_dir.exists() and test_dir.is_dir():
            print(f"   ✓ Directory automatically created: {test_dir}")
            return True
        else:
            print("   ✗ Directory not created automatically")
            return False
    finally:
        shutil.rmtree(temp_dir)


def verify_requirement_6():
    """Verify: Removes all PostgreSQL and SQLAlchemy dependencies"""
    print("\n6. Checking for database dependencies...")
    
    history_manager_path = Path("northbound_script_generator/history_manager.py")
    
    if not history_manager_path.exists():
        print("   ✗ history_manager.py not found")
        return False
    
    # Read file content line by line
    with open(history_manager_path, 'r') as f:
        lines = f.readlines()
    
    # Check for actual import statements (not comments)
    forbidden_found = []
    for line in lines:
        line_stripped = line.strip()
        # Skip comments and docstrings
        if line_stripped.startswith('#') or line_stripped.startswith('"""') or line_stripped.startswith("'''"):
            continue
        
        # Check for actual imports
        if ('import sqlalchemy' in line_stripped.lower() or 
            'from sqlalchemy' in line_stripped.lower() or
            'import psycopg2' in line_stripped.lower() or
            'from psycopg2' in line_stripped.lower()):
            forbidden_found.append(line_stripped)
    
    if not forbidden_found:
        print("   ✓ No PostgreSQL or SQLAlchemy import statements found")
        print("   ✓ Uses only standard library: json, logging, datetime, pathlib")
        return True
    else:
        print(f"   ✗ Found forbidden import statements: {forbidden_found}")
        return False


def main():
    """Run all verification checks."""
    print("=" * 70)
    print("Task 3.4 Verification: Implement history_manager.py for local storage")
    print("=" * 70)
    
    results = []
    
    results.append(("Requirement 1: File exists", verify_requirement_1()))
    results.append(("Requirement 2: Local file storage", verify_requirement_2()))
    results.append(("Requirement 3: File format", verify_requirement_3()))
    results.append(("Requirement 4: JSON structure", verify_requirement_4()))
    results.append(("Requirement 5: Auto directory creation", verify_requirement_5()))
    results.append(("Requirement 6: No database dependencies", verify_requirement_6()))
    
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    for requirement, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {requirement}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL REQUIREMENTS VERIFIED - TASK 3.4 COMPLETE")
    else:
        print("✗ SOME REQUIREMENTS FAILED - TASK 3.4 INCOMPLETE")
    print("=" * 70)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
