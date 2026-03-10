#!/usr/bin/env python3
"""
Simplified Northbound Script Generator - Main Entry Point

This is a minimal implementation that:
- Reads actions from logs/actions.jsonl
- Processes them using ComnetsEMU connector
- Saves results to history/ directory
- Uses Python standard logging
"""

import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Import core components (preserved from original system)
from src.connectors.comnetsemu_connector import ComnetsEMUConnector, ComnetsEMUConfig
from src.core.retry_system import AdvancedRetrySystem, RetryConfig
from src.models.action_models import NetworkAction, ActionType


def setup_logging(log_level: str = "INFO", log_file: str = "logs/system.log"):
    """Setup Python standard logging."""
    # Create logs directory if it doesn't exist
    Path("logs").mkdir(exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file)
        ]
    )
    
    return logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file."""
    import yaml
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        # Return default configuration if file doesn't exist
        return {
            "comnetsemu_host": "localhost",
            "comnetsemu_port": 6653,
            "max_retries": 3,
            "retry_delay": 2.0,
            "log_level": "INFO"
        }


def read_actions(actions_file: str = "logs/actions.jsonl") -> List[Dict[str, Any]]:
    """Read actions from JSON or JSONL file."""
    actions = []
    
    # Try JSONL format first
    if Path(actions_file).exists():
        with open(actions_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        actions.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    
    # Try JSON format if JSONL didn't work
    if not actions:
        json_file = actions_file.replace('.jsonl', '.json')
        if Path(json_file).exists():
            with open(json_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    actions = data
                elif isinstance(data, dict) and 'actions' in data:
                    actions = data['actions']
    
    return actions


def save_result(result: Dict[str, Any], history_dir: str = "history"):
    """Save action result to history directory."""
    # Create history directory if it doesn't exist
    Path(history_dir).mkdir(exist_ok=True)
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    action_id = result.get('action_id', 'unknown')
    filename = f"{history_dir}/result_{action_id}_{timestamp}.json"
    
    # Save result
    with open(filename, 'w') as f:
        json.dump(result, f, indent=2)


def process_action(action_data: Dict[str, Any], 
                   connector: ComnetsEMUConnector,
                   logger: logging.Logger) -> Dict[str, Any]:
    """Process a single network action."""
    try:
        # Convert dict to NetworkAction object
        action = NetworkAction(**action_data)
        
        # Validate action parameters
        validation = action.validate_action_parameters()
        if not validation['is_valid']:
            logger.error(f"Action {action.id} validation failed: {validation['issues']}")
            return {
                "action_id": action.id,
                "status": "failed",
                "timestamp": datetime.now().isoformat(),
                "error": f"Validation failed: {validation['issues']}"
            }
        
        # Log warnings if any
        if validation['warnings']:
            logger.warning(f"Action {action.id} warnings: {validation['warnings']}")
        
        # Execute action based on type
        logger.info(f"Processing action {action.id} of type {action.type}")
        
        if action.type == ActionType.FLOW_MOD:
            result = connector.execute_topology_change(action)
        elif action.type == ActionType.CONFIG_CHANGE:
            config_type = action.parameters.get("config_type", "unknown")
            if config_type == "qos":
                result = connector.execute_qos_policy(action)
            else:
                result = connector.execute_topology_change(action)
        else:
            result = connector.execute_topology_change(action)
        
        # Prepare result
        return {
            "action_id": action.id,
            "status": "success" if result.get("success") else "failed",
            "timestamp": datetime.now().isoformat(),
            "operation": action.type.value,
            "target": action.target,
            "details": result,
            "error": result.get("error") if not result.get("success") else None
        }
        
    except Exception as e:
        logger.error(f"Failed to process action: {e}", exc_info=True)
        return {
            "action_id": action_data.get('id', 'unknown'),
            "status": "failed",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


def main():
    """Main entry point."""
    # Load configuration
    config = load_config()
    
    # Setup logging
    logger = setup_logging(
        log_level=config.get("log_level", "INFO"),
        log_file=config.get("log_file", "logs/system.log")
    )
    
    logger.info("=" * 80)
    logger.info("Starting Simplified Northbound Script Generator")
    logger.info("=" * 80)
    
    try:
        # Initialize ComnetsEMU connector
        comnetsemu_config = ComnetsEMUConfig(
            host=config.get("comnetsemu_host", "localhost"),
            port=config.get("comnetsemu_port", 6653),
            max_retries=config.get("max_retries", 3),
            retry_delay=config.get("retry_delay", 2.0)
        )
        connector = ComnetsEMUConnector(comnetsemu_config)
        logger.info(f"Connected to ComnetsEMU at {comnetsemu_config.host}:{comnetsemu_config.port}")
        
        # Read actions from file
        actions_file = config.get("actions_file", "logs/actions.jsonl")
        actions = read_actions(actions_file)
        logger.info(f"Loaded {len(actions)} actions from {actions_file}")
        
        if not actions:
            logger.warning("No actions found to process")
            return
        
        # Process actions sequentially
        results = []
        for i, action_data in enumerate(actions, 1):
            logger.info(f"Processing action {i}/{len(actions)}")
            
            result = process_action(action_data, connector, logger)
            results.append(result)
            
            # Save result to history
            save_result(result, config.get("history_dir", "history"))
            
            # Log result
            if result['status'] == 'success':
                logger.info(f"Action {result['action_id']} completed successfully")
            else:
                logger.error(f"Action {result['action_id']} failed: {result.get('error')}")
        
        # Summary
        successful = sum(1 for r in results if r['status'] == 'success')
        failed = len(results) - successful
        
        logger.info("=" * 80)
        logger.info(f"Processing complete: {successful} successful, {failed} failed")
        logger.info(f"Results saved to {config.get('history_dir', 'history')}/ directory")
        logger.info("=" * 80)
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
