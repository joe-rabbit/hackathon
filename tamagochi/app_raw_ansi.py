"""Mochi Terminal UI - Raw ANSI style like the original mochi.py.

No frameworks - just direct terminal control with ANSI escape codes,
non-blocking keyboard input, and a render loop.
"""

import os
import sys
import time
import random
import asyncio
import threading
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime

# Import our services
from shared.config import settings
from shared.schemas import AgentStatus, AgentModel, AlertModel, SummaryModel
from tamagochi.services.backend_client import get_backend_client
from tamagochi.services.tool_router import get_tool_router
from tamagochi.services.context_builder import get_context_builder
from tamagochi.services.llm_client import get_llm_client


# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

TICK_SECONDS = 0.1
POLL_SECONDS = 2.0
RESET = "\033[0m"


# ═══════════════════════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MochiState:
    """Mochi's visual state."""
    mood: str = "happy"
    blinking: bool = False
    jumping: bool = False
    thinking: bool = False
    blink_until: float = 0.0
    jump_until: float = 0.0
    message: str = ""
    position: int = 2  # horizontal position in play area


@dataclass 
class AppState:
    """Application state."""
    agents: List[AgentModel] = field(default_factory=list)
    alerts: List[AlertModel] = field(default_factory=list)
    summary: Optional[SummaryModel] = None
    selected_agent_idx: int = 0
    chat_history: List[tuple] = field(default_factory=list)  # (role, text)
    input_buffer: str = ""
    input_mode: bool = True
    show_help: bool = False
    last_event: str = "Mochi ready! Type /help for commands."
    running: bool = True
    last_poll: float = 0.0
    mochi: MochiState = field(default_factory=MochiState)
    backend_status: str = "connecting..."
    processing: bool = False


# ═══════════════════════════════════════════════════════════════════════════
# TERMINAL UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

def clear_screen() -> None:
    sys.stdout.write("\033[H\033[J")
    sys.stdout.flush()


def move_cursor(row: int, col: int) -> None:
    sys.stdout.write(f"\033[{row};{col}H")


def hide_cursor() -> None:
    sys.stdout.write("\033[?25l")


def show_cursor() -> None:
    sys.stdout.write("\033[?25h")


def get_terminal_size() -> tuple:
    try:
        size = os.get_terminal_size()
        return size.lines, size.columns
    except:
        return 40, 120


def color(fg: int = None, bg: int = None, bold: bool = False) -> str:
    """Generate ANSI color code."""
    codes = []
    if bold:
        codes.append("1")
    if fg is not None:
        codes.append(f"38;5;{fg}")
    if bg is not None:
        codes.append(f"48;5;{bg}")
    if codes:
        return f"\033[{';'.join(codes)}m"
    return ""


# ═══════════════════════════════════════════════════════════════════════════
# MOCHI SPRITE - From original mochi.py
# ═══════════════════════════════════════════════════════════════════════════

def sprite_rows(mood: str, blinking: bool, jumping: bool) -> list[str]:
    """Generate Mochi sprite rows based on mood."""
    left_eye = "D"
    right_eye = "d"
    mouth = "M"
    body = "B"
    shine = "P"
    cheek = "C"
    arms = "A"

    if mood in ("sleeping", "sleepy") or blinking:
        left_eye = "L"
        right_eye = "l"
    if mood == "happy" or mood == "excited":
        left_eye = "H"
        right_eye = "h"
    if mood == "warning" or mood == "hot":
        left_eye = "S"
        right_eye = "s"
        body = "Q"
    if mood == "thinking":
        left_eye = "T"
        right_eye = "t"
    if mood == "sick" or mood == "error":
        left_eye = "Y"
        right_eye = "y"
        body = "G"

    template = [
        "......BBBB......",
        "....BBBBBBBB....",
        "..BBBBBBBBBBBB..",
        ".BPBBBBBBBBBBBB.",
        ".BBBCBEBBIBCBBB.",
        "..BBBB.MM.BBBB..",
        "...BBBBBBBBBB...",
        "....BBBBBBBB....",
        "...AABBBBBBAA...",
    ]

    translated = []
    for row in template:
        row = (
            row.replace("P", shine)
            .replace("C", cheek)
            .replace("A", arms)
            .replace("B", body)
            .replace("E", left_eye)
            .replace("I", right_eye)
            .replace("M", mouth)
        )
        translated.append(row)
    return translated


