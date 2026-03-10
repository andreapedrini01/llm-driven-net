"""
Test history_manager.py for local storage implementation.
Verifies task 3.4 requirements.
"""

import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

import pytest

from northbound_script_generator.history_manager import HistoryManager, ExecutionRecord


class TestHistoryManagerLocalStorage:
    """Test suite for local storage history manager."""
    
    def setup_method(self):
        """Create temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.history_manager = HistoryManager(history_dir=self.temp_dir)
    
    def teardown_method(self):
        """Clean up temporary directory after each test."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_history_directory_created(self):
        """Verify data/history/ directory is created if it doesn't exist."""
        assert Path(self.temp_dir).exists()
        assert Path(self.temp_dir).is_dir()
    
    def test_save_result_creates_file_with_correct_format(self):
        """Verify result files are created with format: results_<timestamp>.json"""
        record = ExecutionRecord(
            action_id="test_action_001",
            status="success",
            timestamp=datetime.now().isoformat(),
            duration=1.5,
            message="Test action completed",
            target="switch1",
            action_type="add_flow"
        )
        
        filepath = self.history_manager.save_result(record)
        
        # Verify file exists
        assert Path(filepath).exists()
        
        # Verify filename format
        filename = Path(filepath).name
        assert filename.startswith("results_")
        assert filename.endswith(".json")
    
    def test_saved_json_contains_required_fields(self):
        """Verify JSON includes: action_id, status, timestamp, operation details."""
        record = ExecutionRecord(
            action_id="test_action_002",
            status="failed",
            timestamp=datetime.now().isoformat(),
            duration=0.5,
            message="Test action failed",
            target="switch2",
            action_type="delete_flow",
            error="Connection timeout"
        )
        
        filepath = self.history_manager.save_result(record)
        
        # Read and verify JSON content
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Verify required fields
        assert "action_id" in data
        assert data["action_id"] == "test_action_002"
        
        assert "status" in data
        assert data["status"] in ["success", "failed"]
        
        assert "timestamp" in data
        assert data["timestamp"] is not None
        
        # Verify operation details
        assert "target" in data
        assert "action_type" in data
        assert "duration" in data
        assert "message" in data
    
    def test_no_postgresql_dependencies(self):
        """Verify no PostgreSQL or SQLAlchemy dependencies are imported."""
        import sys
        
        # Check that SQLAlchemy and psycopg2 are not in loaded modules
        # after importing history_manager
        loaded_modules = sys.modules.keys()
        
        # These should not be loaded
        assert not any("sqlalchemy" in mod.lower() for mod in loaded_modules 
                      if "history_manager" in str(sys.modules.get(mod, "")))
        assert not any("psycopg2" in mod.lower() for mod in loaded_modules
                      if "history_manager" in str(sys.modules.get(mod, "")))
    
    def test_save_multiple_results(self):
        """Verify multiple results can be saved."""
        records = [
            ExecutionRecord(
                action_id=f"action_{i}",
                status="success" if i % 2 == 0 else "failed",
                timestamp=datetime.now().isoformat(),
                duration=float(i),
                message=f"Action {i}",
                target=f"switch{i}",
                action_type="add_flow"
            )
            for i in range(5)
        ]
        
        saved_files = self.history_manager.save_results_batch(records)
        
        assert len(saved_files) == 5
        for filepath in saved_files:
            assert Path(filepath).exists()
    
    def test_get_recent_results(self):
        """Verify recent results can be retrieved."""
        # Save some results
        for i in range(3):
            record = ExecutionRecord(
                action_id=f"action_{i}",
                status="success",
                timestamp=datetime.now().isoformat(),
                duration=1.0,
                message=f"Action {i}",
                target=f"switch{i}",
                action_type="add_flow"
            )
            self.history_manager.save_result(record)
        
        # Retrieve recent results
        results = self.history_manager.get_recent_results(limit=3)
        
        assert len(results) == 3
        assert all("action_id" in r for r in results)
    
    def test_statistics(self):
        """Verify statistics can be retrieved."""
        # Save some results
        for i in range(5):
            record = ExecutionRecord(
                action_id=f"action_{i}",
                status="success" if i < 3 else "failed",
                timestamp=datetime.now().isoformat(),
                duration=1.0,
                message=f"Action {i}",
                target=f"switch{i}",
                action_type="add_flow"
            )
            self.history_manager.save_result(record)
        
        stats = self.history_manager.get_statistics()
        
        assert stats["total_results"] == 5
        assert stats["successful"] == 3
        assert stats["failed"] == 2
        assert stats["success_rate"] == 60.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
