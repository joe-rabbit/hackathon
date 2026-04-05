"""Mochi widget - The animated terminal companion.

Preserves the sprite, blink, jump, and mood system from the original mochi.py
but refactored as a Textual widget with reactive state management.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from rich.console import Console, ConsoleOptions, RenderResult
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget
from textual.message import Message

from shared.schemas import MochiMood, AgentStatus


@dataclass
class MochiState:
    """Mochi's internal state."""
    mood: MochiMood = MochiMood.IDLE
    blinking: bool = False
    jumping: bool = False
    blink_until: float = 0.0
    jump_until: float = 0.0
    message: str = ""
    thinking_dots: int = 0
    selected_agent: Optional[str] = None
    alert_count: int = 0
    hot_agents: int = 0


class MochiSprite:
    """Renders the Mochi sprite with various expressions and states."""

    # Color definitions (ANSI 256-color codes)
    COLORS = {
        "body": "114",        # Light green
        "body_sick": "108",   # Muted green
        "body_dead": "240",   # Gray
        "shine": "231",       # White
        "cheek": "217",       # Pink
        "mouth": "210",       # Salmon
        "mouth_open": "203",  # Red-ish
        "arms": "228",        # Light yellow
        "eye_fg": "232",      # Black
        "eye_closed": "65",   # Dark green
        "eye_sick": "161",    # Red
        "eye_dead": "52",     # Dark red
        "eye_happy": "220",   # Yellow
    }

    # Base sprite template (16 chars wide, 9 rows)
    TEMPLATE = [
        "......BBBB......",
        "....BBBBBBBB....",
        "..BBBBBBBBBBBB..",
        ".BPBBBBBBBBBBBB.",
        ".BBBCBLEELICBBB.",  # E=left eye, I=right eye, L=left part
        "..BBBB.MM.BBBB..",  # M=mouth
        "...BBBBBBBBBB...",
        "....BBBBBBBB....",
        "...AABBBBBBAA...",  # A=arms
    ]

    @classmethod
    def render(cls, mood: MochiMood, blinking: bool = False, jumping: bool = False) -> list[str]:
        """Render the sprite for current mood and state."""
        # Determine eye and mouth style based on mood
        left_eye_char = "O"
        right_eye_char = "O"
        left_eye_style = f"bold {cls.COLORS['eye_fg']}"
        right_eye_style = f"bold {cls.COLORS['eye_fg']}"
        mouth_char = "  "
        body_color = cls.COLORS["body"]

        if blinking or mood == MochiMood.SLEEPY:
            left_eye_char = "--"
            right_eye_char = "--"
            left_eye_style = cls.COLORS["eye_closed"]
            right_eye_style = cls.COLORS["eye_closed"]

        if mood == MochiMood.HAPPY or mood == MochiMood.CELEBRATE:
            left_eye_char = " >"
            right_eye_char = "< "

        if mood == MochiMood.WARNING:
            left_eye_char = " @"
            right_eye_char = "@ "
            left_eye_style = cls.COLORS["eye_sick"]
            right_eye_style = cls.COLORS["eye_sick"]

        if mood == MochiMood.SICK:
            left_eye_char = " X"
            right_eye_char = "X "
            left_eye_style = cls.COLORS["eye_dead"]
            right_eye_style = cls.COLORS["eye_dead"]
            body_color = cls.COLORS["body_sick"]

        if mood == MochiMood.THINKING:
            left_eye_char = " ?"
            right_eye_char = "? "

        # Build colored output
        lines = []
        for row in cls.TEMPLATE:
            line_parts = []
            i = 0
            while i < len(row):
                ch = row[i]
                if ch == ".":
                    line_parts.append(("  ", None))  # Transparent
                elif ch == "B":
                    line_parts.append(("  ", f"on color({body_color})"))
                elif ch == "P":
                    line_parts.append(("  ", f"on color({cls.COLORS['shine']})"))
                elif ch == "C":
                    line_parts.append(("  ", f"on color({cls.COLORS['cheek']})"))
                elif ch == "A":
                    line_parts.append(("  ", f"on color({cls.COLORS['arms']})"))
                elif ch == "M":
                    mouth_color = cls.COLORS["mouth_open"] if mood == MochiMood.WARNING else cls.COLORS["mouth"]
                    line_parts.append(("  ", f"on color({mouth_color})"))
                elif ch == "E":
                    # Left eye
                    if i + 1 < len(row) and row[i + 1] == "E":
                        line_parts.append((left_eye_char, f"bold color({cls.COLORS['eye_fg']}) on color({body_color})"))
                        i += 1  # Skip next E
                    else:
                        line_parts.append((" " + left_eye_char[0], f"bold color({cls.COLORS['eye_fg']}) on color({body_color})"))
                elif ch == "I":
                    # Right eye
                    line_parts.append((right_eye_char, f"bold color({cls.COLORS['eye_fg']}) on color({body_color})"))
                elif ch == "L":
                    # Eye padding
                    line_parts.append(("  ", f"on color({body_color})"))
                else:
                    line_parts.append(("  ", f"on color({body_color})"))
                i += 1

            lines.append(line_parts)

        return lines

    @classmethod
    def render_text(cls, mood: MochiMood, blinking: bool = False, jumping: bool = False) -> Text:
        """Render sprite as Rich Text object."""
        lines = cls.render(mood, blinking, jumping)
        text = Text()

        # Add padding if jumping
        if jumping:
            text.append("  ")  # Indent for jump effect

        for i, line_parts in enumerate(lines):
            if jumping and i > 0:
                text.append("\n  ")  # Indent each line for jump
            elif i > 0:
                text.append("\n")

            for chars, style in line_parts:
                if style:
                    text.append(chars, style=style)
                else:
                    text.append(chars)

        return text


