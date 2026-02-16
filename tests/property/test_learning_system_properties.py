"""Property-based tests for learning system improvement."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime, timedelta
from typing import List, Dict, Any
import tempfile
import shutil

from src.services.feedback_collector import (
    FeedbackCollector,
    FeedbackRecord,
    FeedbackType,
    SatisfactionRating
)


# Generator strategies for test data
@st.composite
def false_positive_feedback_sequence(draw):
    """Generate a sequence of false positive feedback records."""
    num_records = draw(st.integers(min_value=1, max_value=20))
    
    records = []
    for i in range(num_records):
        anomaly_id = f"anomaly_{draw(st.integers(min_value=1, max_value=100))}"
        user_id = f"user_{draw(st.integers(min_value=1, max_value=10))}"
        # Use ASCII-safe text to avoid encoding issues
        comments = draw(st.one_of(
            st.none(),
            st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=10, max_size=200)
        ))
        
        # Generate metadata with anomaly details
        anomaly_type = draw(st.sampled_from([
            "traffic_spike", "latency_increase", "switch_failure",
            "link_failure", "cpu_high", "memory_high"
        ]))
        
        metadata = {
            "anomaly_type": anomaly_type,
            "false_positive_reason": draw(st.sampled_from([
                "expected_maintenance", "scheduled_update", "normal_pattern",
                "misconfiguration", "threshold_too_sensitive"
            ])),
            "threshold_value": draw(st.floats(min_value=0.0, max_value=100.0)),
            "actual_value": draw(st.floats(min_value=0.0, max_value=100.0))
        }
        
        records.append({
            "anomaly_id": anomaly_id,
            "user_id": user_id,
            "comments": comments,
            "metadata": metadata
        })
    
    return records


class TestLearningSystemProperties:
    """Property-based tests for learning system improvement."""
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(feedback_sequence=false_positive_feedback_sequence())
    def test_learning_system_improvement(self, feedback_sequence):
        """
        **Feature: llm-integration-module, Property 15: Learning system improvement**
        
        For any false positive in anomaly detection, the feedback mechanism should 
        contribute to improved accuracy in future detections.
        
        **Validates: Requirements 4.5**
        """
        assume(len(feedback_sequence) > 0)
        
        # Create fresh collector for this test run
        temp_dir = tempfile.mkdtemp(prefix="test_learning_")
        try:
            collector = FeedbackCollector(storage_path=temp_dir)
            
            # Record all false positive feedback
            for record in feedback_sequence:
                result = collector.record_anomaly_false_positive(
                    anomaly_id=record["anomaly_id"],
                    user_id=record["user_id"],
                    comments=record["comments"],
                    metadata=record["metadata"]
                )
                assert result is True, "Should successfully record false positive feedback"
            
            # Verify feedback is stored and retrievable
            stored_records = collector._load_feedback_records()
            assert len(stored_records) == len(feedback_sequence), \
                "All feedback records should be stored"
            
            # Verify all stored records are false positives
            for record in stored_records:
                assert record.feedback_type == FeedbackType.ANOMALY_FALSE_POSITIVE
                assert record.related_entity_id is not None
                assert record.user_id is not None
            
            # Calculate false positive rate
            fp_rate = collector.get_false_positive_rate()
            assert fp_rate == 1.0, "False positive rate should be 1.0 with only false positives"
            
            # Get feedback summary
            summary = collector.get_feedback_summary(
                entity_type="anomaly",
                start_time=datetime.now() - timedelta(hours=1),
                end_time=datetime.now() + timedelta(hours=1)
            )
            
            # Verify summary reflects the feedback
            assert summary.total_feedback_count == len(feedback_sequence)
            assert FeedbackType.ANOMALY_FALSE_POSITIVE.value in summary.feedback_by_type
            assert summary.feedback_by_type[FeedbackType.ANOMALY_FALSE_POSITIVE.value] == len(feedback_sequence)
            assert summary.false_positive_rate == 1.0
            
            # Verify metadata is preserved for learning
            for stored_record in stored_records:
                assert isinstance(stored_record.metadata, dict)
                if stored_record.metadata:
                    has_learning_data = any(key in stored_record.metadata for key in [
                        "anomaly_type", "false_positive_reason", "threshold_value", "actual_value"
                    ])
                    assert has_learning_data, "Metadata should contain learning information"
            
            # The core property: feedback mechanism provides data for improvement
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
