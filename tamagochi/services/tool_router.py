"""Tool router - Routes commands and questions to appropriate handlers.

Provides a set of tools that fetch trusted data from the backend/mock
for slash commands and natural language questions.
"""

from dataclasses import dataclass
from typing import Optional, Callable, Awaitable, Any
import asyncio
import logging

from shared.schemas import (
    AgentModel,
    AlertModel,
    CompareModel,
    CommandResult,
    SummaryModel,
    TimelineEvent,
)
from tamagochi.services.backend_client import BackendClient, get_backend_client

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Definition of a tool that can be called by the router."""
    name: str
    description: str
    handler: Callable[..., Awaitable[Any]]
    parameters: list[str] = None


class ToolRouter:
    """Routes commands and questions to appropriate data fetching tools."""

    def __init__(self, client: Optional[BackendClient] = None):
        self._client = client or get_backend_client()
        self._tools: dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        self.register_tool(ToolDefinition(
            name="list_agents",
            description="List all agents with their current status and metrics",
            handler=self._list_agents,
        ))

        self.register_tool(ToolDefinition(
            name="get_agent",
            description="Get detailed information about a specific agent",
            handler=self._get_agent,
            parameters=["agent_id"],
        ))

        self.register_tool(ToolDefinition(
            name="get_summary",
            description="Get system-wide summary including total agents, hot count, and alerts",
            handler=self._get_summary,
        ))

        self.register_tool(ToolDefinition(
            name="get_alerts",
            description="Get list of active alerts sorted by severity",
            handler=self._get_alerts,
        ))

        self.register_tool(ToolDefinition(
            name="get_compare",
            description="Get before/after comparison for an optimized agent",
            handler=self._get_compare,
            parameters=["agent_id"],
        ))

        self.register_tool(ToolDefinition(
            name="get_timeline",
            description="Get timeline of recent events and optimizations",
            handler=self._get_timeline,
        ))

        self.register_tool(ToolDefinition(
            name="trigger_optimization",
            description="Trigger optimization for an agent (demo mode)",
            handler=self._trigger_optimization,
            parameters=["agent_id"],
        ))

    def register_tool(self, tool: ToolDefinition) -> None:
        """Register a new tool."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())

    async def call_tool(self, name: str, **kwargs) -> Any:
        """Call a tool by name with arguments."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")

        try:
            return await tool.handler(**kwargs)
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            raise

    # Tool implementations

    async def _list_agents(self) -> list[AgentModel]:
        """List all agents."""
        return await self._client.get_agents()

    async def _get_agent(self, agent_id: str) -> Optional[AgentModel]:
        """Get a specific agent."""
        return await self._client.get_agent(agent_id)

    async def _get_summary(self) -> SummaryModel:
        """Get system summary."""
        return await self._client.get_summary()

    async def _get_alerts(self) -> list[AlertModel]:
        """Get alerts."""
        return await self._client.get_alerts()

    async def _get_compare(self, agent_id: str) -> Optional[CompareModel]:
        """Get comparison data."""
        return await self._client.get_compare(agent_id)

    async def _get_timeline(self) -> list[TimelineEvent]:
        """Get timeline events."""
        return await self._client.get_timeline()

    async def _trigger_optimization(self, agent_id: str) -> Optional[CompareModel]:
        """Trigger optimization."""
        return await self._client.trigger_optimization(agent_id)

    # Command routing

    async def route_command(self, command: str, args: list[str]) -> CommandResult:
        """Route a slash command to the appropriate handler."""
        command = command.lower().strip("/")

        try:
            if command == "agents":
                agents = await self._list_agents()
                output = self._format_agents_list(agents)
                return CommandResult(
                    success=True,
                    command=f"/{command}",
                    output=output,
                    data={"agents": [a.model_dump() for a in agents]},
                )

            elif command == "inspect":
                if not args:
                    return CommandResult(
                        success=False,
                        command=f"/{command}",
                        output="",
                        error="Usage: /inspect <agent_id>",
                    )
                agent = await self._get_agent(args[0])
                if not agent:
                    return CommandResult(
                        success=False,
                        command=f"/{command}",
                        output="",
                        error=f"Agent not found: {args[0]}",
                    )
                return CommandResult(
                    success=True,
                    command=f"/{command}",
                    output=self._format_agent_detail(agent),
                    data={"agent": agent.model_dump()},
                )

            elif command == "compare":
                if not args:
                    return CommandResult(
                        success=False,
                        command=f"/{command}",
                        output="",
                        error="Usage: /compare <agent_id>",
                    )
                comparison = await self._get_compare(args[0])
                if not comparison:
                    return CommandResult(
                        success=False,
                        command=f"/{command}",
                        output="",
                        error=f"No optimization data for: {args[0]}",
                    )
                return CommandResult(
                    success=True,
                    command=f"/{command}",
                    output=self._format_comparison(comparison),
                    data={"comparison": comparison.model_dump()},
                )

            elif command == "alerts":
                alerts = await self._get_alerts()
                output = self._format_alerts(alerts)
                return CommandResult(
                    success=True,
                    command=f"/{command}",
                    output=output,
                    data={"alerts": [a.model_dump() for a in alerts]},
                )

            elif command == "summary":
                summary = await self._get_summary()
                output = self._format_summary(summary)
                return CommandResult(
                    success=True,
                    command=f"/{command}",
                    output=output,
                    data={"summary": summary.model_dump()},
                )

            elif command == "optimize":
                if not args:
                    return CommandResult(
                        success=False,
                        command=f"/{command}",
                        output="",
                        error="Usage: /optimize <agent_id>",
                    )
                comparison = await self._trigger_optimization(args[0])
                if not comparison:
                    return CommandResult(
                        success=False,
                        command=f"/{command}",
                        output="",
                        error=f"Could not optimize: {args[0]}",
                    )
                return CommandResult(
                    success=True,
                    command=f"/{command}",
                    output=self._format_optimization_result(comparison),
                    data={"comparison": comparison.model_dump()},
                )

            elif command == "timeline" or command == "events":
                events = await self._get_timeline()
                output = self._format_timeline(events)
                return CommandResult(
                    success=True,
                    command=f"/{command}",
                    output=output,
                    data={"events": [e.model_dump() for e in events]},
                )

            else:
                return CommandResult(
                    success=False,
                    command=f"/{command}",
                    output="",
                    error=f"Unknown command: /{command}. Type /help for available commands.",
                )

        except Exception as e:
            logger.error(f"Command {command} failed: {e}")
            return CommandResult(
                success=False,
                command=f"/{command}",
                output="",
                error=str(e),
            )

    # Formatters

    def _format_agents_list(self, agents: list[AgentModel]) -> str:
        """Format agents list for display."""
        if not agents:
            return "No agents found."

        lines = ["Agents:", ""]
        for agent in agents:
            status_icon = {
                "ok": "●",
                "idle": "◌",
                "hot": "🔥",
                "throttled": "⏸",
                "error": "✗",
            }.get(agent.status.value, "?")

            lines.append(
                f"  {status_icon} {agent.agent_id:<15} "
                f"CPU:{agent.cpu_pct:5.1f}%  "
                f"Tok:{agent.tokens_per_min:6.0f}/m  "
                f"{agent.name}"
            )

        return "\n".join(lines)

    def _format_agent_detail(self, agent: AgentModel) -> str:
        """Format agent detail for display."""
        lines = [
            f"Agent: {agent.name}",
            f"ID: {agent.agent_id}",
            f"Status: {agent.status.value.upper()}",
            "",
            "Metrics:",
            f"  CPU:      {agent.cpu_pct:.1f}%",
            f"  Memory:   {agent.mem_mb:.0f} MB",
            f"  Tokens:   {agent.tokens_per_min:.0f}/min",
            f"  Latency:  {agent.avg_latency_ms:.0f}ms",
        ]

        if agent.temp_c is not None:
            lines.append(f"  Temp:     {agent.temp_c:.1f}°C")

        if agent.estimated_energy_score is not None:
            lines.append(f"  Energy:   {agent.estimated_energy_score:.2f}")

        if agent.optimizer_action:
            lines.extend(["", f"Last action: {agent.optimizer_action}"])

        return "\n".join(lines)

    def _format_comparison(self, comparison: CompareModel) -> str:
        """Format comparison for display."""
        b, a = comparison.before, comparison.after
        lines = [
            f"Optimization comparison for: {comparison.agent_id}",
            "",
            "                Before      After      Change",
            f"  CPU:         {b.cpu_pct:6.1f}%    {a.cpu_pct:6.1f}%    {a.cpu_pct - b.cpu_pct:+.1f}%",
            f"  Tokens/min:  {b.tokens_per_min:6.0f}     {a.tokens_per_min:6.0f}     {a.tokens_per_min - b.tokens_per_min:+.0f}",
            f"  Latency:     {b.avg_latency_ms:6.0f}ms   {a.avg_latency_ms:6.0f}ms   {a.avg_latency_ms - b.avg_latency_ms:+.0f}ms",
        ]

        if b.estimated_energy_score and a.estimated_energy_score:
            lines.append(
                f"  Energy:      {b.estimated_energy_score:6.2f}     {a.estimated_energy_score:6.2f}     "
                f"{a.estimated_energy_score - b.estimated_energy_score:+.2f}"
            )

        if comparison.explanation_facts:
            lines.extend(["", "Facts:"])
            for fact in comparison.explanation_facts:
                lines.append(f"  • {fact}")

        return "\n".join(lines)

    def _format_alerts(self, alerts: list[AlertModel]) -> str:
        """Format alerts for display."""
        if not alerts:
            return "No active alerts. ✓"

        lines = [f"Alerts ({len(alerts)}):", ""]
        for alert in alerts:
            icon = {"info": "ℹ", "warning": "⚠", "critical": "🚨"}.get(alert.severity.value, "?")
            time_str = alert.created_at.strftime("%H:%M")
            lines.append(f"  {icon} [{time_str}] {alert.agent_id}: {alert.message}")

        return "\n".join(lines)

    def _format_summary(self, summary: SummaryModel) -> str:
        """Format summary for display."""
        lines = [
            "System Summary",
            "",
            f"  Active agents:   {summary.active_agents}",
            f"  Hot agents:      {summary.hot_agents}",
            f"  Open alerts:     {summary.alerts_open}",
            f"  Total tokens:    {summary.tokens_per_min_total:.0f}/min",
        ]

        if summary.estimated_energy_score_total is not None:
            lines.append(f"  Energy score:    {summary.estimated_energy_score_total:.2f}")

        if summary.estimated_savings_pct is not None:
            lines.append(f"  Est. savings:    {summary.estimated_savings_pct:.1f}%")

        lines.extend(["", f"  Dashboard: {summary.dashboard_url}"])

        return "\n".join(lines)

    def _format_optimization_result(self, comparison: CompareModel) -> str:
        """Format optimization result."""
        lines = [
            f"✓ Optimized {comparison.agent_id}!",
            "",
            self._format_comparison(comparison),
        ]
        return "\n".join(lines)

    def _format_timeline(self, events: list[TimelineEvent]) -> str:
        """Format timeline events."""
        if not events:
            return "No recent events."

        lines = ["Recent events:", ""]
        for event in events[:10]:
            time_str = event.timestamp.strftime("%H:%M:%S")
            agent_str = f" [{event.agent_id}]" if event.agent_id else ""
            lines.append(f"  [{time_str}] {event.event_type}{agent_str}: {event.description}")

        return "\n".join(lines)


# Singleton
_router: Optional[ToolRouter] = None


def get_tool_router(client: Optional[BackendClient] = None) -> ToolRouter:
    """Get or create tool router singleton."""
    global _router
    if _router is None:
        _router = ToolRouter(client)
    return _router
