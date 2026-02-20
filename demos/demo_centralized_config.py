"""Demo script for centralized configuration management."""

import sys
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.centralized_config import CentralizedConfigManager
from src.config.config_manager import ConfigManager


def print_section(title):
    """Print section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def demo_basic_versioning():
    """Demonstrate basic configuration versioning."""
    print_section("Basic Configuration Versioning")
    
    # Create manager
    manager = CentralizedConfigManager(db_path="./config/demo_versions.db")
    
    # Create initial version
    print("Creating initial configuration version...")
    config_v1 = {
        "api": {
            "host": "localhost",
            "port": 8000,
            "workers": 4
        },
        "logging": {
            "level": "INFO",
            "file": "./logs/app.log"
        }
    }
    
    version1 = manager.create_version(
        config_data=config_v1,
        user="admin",
        comment="Initial production configuration",
        ip_address="192.168.1.100"
    )
    
    print(f"✓ Created version {version1.version_number}")
    print(f"  Version ID: {version1.version_id}")
    print(f"  Checksum: {version1.checksum[:16]}...")
    print(f"  Created by: {version1.created_by}")
    
    time.sleep(1)
    
    # Update configuration
    print("\nUpdating configuration...")
    config_v2 = {
        "api": {
            "host": "0.0.0.0",  # Changed
            "port": 8080,  # Changed
            "workers": 8  # Changed
        },
        "logging": {
            "level": "DEBUG",  # Changed
            "file": "./logs/app.log"
        },
        "monitoring": {  # Added
            "enabled": True,
            "interval": 60
        }
    }
    
    version2 = manager.create_version(
        config_data=config_v2,
        user="admin",
        comment="Increased capacity and enabled monitoring",
        ip_address="192.168.1.100"
    )
    
    print(f"✓ Created version {version2.version_number}")
    print(f"  Parent version: {version2.parent_version[:16]}...")
    
    # Get current config
    print("\nCurrent active configuration:")
    current = manager.get_current_config()
    print(f"  API Port: {current['api']['port']}")
    print(f"  Workers: {current['api']['workers']}")
    print(f"  Monitoring: {current.get('monitoring', {}).get('enabled', False)}")


def demo_rollback():
    """Demonstrate configuration rollback."""
    print_section("Configuration Rollback")
    
    manager = CentralizedConfigManager(db_path="./config/demo_versions.db")
    
    # Get version history
    print("Version history:")
    history = manager.get_version_history(limit=10)
    for v in history:
        print(f"  Version {v['version_number']}: {v['comment']}")
        print(f"    Created by {v['created_by']} at {v['created_at']}")
        print(f"    Operation: {v['operation']}")
        print()
    
    # Rollback to version 1
    print("Rolling back to version 1...")
    rollback_version = manager.rollback_to_version(
        version_number=1,
        user="admin",
        comment="Reverting capacity changes due to performance issues",
        ip_address="192.168.1.100"
    )
    
    print(f"✓ Rolled back to version 1")
    print(f"  New version number: {rollback_version.version_number}")
    print(f"  Operation: {rollback_version.operation.value}")
    
    # Verify current config
    current = manager.get_current_config()
    print(f"\nCurrent configuration after rollback:")
    print(f"  API Port: {current['api']['port']}")
    print(f"  Workers: {current['api']['workers']}")
    print(f"  Monitoring: {current.get('monitoring', 'Not configured')}")


def demo_audit_trail():
    """Demonstrate audit trail functionality."""
    print_section("Configuration Audit Trail")
    
    manager = CentralizedConfigManager(db_path="./config/demo_versions.db")
    
    # Get complete audit trail
    print("Complete audit trail:")
    audit_entries = manager.get_audit_trail(limit=20)
    
    for entry in audit_entries:
        print(f"\n[{entry['timestamp']}]")
        print(f"  User: {entry['user']} from {entry['ip_address']}")
        print(f"  Operation: {entry['operation']}")
        print(f"  Version: {entry['version_id'][:16]}...")
        
        changes = entry['changes']
        if isinstance(changes, dict):
            if 'added' in changes and changes['added']:
                print(f"  Added: {list(changes['added'].keys())}")
            if 'modified' in changes and changes['modified']:
                print(f"  Modified: {list(changes['modified'].keys())}")
            if 'removed' in changes and changes['removed']:
                print(f"  Removed: {list(changes['removed'].keys())}")
    
    # Filter by user
    print("\n\nAudit entries for user 'admin':")
    admin_entries = manager.get_audit_trail(user="admin", limit=10)
    print(f"  Total entries: {len(admin_entries)}")


def demo_statistics():
    """Demonstrate statistics tracking."""
    print_section("Configuration Statistics")
    
    manager = CentralizedConfigManager(db_path="./config/demo_versions.db")
    
    stats = manager.get_stats()
    
    print("Configuration Management Statistics:")
    print(f"  Total versions: {stats['total_versions']}")
    print(f"  Total updates: {stats['total_updates']}")
    print(f"  Total rollbacks: {stats['total_rollbacks']}")
    print(f"  Current version: {stats['current_version_number']}")
    print(f"  Current checksum: {stats['current_checksum'][:16]}...")


def demo_integration_with_config_manager():
    """Demonstrate integration with ConfigManager."""
    print_section("Integration with ConfigManager")
    
    # Create config manager
    config_manager = ConfigManager(
        config_file="./config/system_config.example.yaml",
        enable_hot_reload=False
    )
    
    # Create centralized manager
    centralized_manager = CentralizedConfigManager(
        db_path="./config/demo_versions.db"
    )
    
    # Get current config from config manager
    current_config = config_manager.get_config_dict()
    
    print("Creating version from current ConfigManager state...")
    version = centralized_manager.create_version(
        config_data=current_config,
        user="system",
        comment="Snapshot from ConfigManager"
    )
    
    print(f"✓ Created version {version.version_number}")
    print(f"  Configuration sections: {list(current_config.keys())}")
    
    # Update via API
    print("\nUpdating configuration via ConfigManager API...")
    updates = {
        "api": {
            "rate_limit_requests": 200
        }
    }
    
    event = config_manager.update_from_api(updates)
    
    print(f"✓ Configuration updated")
    print(f"  Changes: {len(event.changes)} fields modified")
    
    # Create new version
    updated_config = config_manager.get_config_dict()
    version2 = centralized_manager.create_version(
        config_data=updated_config,
        user="admin",
        comment="Increased rate limit",
        ip_address="192.168.1.100"
    )
    
    print(f"✓ Created version {version2.version_number}")


def demo_version_comparison():
    """Demonstrate version comparison."""
    print_section("Version Comparison")
    
    manager = CentralizedConfigManager(db_path="./config/demo_versions.db")
    
    # Get two versions
    history = manager.get_version_history(limit=5)
    
    if len(history) >= 2:
        v1_num = history[1]['version_number']
        v2_num = history[0]['version_number']
        
        v1 = manager.get_version(v1_num)
        v2 = manager.get_version(v2_num)
        
        print(f"Comparing version {v1_num} vs version {v2_num}:")
        print(f"\nVersion {v1_num}:")
        print(f"  Created: {v1.created_at}")
        print(f"  By: {v1.created_by}")
        print(f"  Comment: {v1.comment}")
        
        print(f"\nVersion {v2_num}:")
        print(f"  Created: {v2.created_at}")
        print(f"  By: {v2.created_by}")
        print(f"  Comment: {v2.comment}")
        
        # Show differences
        print("\nConfiguration differences:")
        
        def compare_dicts(d1, d2, path=""):
            for key in set(list(d1.keys()) + list(d2.keys())):
                current_path = f"{path}.{key}" if path else key
                
                if key not in d1:
                    print(f"  + Added: {current_path} = {d2[key]}")
                elif key not in d2:
                    print(f"  - Removed: {current_path}")
                elif d1[key] != d2[key]:
                    if isinstance(d1[key], dict) and isinstance(d2[key], dict):
                        compare_dicts(d1[key], d2[key], current_path)
                    else:
                        print(f"  ~ Modified: {current_path}")
                        print(f"      Old: {d1[key]}")
                        print(f"      New: {d2[key]}")
        
        compare_dicts(v1.config_data, v2.config_data)


def main():
    """Run all demos."""
    print("\n" + "="*60)
    print("  Centralized Configuration Management Demo")
    print("="*60)
    
    try:
        demo_basic_versioning()
        demo_rollback()
        demo_audit_trail()
        demo_statistics()
        demo_integration_with_config_manager()
        demo_version_comparison()
        
        print("\n" + "="*60)
        print("  Demo completed successfully!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
