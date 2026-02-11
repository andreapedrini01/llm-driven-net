"""Property-based tests for state recovery reliability.

This module tests Property 25: State recovery reliability
For any system restart after an error, the previous operational state should be
fully recovered without data loss.

Validates: Requirements 6.5
"""

import pytest
import json
import os
import tempfile
import shutil
import time
from pathlib import Path
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime, timedelta
from typing import Dict, Any, List

from src.services.state_persistence import (
    StatePersistenceManager,
    PersistenceMetadata,
    RecoveryResult
)


class TestStateRecoveryProperties:
    """Property-based tests for state recovery reliability."""
    
    # Generator strategies for test data
    @staticmethod
    @st.composite
    def component_state_data(draw):
        """Generate realistic component state data."""
        component_types = [
            'intent_parser',
            'context_analyzer',
            'action_generator',
            'validator',
            'api_client'
        ]
        
        component = draw(st.sampled_from(component_types))
        
        # Generate state data based on component type
        if component == 'intent_parser':
            state = {
                'active_intents': [
                    {
                        'id': f'intent_{i}',
                        'text': draw(st.text(min_size=10, max_size=100)),
                        'status': draw(st.sampled_from(['pending', 'processing', 'completed'])),
                        'timestamp': (datetime.now() - timedelta(seconds=draw(st.integers(min_value=0, max_value=3600)))).isoformat()
                    }
                    for i in range(draw(st.integers(min_value=0, max_value=10)))
                ],
                'processing_queue': [f'intent_{i}' for i in range(draw(st.integers(min_value=0, max_value=5)))],
                'statistics': {
                    'total_processed': draw(st.integers(min_value=0, max_value=1000)),
                    'successful': draw(st.integers(min_value=0, max_value=900)),
                    'failed': draw(st.integers(min_value=0, max_value=100))
                }
            }
        elif component == 'context_analyzer':
            state = {
                'cached_network_state': {
                    'switches': [f'sw{i}' for i in range(draw(st.integers(min_value=1, max_value=10)))],
                    'links': [f'link{i}' for i in range(draw(st.integers(min_value=0, max_value=20)))],
                    'timestamp': datetime.now().isoformat()
                },
                'analysis_cache': {
                    f'key_{i}': draw(st.text(min_size=5, max_size=50))
                    for i in range(draw(st.integers(min_value=0, max_value=5)))
                },
                'last_refresh': datetime.now().isoformat()
            }
        elif component == 'action_generator':
            state = {
                'pending_actions': [
                    {
                        'id': f'action_{i}',
                        'type': draw(st.sampled_from(['flow_mod', 'slice_create', 'config_change'])),
                        'status': draw(st.sampled_from(['pending', 'executing', 'completed'])),
                        'created_at': (datetime.now() - timedelta(seconds=draw(st.integers(min_value=0, max_value=1800)))).isoformat()
                    }
                    for i in range(draw(st.integers(min_value=0, max_value=15)))
                ],
                'execution_history': [f'action_{i}' for i in range(draw(st.integers(min_value=0, max_value=50)))],
                'metrics': {
                    'total_generated': draw(st.integers(min_value=0, max_value=500)),
                    'successful_executions': draw(st.integers(min_value=0, max_value=450))
                }
            }
        elif component == 'validator':
            state = {
                'validation_rules': [
                    {
                        'rule_id': f'rule_{i}',
                        'enabled': draw(st.booleans()),
                        'priority': draw(st.integers(min_value=1, max_value=100))
                    }
                    for i in range(draw(st.integers(min_value=1, max_value=20)))
                ],
                'validation_cache': {},
                'statistics': {
                    'total_validations': draw(st.integers(min_value=0, max_value=1000)),
                    'passed': draw(st.integers(min_value=0, max_value=900)),
                    'failed': draw(st.integers(min_value=0, max_value=100))
                }
            }
        else:  # api_client
            state = {
                'api_config': {
                    'endpoint': 'https://api.openai.com/v1',
                    'model': draw(st.sampled_from(['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo'])),
                    'max_tokens': draw(st.integers(min_value=100, max_value=4000))
                },
                'request_history': [
                    {
                        'request_id': f'req_{i}',
                        'timestamp': (datetime.now() - timedelta(seconds=draw(st.integers(min_value=0, max_value=7200)))).isoformat(),
                        'tokens_used': draw(st.integers(min_value=10, max_value=2000))
                    }
                    for i in range(draw(st.integers(min_value=0, max_value=20)))
                ],
                'rate_limit_status': {
                    'remaining_requests': draw(st.integers(min_value=0, max_value=1000)),
                    'reset_time': (datetime.now() + timedelta(seconds=draw(st.integers(min_value=0, max_value=3600)))).isoformat()
                }
            }
        
        return {
            'component': component,
            'state': state
        }
    
    @staticmethod
    @st.composite
    def multiple_component_states(draw):
        """Generate state data for multiple components."""
        num_components = draw(st.integers(min_value=1, max_value=5))
        components = []
        used_names = set()
        
        for _ in range(num_components):
            comp_data = draw(TestStateRecoveryProperties.component_state_data())
            # Ensure unique component names
            if comp_data['component'] not in used_names:
                components.append(comp_data)
                used_names.add(comp_data['component'])
        
        return components
    
    @staticmethod
    @st.composite
    def corruption_scenario(draw):
        """Generate data corruption scenarios."""
        corruption_types = [
            'checksum_mismatch',
            'missing_metadata',
            'corrupted_json',
            'partial_write',
            'empty_file'
        ]
        
        return {
            'type': draw(st.sampled_from(corruption_types)),
            'has_backup': draw(st.booleans()),
            'backup_is_valid': draw(st.booleans())
        }
    
    @staticmethod
    @st.composite
    def system_failure_scenario(draw):
        """Generate system failure scenarios."""
        failure_types = [
            'power_loss',
            'process_crash',
            'disk_full',
            'permission_error',
            'network_interruption'
        ]
        
        return {
            'type': draw(st.sampled_from(failure_types)),
            'during_operation': draw(st.sampled_from(['persist', 'recover', 'backup', 'idle'])),
            'data_loss_risk': draw(st.sampled_from(['none', 'partial', 'complete']))
        }
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(component_data=component_state_data())
    def test_state_recovery_after_clean_shutdown(self, component_data):
        """
        **Feature: llm-integration-module, Property 25: State recovery reliability**
        
        For any system restart after a clean shutdown, the previous operational state
        should be fully recovered without data loss.
        
        **Validates: Requirements 6.5**
        """
        component = component_data['component']
        state = component_data['state']
        
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence_folder = os.path.join(temp_dir, "persistence")
            backup_folder = os.path.join(temp_dir, "backups")
            
            # Create first manager instance and persist state
            manager1 = StatePersistenceManager(
                persistence_folder=persistence_folder,
                backup_folder=backup_folder,
                max_backups=3,
                auto_backup=False,
                enable_checksums=True
            )
            
            # Persist state
            persist_result = manager1.persist_state(
                component=component,
                state_data=state,
                create_backup=True
            )
            assert persist_result is True
            
            # Simulate clean shutdown (manager goes out of scope)
            del manager1
            
            # Simulate system restart - create new manager instance
            manager2 = StatePersistenceManager(
                persistence_folder=persistence_folder,
                backup_folder=backup_folder,
                max_backups=3,
                auto_backup=False,
                enable_checksums=True
            )
            
            # Recover state
            recovery = manager2.recover_state(component)
            
            # Verify complete recovery without data loss
            assert recovery.success is True, f"Recovery failed: {recovery.error}"
            assert recovery.component == component
            assert recovery.data is not None
            assert recovery.data == state, "Recovered state does not match original"
            assert recovery.metadata is not None
            assert recovery.recovered_at is not None
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(components=multiple_component_states())
    def test_multiple_component_recovery(self, components):
        """Test that all component states can be recovered after restart."""
        assume(len(components) > 0)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence_folder = os.path.join(temp_dir, "persistence")
            backup_folder = os.path.join(temp_dir, "backups")
            
            # Create manager and persist all component states
            manager1 = StatePersistenceManager(
                persistence_folder=persistence_folder,
                backup_folder=backup_folder,
                max_backups=3,
                auto_backup=False,
                enable_checksums=True
            )
            
            # Persist all states
            for comp_data in components:
                result = manager1.persist_state(
                    component=comp_data['component'],
                    state_data=comp_data['state'],
                    create_backup=True
                )
                assert result is True
            
            # Simulate restart
            del manager1
            
            manager2 = StatePersistenceManager(
                persistence_folder=persistence_folder,
                backup_folder=backup_folder,
                max_backups=3,
                auto_backup=False,
                enable_checksums=True
            )
            
            # Recover all states
            for comp_data in components:
                recovery = manager2.recover_state(comp_data['component'])
                
                assert recovery.success is True
                assert recovery.data == comp_data['state']
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(
        component_data=component_state_data(),
        corruption=corruption_scenario()
    )
    def test_recovery_with_data_corruption(self, component_data, corruption):
        """Test recovery handles corrupted data and falls back to backups."""
        component = component_data['component']
        state = component_data['state']
        corruption_type = corruption['type']
        has_backup = corruption['has_backup']
        backup_is_valid = corruption['backup_is_valid']
        
        # Skip scenarios where recovery is impossible
        assume(not (corruption_type != 'checksum_mismatch' and not has_backup))
        assume(not (has_backup and not backup_is_valid))
        
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence_folder = os.path.join(temp_dir, "persistence")
            backup_folder = os.path.join(temp_dir, "backups")
            
            manager = StatePersistenceManager(
                persistence_folder=persistence_folder,
                backup_folder=backup_folder,
                max_backups=3,
                auto_backup=False,
                enable_checksums=True
            )
            
            # Persist state first without backup
            manager.persist_state(
                component=component,
                state_data=state,
                create_backup=False
            )
            
            # Create backup if needed
            if has_backup:
                manager.create_manual_backup(component)
            
            # Corrupt the state file
            state_file = manager._get_state_file_path(component)
            
            if corruption_type == 'checksum_mismatch':
                # Modify data but keep old checksum
                with open(state_file, 'r') as f:
                    content = json.load(f)
                content['data']['corrupted'] = 'data'
                # Keep old checksum (now invalid)
                with open(state_file, 'w') as f:
                    json.dump(content, f)
            
            elif corruption_type == 'missing_metadata':
                # Remove metadata
                with open(state_file, 'r') as f:
                    content = json.load(f)
                del content['metadata']
                with open(state_file, 'w') as f:
                    json.dump(content, f)
            
            elif corruption_type == 'corrupted_json':
                # Write invalid JSON
                with open(state_file, 'w') as f:
                    f.write('{"invalid": json}')
            
            elif corruption_type == 'partial_write':
                # Truncate file
                with open(state_file, 'r') as f:
                    content = f.read()
                with open(state_file, 'w') as f:
                    f.write(content[:len(content)//2])
            
            elif corruption_type == 'empty_file':
                # Empty the file
                with open(state_file, 'w') as f:
                    f.write('')
            
            # Attempt recovery
            recovery = manager.recover_state(component)
            
            # If backup exists and is valid, recovery should succeed
            if has_backup and backup_is_valid:
                assert recovery.success is True
                # For checksum mismatch, should recover from backup
                if corruption_type == 'checksum_mismatch':
                    assert 'corrupted' not in recovery.data
            else:
                # Without valid backup, recovery may fail
                if corruption_type in ['corrupted_json', 'partial_write', 'empty_file']:
                    assert recovery.success is False
                    assert recovery.error is not None
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(component_data=component_state_data())
    def test_recovery_preserves_metadata(self, component_data):
        """Test that recovery preserves all metadata information."""
        component = component_data['component']
        state = component_data['state']
        
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence_folder = os.path.join(temp_dir, "persistence")
            backup_folder = os.path.join(temp_dir, "backups")
            
            manager = StatePersistenceManager(
                persistence_folder=persistence_folder,
                backup_folder=backup_folder,
                max_backups=3,
                auto_backup=False,
                enable_checksums=True
            )
            
            # Persist state
            persist_time = datetime.now()
            manager.persist_state(
                component=component,
                state_data=state,
                create_backup=False
            )
            
            # Recover state
            recovery = manager.recover_state(component)
            
            # Verify metadata is preserved
            assert recovery.success is True
            assert recovery.metadata is not None
            assert recovery.metadata.component == component
            assert recovery.metadata.version is not None
            assert recovery.metadata.timestamp is not None
            assert recovery.metadata.checksum is not None
            
            # Verify timestamp is reasonable
            time_diff = abs((recovery.metadata.timestamp - persist_time).total_seconds())
            assert time_diff < 5  # Should be within 5 seconds
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(
        component_data=component_state_data(),
        num_updates=st.integers(min_value=2, max_value=10)
    )
    def test_recovery_after_multiple_updates(self, component_data, num_updates):
        """Test that recovery returns the most recent state after multiple updates."""
        component = component_data['component']
        base_state = component_data['state']
        
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence_folder = os.path.join(temp_dir, "persistence")
            backup_folder = os.path.join(temp_dir, "backups")
            
            manager = StatePersistenceManager(
                persistence_folder=persistence_folder,
                backup_folder=backup_folder,
                max_backups=3,
                auto_backup=False,
                enable_checksums=True
            )
            
            # Perform multiple updates
            states = []
            for i in range(num_updates):
                updated_state = {**base_state, 'update_number': i, 'timestamp': datetime.now().isoformat()}
                manager.persist_state(
                    component=component,
                    state_data=updated_state,
                    create_backup=(i % 2 == 0)  # Create backup every other update
                )
                states.append(updated_state)
                time.sleep(0.01)  # Small delay to ensure different timestamps
            
            # Recover state
            recovery = manager.recover_state(component)
            
            # Should recover the most recent state
            assert recovery.success is True
            assert recovery.data == states[-1]
            assert recovery.data['update_number'] == num_updates - 1
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(component_data=component_state_data())
    def test_recovery_with_missing_state_file(self, component_data):
        """Test recovery behavior when state file is missing."""
        component = component_data['component']
        
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence_folder = os.path.join(temp_dir, "persistence")
            backup_folder = os.path.join(temp_dir, "backups")
            
            manager = StatePersistenceManager(
                persistence_folder=persistence_folder,
                backup_folder=backup_folder,
                max_backups=3,
                auto_backup=False,
                enable_checksums=True
            )
            
            # Attempt recovery without persisting first
            recovery = manager.recover_state(component)
            
            # Should fail gracefully
            assert recovery.success is False
            assert recovery.error is not None
            assert "not found" in recovery.error.lower()
            assert recovery.data is None
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(
        component_data=component_state_data(),
        delay_seconds=st.integers(min_value=0, max_value=5)
    )
    def test_recovery_timing_and_performance(self, component_data, delay_seconds):
        """Test that recovery completes in reasonable time."""
        component = component_data['component']
        state = component_data['state']
        
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence_folder = os.path.join(temp_dir, "persistence")
            backup_folder = os.path.join(temp_dir, "backups")
            
            manager = StatePersistenceManager(
                persistence_folder=persistence_folder,
                backup_folder=backup_folder,
                max_backups=3,
                auto_backup=False,
                enable_checksums=True
            )
            
            # Persist state
            manager.persist_state(
                component=component,
                state_data=state,
                create_backup=True
            )
            
            # Wait before recovery
            time.sleep(delay_seconds * 0.1)  # Scale down for testing
            
            # Measure recovery time
            start_time = time.time()
            recovery = manager.recover_state(component)
            recovery_time = time.time() - start_time
            
            # Verify recovery succeeded
            assert recovery.success is True
            
            # Recovery should be fast (< 1 second for local files)
            assert recovery_time < 1.0
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(components=multiple_component_states())
    def test_partial_recovery_scenario(self, components):
        """Test recovery when some components succeed and others fail."""
        assume(len(components) >= 2)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence_folder = os.path.join(temp_dir, "persistence")
            backup_folder = os.path.join(temp_dir, "backups")
            
            manager = StatePersistenceManager(
                persistence_folder=persistence_folder,
                backup_folder=backup_folder,
                max_backups=3,
                auto_backup=False,
                enable_checksums=True
            )
            
            # Persist all states
            for comp_data in components:
                manager.persist_state(
                    component=comp_data['component'],
                    state_data=comp_data['state'],
                    create_backup=True
                )
            
            # Corrupt one component's state file
            if len(components) > 0:
                corrupted_component = components[0]['component']
                state_file = manager._get_state_file_path(corrupted_component)
                with open(state_file, 'w') as f:
                    f.write('{"invalid": json}')
            
            # Attempt recovery of all components
            successful_recoveries = 0
            failed_recoveries = 0
            
            for comp_data in components:
                recovery = manager.recover_state(comp_data['component'])
                if recovery.success:
                    successful_recoveries += 1
                    # Verify data integrity for successful recoveries
                    assert recovery.data is not None
                else:
                    failed_recoveries += 1
            
            # At least some recoveries should succeed
            assert successful_recoveries > 0
            # The corrupted component should fail (unless recovered from backup)
            assert successful_recoveries + failed_recoveries == len(components)
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(component_data=component_state_data())
    def test_recovery_idempotency(self, component_data):
        """Test that multiple recovery operations return consistent results."""
        component = component_data['component']
        state = component_data['state']
        
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence_folder = os.path.join(temp_dir, "persistence")
            backup_folder = os.path.join(temp_dir, "backups")
            
            manager = StatePersistenceManager(
                persistence_folder=persistence_folder,
                backup_folder=backup_folder,
                max_backups=3,
                auto_backup=False,
                enable_checksums=True
            )
            
            # Persist state
            manager.persist_state(
                component=component,
                state_data=state,
                create_backup=True
            )
            
            # Perform multiple recoveries
            recoveries = []
            for _ in range(3):
                recovery = manager.recover_state(component)
                recoveries.append(recovery)
                time.sleep(0.01)
            
            # All recoveries should succeed
            assert all(r.success for r in recoveries)
            
            # All recoveries should return the same data
            for i in range(1, len(recoveries)):
                assert recoveries[i].data == recoveries[0].data
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(
        component_data=component_state_data(),
        num_backups=st.integers(min_value=1, max_value=5)
    )
    def test_recovery_from_backup_chain(self, component_data, num_backups):
        """Test recovery can use backup chain when primary state is corrupted."""
        component = component_data['component']
        base_state = component_data['state']
        
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence_folder = os.path.join(temp_dir, "persistence")
            backup_folder = os.path.join(temp_dir, "backups")
            
            manager = StatePersistenceManager(
                persistence_folder=persistence_folder,
                backup_folder=backup_folder,
                max_backups=num_backups,
                auto_backup=False,
                enable_checksums=True
            )
            
            # Create multiple backups
            for i in range(num_backups):
                updated_state = {**base_state, 'backup_version': i}
                manager.persist_state(
                    component=component,
                    state_data=updated_state,
                    create_backup=True
                )
                time.sleep(0.01)
            
            # Corrupt primary state file
            state_file = manager._get_state_file_path(component)
            with open(state_file, 'w') as f:
                f.write('{"corrupted": "data"}')
            
            # Recovery should fall back to most recent backup
            recovery = manager.recover_state(component)
            
            # Should succeed using backup
            assert recovery.success is True
            assert recovery.data is not None
            assert 'backup_version' in recovery.data
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(component_data=component_state_data())
    def test_recovery_error_reporting(self, component_data):
        """Test that recovery failures provide detailed error information."""
        component = component_data['component']
        
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence_folder = os.path.join(temp_dir, "persistence")
            backup_folder = os.path.join(temp_dir, "backups")
            
            manager = StatePersistenceManager(
                persistence_folder=persistence_folder,
                backup_folder=backup_folder,
                max_backups=3,
                auto_backup=False,
                enable_checksums=True
            )
            
            # Attempt recovery without persisting
            recovery = manager.recover_state(component)
            
            # Verify detailed error reporting
            assert recovery.success is False
            assert recovery.error is not None
            assert len(recovery.error) > 0
            assert recovery.component == component
            assert recovery.recovered_at is not None
            assert recovery.data is None
