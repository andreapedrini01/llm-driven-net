"""Tests for prompt optimization pipeline."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

from src.services.prompt_optimizer import (
    PromptOptimizer,
    PromptVariant,
    ABTestConfig,
    PromptPerformanceData,
    OptimizationRecommendation
)
from src.services.prompt_engineering import PromptType
from src.services.feedback_collector import FeedbackCollector, FeedbackType


@pytest.fixture
def temp_storage():
    """Create temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def feedback_collector(temp_storage):
    """Create feedback collector instance."""
    feedback_path = Path(temp_storage) / "feedback"
    return FeedbackCollector(storage_path=str(feedback_path))


@pytest.fixture
def optimizer(temp_storage, feedback_collector):
    """Create prompt optimizer instance."""
    optimizer_path = Path(temp_storage) / "optimizer"
    return PromptOptimizer(
        storage_path=str(optimizer_path),
        feedback_collector=feedback_collector
    )


@pytest.fixture
def sample_variant():
    """Create a sample prompt variant."""
    return PromptVariant(
        variant_id="test_variant_001",
        prompt_type=PromptType.INTENT_PARSING,
        system_message="You are a network expert.",
        user_template="Parse this intent: {intent_text}",
        response_schema={"intent_type": "string", "entities": []},
        max_tokens=1000,
        temperature=0.1
    )


class TestPromptVariantRegistration:
    """Test prompt variant registration."""
    
    def test_register_variant_success(self, optimizer, sample_variant):
        """Test successful variant registration."""
        result = optimizer.register_variant(sample_variant)
        
        assert result is True
        assert sample_variant.variant_id in optimizer._variants
        assert sample_variant.variant_id in optimizer._performance_data
    
    def test_register_multiple_variants(self, optimizer):
        """Test registering multiple variants."""
        variants = [
            PromptVariant(
                variant_id=f"variant_{i}",
                prompt_type=PromptType.ACTION_GENERATION,
                system_message=f"System message {i}",
                user_template=f"Template {i}",
                response_schema={}
            )
            for i in range(3)
        ]
        
        for variant in variants:
            result = optimizer.register_variant(variant)
            assert result is True
        
        assert len(optimizer._variants) == 3
    
    def test_variant_persistence(self, temp_storage, feedback_collector, sample_variant):
        """Test that variants are persisted to storage."""
        optimizer_path = Path(temp_storage) / "optimizer"
        
        # Create optimizer and register variant
        optimizer1 = PromptOptimizer(
            storage_path=str(optimizer_path),
            feedback_collector=feedback_collector
        )
        optimizer1.register_variant(sample_variant)
        
        # Create new optimizer instance and verify variant is loaded
        optimizer2 = PromptOptimizer(
            storage_path=str(optimizer_path),
            feedback_collector=feedback_collector
        )
        
        assert sample_variant.variant_id in optimizer2._variants


class TestABTesting:
    """Test A/B testing functionality."""
    
    def test_start_ab_test_success(self, optimizer):
        """Test starting an A/B test."""
        # Register variants
        control = PromptVariant(
            variant_id="control_v1",
            prompt_type=PromptType.INTENT_PARSING,
            system_message="Control",
            user_template="Control template",
            response_schema={}
        )
        test_variant = PromptVariant(
            variant_id="test_v1",
            prompt_type=PromptType.INTENT_PARSING,
            system_message="Test",
            user_template="Test template",
            response_schema={}
        )
        
        optimizer.register_variant(control)
        optimizer.register_variant(test_variant)
        
        # Create A/B test config
        config = ABTestConfig(
            prompt_type=PromptType.INTENT_PARSING,
            control_variant_id="control_v1",
            test_variant_ids=["test_v1"],
            traffic_split={"control_v1": 0.5, "test_v1": 0.5},
            start_time=datetime.now(),
            min_samples=50
        )
        
        result = optimizer.start_ab_test(config)
        
        assert result is True
        assert PromptType.INTENT_PARSING in optimizer._active_ab_tests
    
    def test_start_ab_test_missing_variant(self, optimizer):
        """Test starting A/B test with missing variant fails."""
        config = ABTestConfig(
            prompt_type=PromptType.INTENT_PARSING,
            control_variant_id="nonexistent",
            test_variant_ids=["also_nonexistent"],
            traffic_split={"nonexistent": 0.5, "also_nonexistent": 0.5},
            start_time=datetime.now(),
            min_samples=50
        )
        
        result = optimizer.start_ab_test(config)
        
        assert result is False
    
    def test_select_variant_with_active_test(self, optimizer):
        """Test variant selection with active A/B test."""
        # Setup variants and test
        control = PromptVariant(
            variant_id="control_v1",
            prompt_type=PromptType.ACTION_GENERATION,
            system_message="Control",
            user_template="Control",
            response_schema={}
        )
        test_variant = PromptVariant(
            variant_id="test_v1",
            prompt_type=PromptType.ACTION_GENERATION,
            system_message="Test",
            user_template="Test",
            response_schema={}
        )
        
        optimizer.register_variant(control)
        optimizer.register_variant(test_variant)
        
        config = ABTestConfig(
            prompt_type=PromptType.ACTION_GENERATION,
            control_variant_id="control_v1",
            test_variant_ids=["test_v1"],
            traffic_split={"control_v1": 0.7, "test_v1": 0.3},
            start_time=datetime.now(),
            min_samples=50
        )
        
        optimizer.start_ab_test(config)
        
        # Select variants multiple times and verify distribution
        selections = [
            optimizer.select_variant(PromptType.ACTION_GENERATION)
            for _ in range(100)
        ]
        
        # Should have both variants selected
        assert "control_v1" in selections
        assert "test_v1" in selections
        
        # Rough check of distribution (with tolerance)
        control_count = selections.count("control_v1")
        assert 50 < control_count < 90  # Should be around 70
    
    def test_select_variant_no_active_test(self, optimizer):
        """Test variant selection with no active test."""
        result = optimizer.select_variant(PromptType.CLARIFICATION)
        
        assert result is None