class MochiWidget(Widget):
    """Interactive Mochi widget for Textual apps."""

    DEFAULT_CSS = """
    MochiWidget {
        width: 36;
        height: auto;
        min-height: 14;
        border: round $primary;
        padding: 0 1;
        background: $surface;
    }

    MochiWidget > .mochi-message {
        text-align: center;
        color: $text;
        margin-top: 1;
    }
    """

    # Reactive state
    mood: reactive[MochiMood] = reactive(MochiMood.IDLE)
    message: reactive[str] = reactive("")
    blinking: reactive[bool] = reactive(False)
    jumping: reactive[bool] = reactive(False)
    thinking: reactive[bool] = reactive(False)

    class MochiReacted(Message):
        """Message when Mochi reacts to something."""
        def __init__(self, reaction: str, mood: MochiMood):
            self.reaction = reaction
            self.mood = mood
            super().__init__()

    def __init__(
        self,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self._state = MochiState()
        self._last_blink = 0.0
        self._blink_timer = None
        self._thinking_timer = None

    def on_mount(self) -> None:
        """Set up animation timers when mounted."""
        # Random blinking
        self._blink_timer = self.set_interval(0.1, self._check_blink)
        # Thinking animation
        self._thinking_timer = self.set_interval(0.3, self._update_thinking)

    def _check_blink(self) -> None:
        """Randomly trigger blinks."""
        import time
        now = time.time()

        # Natural random blinking
        if not self.blinking and random.random() < 0.03:
            self.blinking = True
            self._state.blink_until = now + 0.15
            self.refresh()

        # End blink
        if self.blinking and now > self._state.blink_until:
            self.blinking = False
            self.refresh()

        # End jump
        if self.jumping and now > self._state.jump_until:
            self.jumping = False
            self.refresh()

    def _update_thinking(self) -> None:
        """Update thinking animation dots."""
        if self.thinking:
            self._state.thinking_dots = (self._state.thinking_dots + 1) % 4
            self.refresh()

    def render(self) -> Text:
        """Render the Mochi widget."""
        # Get sprite
        sprite = MochiSprite.render_text(self.mood, self.blinking, self.jumping)

        # Add message below sprite
        result = Text()
        result.append(sprite)

        if self.message:
            result.append("\n\n")
            msg = self.message
            if self.thinking:
                msg += "." * self._state.thinking_dots
            result.append(msg, style="italic cyan")

        # Status indicators
        if self._state.alert_count > 0:
            result.append(f"\n⚠️ {self._state.alert_count} alerts", style="bold yellow")

        if self._state.hot_agents > 0:
            result.append(f"\n🔥 {self._state.hot_agents} hot", style="bold red")

        return result

    # Public methods for controlling Mochi

    def set_mood(self, mood: MochiMood, message: str = "") -> None:
        """Set Mochi's mood with optional message."""
        self.mood = mood
        self.message = message
        self._state.mood = mood
        self.refresh()
        self.post_message(self.MochiReacted(message, mood))

    def react_to_agents(self, hot_count: int, alert_count: int) -> None:
        """React to agent status changes."""
        self._state.hot_agents = hot_count
        self._state.alert_count = alert_count

        if hot_count > 0:
            self.set_mood(MochiMood.WARNING, f"Hmm, {hot_count} agent{'s' if hot_count > 1 else ''} running hot...")
        elif alert_count > 0:
            self.set_mood(MochiMood.WARNING, f"Got {alert_count} alert{'s' if alert_count > 1 else ''} to check!")
        else:
            self.set_mood(MochiMood.HAPPY, "All systems looking good!")

    def celebrate(self, message: str = "Yay! Things got better!") -> None:
        """Trigger celebration animation."""
        import time
        self.mood = MochiMood.CELEBRATE
        self.message = message
        self.jumping = True
        self._state.jump_until = time.time() + 0.5
        self.refresh()

    def start_thinking(self, message: str = "Thinking") -> None:
        """Start thinking animation."""
        self.thinking = True
        self.mood = MochiMood.THINKING
        self.message = message
        self._state.thinking_dots = 0
        self.refresh()

    def stop_thinking(self) -> None:
        """Stop thinking animation."""
        self.thinking = False
        self.mood = MochiMood.IDLE
        self.message = ""
        self.refresh()

    def show_idle(self, message: str = "") -> None:
        """Return to idle state."""
        self.mood = MochiMood.IDLE
        self.message = message
        self.thinking = False
        self.refresh()

    def jump(self) -> None:
        """Make Mochi jump."""
        import time
        self.jumping = True
        self._state.jump_until = time.time() + 0.3
        self.refresh()


# Export convenience function
def create_mochi_widget(**kwargs) -> MochiWidget:
    """Create a new Mochi widget."""
    return MochiWidget(**kwargs)
