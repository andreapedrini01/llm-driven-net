#!/usr/bin/env python3
"""
Validation script for action_package.json compatibility with the system.

This script validates that the action package format from .vscode matches
the system's data models and API expectations.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.action_models import NetworkAction, ActionSequence, ActionType
from src.api.models import ActionRequest
from pydantic import ValidationError


class ActionPackageValidator:
    """Validator for action package format."""
    
    def __init__(self, package_path: str):
        self.package_path = package_path
        self.package_data = None
        self.validation_results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "info": []
        }
    
    def load_package(self) -> bool:
        """Load the action package JSON file."""
        try:
            with open(self.package_path, 'r') as f:
                self.package_data = json.load(f)
            self.validation_results["info"].append(f"✓ Loaded package from {self.package_path}")
            return True
        except FileNotFoundError:
            self.validation_results["errors"].append(f"✗ File not found: {self.package_path}")
            self.validation_results["is_valid"] = False
            return False
        except json.JSONDecodeError as e:
            self.validation_results["errors"].append(f"✗ Invalid JSON: {e}")
            self.validation_results["is_valid"] = False
            return False
    
    def validate_package_structure(self) -> bool:
        """Validate the overall package structure."""
        required_fields = [
            "package_id", "package_version", "created_at",
            "source_intent_id", "sequence_id", "actions"
        ]
        
        for field in required_fields:
            if field not in self.package_data:
                self.validation_results["errors"].append(
                    f"✗ Missing required field: {field}"
                )
                self.validation_results["is_valid"] = False
            else:
                self.validation_results["info"].append(
                    f"✓ Found required field: {field}"
                )
        
        # Check optional but recommended fields
        optional_fields = ["execution_order", "metadata", "validation", "rollback", "traceability"]
        for field in optional_fields:
            if field in self.package_data:
                self.validation_results["info"].append(
                    f"✓ Found optional field: {field}"
                )
            else:
                self.validation_results["warnings"].append(
                    f"⚠ Missing optional field: {field}"
                )
        
        return self.validation_results["is_valid"]
    
    def validate_actions(self) -> bool:
        """Validate individual actions against NetworkAction model."""
        if "actions" not in self.package_data:
            return False
        
        actions = self.package_data["actions"]
        self.validation_results["info"].append(
            f"✓ Found {len(actions)} actions to validate"
        )
        
        for idx, action_data in enumerate(actions):
            action_id = action_data.get("action_id", f"action_{idx}")
            
            try:
                # Map action package format to NetworkAction format
                network_action = NetworkAction(
                    id=action_data.get("action_id", f"action_{idx}"),
                    type=ActionType(action_data.get("action_type", "flow_mod")),
                    target=action_data.get("target_resource", "unknown"),
                    parameters=action_data.get("parameters", {}),
                    priority=action_data.get("execution_priority", 1000),
                    timeout=action_data.get("timeout_seconds", 30),
                    description=action_data.get("description")
                )
                
                # Validate action parameters
                validation_result = network_action.validate_action_parameters()
                
                if validation_result["is_valid"]:
                    self.validation_results["info"].append(
                        f"✓ Action {action_id}: Valid {network_action.type.value}"
                    )
                else:
                    self.validation_results["errors"].append(
                        f"✗ Action {action_id}: Validation failed - {validation_result['issues']}"
                    )
                    self.validation_results["is_valid"] = False
                
                # Report warnings
                if validation_result.get("warnings"):
                    for warning in validation_result["warnings"]:
                        self.validation_results["warnings"].append(
                            f"⚠ Action {action_id}: {warning}"
                        )
                
            except ValidationError as e:
                self.validation_results["errors"].append(
                    f"✗ Action {action_id}: Pydantic validation error - {e}"
                )
                self.validation_results["is_valid"] = False
            except Exception as e:
                self.validation_results["errors"].append(
                    f"✗ Action {action_id}: Unexpected error - {e}"
                )
                self.validation_results["is_valid"] = False
        
        return self.validation_results["is_valid"]
    
    def validate_api_compatibility(self) -> bool:
        """Validate compatibility with API Gateway ActionRequest model."""
        if "actions" not in self.package_data:
            return False
        
        self.validation_results["info"].append(
            "✓ Checking API Gateway compatibility..."
        )
        
        for idx, action_data in enumerate(self.package_data["actions"]):
            action_id = action_data.get("action_id", f"action_{idx}")
            
            try:
                # Map to ActionRequest format (what the API expects)
                action_request = ActionRequest(
                    type=action_data.get("action_type", "flow_mod"),
                    target=action_data.get("target_resource", "unknown"),
                    parameters=action_data.get("parameters", {}),
                    priority=action_data.get("execution_priority", 1000),
                    timeout=action_data.get("timeout_seconds", 30),
                    description=action_data.get("description")
                )
                
                self.validation_results["info"].append(
                    f"✓ Action {action_id}: Compatible with API Gateway"
                )
                
            except ValidationError as e:
                self.validation_results["errors"].append(
                    f"✗ Action {action_id}: API incompatibility - {e}"
                )
                self.validation_results["is_valid"] = False
        
        return self.validation_results["is_valid"]
    
    def validate_action_sequence(self) -> bool:
        """Validate the action sequence model compatibility."""
        try:
            # Create ActionSequence from package data
            actions = []
            for action_data in self.package_data.get("actions", []):
                network_action = NetworkAction(
                    id=action_data.get("action_id"),
                    type=ActionType(action_data.get("action_type")),
                    target=action_data.get("target_resource"),
                    parameters=action_data.get("parameters", {}),
                    priority=action_data.get("execution_priority", 1000),
                    timeout=action_data.get("timeout_seconds", 30),
                    description=action_data.get("description")
                )
                actions.append(network_action)
            
            # Create rollback actions if present
            rollback_actions = []
            if "rollback" in self.package_data and "rollback_actions" in self.package_data["rollback"]:
                for rollback_data in self.package_data["rollback"]["rollback_actions"]:
                    rollback_action = NetworkAction(
                        id=rollback_data.get("action_id"),
                        type=ActionType(rollback_data.get("action_type")),
                        target=rollback_data.get("target_resource"),
                        parameters=rollback_data.get("parameters", {}),
                        priority=rollback_data.get("execution_priority", 1000),
                        timeout=rollback_data.get("timeout_seconds", 30),
                        description=rollback_data.get("description")
                    )
                    rollback_actions.append(rollback_action)
            
            # Create ActionSequence
            action_sequence = ActionSequence(
                id=self.package_data.get("sequence_id"),
                intent_id=self.package_data.get("source_intent_id"),
                actions=actions,
                estimated_duration=self.package_data.get("metadata", {}).get("estimated_duration_seconds", 0),
                dependencies=self.package_data.get("metadata", {}).get("dependencies", []),
                rollback_plan=rollback_actions
            )
            
            # Validate sequence integrity
            integrity_result = action_sequence.validate_sequence_integrity()
            
            if integrity_result["is_valid"]:
                self.validation_results["info"].append(
                    f"✓ Action sequence is valid"
                )
                self.validation_results["info"].append(
                    f"  - {integrity_result['action_count']} actions"
                )
                self.validation_results["info"].append(
                    f"  - {integrity_result['unique_targets']} unique targets"
                )
                self.validation_results["info"].append(
                    f"  - Rollback plan: {'Yes' if integrity_result['has_rollback'] else 'No'}"
                )
            else:
                self.validation_results["errors"].append(
                    f"✗ Action sequence validation failed: {integrity_result['issues']}"
                )
                self.validation_results["is_valid"] = False
            
            # Report warnings
            for warning in integrity_result.get("warnings", []):
                self.validation_results["warnings"].append(f"⚠ {warning}")
            
            return integrity_result["is_valid"]
            
        except ValidationError as e:
            self.validation_results["errors"].append(
                f"✗ Action sequence validation error: {e}"
            )
            self.validation_results["is_valid"] = False
            return False
        except Exception as e:
            self.validation_results["errors"].append(
                f"✗ Unexpected error in sequence validation: {e}"
            )
            self.validation_results["is_valid"] = False
            return False
    
    def check_field_mapping(self) -> None:
        """Check field name mapping between package format and system models."""
        self.validation_results["info"].append("\n✓ Field Mapping Analysis:")
        
        mapping = {
            "action_id": "id (NetworkAction)",
            "action_type": "type (NetworkAction)",
            "target_resource": "target (NetworkAction)",
            "parameters": "parameters (NetworkAction)",
            "execution_priority": "priority (NetworkAction)",
            "timeout_seconds": "timeout (NetworkAction)",
            "description": "description (NetworkAction)",
            "sequence_id": "id (ActionSequence)",
            "source_intent_id": "intent_id (ActionSequence)",
            "actions": "actions (ActionSequence)",
            "metadata.estimated_duration_seconds": "estimated_duration (ActionSequence)",
            "metadata.dependencies": "dependencies (ActionSequence)",
            "rollback.rollback_actions": "rollback_plan (ActionSequence)"
        }
        
        for package_field, system_field in mapping.items():
            self.validation_results["info"].append(
                f"  {package_field} → {system_field}"
            )
    
    def generate_conversion_example(self) -> None:
        """Generate example code for converting package format to API request."""
        self.validation_results["info"].append("\n✓ Conversion Example:")
        self.validation_results["info"].append("""
