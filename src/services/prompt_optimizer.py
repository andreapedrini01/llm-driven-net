"""Prompt optimization pipeline for continuous improvement.

This module provides A/B testing, data collection, and automated refinement
of prompt templates based on feedback and performance metrics.
"""

import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, validator
import random
import statistics

from src.services.prompt_engineering import PromptType, PromptTemplate
from src.services.feedback_collector import FeedbackCollector, FeedbackType

logger = logging.getLogger(__name__)


class PromptVariant(BaseModel):
    """A variant of a prompt template for A/B testing."""
    variant_id: str
    prompt_type: PromptType
    system_message: str
    user_template: str
    response_schema: Dict[str, Any]
    max_tokens: int = 2000
    temperature: float = 0.1
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('variant_id')
    def validate_variant_id(cls, v):
        """Validate variant ID format."""
        if not v or len(v) < 3:
            raise ValueError("Variant ID must be at least 3 characters")
        return v


class PromptPerformanceData(BaseModel):
    """Performance data for a prompt variant."""
    variant_id: str
    prompt_type: PromptType
    total_uses: int = 0
    successful_parses: int = 0
    average_confidence: float = 0.0
    average_response_time: float = 0.0
    user_satisfaction_scores: List[float] = Field(default_factory=list)
    false_positive_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_updated: datetime = Field(default_factory=datetime.now)
    
    def get_success_rate(self) -> Optional[float]:
        """Calculate success rate."""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else None
    
    def get_parse_success_rate(self) -> Optional[float]:
        """Calculate parse success rate."""
        return self.successful_parses / self.total_uses if self.total_uses > 0 else None
    
    def get_average_satisfaction(self) -> Optional[float]:
        """Calculate average user satisfaction."""
        return statistics.mean(self.user_satisfaction_scores) if self.user_satisfaction_scores else None


class ABTestConfig(BaseModel):
    """Configuration for A/B testing."""
    prompt_type: PromptType
    control_variant_id: str
    test_variant_ids: List[str]
    traffic_split: Dict[str, float]  # variant_id -> percentage (0.0-1.0)
    start_time: datetime
    end_time: Optional[datetime] = None
    min_samples: int = 100
    confidence_threshold: float = 0.95
    is_active: bool = True
    
    @validator('traffic_split')
    def validate_traffic_split(cls, v):
        """Validate traffic split sums to 1.0."""
        total = sum(v.values())
        if not (0.99 <= total <= 1.01):  # Allow small floating point errors
            raise ValueError(f"Traffic split must sum to 1.0, got {total}")
        return v


class OptimizationRecommendation(BaseModel):
    """Recommendation for prompt optimization."""
    prompt_type: PromptType
    recommendation_type: str  # "adopt_variant", "adjust_temperature", "modify_template"
    description: str
    current_performance: Dict[str, Any]
    expected_improvement: Dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    priority: str = "medium"  # "low", "medium", "high"
    created_at: datetime = Field(default_factory=datetime.now)


