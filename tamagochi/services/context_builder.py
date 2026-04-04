"""Context builder - Compresses data into compact context for LLM.

Builds minimal, token-efficient context from backend data to ground
the LLM's responses without sending raw verbose data.
"""

from dataclasses import dataclass
from typing import Optional
import json

from shared.schemas import (
    AgentModel,
    AlertModel,
    CompareModel,
    SummaryModel,
    AgentStatus,
)


@dataclass
class ContextStats:
    """Statistics about context compression."""
    original_chars: int
    compressed_chars: int
    estimated_tokens_saved: int

    @property
    def compression_ratio(self) -> float:
        if self.original_chars == 0:
            return 0.0
        return 1 - (self.compressed_chars / self.original_chars)


class ContextBuilder:
    """Builds compact context for LLM queries."""

    # Rough estimate: 1 token ≈ 4 chars for English text
    CHARS_PER_TOKEN = 4

    def __init__(self):
        self._last_stats: Optional[ContextStats] = None

    @property
    def last_stats(self) -> Optional[ContextStats]:
        """Get stats from last context build."""
        return self._last_stats

    def build_agent_context(self, agent: AgentModel) -> str:
        """Build compact context for a single agent."""
        status_desc = {
            AgentStatus.OK: "running normally",
            AgentStatus.IDLE: "idle/low activity",
            AgentStatus.HOT: "running hot, high resource use",
            AgentStatus.THROTTLED: "being throttled",
            AgentStatus.ERROR: "in error state",
        }

        lines = [
            f"Agent: {agent.name} ({agent.agent_id})",
            f"Status: {status_desc.get(agent.status, 'unknown')}",
            f"CPU: {agent.cpu_pct:.1f}%",
            f"Tokens: {agent.tokens_per_min:.0f}/min",
            f"Latency: {agent.avg_latency_ms:.0f}ms",
        ]

        if agent.temp_c is not None:
            lines.append(f"Temp: {agent.temp_c:.1f}C")

        if agent.estimated_energy_score is not None:
            score = agent.estimated_energy_score
            efficiency = "efficient" if score < 0.4 else ("moderate" if score < 0.7 else "wasteful")
            lines.append(f"Energy: {efficiency} ({score:.2f})")

        if agent.optimizer_action:
            lines.append(f"Last action: {agent.optimizer_action}")

        return "\n".join(lines)

    def build_agents_summary(self, agents: list[AgentModel]) -> str:
        """Build compact summary of all agents."""
        if not agents:
            return "No agents registered."

        hot = [a for a in agents if a.status == AgentStatus.HOT]
        idle = [a for a in agents if a.status == AgentStatus.IDLE]
        ok = [a for a in agents if a.status == AgentStatus.OK]

        lines = [f"Total agents: {len(agents)}"]

        if hot:
            hot_names = ", ".join(a.agent_id for a in hot)
            lines.append(f"Hot ({len(hot)}): {hot_names}")

        if ok:
            lines.append(f"OK: {len(ok)}")

        if idle:
            lines.append(f"Idle: {len(idle)}")

        # Top token consumers
        by_tokens = sorted(agents, key=lambda a: a.tokens_per_min, reverse=True)[:3]
        if by_tokens:
            top_str = ", ".join(f"{a.agent_id}:{a.tokens_per_min:.0f}" for a in by_tokens)
            lines.append(f"Top tokens/min: {top_str}")

        # Top CPU consumers
        by_cpu = sorted(agents, key=lambda a: a.cpu_pct, reverse=True)[:3]
        if by_cpu:
            top_str = ", ".join(f"{a.agent_id}:{a.cpu_pct:.0f}%" for a in by_cpu)
            lines.append(f"Top CPU: {top_str}")

        return "\n".join(lines)

    def build_alerts_context(self, alerts: list[AlertModel]) -> str:
        """Build compact context for alerts."""
        if not alerts:
            return "No active alerts."

        by_severity = {"critical": [], "warning": [], "info": []}
        for alert in alerts:
            by_severity[alert.severity.value].append(alert)

        lines = [f"Active alerts: {len(alerts)}"]

        if by_severity["critical"]:
            lines.append(f"Critical ({len(by_severity['critical'])}):")
            for a in by_severity["critical"][:3]:
                lines.append(f"  - {a.agent_id}: {a.message[:50]}")

        if by_severity["warning"]:
            lines.append(f"Warnings ({len(by_severity['warning'])}):")
            for a in by_severity["warning"][:3]:
                lines.append(f"  - {a.agent_id}: {a.message[:50]}")

        return "\n".join(lines)

    def build_comparison_context(self, comparison: CompareModel) -> str:
        """Build compact context for optimization comparison."""
        b, a = comparison.before, comparison.after

        cpu_change = a.cpu_pct - b.cpu_pct
        token_change = a.tokens_per_min - b.tokens_per_min
        latency_change = a.avg_latency_ms - b.avg_latency_ms

        lines = [
            f"Optimization for: {comparison.agent_id}",
            f"CPU: {b.cpu_pct:.1f}% -> {a.cpu_pct:.1f}% ({cpu_change:+.1f}%)",
            f"Tokens: {b.tokens_per_min:.0f} -> {a.tokens_per_min:.0f}/min ({token_change:+.0f})",
            f"Latency: {b.avg_latency_ms:.0f} -> {a.avg_latency_ms:.0f}ms ({latency_change:+.0f})",
        ]

        if b.estimated_energy_score and a.estimated_energy_score:
            energy_change = a.estimated_energy_score - b.estimated_energy_score
            lines.append(f"Energy: {b.estimated_energy_score:.2f} -> {a.estimated_energy_score:.2f} ({energy_change:+.2f})")

        if comparison.explanation_facts:
            lines.append("Facts:")
            for fact in comparison.explanation_facts[:5]:
                lines.append(f"  - {fact}")

        return "\n".join(lines)

    def build_summary_context(self, summary: SummaryModel) -> str:
        """Build compact context for system summary."""
        lines = [
            f"Active agents: {summary.active_agents}",
            f"Hot agents: {summary.hot_agents}",
            f"Open alerts: {summary.alerts_open}",
            f"Total tokens: {summary.tokens_per_min_total:.0f}/min",
        ]

        if summary.estimated_energy_score_total is not None:
            lines.append(f"System energy score: {summary.estimated_energy_score_total:.2f}")

        if summary.estimated_savings_pct is not None:
            lines.append(f"Estimated savings from optimizations: {summary.estimated_savings_pct:.1f}%")

        return "\n".join(lines)

    def build_question_context(
        self,
        question: str,
        agents: Optional[list[AgentModel]] = None,
        summary: Optional[SummaryModel] = None,
        alerts: Optional[list[AlertModel]] = None,
        comparison: Optional[CompareModel] = None,
        target_agent: Optional[AgentModel] = None,
    ) -> tuple[str, ContextStats]:
        """Build complete context for answering a question.

        Returns the context string and compression stats.
        """
        # Track original size (estimate if we had sent everything)
        original_size = 0

        sections = []

        # Add relevant context based on what's provided
        if target_agent:
            ctx = self.build_agent_context(target_agent)
            sections.append(f"Target agent:\n{ctx}")
            original_size += len(json.dumps(target_agent.model_dump()))

        if comparison:
            ctx = self.build_comparison_context(comparison)
            sections.append(f"Optimization data:\n{ctx}")
            original_size += len(json.dumps(comparison.model_dump()))

        if agents:
            ctx = self.build_agents_summary(agents)
            sections.append(f"All agents:\n{ctx}")
            original_size += sum(len(json.dumps(a.model_dump())) for a in agents)

        if summary:
            ctx = self.build_summary_context(summary)
            sections.append(f"System summary:\n{ctx}")
            original_size += len(json.dumps(summary.model_dump()))

        if alerts:
            ctx = self.build_alerts_context(alerts)
            sections.append(f"Alerts:\n{ctx}")
            original_size += sum(len(json.dumps(a.model_dump())) for a in alerts)

        # Build final context
        context = "\n\n".join(sections)
        compressed_size = len(context)

        # Calculate stats
        self._last_stats = ContextStats(
            original_chars=original_size,
            compressed_chars=compressed_size,
            estimated_tokens_saved=(original_size - compressed_size) // self.CHARS_PER_TOKEN,
        )

        return context, self._last_stats

    def extract_agent_id_from_question(self, question: str, agents: list[AgentModel]) -> Optional[str]:
        """Try to extract an agent ID mentioned in the question."""
        question_lower = question.lower()

        # Check for exact agent ID matches
        for agent in agents:
            if agent.agent_id.lower() in question_lower:
                return agent.agent_id

        # Check for name matches
        for agent in agents:
            # Try various name forms
            name_lower = agent.name.lower()
            name_parts = name_lower.split()

            if name_lower in question_lower:
                return agent.agent_id

            # Check first word of name
            if name_parts and name_parts[0] in question_lower:
                return agent.agent_id

        return None


# Singleton
_builder: Optional[ContextBuilder] = None


def get_context_builder() -> ContextBuilder:
    """Get or create context builder singleton."""
    global _builder
    if _builder is None:
        _builder = ContextBuilder()
    return _builder
