"""Unit tests for feedback collection system."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

from src.services.feedback_collector import (
    FeedbackCollector,
    FeedbackRecord,
    FeedbackType,
    SatisfactionRating,
    PerformanceMetric
)


@pytest.fixture
def temp_storage():
    """Create temporary storage directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def collector(temp_storage):
    """Create a FeedbackCollector instance with temporary storage."""
    return FeedbackCollector(storage_path=temp_storage)


def test_feedback_collector_initialization(temp_storage):
    """Test that FeedbackCollector initializes correctly."""
    collector = FeedbackCollector(storage_path=temp_storage)
    
    assert collector.storage_path.exists()
    assert collector.feedback_file.parent.exists()
    assert collector.metrics_file.parent.exists()


def test_record_anomaly_false_positive(collector):
    """Test recording an anomaly false positive."""
    result = collector.record_anomaly_false_positive(
        anomaly_id="anomaly_123",
        user_id="user_456",
        comments="This was not actually an anomaly",
        metadata={"anomaly_type": "traffic_spike"}
    )
    
    assert result is True
    assert collector.feedback_file.exists()
    
    # Verify the record was saved
    records = collector._load_feedback_records()
    assert len(records) == 1
    assert records[0].feedback_type == FeedbackType.ANOMALY_FALSE_POSITIVE
    assert records[0].related_entity_id == "anomaly_123"
    assert records[0].user_id == "user_456"


def test_record_user_satisfaction(collector):
    """Test recording user satisfaction."""
    result = collector.record_user_satisfaction(
        user_id="user_789",
        rating=SatisfactionRating.SATISFIED,
        related_entity_id="intent_123",
        comments="Great job!"
    )
    
    assert result is True
    
    records = collector._load_feedback_records()
    assert len(records) == 1
    assert records[0].feedback_type == FeedbackType.USER_SATISFACTION
    assert records[0].rating == SatisfactionRating.SATISFIED
    assert records[0].comments == "Great job!"


def test_record_performance_metric(collector):
    """Test recording a performance metric."""
    result = collector.record_performance_metric(
        metric_name="response_time_ms",
        metric_value=150.5,
        component="intent_parser",
        metadata={"intent_type": "configuration"}
    )
    
    assert result is True
    assert collector.metrics_file.exists()
    
    metrics = collector._load_performance_metrics()
    assert len(metrics) == 1
    assert metrics[0].metric_name == "response_time_ms"
    assert metrics[0].metric_value == 150.5
    assert metrics[0].component == "intent_parser"


def test_get_feedback_summary(collector):
    """Test getting feedback summary."""
    # Record multiple feedback entries
    collector.record_anomaly_false_positive("anomaly_1", "user_1")
    collector.record_anomaly_false_positive("anomaly_2", "user_1")
    collector.record_user_satisfaction("user_1", SatisfactionRating.SATISFIED, "intent_1")
    collector.record_user_satisfaction("user_2", SatisfactionRating.VERY_SATISFIED, "intent_2")
    
    summary = collector.get_feedback_summary(entity_type="anomaly")
    
    assert summary.total_feedback_count == 4
    assert summary.feedback_by_type[FeedbackType.ANOMALY_FALSE_POSITIVE.value] == 2
    assert summary.feedback_by_type[FeedbackType.USER_SATISFACTION.value] == 2
    assert summary.average_satisfaction == 4.5  # (4 + 5) / 2


def test_get_feedback_summary_with_entity_filter(collector):
    """Test getting feedback summary filtered by entity ID."""
    collector.record_user_satisfaction("user_1", SatisfactionRating.SATISFIED, "intent_1")
    collector.record_user_satisfaction("user_2", SatisfactionRating.DISSATISFIED, "intent_2")
    
    summary = collector.get_feedback_summary(
        entity_type="intent",
        entity_id="intent_1"
    )
    
    assert summary.total_feedback_count == 1
    assert summary.entity_id == "intent_1"


def test_get_feedback_summary_with_time_filter(collector):
    """Test getting feedback summary filtered by time period."""
    now = datetime.now()
    
    # Record feedback
    collector.record_user_satisfaction("user_1", SatisfactionRating.SATISFIED)
    
    # Query with time range that includes the feedback
    summary = collector.get_feedback_summary(
        entity_type="intent",
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=1)
    )
    
    assert summary.total_feedback_count == 1


