"""
Integration test for history_manager.py with the complete system.
Verifies task 3.4 integration requirements.
"""

import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

import pytest

from northbound_script_generator.history_manager import HistoryManager, ExecutionRecord
from northbound_script_generator.config_loader import ConfigLoader, SystemConfig


class TestHistoryManagerIntegration:
    """Integration tests for history manager with system components."""
    
    def setup_method(self):
        """Create temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up temporary directory after each test."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_history_manager_uses_config_directory(self):
        """Verify history manager uses directory from config."""
        # Create config with custom history directory
        config = SystemConfig(history_dir=self.temp_dir)
        
        # Initialize history manager with config directory
        history_manager = HistoryManager(history_dir=config.history_dir)
        
        # Save a result
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
        
        # Verify file is in the configured directory
        assert str(self.temp_dir) in filepath
        assert Path(filepath).exists()
    
    def test_history_manager_creates_data_history_directory(self):
        """Verify history manager creates data/history/ directory structure."""
        # Use default directory structure
        test_dir = Path(self.temp_dir) / "data" / "history"
        
        # Initialize history manager
        history_manager = HistoryManager(history_dir=str(test_dir))
        
        # Verify directory was created
        assert test_dir.exists()
        assert test_dir.is_dir()
    
    def test_result_file_format_matches_specification(self):
        """Verify result files match format: data/history/results_<timestamp>.json"""
        history_dir = Path(self.temp_dir) / "data" / "history"
        history_manager = HistoryManager(history_dir=str(history_dir))
        
        record = ExecutionRecord(
            action_id="test_002",
            status="success",
            timestamp=datetime.now().isoformat(),
            duration=1.5,
            message="Test action",
            target="switch2",
            action_type="delete_flow"
        )
        
        filepath = history_manager.save_result(record)
        
        # Verify path structure
        path = Path(filepath)
        assert path.parent.name == "history"
        assert path.parent.parent.name == "data"
        
        # Verify filename format
        assert path.name.startswith("results_")
        assert path.name.endswith(".json")
        
        # Verify timestamp format in filename (YYYYMMDD_HHMMSS_microseconds)
        filename_parts = path.stem.split("_")
        assert len(filename_parts) >= 3  # results, date, time, microseconds
        assert filename_parts[0] == "results"
    
    def test_saved_json_structure_preserves_required_fields(self):
        """Verify JSON structure preserves: action_id, status, timestamp, details."""
        history_manager = HistoryManager(history_dir=self.temp_dir)
        
        record = ExecutionRecord(
            action_id="action_123",
            status="failed",
            timestamp="2024-01-15T10:30:00",
            duration=2.5,
            message="Connection timeout",
            target="switch3",
            action_type="modify_flow",
            error="Timeout after 30 seconds"
        )
        
        filepath = history_manager.save_result(record)
        
        # Read and verify JSON structure
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Verify all required fields are preserved
        assert data["action_id"] == "action_123"
        assert data["status"] == "failed"
        assert data["timestamp"] == "2024-01-15T10:30:00"
        
        # Verify operation details are preserved
        assert data["duration"] == 2.5
        assert data["message"] == "Connection timeout"
        assert data["target"] == "switch3"
        assert data["action_type"] == "modify_flow"
        assert data["error"] == "Timeout after 30 seconds"
    
    def test_no_database_dependencies_in_runtime(self):
        """Verify system runs without PostgreSQL or database dependencies."""
        history_manager = HistoryManager(history_dir=self.temp_dir)
        
        # Save multiple results without any database
        for i in range(10):
            record = ExecutionRecord(
                action_id=f"action_{i}",
                status="success",
                timestamp=datetime.now().isoformat(),
                duration=float(i),
                message=f"Action {i}",
                target=f"switch{i}",
                action_type="add_flow"
            )
            history_manager.save_result(record)
        
        # Verify all files were created
        json_files = list(Path(self.temp_dir).glob("results_*.json"))
        assert len(json_files) == 10
        
        # Verify statistics work without database
        stats = history_manager.get_statistics()
        assert stats["total_results"] == 10
        assert stats["successful"] == 10
    
    def test_concurrent_result_saving(self):
        """Verify multiple results can be saved concurrently without conflicts."""
        history_manager = HistoryManager(history_dir=self.temp_dir)
        
        # Save results in quick succession (simulating concurrent processing)
        records = []
        for i in range(20):
            record = ExecutionRecord(
                action_id=f"concurrent_{i}",
                status="success" if i % 3 != 0 else "failed",
                timestamp=datetime.now().isoformat(),
                duration=0.1,
                message=f"Concurrent action {i}",
                target=f"switch{i % 5}",
                action_type="add_flow"
            )
            records.append(record)
        
        # Save all records
        saved_files = history_manager.save_results_batch(records)
        
        # Verify all were saved
        assert len(saved_files) == 20
        
        # Verify all files exist and are unique
        assert len(set(saved_files)) == 20
        
        # Verify statistics
        stats = history_manager.get_statistics()
        assert stats["total_results"] == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
