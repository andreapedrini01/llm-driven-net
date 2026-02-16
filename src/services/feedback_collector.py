"""Feedback collection system for learning and adaptation."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator
import json
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """Types of feedback that can be collected."""
    ANOMALY_FALSE_POSITIVE = "anomaly_false_positive"
    ANOMALY_MISSED = "anomaly_missed"
    ACTION_SUCCESS = "action_success"
    ACTION_FAILURE = "action_failure"
    INTENT_MISUNDERSTOOD = "intent_misunderstood"
    INTENT_CORRECT = "intent_correct"
    USER_SATISFACTION = "user_satisfaction"


class SatisfactionRating(int, Enum):
    """User satisfaction rating scale."""
    VERY_DISSATISFIED = 1
    DISSATISFIED = 2
    NEUTRAL = 3
    SATISFIED = 4
    VERY_SATISFIED = 5


class FeedbackRecord(BaseModel):
    """Individual feedback record."""
    id: str
    feedback_type: FeedbackType
    timestamp: datetime
    user_id: str
    related_entity_id: Optional[str] = None  # Intent ID, Anomaly ID, Action ID, etc.
    rating: Optional[SatisfactionRating] = None
    comments: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('comments')
    def validate_comments(cls, v):
        """Validate comments length."""
        if v and len(v) > 5000:
            raise ValueError("Comments cannot exceed 5000 characters")
        return v


class PerformanceMetric(BaseModel):
    """Performance metric record."""
    id: str
    metric_name: str
    metric_value: float
    timestamp: datetime
    component: str  # e.g., "intent_parser", "action_generator", "anomaly_detector"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('metric_name')
    def validate_metric_name(cls, v):
        """Validate metric name format."""
        if not v or len(v) < 3:
            raise ValueError("Metric name must be at least 3 characters")
        return v


class FeedbackSummary(BaseModel):
    """Summary of feedback for a specific entity or time period."""
    entity_type: str  # "anomaly", "intent", "action"
    entity_id: Optional[str] = None
    total_feedback_count: int = 0
    feedback_by_type: Dict[str, int] = Field(default_factory=dict)
    average_satisfaction: Optional[float] = None
    false_positive_rate: Optional[float] = None
    success_rate: Optional[float] = None
    time_period_start: datetime
    time_period_end: datetime


class FeedbackCollector:
    """
    System for collecting and managing feedback for learning and adaptation.
    Supports false positive reporting, user satisfaction tracking, and performance metrics.
    """
    
    def __init__(self, storage_path: str = "data/feedback"):
        """
        Initialize the feedback collector.
        
        Args:
            storage_path: Directory path for storing feedback data
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.feedback_file = self.storage_path / "feedback_records.jsonl"
        self.metrics_file = self.storage_path / "performance_metrics.jsonl"
        
        logger.info(f"FeedbackCollector initialized with storage at {self.storage_path}")
    
    def record_feedback(self, feedback: FeedbackRecord) -> bool:
        """
        Record user feedback.
        
        Args:
            feedback: The feedback record to store
            
        Returns:
            True if successfully recorded, False otherwise
        """
        try:
            with open(self.feedback_file, 'a', encoding='utf-8') as f:
                f.write(feedback.json() + '\n')
            
            logger.info(f"Recorded feedback: {feedback.feedback_type} for entity {feedback.related_entity_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record feedback: {e}")
            return False
    
    def record_anomaly_false_positive(
        self,
        anomaly_id: str,
        user_id: str,
        comments: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record feedback that an anomaly detection was a false positive.
        
        Args:
            anomaly_id: ID of the anomaly that was incorrectly detected
            user_id: ID of the user providing feedback
            comments: Optional explanation of why it's a false positive
            metadata: Additional context information
            
        Returns:
            True if successfully recorded
        """
        feedback = FeedbackRecord(
            id=f"fb_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            feedback_type=FeedbackType.ANOMALY_FALSE_POSITIVE,
            timestamp=datetime.now(),
            user_id=user_id,
            related_entity_id=anomaly_id,
            comments=comments,
            metadata=metadata or {}
        )
        
        return self.record_feedback(feedback)
    
    def record_user_satisfaction(
        self,
        user_id: str,
        rating: SatisfactionRating,
        related_entity_id: Optional[str] = None,
        comments: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record user satisfaction rating.
        
        Args:
            user_id: ID of the user providing feedback
            rating: Satisfaction rating (1-5)
            related_entity_id: Optional ID of related intent, action, or anomaly
            comments: Optional user comments
            metadata: Additional context information
            
        Returns:
            True if successfully recorded
        """
        feedback = FeedbackRecord(
            id=f"fb_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            feedback_type=FeedbackType.USER_SATISFACTION,
            timestamp=datetime.now(),
            user_id=user_id,
            related_entity_id=related_entity_id,
            rating=rating,
            comments=comments,
            metadata=metadata or {}
        )
        
        return self.record_feedback(feedback)
    
    def record_performance_metric(
        self,
        metric_name: str,
        metric_value: float,
        component: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record a performance metric.
        
        Args:
            metric_name: Name of the metric (e.g., "response_time_ms", "accuracy")
            metric_value: Numeric value of the metric
            component: Component being measured
            metadata: Additional context information
            
        Returns:
            True if successfully recorded
        """
        try:
            metric = PerformanceMetric(
                id=f"pm_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                metric_name=metric_name,
                metric_value=metric_value,
                timestamp=datetime.now(),
                component=component,
                metadata=metadata or {}
            )
            
            with open(self.metrics_file, 'a', encoding='utf-8') as f:
                f.write(metric.json() + '\n')
            
            logger.debug(f"Recorded metric: {metric_name}={metric_value} for {component}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record performance metric: {e}")
            return False
    
    def get_feedback_summary(
        self,
        entity_type: str,
        entity_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> FeedbackSummary:
        """
        Get summary of feedback for a specific entity or time period.
        
        Args:
            entity_type: Type of entity ("anomaly", "intent", "action")
            entity_id: Optional specific entity ID
            start_time: Optional start of time period
            end_time: Optional end of time period
            
        Returns:
            FeedbackSummary with aggregated statistics
        """
        feedback_records = self._load_feedback_records(start_time, end_time)
        
        # Filter by entity
        if entity_id:
            feedback_records = [f for f in feedback_records if f.related_entity_id == entity_id]
        
        # Calculate statistics
        total_count = len(feedback_records)
        feedback_by_type = {}
        satisfaction_ratings = []
        false_positives = 0
        total_anomaly_feedback = 0
        successes = 0
        total_action_feedback = 0
        
        for record in feedback_records:
            # Count by type
            type_str = record.feedback_type.value
            feedback_by_type[type_str] = feedback_by_type.get(type_str, 0) + 1
            
            # Collect satisfaction ratings
            if record.rating:
                satisfaction_ratings.append(record.rating.value)
            
            # Calculate false positive rate for anomalies
            if record.feedback_type == FeedbackType.ANOMALY_FALSE_POSITIVE:
                false_positives += 1
                total_anomaly_feedback += 1
            elif record.feedback_type == FeedbackType.ANOMALY_MISSED:
                total_anomaly_feedback += 1
            
            # Calculate success rate for actions
            if record.feedback_type == FeedbackType.ACTION_SUCCESS:
                successes += 1
                total_action_feedback += 1
            elif record.feedback_type == FeedbackType.ACTION_FAILURE:
                total_action_feedback += 1
        
        # Calculate averages
        avg_satisfaction = sum(satisfaction_ratings) / len(satisfaction_ratings) if satisfaction_ratings else None
        false_positive_rate = false_positives / total_anomaly_feedback if total_anomaly_feedback > 0 else None
        success_rate = successes / total_action_feedback if total_action_feedback > 0 else None
        
        return FeedbackSummary(
            entity_type=entity_type,
            entity_id=entity_id,
            total_feedback_count=total_count,
            feedback_by_type=feedback_by_type,
            average_satisfaction=avg_satisfaction,
            false_positive_rate=false_positive_rate,
            success_rate=success_rate,
            time_period_start=start_time or datetime.min,
            time_period_end=end_time or datetime.now()
        )
    
    def get_performance_metrics(
        self,
        component: Optional[str] = None,
        metric_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[PerformanceMetric]:
        """
        Retrieve performance metrics with optional filtering.
        
        Args:
            component: Optional component filter
            metric_name: Optional metric name filter
            start_time: Optional start of time period
            end_time: Optional end of time period
            
        Returns:
            List of matching performance metrics
        """
        metrics = self._load_performance_metrics(start_time, end_time)
        
        # Apply filters
        if component:
            metrics = [m for m in metrics if m.component == component]
        
        if metric_name:
            metrics = [m for m in metrics if m.metric_name == metric_name]
        
        return metrics
    
    def get_false_positive_rate(
        self,
        component: str = "anomaly_detector",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Optional[float]:
        """
        Calculate false positive rate for anomaly detection.
        
        Args:
            component: Component to calculate rate for
            start_time: Optional start of time period
            end_time: Optional end of time period
            
        Returns:
            False positive rate (0.0 to 1.0) or None if insufficient data
        """
        feedback_records = self._load_feedback_records(start_time, end_time)
        
        false_positives = sum(1 for f in feedback_records 
                             if f.feedback_type == FeedbackType.ANOMALY_FALSE_POSITIVE)
        
        total_anomaly_feedback = sum(1 for f in feedback_records 
                                     if f.feedback_type in [FeedbackType.ANOMALY_FALSE_POSITIVE,
                                                           FeedbackType.ANOMALY_MISSED])
        
        if total_anomaly_feedback == 0:
            return None
        
        return false_positives / total_anomaly_feedback
    
    def _load_feedback_records(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[FeedbackRecord]:
        """Load feedback records from storage with optional time filtering."""
        records = []
        
        if not self.feedback_file.exists():
            return records
        
        try:
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        record = FeedbackRecord.parse_raw(line)
                        
                        # Apply time filters
                        if start_time and record.timestamp < start_time:
                            continue
                        if end_time and record.timestamp > end_time:
                            continue
                        
                        records.append(record)
        
        except Exception as e:
            logger.error(f"Failed to load feedback records: {e}")
        
        return records
    
    def _load_performance_metrics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[PerformanceMetric]:
        """Load performance metrics from storage with optional time filtering."""
        metrics = []
        
        if not self.metrics_file.exists():
            return metrics
        
        try:
            with open(self.metrics_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        metric = PerformanceMetric.parse_raw(line)
                        
                        # Apply time filters
                        if start_time and metric.timestamp < start_time:
                            continue
                        if end_time and metric.timestamp > end_time:
                            continue
                        
                        metrics.append(metric)
        
        except Exception as e:
            logger.error(f"Failed to load performance metrics: {e}")
        
        return metrics
