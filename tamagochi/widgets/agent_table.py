"""Agent table widget - Live display of all agents.

Shows agent name, status, CPU, memory, tokens, and optimizer status
with real-time updates and row selection.
"""

from typing import Optional

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import DataTable
from textual.message import Message

from shared.schemas import AgentModel, AgentStatus


class AgentTable(DataTable):
    """Data table displaying agent metrics with live updates."""

    DEFAULT_CSS = """
    AgentTable {
        height: 100%;
        border: round $primary;
    }

    AgentTable > .datatable--header {
        background: $primary-darken-2;
        color: $text;
        text-style: bold;
    }

    AgentTable > .datatable--cursor {
        background: $primary;
        color: $text;
    }

    AgentTable .hot-row {
        background: $error 30%;
    }
    """

    selected_agent_id: reactive[Optional[str]] = reactive(None)

    class AgentSelected(Message):
        """Message when an agent is selected."""
        def __init__(self, agent: AgentModel):
            self.agent = agent
            super().__init__()

    def __init__(
        self,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self._agents: dict[str, AgentModel] = {}
        self._row_keys: dict[str, any] = {}  # agent_id -> row_key

    def on_mount(self) -> None:
        """Set up the table columns."""
        self.cursor_type = "row"
        self.zebra_stripes = True

        # Define columns
        self.add_column("Status", key="status", width=6)
        self.add_column("Agent", key="name", width=18)
        self.add_column("CPU", key="cpu", width=7)
        self.add_column("Mem", key="mem", width=8)
        self.add_column("Tok/m", key="tokens", width=8)
        self.add_column("Action", key="action", width=14)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        row_key = event.row_key
        # Find agent by row key
        for agent_id, key in self._row_keys.items():
            if key == row_key:
                agent = self._agents.get(agent_id)
                if agent:
                    self.selected_agent_id = agent_id
                    self.post_message(self.AgentSelected(agent))
                break

    def _format_status(self, status: AgentStatus) -> Text:
        """Format status with color indicator."""
        status_styles = {
            AgentStatus.OK: ("●", "green"),
            AgentStatus.IDLE: ("◌", "dim"),
            AgentStatus.HOT: ("🔥", "red bold"),
            AgentStatus.THROTTLED: ("⏸", "yellow"),
            AgentStatus.ERROR: ("✗", "red bold"),
        }
        icon, style = status_styles.get(status, ("?", "white"))
        return Text(f" {icon} ", style=style)

    def _format_cpu(self, cpu_pct: float) -> Text:
        """Format CPU with color coding."""
        style = "green"
        if cpu_pct > 75:
            style = "red bold"
        elif cpu_pct > 50:
            style = "yellow"
        return Text(f"{cpu_pct:5.1f}%", style=style)

    def _format_mem(self, mem_mb: float) -> Text:
        """Format memory usage."""
        if mem_mb >= 1024:
            return Text(f"{mem_mb/1024:.1f}GB", style="cyan")
        return Text(f"{mem_mb:.0f}MB", style="cyan")

    def _format_tokens(self, tokens_per_min: float) -> Text:
        """Format token throughput."""
        style = "white"
        if tokens_per_min > 1500:
            style = "red"
        elif tokens_per_min > 800:
            style = "yellow"
        return Text(f"{tokens_per_min:.0f}", style=style)

    def _format_action(self, action: Optional[str]) -> Text:
        """Format optimizer action."""
        if not action:
            return Text("-", style="dim")
        # Truncate and format
        short = action[:12] + ".." if len(action) > 14 else action
        return Text(short, style="cyan italic")

    def update_agents(self, agents: list[AgentModel]) -> None:
        """Update the table with new agent data."""
        # Update internal cache
        for agent in agents:
            self._agents[agent.agent_id] = agent

        # Update existing rows or add new ones
        for agent in agents:
            row_data = [
                self._format_status(agent.status),
                Text(agent.name[:16], style="bold" if agent.status == AgentStatus.HOT else ""),
                self._format_cpu(agent.cpu_pct),
                self._format_mem(agent.mem_mb),
                self._format_tokens(agent.tokens_per_min),
                self._format_action(agent.optimizer_action),
            ]

            if agent.agent_id in self._row_keys:
                # Update existing row
                row_key = self._row_keys[agent.agent_id]
                for col_idx, value in enumerate(row_data):
                    col_key = ["status", "name", "cpu", "mem", "tokens", "action"][col_idx]
                    self.update_cell(row_key, col_key, value)
            else:
                # Add new row
                row_key = self.add_row(*row_data, key=agent.agent_id)
                self._row_keys[agent.agent_id] = row_key

        # Remove agents no longer present
        current_ids = {a.agent_id for a in agents}
        for agent_id in list(self._row_keys.keys()):
            if agent_id not in current_ids:
                row_key = self._row_keys.pop(agent_id)
                self.remove_row(row_key)
                self._agents.pop(agent_id, None)

    def get_selected_agent(self) -> Optional[AgentModel]:
        """Get the currently selected agent."""
        if self.selected_agent_id:
            return self._agents.get(self.selected_agent_id)
        return None

    def select_agent(self, agent_id: str) -> None:
        """Programmatically select an agent."""
        if agent_id in self._row_keys:
            self.selected_agent_id = agent_id
            # Move cursor to that row
            row_key = self._row_keys[agent_id]
            self.move_cursor(row=row_key)

    def get_hot_agents(self) -> list[AgentModel]:
        """Get list of agents in hot status."""
        return [a for a in self._agents.values() if a.status == AgentStatus.HOT]

    def get_agent_count(self) -> int:
        """Get total agent count."""
        return len(self._agents)
