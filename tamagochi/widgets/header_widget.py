"""Header widget - App title, status indicators, and dashboard link."""

from typing import Optional

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from shared.schemas import BackendStatus


class HeaderWidget(Static):
    """Application header with status indicators."""

    DEFAULT_CSS = """
    HeaderWidget {
        dock: top;
        height: 3;
        background: $primary-darken-2;
        color: $text;
        padding: 0 2;
        content-align: center middle;
    }
    """

    device_name: reactive[str] = reactive("edge-01")
    backend_status: reactive[str] = reactive("mock")
    model_name: reactive[str] = reactive("gemma3:1b")
    alert_count: reactive[int] = reactive(0)
    dashboard_url: reactive[str] = reactive("http://127.0.0.1:8501")

    def __init__(
        self,
        device_name: str = "edge-01",
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.device_name = device_name

    def render(self) -> Text:
        """Render the header."""
        text = Text()

        # App title
        text.append("🍡 Mochi ", style="bold cyan")
        text.append("Edge AI Orchestrator", style="bold white")

        # Separator
        text.append(" │ ", style="dim")

        # Device name
        text.append("📍 ", style="")
        text.append(self.device_name, style="yellow")

        # Separator
        text.append(" │ ", style="dim")

        # Backend status
        if self.backend_status == "connected":
            text.append("● ", style="green")
            text.append("live", style="green")
        elif self.backend_status == "mock":
            text.append("◌ ", style="yellow")
            text.append("mock", style="yellow")
        else:
            text.append("✗ ", style="red")
            text.append("offline", style="red")

        # Separator
        text.append(" │ ", style="dim")

        # Model name
        text.append("🤖 ", style="")
        text.append(self.model_name, style="cyan")

        # Separator
        text.append(" │ ", style="dim")

        # Alerts
        if self.alert_count > 0:
            text.append(f"⚠️ {self.alert_count}", style="bold yellow")
        else:
            text.append("✓ 0", style="green dim")

        # Dashboard link
        text.append(" │ ", style="dim")
        text.append("📊 ", style="")
        text.append("[d]ashboard", style="underline blue")

        return text

    def update_status(
        self,
        backend_status: Optional[str] = None,
        model_name: Optional[str] = None,
        alert_count: Optional[int] = None,
        dashboard_url: Optional[str] = None,
    ) -> None:
        """Update header status indicators."""
        if backend_status is not None:
            self.backend_status = backend_status
        if model_name is not None:
            self.model_name = model_name
        if alert_count is not None:
            self.alert_count = alert_count
        if dashboard_url is not None:
            self.dashboard_url = dashboard_url
        self.refresh()
