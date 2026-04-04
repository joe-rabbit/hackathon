"""Chat panel widget - Command input and response history.

Supports slash commands for deterministic actions and natural language
questions routed to the LLM for explanation.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable, Awaitable
import asyncio

from rich.text import Text
from rich.panel import Panel
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, RichLog, Static
from textual.containers import Vertical, Horizontal
from textual.message import Message


@dataclass
class ChatMessage:
    """A message in the chat history."""
    role: str  # "user", "mochi", "system", "error"
    content: str
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class ChatHistory(RichLog):
    """Scrollable chat history display."""

    DEFAULT_CSS = """
    ChatHistory {
        height: 1fr;
        border: round $primary;
        background: $surface;
        padding: 0 1;
    }
    """

    def add_message(self, msg: ChatMessage) -> None:
        """Add a message to the history."""
        timestamp = msg.timestamp.strftime("%H:%M")

        if msg.role == "user":
            self.write(Text(f"[{timestamp}] > ", style="dim"))
            self.write(Text(msg.content, style="bold cyan"))
        elif msg.role == "mochi":
            self.write(Text(f"[{timestamp}] 🍡 ", style="dim"))
            self.write(Text(msg.content, style="green"))
        elif msg.role == "system":
            self.write(Text(f"[{timestamp}] ℹ ", style="dim"))
            self.write(Text(msg.content, style="yellow"))
        elif msg.role == "error":
            self.write(Text(f"[{timestamp}] ✗ ", style="dim"))
            self.write(Text(msg.content, style="red bold"))
        else:
            self.write(Text(msg.content))

        self.write("")  # Add spacing


class CommandInput(Input):
    """Input field for commands and questions."""

    DEFAULT_CSS = """
    CommandInput {
        dock: bottom;
        margin: 1 0 0 0;
        border: round $accent;
        background: $surface;
    }

    CommandInput:focus {
        border: round $accent-lighten-2;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(
            placeholder="Type /help for commands or ask a question...",
            **kwargs
        )


class ChatPanel(Vertical):
    """Combined chat history and input panel."""

    DEFAULT_CSS = """
    ChatPanel {
        height: 100%;
        width: 100%;
    }
    """

    class CommandSubmitted(Message):
        """Message when a command is submitted."""
        def __init__(self, command: str, is_slash: bool):
            self.command = command
            self.is_slash = is_slash
            super().__init__()

    class QuestionAsked(Message):
        """Message when a natural language question is asked."""
        def __init__(self, question: str):
            self.question = question
            super().__init__()

    def __init__(
        self,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self._history: list[ChatMessage] = []
        self._command_history: list[str] = []
        self._history_index = -1

    def compose(self):
        """Compose the chat panel."""
        yield ChatHistory(id="chat-history", wrap=True, highlight=True, markup=True)
        yield CommandInput(id="chat-input")

    def on_mount(self) -> None:
        """Initialize with welcome message."""
        self.add_system_message(
            "Welcome! I'm Mochi, your edge AI companion. 🍡\n"
            "Type /help for commands or ask me anything about your agents!"
        )

    @property
    def history_widget(self) -> ChatHistory:
        """Get the chat history widget."""
        return self.query_one("#chat-history", ChatHistory)

    @property
    def input_widget(self) -> CommandInput:
        """Get the input widget."""
        return self.query_one("#chat-input", CommandInput)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        text = event.value.strip()
        if not text:
            return

        # Clear input
        self.input_widget.value = ""

        # Add to history
        self._command_history.append(text)
        self._history_index = -1

        # Add user message
        self.add_user_message(text)

        # Determine if slash command or natural language
        if text.startswith("/"):
            self.post_message(self.CommandSubmitted(text, is_slash=True))
        else:
            self.post_message(self.QuestionAsked(text))

    def add_user_message(self, content: str) -> None:
        """Add a user message to history."""
        msg = ChatMessage(role="user", content=content)
        self._history.append(msg)
        self.history_widget.add_message(msg)

    def add_mochi_message(self, content: str) -> None:
        """Add a Mochi response to history."""
        msg = ChatMessage(role="mochi", content=content)
        self._history.append(msg)
        self.history_widget.add_message(msg)

    def add_system_message(self, content: str) -> None:
        """Add a system message to history."""
        msg = ChatMessage(role="system", content=content)
        self._history.append(msg)
        self.history_widget.add_message(msg)

    def add_error_message(self, content: str) -> None:
        """Add an error message to history."""
        msg = ChatMessage(role="error", content=content)
        self._history.append(msg)
        self.history_widget.add_message(msg)

    def show_thinking(self) -> None:
        """Show thinking indicator."""
        self.add_system_message("Thinking...")

    def clear_history(self) -> None:
        """Clear chat history."""
        self._history.clear()
        self.history_widget.clear()

    def focus_input(self) -> None:
        """Focus the input field."""
        self.input_widget.focus()


# Slash command definitions
SLASH_COMMANDS = {
    "/help": "Show available commands",
    "/agents": "List all agents",
    "/inspect": "Inspect agent details (/inspect <agent_id>)",
    "/compare": "Show before/after optimization (/compare <agent_id>)",
    "/alerts": "Show active alerts",
    "/summary": "Show system summary",
    "/optimize": "Trigger optimization (/optimize <agent_id>)",
    "/dashboard": "Open web dashboard",
    "/replay": "Replay last optimization event",
    "/clear": "Clear chat history",
    "/quit": "Exit the application",
}


def parse_command(text: str) -> tuple[str, list[str]]:
    """Parse a slash command into command and arguments."""
    parts = text.strip().split()
    if not parts:
        return "", []

    command = parts[0].lower()
    args = parts[1:] if len(parts) > 1 else []
    return command, args


def get_help_text() -> str:
    """Generate help text for all commands."""
    lines = ["Available commands:", ""]
    for cmd, desc in SLASH_COMMANDS.items():
        lines.append(f"  {cmd:<12} {desc}")

    lines.extend([
        "",
        "You can also ask questions in natural language:",
        "  • Why is camera-agent marked hot?",
        "  • What did the optimizer change?",
        "  • Which agent is using the most tokens?",
        "",
        "Keyboard shortcuts:",
        "  Ctrl+Q     Quit",
        "  Ctrl+D     Open dashboard",
        "  Tab        Cycle focus",
        "  ↑/↓        Navigate agents",
    ])

    return "\n".join(lines)
