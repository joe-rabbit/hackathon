"""Mock backend for offline demos and development.

Generates believable agent telemetry for 3-5 agents, including one intentionally
wasteful agent to demonstrate the optimizer's value.
"""

import asyncio
import random
import uuid
from datetime import datetime, timedelta
from typing import Optional

from shared.schemas import (
    AgentModel,
    AgentStatus,
    AlertModel,
    AlertSeverity,
    CompareModel,
    MetricSnapshot,
    SummaryModel,
    TimelineEvent,
)


class MockBackend:
    """Mock backend that generates realistic agent telemetry."""

    def __init__(self):
        self._agents: dict[str, AgentModel] = {}
        self._alerts: list[AlertModel] = []
        self._timeline: list[TimelineEvent] = []
        self._comparisons: dict[str, CompareModel] = {}
        self._optimization_history: dict[str, list[MetricSnapshot]] = {}
        self._running = False
        self._tick = 0
        self._initialize_agents()

    def _initialize_agents(self) -> None:
        """Create initial set of mock agents."""
        agent_configs = [
            {
                "agent_id": "camera-agent",
                "name": "Camera Vision Agent",
                "base_cpu": 75,
                "base_mem": 380,
                "base_tokens": 1800,
                "wasteful": True,  # This one will be intentionally wasteful
            },
            {
                "agent_id": "nlp-agent",
                "name": "NLP Processing Agent",
                "base_cpu": 35,
                "base_mem": 256,
                "base_tokens": 650,
                "wasteful": False,
            },
            {
                "agent_id": "vision-agent",
                "name": "Object Detection Agent",
                "base_cpu": 28,
                "base_mem": 180,
                "base_tokens": 320,
                "wasteful": False,
            },
            {
                "agent_id": "router-agent",
                "name": "Request Router Agent",
                "base_cpu": 12,
                "base_mem": 64,
                "base_tokens": 150,
                "wasteful": False,
            },
            {
                "agent_id": "audio-agent",
                "name": "Audio Processing Agent",
                "base_cpu": 45,
                "base_mem": 210,
                "base_tokens": 480,
                "wasteful": False,
            },
        ]

        for config in agent_configs:
            agent = self._create_agent(config)
            self._agents[agent.agent_id] = agent
            self._optimization_history[agent.agent_id] = []

        # Add initial alerts for the wasteful agent
        self._add_alert(
            "camera-agent",
            AlertSeverity.WARNING,
            "High CPU usage detected (78%). Consider prompt compression.",
        )
        self._add_alert(
            "camera-agent",
            AlertSeverity.INFO,
            "Token throughput above threshold (1850 tok/min).",
        )

    def _create_agent(self, config: dict) -> AgentModel:
        """Create an agent from config."""
        is_wasteful = config.get("wasteful", False)
        base_cpu = config["base_cpu"]
        base_tokens = config["base_tokens"]

        # Wasteful agents have worse metrics
        if is_wasteful:
            status = AgentStatus.HOT
            cpu = base_cpu + random.uniform(5, 15)
            tokens = base_tokens + random.randint(100, 300)
            energy_score = 0.75 + random.uniform(0, 0.15)
            latency = 450 + random.uniform(50, 150)
        else:
            status = random.choice([AgentStatus.OK, AgentStatus.OK, AgentStatus.IDLE])
            cpu = base_cpu + random.uniform(-5, 10)
            tokens = base_tokens + random.randint(-50, 100)
            energy_score = 0.25 + random.uniform(0, 0.25)
            latency = 120 + random.uniform(20, 80)

        return AgentModel(
            agent_id=config["agent_id"],
            name=config["name"],
            status=status,
            cpu_pct=min(100, max(0, cpu)),
            mem_mb=config["base_mem"] + random.uniform(-10, 30),
            temp_c=45 + random.uniform(0, 25) if is_wasteful else 38 + random.uniform(0, 12),
            tokens_in=int(tokens * 0.8),
            tokens_out=int(tokens * 0.2),
            tokens_per_min=tokens,
            avg_latency_ms=latency,
            optimizer_action=None,
            estimated_energy_score=energy_score,
            last_updated=datetime.now(),
        )

    def _add_alert(
        self,
        agent_id: str,
        severity: AlertSeverity,
        message: str,
    ) -> AlertModel:
        """Add a new alert."""
        alert = AlertModel(
            id=f"alert-{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            severity=severity,
            message=message,
            created_at=datetime.now(),
        )
        self._alerts.append(alert)
        return alert

    def _add_timeline_event(
        self,
        event_type: str,
        description: str,
        agent_id: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> TimelineEvent:
        """Add a timeline event."""
        event = TimelineEvent(
            id=f"event-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(),
            event_type=event_type,
            agent_id=agent_id,
            description=description,
            data=data,
        )
        self._timeline.append(event)
        # Keep only last 100 events
        if len(self._timeline) > 100:
            self._timeline = self._timeline[-100:]
        return event

    def tick(self) -> None:
        """Simulate one tick of time passing."""
        self._tick += 1

        for agent_id, agent in self._agents.items():
            # Add some variance to metrics
            cpu_delta = random.uniform(-3, 3)
            token_delta = random.randint(-50, 50)
            latency_delta = random.uniform(-10, 10)

            # Wasteful agent tends to get worse over time
            if agent.status == AgentStatus.HOT:
                cpu_delta += random.uniform(0, 2)
                token_delta += random.randint(0, 30)

            agent.cpu_pct = min(100, max(5, agent.cpu_pct + cpu_delta))
            agent.tokens_per_min = max(50, agent.tokens_per_min + token_delta)
            agent.avg_latency_ms = max(50, agent.avg_latency_ms + latency_delta)
            agent.tokens_in = int(agent.tokens_per_min * 0.8)
            agent.tokens_out = int(agent.tokens_per_min * 0.2)
            agent.last_updated = datetime.now()

            # Update status based on metrics
            if agent.cpu_pct > 75 or agent.tokens_per_min > 1500:
                agent.status = AgentStatus.HOT
                agent.estimated_energy_score = min(1.0, 0.6 + agent.cpu_pct / 200)
            elif agent.cpu_pct < 15:
                agent.status = AgentStatus.IDLE
                agent.estimated_energy_score = max(0.1, agent.cpu_pct / 100)
            else:
                agent.status = AgentStatus.OK
                agent.estimated_energy_score = 0.2 + agent.cpu_pct / 200

            # Random temperature fluctuations
            if agent.temp_c is not None:
                temp_base = 65 if agent.status == AgentStatus.HOT else 42
                agent.temp_c = temp_base + random.uniform(-5, 10)

        # Occasionally generate new alerts
        if self._tick % 10 == 0:
            hot_agents = [a for a in self._agents.values() if a.status == AgentStatus.HOT]
            if hot_agents and random.random() < 0.3:
                agent = random.choice(hot_agents)
                self._add_alert(
                    agent.agent_id,
                    AlertSeverity.WARNING,
                    f"Sustained high resource usage on {agent.name}",
                )

    def simulate_optimization(self, agent_id: str) -> Optional[CompareModel]:
        """Simulate an optimization event for an agent."""
        if agent_id not in self._agents:
            return None

        agent = self._agents[agent_id]

        # Store before snapshot
        before = MetricSnapshot(
            cpu_pct=agent.cpu_pct,
            tokens_per_min=agent.tokens_per_min,
            avg_latency_ms=agent.avg_latency_ms,
            estimated_energy_score=agent.estimated_energy_score,
        )

        # Apply "optimization" - improve metrics
        improvement = random.uniform(0.25, 0.45)
        agent.cpu_pct = max(15, agent.cpu_pct * (1 - improvement))
        agent.tokens_per_min = max(100, agent.tokens_per_min * (1 - improvement * 0.6))
        agent.avg_latency_ms = max(80, agent.avg_latency_ms * (1 - improvement * 0.3))
        agent.estimated_energy_score = max(0.15, (agent.estimated_energy_score or 0.5) * (1 - improvement))
        agent.status = AgentStatus.OK
        agent.optimizer_action = random.choice([
            "prompt_compression",
            "batch_optimization",
            "context_pruning",
            "rate_limiting",
            "cache_enabled",
        ])
        agent.last_updated = datetime.now()

        # Store after snapshot
        after = MetricSnapshot(
            cpu_pct=agent.cpu_pct,
            tokens_per_min=agent.tokens_per_min,
            avg_latency_ms=agent.avg_latency_ms,
            estimated_energy_score=agent.estimated_energy_score,
        )

        # Create comparison
        explanation_facts = [
            f"CPU usage reduced from {before.cpu_pct:.1f}% to {after.cpu_pct:.1f}%",
            f"Token rate reduced from {before.tokens_per_min:.0f} to {after.tokens_per_min:.0f} tok/min",
            f"Applied {agent.optimizer_action.replace('_', ' ')}",
        ]

        if before.estimated_energy_score and after.estimated_energy_score:
            savings = (1 - after.estimated_energy_score / before.estimated_energy_score) * 100
            explanation_facts.append(f"Estimated energy savings: {savings:.1f}%")

        comparison = CompareModel(
            agent_id=agent_id,
            before=before,
            after=after,
            explanation_facts=explanation_facts,
        )

        self._comparisons[agent_id] = comparison
        self._optimization_history[agent_id].append(before)

        # Add timeline event
        self._add_timeline_event(
            "optimization",
            f"Optimized {agent.name}: {agent.optimizer_action}",
            agent_id=agent_id,
            data={"improvement_pct": improvement * 100},
        )

        return comparison

    # API methods
    def get_agents(self) -> list[AgentModel]:
        """Get all agents."""
        return list(self._agents.values())

    def get_agent(self, agent_id: str) -> Optional[AgentModel]:
        """Get a specific agent."""
        return self._agents.get(agent_id)

    def get_alerts(self, limit: int = 20) -> list[AlertModel]:
        """Get recent alerts."""
        return sorted(self._alerts, key=lambda a: a.created_at, reverse=True)[:limit]

    def get_summary(self) -> SummaryModel:
        """Get system summary."""
        agents = self.get_agents()
        hot_count = sum(1 for a in agents if a.status == AgentStatus.HOT)
        total_tokens = sum(a.tokens_per_min for a in agents)
        total_energy = sum(a.estimated_energy_score or 0 for a in agents) / len(agents) if agents else 0

        # Calculate estimated savings from optimizations
        savings = None
        if self._comparisons:
            total_before = sum(c.before.tokens_per_min for c in self._comparisons.values())
            total_after = sum(c.after.tokens_per_min for c in self._comparisons.values())
            if total_before > 0:
                savings = ((total_before - total_after) / total_before) * 100

        return SummaryModel(
            active_agents=len([a for a in agents if a.status != AgentStatus.IDLE]),
            hot_agents=hot_count,
            alerts_open=len([a for a in self._alerts if a.severity != AlertSeverity.INFO]),
            tokens_per_min_total=total_tokens,
            estimated_energy_score_total=total_energy,
            estimated_savings_pct=savings,
            dashboard_url="http://127.0.0.1:8501",
        )

    def get_compare(self, agent_id: str) -> Optional[CompareModel]:
        """Get comparison data for an agent."""
        return self._comparisons.get(agent_id)

    def get_timeline(self, limit: int = 50) -> list[TimelineEvent]:
        """Get timeline events."""
        return sorted(self._timeline, key=lambda e: e.timestamp, reverse=True)[:limit]


# Singleton instance for the app
_mock_backend: Optional[MockBackend] = None


def get_mock_backend() -> MockBackend:
    """Get or create the mock backend singleton."""
    global _mock_backend
    if _mock_backend is None:
        _mock_backend = MockBackend()
    return _mock_backend