class PromptOptimizer:
    """
    System for optimizing prompts through A/B testing and automated refinement.
    Collects performance data, runs experiments, and generates recommendations.
    """
    
    def __init__(
        self,
        storage_path: str = "data/prompt_optimization",
        feedback_collector: Optional[FeedbackCollector] = None
    ):
        """
        Initialize the prompt optimizer.
        
        Args:
            storage_path: Directory for storing optimization data
            feedback_collector: FeedbackCollector instance for accessing feedback
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.variants_file = self.storage_path / "prompt_variants.jsonl"
        self.performance_file = self.storage_path / "performance_data.jsonl"
        self.ab_tests_file = self.storage_path / "ab_tests.jsonl"
        self.recommendations_file = self.storage_path / "recommendations.jsonl"
        
        self.feedback_collector = feedback_collector or FeedbackCollector()
        
        # In-memory caches
        self._variants: Dict[str, PromptVariant] = {}
        self._performance_data: Dict[str, PromptPerformanceData] = {}
        self._active_ab_tests: Dict[PromptType, ABTestConfig] = {}
        
        self._load_data()
        
        logger.info(f"PromptOptimizer initialized with storage at {self.storage_path}")
    
    def register_variant(self, variant: PromptVariant) -> bool:
        """
        Register a new prompt variant for testing.
        
        Args:
            variant: The prompt variant to register
            
        Returns:
            True if successfully registered
        """
        try:
            self._variants[variant.variant_id] = variant
            
            # Initialize performance data
            if variant.variant_id not in self._performance_data:
                self._performance_data[variant.variant_id] = PromptPerformanceData(
                    variant_id=variant.variant_id,
                    prompt_type=variant.prompt_type
                )
            
            # Persist to storage
            with open(self.variants_file, 'a', encoding='utf-8') as f:
                f.write(variant.json() + '\n')
            
            logger.info(f"Registered prompt variant: {variant.variant_id} for {variant.prompt_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register variant: {e}")
            return False
    
    def start_ab_test(self, config: ABTestConfig) -> bool:
        """
        Start an A/B test for a prompt type.
        
        Args:
            config: A/B test configuration
            
        Returns:
            True if test started successfully
        """
        try:
            # Validate all variants exist
            all_variant_ids = [config.control_variant_id] + config.test_variant_ids
            for variant_id in all_variant_ids:
                if variant_id not in self._variants:
                    raise ValueError(f"Variant {variant_id} not found")
            
            # Store active test
            self._active_ab_tests[config.prompt_type] = config
            
            # Persist to storage
            with open(self.ab_tests_file, 'a', encoding='utf-8') as f:
                f.write(config.json() + '\n')
            
            logger.info(
                f"Started A/B test for {config.prompt_type} with "
                f"{len(config.test_variant_ids)} test variants"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to start A/B test: {e}")
            return False
    
    def select_variant(self, prompt_type: PromptType) -> Optional[str]:
        """
        Select a prompt variant based on active A/B tests.
        
        Args:
            prompt_type: Type of prompt needed
            
        Returns:
            Variant ID to use, or None if no test active
        """
        # Check if there's an active A/B test
        if prompt_type not in self._active_ab_tests:
            return None
        
        config = self._active_ab_tests[prompt_type]
        
        if not config.is_active:
            return None
        
        # Select variant based on traffic split
        rand_val = random.random()
        cumulative = 0.0
        
        for variant_id, percentage in config.traffic_split.items():
            cumulative += percentage
            if rand_val <= cumulative:
                logger.debug(f"Selected variant {variant_id} for {prompt_type}")
                return variant_id
        
        # Fallback to control
        return config.control_variant_id
    
    def record_prompt_usage(
        self,
        variant_id: str,
        success: bool,
        confidence: float,
        response_time: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record usage of a prompt variant.
        
        Args:
            variant_id: ID of the variant used
            success: Whether the prompt was successfully parsed
            confidence: Confidence score of the response
            response_time: Response time in seconds
            metadata: Additional metadata
            
        Returns:
            True if recorded successfully
        """
        try:
            if variant_id not in self._performance_data:
                logger.warning(f"Variant {variant_id} not found in performance data")
                return False
            
            perf_data = self._performance_data[variant_id]
            
            # Update statistics
            perf_data.total_uses += 1
            if success:
                perf_data.successful_parses += 1
            
            # Update running averages
            n = perf_data.total_uses
            perf_data.average_confidence = (
                (perf_data.average_confidence * (n - 1) + confidence) / n
            )
            perf_data.average_response_time = (
                (perf_data.average_response_time * (n - 1) + response_time) / n
            )
            perf_data.last_updated = datetime.now()
            
            # Persist updated performance data
            self._persist_performance_data(variant_id)
            
            logger.debug(f"Recorded usage for variant {variant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record prompt usage: {e}")
            return False
    
    def update_from_feedback(
        self,
        variant_id: str,
        feedback_type: FeedbackType,
        satisfaction_score: Optional[float] = None
    ) -> bool:
        """
        Update performance data based on user feedback.
        
        Args:
            variant_id: ID of the variant
            feedback_type: Type of feedback received
            satisfaction_score: Optional satisfaction score (1-5)
            
        Returns:
            True if updated successfully
        """
        try:
            if variant_id not in self._performance_data:
                logger.warning(f"Variant {variant_id} not found")
                return False
            
            perf_data = self._performance_data[variant_id]
            
            # Update based on feedback type
            if feedback_type == FeedbackType.ANOMALY_FALSE_POSITIVE:
                perf_data.false_positive_count += 1
            elif feedback_type == FeedbackType.ACTION_SUCCESS:
                perf_data.success_count += 1
            elif feedback_type == FeedbackType.ACTION_FAILURE:
                perf_data.failure_count += 1
            elif feedback_type == FeedbackType.USER_SATISFACTION and satisfaction_score:
                perf_data.user_satisfaction_scores.append(satisfaction_score)
            
            perf_data.last_updated = datetime.now()
            
            # Persist updated data
            self._persist_performance_data(variant_id)
            
            logger.debug(f"Updated variant {variant_id} from feedback: {feedback_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update from feedback: {e}")
            return False
    
    def analyze_ab_test(self, prompt_type: PromptType) -> Optional[Dict[str, Any]]:
        """
        Analyze results of an A/B test.
        
        Args:
            prompt_type: Type of prompt being tested
            
        Returns:
            Analysis results or None if test not found/insufficient data
        """
        if prompt_type not in self._active_ab_tests:
            logger.warning(f"No active A/B test for {prompt_type}")
            return None
        
        config = self._active_ab_tests[prompt_type]
        
        # Collect performance data for all variants
        variant_performances = {}
        
        for variant_id in [config.control_variant_id] + config.test_variant_ids:
            if variant_id in self._performance_data:
                variant_performances[variant_id] = self._performance_data[variant_id]
        
        # Check if we have enough samples
        min_samples_met = all(
            perf.total_uses >= config.min_samples
            for perf in variant_performances.values()
        )
        
        if not min_samples_met:
            logger.info(f"Insufficient samples for {prompt_type} A/B test analysis")
            return {
                "status": "insufficient_data",
                "min_samples_required": config.min_samples,
                "current_samples": {
                    vid: perf.total_uses
                    for vid, perf in variant_performances.items()
                }
            }
        
        # Compare variants
        control_perf = variant_performances[config.control_variant_id]
        
        results = {
            "status": "complete",
            "prompt_type": prompt_type.value,
            "control_variant": config.control_variant_id,
            "control_performance": {
                "success_rate": control_perf.get_success_rate(),
                "parse_success_rate": control_perf.get_parse_success_rate(),
                "average_confidence": control_perf.average_confidence,
                "average_satisfaction": control_perf.get_average_satisfaction(),
                "total_uses": control_perf.total_uses
            },
            "test_variants": []
        }
        
        # Analyze each test variant
        for test_variant_id in config.test_variant_ids:
            test_perf = variant_performances[test_variant_id]
            
            # Calculate improvements
            control_success = control_perf.get_success_rate() or 0
            test_success = test_perf.get_success_rate() or 0
            success_improvement = (
                ((test_success - control_success) / control_success * 100)
                if control_success > 0 else 0
            )
            
            control_confidence = control_perf.average_confidence
            test_confidence = test_perf.average_confidence
            confidence_improvement = (
                ((test_confidence - control_confidence) / control_confidence * 100)
                if control_confidence > 0 else 0
            )
            
            # Consider variant better if it improves on either metric significantly
            # or improves on both metrics even slightly
            is_better = (
                (test_success > control_success and test_confidence >= control_confidence) or
                (test_confidence > control_confidence and test_success >= control_success) or
                (test_success > control_success * 1.05 or test_confidence > control_confidence * 1.05)
            )
            
            results["test_variants"].append({
                "variant_id": test_variant_id,
                "performance": {
                    "success_rate": test_success,
                    "parse_success_rate": test_perf.get_parse_success_rate(),
                    "average_confidence": test_confidence,
                    "average_satisfaction": test_perf.get_average_satisfaction(),
                    "total_uses": test_perf.total_uses
                },
                "improvements": {
                    "success_rate_change_percent": success_improvement,
                    "confidence_change_percent": confidence_improvement
                },
                "is_better": is_better
            })
        
        logger.info(f"Completed A/B test analysis for {prompt_type}")
        return results
    
    def generate_recommendations(
        self,
        prompt_type: Optional[PromptType] = None,
        min_confidence: float = 0.7
    ) -> List[OptimizationRecommendation]:
        """
        Generate optimization recommendations based on collected data.
        
        Args:
            prompt_type: Optional specific prompt type to analyze
            min_confidence: Minimum confidence threshold for recommendations
            
        Returns:
            List of optimization recommendations
        """
        recommendations = []
        
        # Determine which prompt types to analyze
        prompt_types_to_analyze = [prompt_type] if prompt_type else list(PromptType)
        
        for ptype in prompt_types_to_analyze:
            # Check if there's an active A/B test
            if ptype in self._active_ab_tests:
                ab_results = self.analyze_ab_test(ptype)
                
                if ab_results and ab_results.get("status") == "complete":
                    # Generate recommendations from A/B test
                    recommendations.extend(
                        self._generate_ab_test_recommendations(ptype, ab_results, min_confidence)
                    )
            
            # Analyze performance trends
            recommendations.extend(
                self._generate_performance_recommendations(ptype, min_confidence)
            )
        
        # Sort by priority and confidence
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(
            key=lambda r: (priority_order.get(r.priority, 1), -r.confidence)
        )
        
        # Persist recommendations
        for rec in recommendations:
            self._persist_recommendation(rec)
        
        logger.info(f"Generated {len(recommendations)} optimization recommendations")
        return recommendations
    
    def _generate_ab_test_recommendations(
        self,
        prompt_type: PromptType,
        ab_results: Dict[str, Any],
        min_confidence: float
    ) -> List[OptimizationRecommendation]:
        """Generate recommendations from A/B test results."""
        recommendations = []
        
        control_perf = ab_results["control_performance"]
        
        for variant_result in ab_results["test_variants"]:
            if variant_result["is_better"]:
                success_improvement = variant_result["improvements"]["success_rate_change_percent"]
                confidence_improvement = variant_result["improvements"]["confidence_change_percent"]
                
                # Calculate recommendation confidence based on magnitude of improvements
                # Scale improvements to 0-1 range (10% improvement = 0.1, 100% = 1.0)
                success_factor = min(abs(success_improvement) / 100, 1.0)
                confidence_factor = min(abs(confidence_improvement) / 100, 1.0)
                
                # Average the two factors and ensure minimum of 0.6 for any improvement
                rec_confidence = max(
                    (success_factor + confidence_factor) / 2,
                    0.6
                )
                
                if rec_confidence >= min_confidence:
                    recommendations.append(OptimizationRecommendation(
                        prompt_type=prompt_type,
                        recommendation_type="adopt_variant",
                        description=(
                            f"Adopt variant {variant_result['variant_id']} as it shows "
                            f"{success_improvement:.1f}% improvement in success rate and "
                            f"{confidence_improvement:.1f}% improvement in confidence"
                        ),
                        current_performance=control_perf,
                        expected_improvement={
                            "success_rate_improvement": success_improvement,
                            "confidence_improvement": confidence_improvement
                        },
                        confidence=rec_confidence,
                        priority="high" if rec_confidence > 0.85 else "medium"
                    ))
        
        return recommendations
    
    def _generate_performance_recommendations(
        self,
        prompt_type: PromptType,
        min_confidence: float
    ) -> List[OptimizationRecommendation]:
        """Generate recommendations from performance trends."""
        recommendations = []
        
        # Find variants of this type
        variants_of_type = [
            (vid, perf) for vid, perf in self._performance_data.items()
            if perf.prompt_type == prompt_type and perf.total_uses >= 50
        ]
        
        if not variants_of_type:
            return recommendations
        
        # Analyze temperature settings
        for variant_id, perf_data in variants_of_type:
            variant = self._variants.get(variant_id)
            if not variant:
                continue
            
            # Check if low confidence suggests temperature adjustment
            if perf_data.average_confidence < 0.6 and perf_data.total_uses >= 100:
                recommendations.append(OptimizationRecommendation(
                    prompt_type=prompt_type,
                    recommendation_type="adjust_temperature",
                    description=(
                        f"Consider reducing temperature for variant {variant_id} "
                        f"(current: {variant.temperature}) to improve confidence "
                        f"(current avg: {perf_data.average_confidence:.2f})"
                    ),
                    current_performance={
                        "average_confidence": perf_data.average_confidence,
                        "temperature": variant.temperature
                    },
                    expected_improvement={
                        "confidence_increase": "10-20%"
                    },
                    confidence=0.7,
                    priority="medium"
                ))
            
            # Check if high false positive rate suggests template modification
            false_positive_rate = (
                perf_data.false_positive_count / perf_data.total_uses
                if perf_data.total_uses > 0 else 0
            )
            
            if false_positive_rate > 0.15 and perf_data.total_uses >= 100:
                recommendations.append(OptimizationRecommendation(
                    prompt_type=prompt_type,
                    recommendation_type="modify_template",
                    description=(
                        f"High false positive rate ({false_positive_rate:.1%}) for variant {variant_id}. "
                        f"Consider refining system message or adding more specific constraints."
                    ),
                    current_performance={
                        "false_positive_rate": false_positive_rate,
                        "total_uses": perf_data.total_uses
                    },
                    expected_improvement={
                        "false_positive_reduction": "30-50%"
                    },
                    confidence=0.75,
                    priority="high"
                ))
        
        return recommendations
    
    def _load_data(self) -> None:
        """Load optimization data from storage."""
        # Load variants
        if self.variants_file.exists():
            try:
                with open(self.variants_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            variant = PromptVariant.parse_raw(line)
                            self._variants[variant.variant_id] = variant
                logger.info(f"Loaded {len(self._variants)} prompt variants")
            except Exception as e:
                logger.error(f"Failed to load variants: {e}")
        
        # Load performance data
        if self.performance_file.exists():
            try:
                with open(self.performance_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            perf = PromptPerformanceData.parse_raw(line)
                            self._performance_data[perf.variant_id] = perf
                logger.info(f"Loaded performance data for {len(self._performance_data)} variants")
            except Exception as e:
                logger.error(f"Failed to load performance data: {e}")
        
        # Load active A/B tests
        if self.ab_tests_file.exists():
            try:
                with open(self.ab_tests_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            config = ABTestConfig.parse_raw(line)
                            if config.is_active:
                                self._active_ab_tests[config.prompt_type] = config
                logger.info(f"Loaded {len(self._active_ab_tests)} active A/B tests")
            except Exception as e:
                logger.error(f"Failed to load A/B tests: {e}")
    
    def _persist_performance_data(self, variant_id: str) -> None:
        """Persist performance data for a variant."""
        try:
            perf_data = self._performance_data[variant_id]
            
            # Rewrite entire file (simple approach for now)
            with open(self.performance_file, 'w', encoding='utf-8') as f:
                for vid, perf in self._performance_data.items():
                    f.write(perf.json() + '\n')
        
        except Exception as e:
            logger.error(f"Failed to persist performance data: {e}")
    
    def _persist_recommendation(self, recommendation: OptimizationRecommendation) -> None:
        """Persist an optimization recommendation."""
        try:
            with open(self.recommendations_file, 'a', encoding='utf-8') as f:
                f.write(recommendation.json() + '\n')
        except Exception as e:
            logger.error(f"Failed to persist recommendation: {e}")