# Convert action package to API requests:

import requests

# Load action package
with open('.vscode/action_package.json', 'r') as f:
    package = json.load(f)

# Submit each action to API
for action in package['actions']:
    api_request = {
        "type": action["action_type"],
        "target": action["target_resource"],
        "parameters": action["parameters"],
        "priority": action["execution_priority"],
        "timeout": action["timeout_seconds"],
        "description": action.get("description")
    }
    
    response = requests.post(
        "http://localhost:8000/api/v1/actions",
        json=api_request,
        headers={"Authorization": "Bearer YOUR_TOKEN"}
    )
    
    print(f"Action {action['action_id']}: {response.json()}")
""")
    
    def print_results(self) -> None:
        """Print validation results."""
        print("\n" + "=" * 80)
        print("ACTION PACKAGE VALIDATION RESULTS")
        print("=" * 80 + "\n")
        
        # Print info messages
        if self.validation_results["info"]:
            for msg in self.validation_results["info"]:
                print(msg)
        
        # Print warnings
        if self.validation_results["warnings"]:
            print("\nWARNINGS:")
            for msg in self.validation_results["warnings"]:
                print(msg)
        
        # Print errors
        if self.validation_results["errors"]:
            print("\nERRORS:")
            for msg in self.validation_results["errors"]:
                print(msg)
        
        # Print summary
        print("\n" + "=" * 80)
        if self.validation_results["is_valid"]:
            print("✓ VALIDATION PASSED - Action package is compatible with the system")
        else:
            print("✗ VALIDATION FAILED - Action package has compatibility issues")
        print("=" * 80 + "\n")
    
    def run_validation(self) -> bool:
        """Run all validation checks."""
        if not self.load_package():
            return False
        
        self.validate_package_structure()
        self.validate_actions()
        self.validate_api_compatibility()
        self.validate_action_sequence()
        self.check_field_mapping()
        self.generate_conversion_example()
        
        return self.validation_results["is_valid"]


def main():
    """Main entry point."""
    # Find action package file
    vscode_dir = Path(".vscode")
    action_packages = list(vscode_dir.glob("action_package*.json"))
    
    if not action_packages:
        print("✗ No action package files found in .vscode directory")
        return 1
    
    # Use the most recent one
    package_file = max(action_packages, key=lambda p: p.stat().st_mtime)
    print(f"Using action package: {package_file}")
    
    # Run validation
    validator = ActionPackageValidator(str(package_file))
    is_valid = validator.run_validation()
    validator.print_results()
    
    return 0 if is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