def test_get_performance_metrics(collector):
    """Test retrieving performance metrics."""
    collector.record_performance_metric("latency", 100.0, "intent_parser")
    collector.record_performance_metric("accuracy", 0.95, "anomaly_detector")
    collector.record_performance_metric("latency", 200.0, "action_generator")
    
    # Get all metrics
    all_metrics = collector.get_performance_metrics()
    assert len(all_metrics) == 3
    
    # Filter by component
    parser_metrics = collector.get_performance_metrics(component="intent_parser")
    assert len(parser_metrics) == 1
    assert parser_metrics[0].component == "intent_parser"
    
    # Filter by metric name
    latency_metrics = collector.get_performance_metrics(metric_name="latency")
    assert len(latency_metrics) == 2


def test_get_false_positive_rate(collector):
    """Test calculating false positive rate."""
    # Record some false positives and correct detections
    collector.record_anomaly_false_positive("anomaly_1", "user_1")
    collector.record_anomaly_false_positive("anomaly_2", "user_1")
    
    # Record a missed anomaly (not a false positive)
    feedback = FeedbackRecord(
        id="fb_test",
        feedback_type=FeedbackType.ANOMALY_MISSED,
        timestamp=datetime.now(),
        user_id="user_1",
        related_entity_id="anomaly_3"
    )
    collector.record_feedback(feedback)
    
    rate = collector.get_false_positive_rate()
    
    # 2 false positives out of 3 total anomaly feedback = 0.667
    assert rate is not None
    assert abs(rate - 0.667) < 0.01


def test_get_false_positive_rate_no_data(collector):
    """Test false positive rate with no data."""
    rate = collector.get_false_positive_rate()
    assert rate is None


def test_feedback_record_validation():
    """Test FeedbackRecord validation."""
    # Valid record
    record = FeedbackRecord(
        id="fb_123",
        feedback_type=FeedbackType.USER_SATISFACTION,
        timestamp=datetime.now(),
        user_id="user_1",
        rating=SatisfactionRating.SATISFIED
    )
    assert record.rating == SatisfactionRating.SATISFIED
    
    # Test comments length validation
    with pytest.raises(ValueError):
        FeedbackRecord(
            id="fb_456",
            feedback_type=FeedbackType.USER_SATISFACTION,
            timestamp=datetime.now(),
            user_id="user_1",
            comments="x" * 6000  # Exceeds 5000 character limit
        )


def test_performance_metric_validation():
    """Test PerformanceMetric validation."""
    # Valid metric
    metric = PerformanceMetric(
        id="pm_123",
        metric_name="response_time",
        metric_value=100.5,
        timestamp=datetime.now(),
        component="intent_parser"
    )
    assert metric.metric_name == "response_time"
    
    # Test metric name validation
    with pytest.raises(ValueError):
        PerformanceMetric(
            id="pm_456",
            metric_name="ab",  # Too short
            metric_value=100.0,
            timestamp=datetime.now(),
            component="test"
        )


def test_multiple_feedback_types(collector):
    """Test recording different types of feedback."""
    # Record various feedback types
    collector.record_anomaly_false_positive("anomaly_1", "user_1")
    
    feedback_success = FeedbackRecord(
        id="fb_success",
        feedback_type=FeedbackType.ACTION_SUCCESS,
        timestamp=datetime.now(),
        user_id="user_1",
        related_entity_id="action_1"
    )
    collector.record_feedback(feedback_success)
    
    feedback_failure = FeedbackRecord(
        id="fb_failure",
        feedback_type=FeedbackType.ACTION_FAILURE,
        timestamp=datetime.now(),
        user_id="user_1",
        related_entity_id="action_2"
    )
    collector.record_feedback(feedback_failure)
    
    summary = collector.get_feedback_summary(entity_type="action")
    
    assert summary.total_feedback_count == 3
    assert summary.success_rate == 0.5  # 1 success out of 2 action feedback


def test_feedback_persistence(temp_storage):
    """Test that feedback persists across collector instances."""
    # Create first collector and record feedback
    collector1 = FeedbackCollector(storage_path=temp_storage)
    collector1.record_user_satisfaction("user_1", SatisfactionRating.SATISFIED)
    
    # Create second collector with same storage
    collector2 = FeedbackCollector(storage_path=temp_storage)
    records = collector2._load_feedback_records()
    
    assert len(records) == 1
    assert records[0].rating == SatisfactionRating.SATISFIED
