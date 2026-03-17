"""
Simplified Main Entry Point
Minimal implementation for local file-based network action processing
"""

import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from .config_loader import ConfigLoader, SystemConfig
from .models import NetworkAction, ActionType
from .action_processor import ActionProcessor, ExecutionResult
from .history_manager import HistoryManager, ExecutionRecord


def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def load_actions_from_file(filepath: str) -> List[NetworkAction]:
    """
    Load network actions from JSON or JSONL file.
    
    Args:
        filepath: Path to actions file
        
    Returns:
        List of NetworkAction objects
    """
    logger = logging.getLogger("ActionLoader")
    actions = []
    
    try:
        path = Path(filepath)
        
        if not path.exists():
            logger.error(f"Actions file not found: {filepath}")
            return actions
        
        # Check file extension
        if path.suffix == '.jsonl':
            # JSONL format - one JSON object per line
            with open(path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        action_data = json.loads(line)
                        action = NetworkAction(**action_data)
                        actions.append(action)
                    except Exception as e:
                        logger.error(f"Failed to parse action on line {line_num}: {e}")
        
        elif path.suffix == '.json':
            # JSON format - array of actions
            with open(path, 'r') as f:
                data = json.load(f)
                
                # Handle both single action and array of actions
                if isinstance(data, list):
                    for action_data in data:
                        try:
                            action = NetworkAction(**action_data)
                            actions.append(action)
                        except Exception as e:
                            logger.error(f"Failed to parse action: {e}")
                elif isinstance(data, dict):
                    try:
                        action = NetworkAction(**data)
                        actions.append(action)
                    except Exception as e:
                        logger.error(f"Failed to parse action: {e}")
        
        else:
            logger.error(f"Unsupported file format: {path.suffix}")
        
        logger.info(f"Loaded {len(actions)} actions from {filepath}")
        return actions
        
    except Exception as e:
        logger.error(f"Failed to load actions from {filepath}: {e}")
        return actions


def convert_execution_result_to_record(result: ExecutionResult, action: NetworkAction) -> ExecutionRecord:
    """
    Convert ExecutionResult to ExecutionRecord for history storage.
    
    Args:
        result: ExecutionResult from action processor
        action: Original NetworkAction
        
    Returns:
        ExecutionRecord for history manager
    """
    return ExecutionRecord(
        action_id=result.action_id,
        status=result.status.value,
        timestamp=result.timestamp.isoformat(),
        duration=result.duration,
        message=result.message,
        target=action.target,
        action_type=action.type.value,
        error=result.error,
        network_state_before=result.network_state_before,
        network_state_after=result.network_state_after
    )


def main():
    """Main entry point for simplified northbound script."""
    logger = logging.getLogger("Main")
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config_loader = ConfigLoader("config.yaml")
        config = config_loader.load()
        
        # Setup logging with configured level
        setup_logging(config.log_level)
        logger.info("Configuration loaded successfully")
        logger.info(f"ComnetsEMU: {config.comnetsemu_host}:{config.comnetsemu_port}")
        logger.info(f"Max retries: {config.max_retries}, Retry delay: {config.retry_delay}s")
        
        # Initialize components
        logger.info("Initializing components...")
        
        # Initialize action processor
        processor_config = {
            "comnetsemu_host": config.comnetsemu_host,
            "comnetsemu_port": config.comnetsemu_port,
            "max_retries": config.max_retries,
            "retry_delay": config.retry_delay,
            "timeout_seconds": config.timeout_seconds
        }
        action_processor = ActionProcessor(processor_config)
        
        # Initialize history manager
        history_manager = HistoryManager(config.history_dir)
        
        logger.info("Components initialized successfully")
        
        # Load actions from file
        logger.info(f"Loading actions from {config.actions_file}...")
        actions = load_actions_from_file(config.actions_file)
        
        if not actions:
            logger.warning("No actions to process")
            return
        
        logger.info(f"Processing {len(actions)} actions...")
        
        # Process actions
        results = []
        for i, action in enumerate(actions, 1):
            logger.info(f"Processing action {i}/{len(actions)}: {action.id}")
            
            try:
                # Execute action
                result = action_processor.execute_action(action)
                results.append(result)
                
                # Convert to history record and save
                record = convert_execution_result_to_record(result, action)
                history_manager.save_result(record)
                
                # Log result
                if result.status.value == "success":
                    logger.info(f"Action {action.id} completed successfully in {result.duration:.2f}s")
                else:
                    logger.error(f"Action {action.id} failed: {result.error}")
                
            except Exception as e:
                logger.error(f"Error processing action {action.id}: {e}")
        
        # Summary
        successful = sum(1 for r in results if r.status.value == "success")
        failed = sum(1 for r in results if r.status.value == "failed")
        
        logger.info("=" * 60)
        logger.info("Processing Summary:")
        logger.info(f"  Total actions: {len(actions)}")
        logger.info(f"  Successful: {successful}")
        logger.info(f"  Failed: {failed}")
        logger.info(f"  Success rate: {(successful / len(actions) * 100):.1f}%")
        logger.info("=" * 60)
        
        # Get history statistics
        stats = history_manager.get_statistics()
        logger.info(f"History: {stats['total_results']} total results stored")
        
        # Cleanup
        logger.info("Closing connections...")
        action_processor.close()
        logger.info("Done")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
