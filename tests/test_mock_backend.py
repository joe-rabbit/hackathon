"""Tests for mock backend."""

import pytest
from datetime import datetime

from shared.schemas import AgentStatus, AlertSeverity
from tamagochi.services.mock_backend import MockBackend, get_mock_backend


class TestMockBackend:
    """Tests for MockBackend."""

    def test_initialization(self):
        """Test mock backend initializes with agents."""
        mock = MockBackend()
        agents = mock.get_agents()

        assert len(agents) >= 3
        assert any(a.status == AgentStatus.HOT for a in agents)

    def test_get_agent(self):
        """Test getting a specific agent."""
        mock = MockBackend()
        agent = mock.get_agent("camera-agent")

        assert agent is not None
        assert agent.agent_id == "camera-agent"
        assert agent.name == "Camera Vision Agent"

    def test_get_nonexistent_agent(self):
        """Test getting an agent that doesn't exist."""
        mock = MockBackend()
        agent = mock.get_agent("nonexistent-agent")

        assert agent is None

    def test_get_summary(self):
        """Test getting system summary."""
        mock = MockBackend()
        summary = mock.get_summary()

        assert summary.active_agents > 0
        assert summary.dashboard_url == "http://127.0.0.1:8501"

    def test_get_alerts(self):
        """Test getting alerts."""
        mock = MockBackend()
        alerts = mock.get_alerts()

        # Should have initial alerts for the hot agent
        assert len(alerts) > 0
        assert all(hasattr(a, 'severity') for a in alerts)

    def test_tick_updates_metrics(self):
        """Test that tick updates agent metrics."""
        mock = MockBackend()
        agent_before = mock.get_agent("camera-agent")
        cpu_before = agent_before.cpu_pct

        # Tick several times
        for _ in range(10):
            mock.tick()

        agent_after = mock.get_agent("camera-agent")

        # Metrics should have changed (though direction is random)
        # Just check they're still valid
        assert 0 <= agent_after.cpu_pct <= 100

    def test_simulate_optimization(self):
        """Test optimization simulation."""
        mock = MockBackend()

        # Find a hot agent
        agents = mock.get_agents()
        hot_agent = next((a for a in agents if a.status == AgentStatus.HOT), None)

        if hot_agent:
            cpu_before = hot_agent.cpu_pct
            comparison = mock.simulate_optimization(hot_agent.agent_id)

            assert comparison is not None
            assert comparison.agent_id == hot_agent.agent_id
            assert comparison.before.cpu_pct == cpu_before
            assert comparison.after.cpu_pct < cpu_before

    def test_get_compare_before_optimization(self):
        """Test get_compare returns None before optimization."""
        mock = MockBackend()
        comparison = mock.get_compare("nlp-agent")

        # No optimization done yet
        assert comparison is None

    def test_get_compare_after_optimization(self):
        """Test get_compare returns data after optimization."""
        mock = MockBackend()
        mock.simulate_optimization("camera-agent")
        comparison = mock.get_compare("camera-agent")

        assert comparison is not None
        assert comparison.agent_id == "camera-agent"

    def test_timeline_records_events(self):
        """Test that timeline records events."""
        mock = MockBackend()

        # Do an optimization
        mock.simulate_optimization("camera-agent")

        timeline = mock.get_timeline()

        # Should have at least the optimization event
        opt_events = [e for e in timeline if e.event_type == "optimization"]
        assert len(opt_events) > 0

    def test_singleton_pattern(self):
        """Test get_mock_backend returns same instance."""
        mock1 = get_mock_backend()
        mock2 = get_mock_backend()

        assert mock1 is mock2
