"""
Local History Manager
Saves execution results to local JSON files without database dependencies
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class ExecutionRecord:
    """Record of action execution for history storage."""
    action_id: str
    status: str
    timestamp: str
    duration: float
    message: str
    target: str
    action_type: str
    error: Optional[str] = None
    network_state_before: Optional[Dict] = None
    network_state_after: Optional[Dict] = None


class HistoryManager:
    """
    Manages local file-based history storage.
    
    Responsibilities:
    - Save execution results to JSON files
    - Create and manage history directory
    - Provide simple query interface for recent results
    
    Does NOT depend on:
    - PostgreSQL or any database
    - SQLAlchemy
    - Complex ORM systems
    """
    
    def __init__(self, history_dir: str = "data/history"):
        """
        Initialize history manager.
        
        Args:
            history_dir: Directory path for storing history files
        """
        self.logger = logging.getLogger("HistoryManager")
        self.history_dir = Path(history_dir)
        
        # Create history directory if it doesn't exist
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"History manager initialized with directory: {self.history_dir}")
    
    def save_result(self, result: ExecutionRecord) -> str:
        """
        Save execution result to JSON file.
        
        Args:
            result: ExecutionRecord to save
            
        Returns:
            Path to saved file
        """
        try:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"result_{result.action_id}_{timestamp}.json"
            filepath = self.history_dir / filename
            
            # Convert to dictionary
            result_dict = asdict(result)
            
            # Write to file
            with open(filepath, 'w') as f:
                json.dump(result_dict, f, indent=2)
            
            self.logger.info(f"Saved result for action {result.action_id} to {filepath}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Failed to save result for action {result.action_id}: {e}")
            raise
    
    def save_results_batch(self, results: List[ExecutionRecord]) -> List[str]:
        """
        Save multiple execution results.
        
        Args:
            results: List of ExecutionRecord objects
            
        Returns:
            List of file paths
        """
        saved_files = []
        
        for result in results:
            try:
                filepath = self.save_result(result)
                saved_files.append(filepath)
            except Exception as e:
                self.logger.error(f"Failed to save result in batch: {e}")
        
        self.logger.info(f"Saved {len(saved_files)}/{len(results)} results")
        return saved_files
    
    def get_recent_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most recent execution results.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of result dictionaries
        """
        try:
            # Get all JSON files in history directory
            json_files = sorted(
                self.history_dir.glob("result_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            results = []
            for filepath in json_files[:limit]:
                try:
                    with open(filepath, 'r') as f:
                        result = json.load(f)
                        results.append(result)
                except Exception as e:
                    self.logger.warning(f"Failed to read {filepath}: {e}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to get recent results: {e}")
            return []
    
    def get_results_by_action_id(self, action_id: str) -> List[Dict[str, Any]]:
        """
        Get all results for a specific action ID.
        
        Args:
            action_id: Action ID to search for
            
        Returns:
            List of result dictionaries
        """
        try:
            # Find files matching the action ID pattern
            pattern = f"result_{action_id}_*.json"
            json_files = sorted(
                self.history_dir.glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            results = []
            for filepath in json_files:
                try:
                    with open(filepath, 'r') as f:
                        result = json.load(f)
                        results.append(result)
                except Exception as e:
                    self.logger.warning(f"Failed to read {filepath}: {e}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to get results for action {action_id}: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about stored results.
        
        Returns:
            Dictionary with statistics
        """
        try:
            json_files = list(self.history_dir.glob("result_*.json"))
            
            total_results = len(json_files)
            successful = 0
            failed = 0
            
            # Count successes and failures
            for filepath in json_files:
                try:
                    with open(filepath, 'r') as f:
                        result = json.load(f)
                        if result.get("status") == "success":
                            successful += 1
                        elif result.get("status") == "failed":
                            failed += 1
                except Exception:
                    pass
            
            return {
                "total_results": total_results,
                "successful": successful,
                "failed": failed,
                "success_rate": (successful / max(total_results, 1)) * 100,
                "history_directory": str(self.history_dir)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {
                "total_results": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0.0,
                "error": str(e)
            }
    
    def cleanup_old_results(self, days: int = 30) -> int:
        """
        Remove result files older than specified days.
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of files deleted
        """
        try:
            import time
            
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            json_files = list(self.history_dir.glob("result_*.json"))
            
            deleted = 0
            for filepath in json_files:
                if filepath.stat().st_mtime < cutoff_time:
                    filepath.unlink()
                    deleted += 1
            
            self.logger.info(f"Cleaned up {deleted} old result files")
            return deleted
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old results: {e}")
            return 0
