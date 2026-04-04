"""Agent detail widget - Shows detailed info for selected agent."""

from typing import Optional

from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich.console import Group
from textual.reactive import reactive
from textual.widgets import Static

from shared.schemas import AgentModel, AgentStatus, CompareModel


class AgentDetailWidget(Static):
    """Displays detailed information about a selected agent."""

    DEFAULT_CSS = """
    AgentDetailWidget {
        height: auto;
        min-height: 8;
        border: round $primary;
        padding: 1;
        background: $surface;
    }
    """

    def __init__(
        self,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self._agent: Optional[AgentModel] = None
        self._comparison: Optional[CompareModel] = None

    def render(self) -> Text:
        """Render agent details."""
        if not self._agent:
            return Text("No agent selected\n\nSelect an agent from the table\nor use /inspect <agent_id>", style="dim italic")

        agent = self._agent
        text = Text()

        # Agent name and status
        status_icon = {
            AgentStatus.OK: ("●", "green"),
            AgentStatus.IDLE: ("◌", "dim"),
            AgentStatus.HOT: ("🔥", "red"),
            AgentStatus.THROTTLED: ("⏸", "yellow"),
            AgentStatus.ERROR: ("✗", "red"),
        }.get(agent.status, ("?", "white"))

        text.append(f"{status_icon[0]} ", style=status_icon[1])
        text.append(f"{agent.name}\n", style="bold")
        text.append(f"ID: {agent.agent_id}\n\n", style="dim")

        # Metrics
        text.append("Metrics\n", style="bold underline")

        # CPU with bar
        cpu_style = "green" if agent.cpu_pct < 50 else ("yellow" if agent.cpu_pct < 75 else "red")
        bar_width = 15
        filled = int((agent.cpu_pct / 100) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        text.append(f"  CPU:    [{bar}] ", style=cpu_style)
        text.append(f"{agent.cpu_pct:.1f}%\n", style=cpu_style + " bold")

        # Memory
        if agent.mem_mb >= 1024:
            mem_str = f"{agent.mem_mb/1024:.1f} GB"
        else:
            mem_str = f"{agent.mem_mb:.0f} MB"
        text.append(f"  Memory: {mem_str}\n", style="cyan")

        # Temperature
        if agent.temp_c is not None:
            temp_style = "green" if agent.temp_c < 50 else ("yellow" if agent.temp_c < 65 else "red")
            text.append(f"  Temp:   {agent.temp_c:.1f}°C\n", style=temp_style)

        # Tokens
        text.append(f"  Tokens: {agent.tokens_per_min:.0f}/min ", style="white")
        text.append(f"(in:{agent.tokens_in} out:{agent.tokens_out})\n", style="dim")

        # Latency
        text.append(f"  Latency: {agent.avg_latency_ms:.0f}ms\n", style="white")

        # Energy score
        if agent.estimated_energy_score is not None:
            score = agent.estimated_energy_score
            score_style = "green" if score < 0.4 else ("yellow" if score < 0.7 else "red")
            score_bar = "●" * int(score * 5) + "○" * (5 - int(score * 5))
            text.append(f"  Energy: [{score_bar}] ", style=score_style)
            text.append(f"{score:.2f}\n", style=score_style)

        # Optimizer action
        if agent.optimizer_action:
            text.append(f"\nLast Action\n", style="bold underline")
            text.append(f"  {agent.optimizer_action.replace('_', ' ').title()}\n", style="cyan italic")

        # Comparison data if available
        if self._comparison:
            text.append(f"\nOptimization Impact\n", style="bold underline")
            c = self._comparison
            cpu_change = c.after.cpu_pct - c.before.cpu_pct
            token_change = c.after.tokens_per_min - c.before.tokens_per_min

            cpu_arrow = "↓" if cpu_change < 0 else "↑"
            cpu_color = "green" if cpu_change < 0 else "red"
            text.append(f"  CPU:    {cpu_arrow} {abs(cpu_change):.1f}%\n", style=cpu_color)

            token_arrow = "↓" if token_change < 0 else "↑"
            token_color = "green" if token_change < 0 else "red"
            text.append(f"  Tokens: {token_arrow} {abs(token_change):.0f}/min\n", style=token_color)

        # Last updated
        text.append(f"\nUpdated: {agent.last_updated.strftime('%H:%M:%S')}", style="dim")

        return text

    def set_agent(self, agent: Optional[AgentModel], comparison: Optional[CompareModel] = None) -> None:
        """Set the agent to display."""
        self._agent = agent
        self._comparison = comparison
        self.refresh()

    def clear(self) -> None:
        """Clear the display."""
        self._agent = None
        self._comparison = None
        self.refresh()
