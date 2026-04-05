"""Tests for shared schemas."""

import pytest
from datetime import datetime

from shared.schemas import (
    AgentModel,
    AgentStatus,
    AlertModel,
    AlertSeverity,
    CompareModel,
    MetricSnapshot,
    SummaryModel,
    LLMExplanation,
    CommandResult,
    MochiMood,
)


class TestAgentModel:
    """Tests for AgentModel."""

    def test_create_agent(self):
        """Test creating an agent with required fields."""
        agent = AgentModel(
            agent_id="test-agent",
            name="Test Agent",
        )
        assert agent.agent_id == "test-agent"
        assert agent.name == "Test Agent"
        assert agent.status == AgentStatus.OK
        assert agent.cpu_pct == 0.0

    def test_agent_with_metrics(self):
        """Test agent with all metrics."""
        agent = AgentModel(
            agent_id="camera-agent",
            name="Camera Vision Agent",
            status=AgentStatus.HOT,
            cpu_pct=82.5,
            mem_mb=410.0,
            temp_c=68.0,
            tokens_in=1800,
            tokens_out=300,
            tokens_per_min=2100.0,
            avg_latency_ms=540.0,
            optimizer_action="prompt_compression",
            estimated_energy_score=0.81,
        )
        assert agent.is_hot is True
        assert agent.is_wasteful is True

    def test_agent_not_wasteful(self):
        """Test agent that is not wasteful."""
        agent = AgentModel(
            agent_id="efficient-agent",
            name="Efficient Agent",
            cpu_pct=25.0,
            tokens_per_min=500.0,
            estimated_energy_score=0.3,
        )
        assert agent.is_wasteful is False

    def test_agent_status_enum(self):
        """Test all agent status values."""
        for status in AgentStatus:
            agent = AgentModel(
                agent_id="test",
                name="Test",
                status=status,
            )
            assert agent.status == status


class TestAlertModel:
    """Tests for AlertModel."""

    def test_create_alert(self):
        """Test creating an alert."""
        alert = AlertModel(
            id="alert-001",
            agent_id="camera-agent",
            severity=AlertSeverity.WARNING,
            message="High CPU usage detected",
        )
        assert alert.id == "alert-001"
        assert alert.is_critical is False

    def test_critical_alert(self):
        """Test critical alert detection."""
        alert = AlertModel(
            id="alert-002",
            agent_id="test-agent",
            severity=AlertSeverity.CRITICAL,
            message="Agent unresponsive",
        )
        assert alert.is_critical is True


class TestCompareModel:
    """Tests for CompareModel."""

    def test_compare_with_improvement(self):
        """Test comparison showing improvement."""
        comparison = CompareModel(
            agent_id="test-agent",
            before=MetricSnapshot(
                cpu_pct=80.0,
                tokens_per_min=2000.0,
                avg_latency_ms=500.0,
                estimated_energy_score=0.8,
            ),
            after=MetricSnapshot(
                cpu_pct=40.0,
                tokens_per_min=1000.0,
                avg_latency_ms=300.0,
                estimated_energy_score=0.4,
            ),
            explanation_facts=["CPU reduced by 50%"],
        )

        assert comparison.cpu_improvement == 50.0
        assert comparison.token_improvement == 50.0

    def test_compare_no_improvement(self):
        """Test comparison with no improvement."""
        comparison = CompareModel(
            agent_id="test-agent",
            before=MetricSnapshot(cpu_pct=50.0, tokens_per_min=1000.0),
            after=MetricSnapshot(cpu_pct=50.0, tokens_per_min=1000.0),
        )

        assert comparison.cpu_improvement == 0.0


class TestSummaryModel:
    """Tests for SummaryModel."""

    def test_summary_defaults(self):
        """Test summary with defaults."""
        summary = SummaryModel()
        assert summary.active_agents == 0
        assert summary.hot_agents == 0
        assert summary.dashboard_url == "http://127.0.0.1:8501"

    def test_summary_with_data(self):
        """Test summary with data."""
        summary = SummaryModel(
            active_agents=5,
            hot_agents=2,
            alerts_open=3,
            tokens_per_min_total=5000.0,
            estimated_savings_pct=25.5,
        )
        assert summary.active_agents == 5
        assert summary.estimated_savings_pct == 25.5


class TestLLMExplanation:
    """Tests for LLMExplanation."""

    def test_explanation_minimal(self):
        """Test minimal explanation."""
        explanation = LLMExplanation(
            summary="Agent is running hot",
            problem="High CPU usage",
        )
        assert explanation.confidence == "medium"
        assert explanation.culprit_agent is None

    def test_explanation_full(self):
        """Test full explanation."""
        explanation = LLMExplanation(
            summary="Camera agent optimized successfully",
            culprit_agent="camera-agent",
            problem="High token usage",
            optimizer_effect="Prompt compression applied",
            evidence=["CPU reduced by 40%", "Tokens reduced by 50%"],
            confidence="high",
        )
        assert len(explanation.evidence) == 2


class TestMochiMood:
    """Tests for MochiMood enum."""

    def test_all_moods_exist(self):
        """Test all expected moods exist."""
        expected_moods = ["IDLE", "THINKING", "HAPPY", "WARNING", "SLEEPY", "CELEBRATE", "SICK"]
        for mood_name in expected_moods:
            assert hasattr(MochiMood, mood_name)