def colorize_sprite(rows: list[str]) -> list[str]:
    """Convert sprite template to colored output."""
    cells = {
        ".": ("", "  "),
        "B": ("48;5;114", "  "),  # body green
        "Q": ("48;5;178", "  "),  # warning orange
        "G": ("48;5;240", "  "),  # gray/dead
        "P": ("48;5;231", "  "),  # shine white
        "C": ("48;5;217", "  "),  # cheek pink
        # left eye variants
        "D": ("1;38;5;232;48;5;114", " O"),  # normal
        "H": ("1;38;5;232;48;5;114", " >"),  # happy
        "L": ("38;5;65;48;5;114", "--"),     # sleeping
        "S": ("1;38;5;196;48;5;178", " @"),  # warning
        "T": ("1;38;5;45;48;5;114", " ?"),   # thinking
        "Y": ("1;38;5;52;48;5;240", " X"),   # error
        # right eye variants  
        "d": ("1;38;5;232;48;5;114", "O "),
        "h": ("1;38;5;232;48;5;114", "< "),
        "l": ("38;5;65;48;5;114", "--"),
        "s": ("1;38;5;196;48;5;178", "@ "),
        "t": ("1;38;5;45;48;5;114", "? "),
        "y": ("1;38;5;52;48;5;240", "X "),
        # mouth
        "M": ("48;5;210", "  "),
        # arms
        "A": ("48;5;228", "  "),
    }

    lines = []
    for row in rows:
        out = []
        for cell in row:
            code, chars = cells.get(cell, ("", "  "))
            if code:
                out.append(f"\033[{code}m{chars}")
            else:
                out.append(f"{RESET}  ")
        lines.append("".join(out) + RESET)
    return lines


# ═══════════════════════════════════════════════════════════════════════════
# KEYBOARD INPUT - From original mochi.py
# ═══════════════════════════════════════════════════════════════════════════

class KeyReader:
    """Non-blocking keyboard input."""
    
    def __enter__(self):
        if os.name == "nt":
            import msvcrt
            self._msvcrt = msvcrt
            return self

        import select
        import termios
        import tty

        self._select = select
        self._termios = termios
        self._stdin_fd = sys.stdin.fileno()
        self._old_settings = termios.tcgetattr(self._stdin_fd)
        tty.setcbreak(self._stdin_fd)
        return self

    def __exit__(self, exc_type, exc, tb):
        if os.name != "nt":
            self._termios.tcsetattr(
                self._stdin_fd, self._termios.TCSADRAIN, self._old_settings
            )

    def read_key(self) -> Optional[str]:
        if os.name == "nt":
            if self._msvcrt.kbhit():
                key = self._msvcrt.getwch()
                if key in ("\x00", "\xe0"):
                    extra = self._msvcrt.getwch()
                    # Arrow keys
                    if extra == "H": return "UP"
                    if extra == "P": return "DOWN"
                    if extra == "K": return "LEFT"
                    if extra == "M": return "RIGHT"
                    return None
                return key
            return None

        ready, _, _ = self._select.select([sys.stdin], [], [], 0)
        if ready:
            ch = sys.stdin.read(1)
            # Handle escape sequences (arrow keys)
            if ch == '\x1b':
                ready2, _, _ = self._select.select([sys.stdin], [], [], 0.01)
                if ready2:
                    ch2 = sys.stdin.read(1)
                    if ch2 == '[':
                        ch3 = sys.stdin.read(1)
                        if ch3 == 'A': return "UP"
                        if ch3 == 'B': return "DOWN"
                        if ch3 == 'C': return "RIGHT"
                        if ch3 == 'D': return "LEFT"
                return "ESC"
            return ch
        return None


# ═══════════════════════════════════════════════════════════════════════════
# RENDERING
# ═══════════════════════════════════════════════════════════════════════════