class TestPerformanceTracking:
    """Test performance tracking functionality."""
    
    def test_record_prompt_usage(self, optimizer, sample_variant):
        """Test recording prompt usage."""
        optimizer.register_variant(sample_variant)
        
        result = optimizer.record_prompt_usage(
            variant_id=sample_variant.variant_id,
            success=True,
            confidence=0.85,
            response_time=1.5
        )
        
        assert result is True
        
        perf_data = optimizer._performance_data[sample_variant.variant_id]
        assert perf_data.total_uses == 1
        assert perf_data.successful_parses == 1
        assert perf_data.average_confidence == 0.85
        assert perf_data.average_response_time == 1.5
    
    def test_record_multiple_usages(self, optimizer, sample_variant):
        """Test recording multiple usages updates averages correctly."""
        optimizer.register_variant(sample_variant)
        
        # Record multiple usages
        usages = [
            (True, 0.8, 1.0),
            (True, 0.9, 1.5),
            (False, 0.6, 2.0),
            (True, 0.85, 1.2)
        ]
        
        for success, confidence, response_time in usages:
            optimizer.record_prompt_usage(
                variant_id=sample_variant.variant_id,
                success=success,
                confidence=confidence,
                response_time=response_time
            )
        
        perf_data = optimizer._performance_data[sample_variant.variant_id]
        
        assert perf_data.total_uses == 4
        assert perf_data.successful_parses == 3
        
        # Check averages
        expected_avg_confidence = (0.8 + 0.9 + 0.6 + 0.85) / 4
        expected_avg_response_time = (1.0 + 1.5 + 2.0 + 1.2) / 4
        
        assert abs(perf_data.average_confidence - expected_avg_confidence) < 0.01
        assert abs(perf_data.average_response_time - expected_avg_response_time) < 0.01
    
    def test_update_from_feedback(self, optimizer, sample_variant):
        """Test updating performance from feedback."""
        optimizer.register_variant(sample_variant)
        
        # Record various feedback types
        optimizer.update_from_feedback(
            variant_id=sample_variant.variant_id,
            feedback_type=FeedbackType.ACTION_SUCCESS
        )
        optimizer.update_from_feedback(
            variant_id=sample_variant.variant_id,
            feedback_type=FeedbackType.ACTION_FAILURE
        )
        optimizer.update_from_feedback(
            variant_id=sample_variant.variant_id,
            feedback_type=FeedbackType.ANOMALY_FALSE_POSITIVE
        )
        optimizer.update_from_feedback(
            variant_id=sample_variant.variant_id,
            feedback_type=FeedbackType.USER_SATISFACTION,
            satisfaction_score=4.5
        )
        
        perf_data = optimizer._performance_data[sample_variant.variant_id]
        
        assert perf_data.success_count == 1
        assert perf_data.failure_count == 1
        assert perf_data.false_positive_count == 1
        assert len(perf_data.user_satisfaction_scores) == 1
        assert perf_data.user_satisfaction_scores[0] == 4.5


class TestABTestAnalysis:
    """Test A/B test analysis."""
    
    def test_analyze_ab_test_insufficient_data(self, optimizer):
        """Test analysis with insufficient data."""
        # Setup test
        control = PromptVariant(
            variant_id="control",
            prompt_type=PromptType.VALIDATION,
            system_message="Control",
            user_template="Control",
            response_schema={}
        )
        test_v = PromptVariant(
            variant_id="test",
            prompt_type=PromptType.VALIDATION,
            system_message="Test",
            user_template="Test",
            response_schema={}
        )
        
        optimizer.register_variant(control)
        optimizer.register_variant(test_v)
        
        config = ABTestConfig(
            prompt_type=PromptType.VALIDATION,
            control_variant_id="control",
            test_variant_ids=["test"],
            traffic_split={"control": 0.5, "test": 0.5},
            start_time=datetime.now(),
            min_samples=100
        )
        
        optimizer.start_ab_test(config)
        
        # Record only a few usages
        for _ in range(10):
            optimizer.record_prompt_usage("control", True, 0.8, 1.0)
            optimizer.record_prompt_usage("test", True, 0.85, 1.0)
        
        result = optimizer.analyze_ab_test(PromptType.VALIDATION)
        
        assert result is not None
        assert result["status"] == "insufficient_data"
    
    def test_analyze_ab_test_complete(self, optimizer):
        """Test complete A/B test analysis."""
        # Setup test
        control = PromptVariant(
            variant_id="control",
            prompt_type=PromptType.ANOMALY_ANALYSIS,
            system_message="Control",
            user_template="Control",
            response_schema={}
        )
        test_v = PromptVariant(
            variant_id="test",
            prompt_type=PromptType.ANOMALY_ANALYSIS,
            system_message="Test",
            user_template="Test",
            response_schema={}
        )
        
        optimizer.register_variant(control)
        optimizer.register_variant(test_v)
        
        config = ABTestConfig(
            prompt_type=PromptType.ANOMALY_ANALYSIS,
            control_variant_id="control",
            test_variant_ids=["test"],
            traffic_split={"control": 0.5, "test": 0.5},
            start_time=datetime.now(),
            min_samples=50
        )
        
        optimizer.start_ab_test(config)
        
        # Record enough usages with test variant performing better
        for _ in range(60):
            optimizer.record_prompt_usage("control", True, 0.75, 1.0)
            optimizer.update_from_feedback("control", FeedbackType.ACTION_SUCCESS)
        
        for _ in range(60):
            optimizer.record_prompt_usage("test", True, 0.85, 0.9)
            optimizer.update_from_feedback("test", FeedbackType.ACTION_SUCCESS)
            optimizer.update_from_feedback("test", FeedbackType.ACTION_SUCCESS)
        
        result = optimizer.analyze_ab_test(PromptType.ANOMALY_ANALYSIS)
        
        assert result is not None
        assert result["status"] == "complete"
        assert result["control_variant"] == "control"
        assert len(result["test_variants"]) == 1
        
        test_result = result["test_variants"][0]
        assert test_result["variant_id"] == "test"
        assert test_result["performance"]["average_confidence"] > result["control_performance"]["average_confidence"]