def render_box(lines: list[str], width: int, title: str = "") -> list[str]:
    """Render lines inside a box."""
    result = []
    top = "╭" + (f"─ {title} " if title else "─") + "─" * (width - len(title) - 4 if title else width - 2) + "╮"
    result.append(top)
    for line in lines:
        # Pad or truncate line to width
        visible_len = len(line.replace(RESET, "").replace("\033[", ""))
        # Rough estimate - strip ANSI for length
        import re
        clean = re.sub(r'\033\[[0-9;]*m', '', line)
        pad = width - 2 - len(clean)
        result.append(f"│{line}{' ' * max(0, pad)}│")
    result.append("╰" + "─" * (width - 2) + "╯")
    return result


def status_color(status: AgentStatus) -> str:
    """Get color for agent status."""
    if status == AgentStatus.OK:
        return color(82)  # green
    elif status == AgentStatus.HOT:
        return color(196, bold=True)  # red
    elif status == AgentStatus.IDLE:
        return color(244)  # gray
    elif status == AgentStatus.THROTTLED:
        return color(214)  # orange
    elif status == AgentStatus.ERROR:
        return color(196)  # red
    return color(255)


def render(state: AppState) -> None:
    """Render the full UI."""
    rows, cols = get_terminal_size()
    now = time.time()
    
    # Update Mochi animation state
    mochi = state.mochi
    if now < mochi.blink_until:
        mochi.blinking = True
    else:
        mochi.blinking = False
    if now < mochi.jump_until:
        mochi.jumping = True
    else:
        mochi.jumping = False
    
    # Calculate layout
    left_width = min(45, cols // 3)
    right_width = min(38, cols // 4)
    center_width = cols - left_width - right_width - 2
    
    # Build output
    output = []
    
    # ═══ HEADER ═══
    header = f"{color(219, bold=True)}🍡 Mochi{RESET} │ "
    header += f"{color(244)}{state.backend_status}{RESET} │ "
    if state.summary:
        hot = len([a for a in state.agents if a.status == AgentStatus.HOT])
        header += f"{color(82)}{len(state.agents)} agents{RESET} │ "
        if hot > 0:
            header += f"{color(196, bold=True)}{hot} HOT{RESET} │ "
        header += f"{color(214)}{state.summary.alerts_open} alerts{RESET} │ "
        header += f"{color(45)}{state.summary.tokens_per_min_total:.0f} tok/min{RESET}"
    output.append("═" * cols)
    output.append(header)
    output.append("═" * cols)
    
    # ═══ MAIN AREA ═══
    # Build each column
    
    # LEFT: Agent table
    agent_lines = []
    agent_lines.append(f"{color(255, bold=True)}{'NAME':<14} {'CPU':>5} {'MEM':>6} {'TOK':>6} {'ST':<4}{RESET}")
    agent_lines.append("─" * (left_width - 4))
    for i, agent in enumerate(state.agents[:12]):
        sel = "►" if i == state.selected_agent_idx else " "
        st_color = status_color(agent.status)
        st = agent.status.value[:3].upper()
        name = agent.name[:13]
        line = f"{sel}{name:<13} {agent.cpu_pct:>4.0f}% {agent.mem_mb:>5.0f}M {agent.tokens_per_min:>5.0f} {st_color}{st}{RESET}"
        if i == state.selected_agent_idx:
            line = f"{color(bg=236)}{line}{RESET}"
        agent_lines.append(line)
    
    # RIGHT: Mochi + selected agent
    sprite = colorize_sprite(sprite_rows(mochi.mood, mochi.blinking, mochi.jumping))
    pad = "  " if mochi.jumping else ""
    mochi_lines = [f"{pad}{line}" for line in sprite]
    
    # Add mochi message
    if mochi.message:
        mochi_lines.append("")
        msg = mochi.message[:right_width-4]
        mochi_lines.append(f"{color(219)}{msg}{RESET}")
    
    # Add thinking indicator
    if state.processing:
        dots = "." * (int(now * 3) % 4)
        mochi_lines.append(f"{color(45)}thinking{dots}{RESET}")
    
    # Selected agent detail
    detail_lines = []
    if state.agents and state.selected_agent_idx < len(state.agents):
        agent = state.agents[state.selected_agent_idx]
        detail_lines.append(f"{color(45, bold=True)}{agent.name}{RESET}")
        detail_lines.append(f"Status: {status_color(agent.status)}{agent.status.value}{RESET}")
        detail_lines.append(f"CPU: {agent.cpu_pct:.1f}%  Mem: {agent.mem_mb:.0f}MB")
        if agent.temp_c:
            detail_lines.append(f"Temp: {agent.temp_c:.1f}°C")
        detail_lines.append(f"Tokens: {agent.tokens_per_min:.0f}/min")
        if agent.optimizer_action:
            detail_lines.append(f"{color(82)}✓ {agent.optimizer_action}{RESET}")
    
    # CENTER: Chat history
    chat_lines = []
    # Show last N messages that fit
    max_chat = rows - 15
    history_to_show = state.chat_history[-(max_chat):]
    for role, text in history_to_show:
        if role == "user":
            chat_lines.append(f"{color(82, bold=True)}❯{RESET} {text}")
        elif role == "mochi":
            # Word wrap long messages
            wrapped = text[:center_width - 6]
            chat_lines.append(f"{color(219, bold=True)}🍡{RESET} {wrapped}")
            if len(text) > center_width - 6:
                for i in range(center_width - 6, len(text), center_width - 4):
                    chat_lines.append(f"   {text[i:i+center_width-4]}")
        elif role == "system":
            chat_lines.append(f"{color(244)}  {text}{RESET}")
        elif role == "error":
            chat_lines.append(f"{color(196)}✗ {text}{RESET}")
    
    # Combine columns row by row
    main_height = rows - 10
    for i in range(main_height):
        line = ""
        
        # Left column (agents)
        if i < len(agent_lines):
            aline = agent_lines[i]
        else:
            aline = ""
        import re
        clean_a = re.sub(r'\033\[[0-9;]*m', '', aline)
        line += aline + " " * (left_width - len(clean_a))
        
        line += "│"
        
        # Center column (chat)
        if i < len(chat_lines):
            cline = chat_lines[i]
        else:
            cline = ""
        clean_c = re.sub(r'\033\[[0-9;]*m', '', cline)
        line += cline + " " * (center_width - len(clean_c) - 1)
        
        line += "│"
        
        # Right column (mochi + detail)
        if i < len(mochi_lines):
            rline = mochi_lines[i]
        elif i - len(mochi_lines) - 1 >= 0 and i - len(mochi_lines) - 1 < len(detail_lines):
            rline = detail_lines[i - len(mochi_lines) - 1]
        else:
            rline = ""
        line += rline
        
        output.append(line)
    
    # ═══ INPUT AREA ═══
    output.append("═" * cols)
    prompt = f"{color(82)}❯{RESET} {state.input_buffer}"
    if state.input_mode:
        prompt += f"{color(255)}▌{RESET}"
    output.append(prompt)
    
    # ═══ FOOTER ═══
    footer = f"{color(244)}↑↓ select │ / commands │ Enter send │ "
    footer += f"F1 help │ q quit{RESET}"
    output.append(footer)
    
    # ═══ HELP OVERLAY ═══
    if state.show_help:
        help_text = [
            "",
            f"{color(219, bold=True)}  MOCHI HELP  {RESET}",
            "",
            f"{color(255, bold=True)}COMMANDS{RESET}",
            "  /agents        List all agents",
            "  /inspect <id>  Inspect agent details",
            "  /compare <id>  Before/after comparison",
            "  /alerts        Show alerts",
            "  /summary       System summary",
            "  /optimize <id> Trigger optimization",
            "  /replay        Demo optimization",
            "  /dashboard     Open web dashboard",
            "  /clear         Clear chat",
            "  /help          This help",
            "  /quit          Exit",
            "",
            f"{color(255, bold=True)}NATURAL LANGUAGE{RESET}",
            "  'why is camera-agent hot?'",
            "  'what did the optimizer do?'",
            "  'which agent uses most tokens?'",
            "",
            f"{color(244)}Press any key to close{RESET}",
        ]
        # Center the help box
        help_width = 45
        start_col = (cols - help_width) // 2
        start_row = 5
        for i, hline in enumerate(help_text):
            move_cursor(start_row + i, start_col)
            sys.stdout.write(f"{color(bg=236)}{hline:<{help_width}}{RESET}")
    
    # Write everything
    sys.stdout.write("\033[H")  # Move to top
    sys.stdout.write("\n".join(output[:rows-1]))
    sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════════════
# COMMAND HANDLING
# ═══════════════════════════════════════════════════════════════════════════

async def handle_input(state: AppState, text: str, client, router, context_builder, llm_client) -> None:
    """Process user input."""
    if not text.strip():
        return
    
    # Add to chat history
    state.chat_history.append(("user", text))
    
    # Check for slash command
    if text.startswith("/"):
        await handle_command(state, text, client, router)
    else:
        await handle_question(state, text, client, context_builder, llm_client)


async def handle_command(state: AppState, text: str, client, router) -> None:
    """Handle slash command."""
    parts = text.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    
    if command == "/help":
        state.show_help = True
        return
    
    if command == "/quit" or command == "/exit":
        state.running = False
        return
    
    if command == "/clear":
        state.chat_history = []
        state.chat_history.append(("system", "Chat cleared!"))
        return
    
    if command == "/dashboard":
        import webbrowser
        s = settings()
        webbrowser.open(s.dashboard_url)
        state.chat_history.append(("mochi", f"Opening dashboard at {s.dashboard_url}"))
        return
    
    if command == "/replay":
        await handle_replay(state, client, router)
        return
    
    # Route through tool router
    state.processing = True
    state.mochi.mood = "thinking"
    state.mochi.message = "Processing..."
    
    result = await router.route_command(command, args)
    
    state.processing = False
    state.mochi.mood = "happy"
    state.mochi.message = ""
    
    if result.success:
        state.chat_history.append(("mochi", result.output))
        if "/optimize" in command:
            state.mochi.mood = "excited"
            state.mochi.message = "Optimized! 🎉"
            state.mochi.jump_until = time.time() + 0.5
    else:
        state.chat_history.append(("error", result.error or "Command failed"))


async def handle_question(state: AppState, text: str, client, context_builder, llm_client) -> None:
    """Handle natural language question."""
    state.processing = True
    state.mochi.mood = "thinking"
    state.mochi.message = "Thinking..."
    
    try:
        # Gather context
        agents = await client.get_agents()
        summary = await client.get_summary()
        alerts = await client.get_alerts()
        
        # Find target agent
        target_id = context_builder.extract_agent_id_from_question(text, agents)
        target_agent = None
        comparison = None
        
        if target_id:
            target_agent = await client.get_agent(target_id)
            comparison = await client.get_compare(target_id)
        
        # Build context
        context, stats = context_builder.build_question_context(
            question=text,
            agents=agents,
            summary=summary,
            alerts=alerts,
            comparison=comparison,
            target_agent=target_agent,
        )
        
        # Show compression stats
        if stats.compression_ratio > 0.3:
            state.chat_history.append(("system", 
                f"Context: {stats.original_chars}→{stats.compressed_chars} chars"))
        
        # Generate response
        response = await llm_client.generate(text, context)
        
        state.processing = False
        state.mochi.mood = "happy"
        state.mochi.message = ""
        
        if response.error and not response.text:
            state.chat_history.append(("error", f"LLM: {response.error}"))
            state.mochi.mood = "warning"
        else:
            state.chat_history.append(("mochi", response.text))
            if response.explanation and response.explanation.confidence == "high":
                state.mochi.mood = "excited"
                state.mochi.message = "Found it!"
                
    except Exception as e:
        state.processing = False
        state.mochi.mood = "warning"
        state.chat_history.append(("error", str(e)))


async def handle_replay(state: AppState, client, router) -> None:
    """Demo optimization event."""
    hot_agents = [a for a in state.agents if a.status == AgentStatus.HOT]
    
    if not hot_agents:
        state.chat_history.append(("mochi", "No hot agents to optimize. All good! ✨"))
        state.mochi.mood = "happy"
        return
    
    target = hot_agents[0]
    state.chat_history.append(("system", f"Optimizing {target.name}..."))
    state.mochi.mood = "thinking"
    state.mochi.message = "Optimizing..."
    state.processing = True
    
    comparison = await client.trigger_optimization(target.agent_id)
    
    state.processing = False
    
    if comparison:
        output = router._format_optimization_result(comparison)
        state.chat_history.append(("mochi", output))
        state.mochi.mood = "excited"
        state.mochi.message = f"Optimized {target.name}! 🎉"
        state.mochi.jump_until = time.time() + 0.5
    else:
        state.chat_history.append(("error", "Optimization failed"))


# ═══════════════════════════════════════════════════════════════════════════
# DATA POLLING
# ═══════════════════════════════════════════════════════════════════════════

async def poll_data(state: AppState, client) -> None:
    """Poll backend for data updates."""
    try:
        # Tick mock backend
        if client.is_mock_mode:
            client._mock.tick()
        
        # Fetch data
        state.agents = await client.get_agents()
        state.summary = await client.get_summary()
        state.alerts = await client.get_alerts(5)
        
        # Update Mochi mood based on system state
        hot_count = len([a for a in state.agents if a.status == AgentStatus.HOT])
        if hot_count > 0 and state.mochi.mood == "happy":
            state.mochi.mood = "warning"
            state.mochi.message = f"{hot_count} hot!"
        elif hot_count == 0 and state.mochi.mood == "warning":
            state.mochi.mood = "happy"
            state.mochi.message = "All good!"
            
    except Exception as e:
        state.last_event = f"Poll error: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════════

async def async_main() -> None:
    """Async main loop."""
    # Initialize services
    s = settings()
    client = get_backend_client()
    router = get_tool_router(client)
    context_builder = get_context_builder()
    llm_client = get_llm_client(use_mock=s.use_mocks)
    
    # Connect
    await client.connect()
    
    # Initialize state
    state = AppState()
    state.backend_status = "mock" if client.is_mock_mode else "connected"
    state.mochi.mood = "happy"
    state.mochi.message = "Hello! 🍡"
    
    # Welcome message
    state.chat_history.append(("mochi", f"Hi! I'm Mochi! 🍡 ({state.backend_status} mode)"))
    state.chat_history.append(("system", "Type /agents to see agents, or ask me anything!"))
    
    # Check LLM availability
    if not s.use_mocks:
        available = await llm_client.check_availability()
        if available:
            state.chat_history.append(("system", f"LLM ready: {s.model_name}"))
        else:
            state.chat_history.append(("system", f"LLM not available - using mock responses"))
    
    # Initial data fetch
    await poll_data(state, client)
    
    last_poll = time.time()
    pending_input = None
    
    with KeyReader() as reader:
        hide_cursor()
        try:
            while state.running:
                now = time.time()
                
                # Random blink
                if random.random() < 0.03:
                    state.mochi.blink_until = now + 0.15
                
                # Poll data periodically
                if now - last_poll > POLL_SECONDS:
                    await poll_data(state, client)
                    last_poll = now
                
                # Handle any pending async input
                if pending_input is not None:
                    await handle_input(state, pending_input, client, router, context_builder, llm_client)
                    pending_input = None
                
                # Read keyboard
                key = reader.read_key()
                if key:
                    if state.show_help:
                        state.show_help = False
                    elif key == "UP":
                        if state.selected_agent_idx > 0:
                            state.selected_agent_idx -= 1
                    elif key == "DOWN":
                        if state.selected_agent_idx < len(state.agents) - 1:
                            state.selected_agent_idx += 1
                    elif key == '\x7f' or key == '\b':  # Backspace
                        state.input_buffer = state.input_buffer[:-1]
                    elif key == '\n' or key == '\r':  # Enter
                        if state.input_buffer.strip():
                            pending_input = state.input_buffer
                            state.input_buffer = ""
                    elif key == '\x03':  # Ctrl+C
                        state.running = False
                    elif key == 'q' and not state.input_buffer:
                        state.running = False
                    elif key == '\x1b' or key == 'ESC':  # Escape
                        state.input_buffer = ""
                    elif len(key) == 1 and ord(key) >= 32:
                        state.input_buffer += key
                
                # Render
                render(state)
                
                # Sleep
                await asyncio.sleep(TICK_SECONDS)
                
        finally:
            show_cursor()
            clear_screen()
            print("🍡 Mochi says bye bye!")


def main() -> None:
    """Entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        show_cursor()
        clear_screen()
        print("🍡 Mochi got interrupted but still loves you!")


if __name__ == "__main__":
    main()