class TestRecommendationGeneration:
    """Test optimization recommendation generation."""
    
    def test_generate_recommendations_from_ab_test(self, optimizer):
        """Test generating recommendations from A/B test results."""
        # Setup successful A/B test
        control = PromptVariant(
            variant_id="control",
            prompt_type=PromptType.SLICE_ORCHESTRATION,
            system_message="Control",
            user_template="Control",
            response_schema={},
            temperature=0.2
        )
        test_v = PromptVariant(
            variant_id="test_better",
            prompt_type=PromptType.SLICE_ORCHESTRATION,
            system_message="Improved test",
            user_template="Improved",
            response_schema={},
            temperature=0.1
        )
        
        optimizer.register_variant(control)
        optimizer.register_variant(test_v)
        
        config = ABTestConfig(
            prompt_type=PromptType.SLICE_ORCHESTRATION,
            control_variant_id="control",
            test_variant_ids=["test_better"],
            traffic_split={"control": 0.5, "test_better": 0.5},
            start_time=datetime.now(),
            min_samples=50
        )
        
        optimizer.start_ab_test(config)
        
        # Simulate test variant performing significantly better
        for _ in range(100):
            optimizer.record_prompt_usage("control", True, 0.70, 1.5)
            optimizer.update_from_feedback("control", FeedbackType.ACTION_SUCCESS)
        
        for _ in range(100):
            optimizer.record_prompt_usage("test_better", True, 0.90, 1.2)
            optimizer.update_from_feedback("test_better", FeedbackType.ACTION_SUCCESS)
            optimizer.update_from_feedback("test_better", FeedbackType.ACTION_SUCCESS)
        
        recommendations = optimizer.generate_recommendations(
            prompt_type=PromptType.SLICE_ORCHESTRATION,
            min_confidence=0.5
        )
        
        assert len(recommendations) > 0
        
        # Should have recommendation to adopt better variant
        adopt_recs = [r for r in recommendations if r.recommendation_type == "adopt_variant"]
        assert len(adopt_recs) > 0
        assert "test_better" in adopt_recs[0].description
    
    def test_generate_temperature_recommendation(self, optimizer):
        """Test generating temperature adjustment recommendation."""
        variant = PromptVariant(
            variant_id="low_confidence_variant",
            prompt_type=PromptType.CLARIFICATION,
            system_message="System",
            user_template="Template",
            response_schema={},
            temperature=0.5
        )
        
        optimizer.register_variant(variant)
        
        # Simulate low confidence scores
        for _ in range(150):
            optimizer.record_prompt_usage(
                variant_id="low_confidence_variant",
                success=True,
                confidence=0.55,  # Below 0.6 threshold
                response_time=1.0
            )
        
        recommendations = optimizer.generate_recommendations(
            prompt_type=PromptType.CLARIFICATION,
            min_confidence=0.5
        )
        
        # Should recommend temperature adjustment
        temp_recs = [r for r in recommendations if r.recommendation_type == "adjust_temperature"]
        assert len(temp_recs) > 0
        assert "temperature" in temp_recs[0].description.lower()
    
    def test_generate_false_positive_recommendation(self, optimizer):
        """Test generating recommendation for high false positive rate."""
        variant = PromptVariant(
            variant_id="high_fp_variant",
            prompt_type=PromptType.ANOMALY_ANALYSIS,
            system_message="System",
            user_template="Template",
            response_schema={}
        )
        
        optimizer.register_variant(variant)
        
        # Simulate high false positive rate
        for _ in range(120):
            optimizer.record_prompt_usage(
                variant_id="high_fp_variant",
                success=True,
                confidence=0.8,
                response_time=1.0
            )
            # 20% false positive rate
            if _ % 5 == 0:
                optimizer.update_from_feedback(
                    variant_id="high_fp_variant",
                    feedback_type=FeedbackType.ANOMALY_FALSE_POSITIVE
                )
        
        recommendations = optimizer.generate_recommendations(
            prompt_type=PromptType.ANOMALY_ANALYSIS,
            min_confidence=0.5
        )
        
        # Should recommend template modification
        modify_recs = [r for r in recommendations if r.recommendation_type == "modify_template"]
        assert len(modify_recs) > 0
        assert "false positive" in modify_recs[0].description.lower()


class TestPerformanceDataMethods:
    """Test PromptPerformanceData methods."""
    
    def test_get_success_rate(self):
        """Test success rate calculation."""
        perf_data = PromptPerformanceData(
            variant_id="test",
            prompt_type=PromptType.INTENT_PARSING,
            success_count=80,
            failure_count=20
        )
        
        success_rate = perf_data.get_success_rate()
        
        assert success_rate == 0.8
    
    def test_get_success_rate_no_data(self):
        """Test success rate with no data."""
        perf_data = PromptPerformanceData(
            variant_id="test",
            prompt_type=PromptType.INTENT_PARSING
        )
        
        success_rate = perf_data.get_success_rate()
        
        assert success_rate is None
    
    def test_get_parse_success_rate(self):
        """Test parse success rate calculation."""
        perf_data = PromptPerformanceData(
            variant_id="test",
            prompt_type=PromptType.ACTION_GENERATION,
            total_uses=100,
            successful_parses=95
        )
        
        parse_rate = perf_data.get_parse_success_rate()
        
        assert parse_rate == 0.95
    
    def test_get_average_satisfaction(self):
        """Test average satisfaction calculation."""
        perf_data = PromptPerformanceData(
            variant_id="test",
            prompt_type=PromptType.VALIDATION,
            user_satisfaction_scores=[4.0, 5.0, 3.5, 4.5, 4.0]
        )
        
        avg_satisfaction = perf_data.get_average_satisfaction()
        
        assert avg_satisfaction == 4.2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
