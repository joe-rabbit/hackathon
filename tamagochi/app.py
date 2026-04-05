"""Mochi Terminal UI - Nyan Cat Style Animated Hero.

Mochi flies across the screen with a rainbow trail, pixel sparkles, and
full Nyan Cat-inspired energy. Drop-in replacement for the hero rendering.
"""

import os
import sys
import time
import math
import random
import re
from dataclasses import dataclass, field
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# COLOR PALETTE
# ═══════════════════════════════════════════════════════════════════════════════

RESET = "\033[0m"

BG_MAIN = "17"
BG_SURFACE = "234"
BG_SURFACE2 = "235"
BORDER_COLOR = "238"

TEXT_MAIN = "255"
TEXT_DIM = "248"
TEXT_DIMMER = "240"

GREEN = "114"
PINK = "211"
HOT = "204"
MINT = "158"
YELLOW = "227"

MOCHI_BODY = "186"
MOCHI_DARK = "236"
MOCHI_CHEEK = "211"
MOCHI_SHINE = "231"
MOCHI_MOUTH = "210"
MOCHI_ARMS = "228"

DASHBOARD_URL = "http://localhost:8501"

# Rainbow stripe colors (ANSI 256 approximations of ROYGBIV)
RAINBOW_COLORS = ["196", "208", "226", "46", "27", "57", "129"]  # red orange yellow green blue indigo violet

# Star/sparkle chars
SPARKLE_CHARS = ["✦", "✧", "★", "☆", "·", "✸", "✺", "⋆", "*"]

# ═══════════════════════════════════════════════════════════════════════════════
# ANSI UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def fg(color: str) -> str:
    return f"\033[38;5;{color}m"

def bg(color: str) -> str:
    return f"\033[48;5;{color}m"

def bold() -> str:
    return "\033[1m"

def clear_screen() -> str:
    return "\033[2J\033[H"

def move_cursor(row: int, col: int) -> str:
    return f"\033[{row};{col}H"

def hide_cursor() -> str:
    return "\033[?25l"

def show_cursor() -> str:
    return "\033[?25h"

def enter_alt_screen() -> str:
    return "\033[?1049h"

def exit_alt_screen() -> str:
    return "\033[?1049l"

def clear_line() -> str:
    return "\033[2K"

def get_terminal_size() -> tuple[int, int]:
    try:
        size = os.get_terminal_size()
        return size.lines, size.columns
    except:
        return 24, 80


# ═══════════════════════════════════════════════════════════════════════════════
# MOCK DATA
# ═══════════════════════════════════════════════════════════════════════════════

MOCK_AGENTS = [
    {"name": "Camera Vision", "cpu": 85, "mem": 380, "tok": 1997, "status": "HOT",
     "latency": 540, "temp": 61.7, "optimizer": "compressing"},
    {"name": "NLP Process", "cpu": 39, "mem": 280, "tok": 677, "status": "OK",
     "latency": 210, "temp": 45.2, "optimizer": "none"},
    {"name": "Object Detect", "cpu": 38, "mem": 172, "tok": 523, "status": "OK",
     "latency": 180, "temp": 44.8, "optimizer": "batched"},
    {"name": "Request Router", "cpu": 19, "mem": 77, "tok": 220, "status": "OK",
     "latency": 50, "temp": 38.1, "optimizer": "none"},
    {"name": "Audio Process", "cpu": 49, "mem": 231, "tok": 592, "status": "OK",
     "latency": 260, "temp": 48.3, "optimizer": "none"},
]

MOCK_ALERTS = [
    "camera-agent token spike detected",
    "camera-agent CPU above hot threshold",
]


# ═══════════════════════════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════════════════════════

# Random cat speech bubbles
CAT_MESSAGES = [
    "meow~",
    "purrrr...",
    "*yawn*",
    "feed me!",
    "nyaa~",
    "zzz...",
    "*stretch*",
    "pet me?",
    "mrrp!",
    "...",
    "*blink*",
    "uwu",
    "ฅ^•ﻌ•^ฅ",
    "~nya",
    "*purr*",
    "hmm?",
    "!!",
    "♪♫",
    "*tail wag*",
    "?_?",
]

@dataclass
class AppState:
    running: bool = True
    input_buffer: str = ""
    transcript: list = field(default_factory=list)
    transcript_scroll: int = 0
    mood: str = "idle"
    mood_timer: int = 0
    frame: int = 0
    blink_until: float = 0.0
    jump_until: float = 0.0
    last_resize: tuple = (0, 0)
    model_name: str = "gemma3:1b"
    backend_status: str = "connected"
    mode: str = "mock"
    # Cat animation state
    current_message: str = "meow~"
    message_timer: int = 0
    tail_frame: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# MOCHI SPRITE - Custom Pixel Art Cat (28x28 scaled down for terminal)
# ═══════════════════════════════════════════════════════════════════════════════

# Custom pixel art cat - 19 cols wide × 14 rows tall (sampled from 28x28)
# Colors: .=transparent, K=black, G=dark gray (#121212), A=gray (#454545), 
#         W=white, Y=yellow (#ffc231), P=pink (#76374c)

# Full 28x28 pixel data (parsed from CSS box-shadow)
CAT_PIXEL_DATA = [
    "............................",
    ".........................KK.",
    ".......................GKAK.",
    "........KKKK..........GGAAK.",
    ".........GAGGG.......GAAAAK.",
    ".........GAAAAGGGGGGKAAAAAK.",
    ".........GAAAAAAAAAAAAAAAAG.",
    ".........GAKKGGGAAAAAGGGKAG.",
    ".........GKKWKGGGGAAGWGGGGK.",
    ".........GKWWWGGYKAGWWWGYYG.",
    "........GAKWWGGGYGAGWWGGGYG.",
    "........GAGGGGGGYGAGGGGGGYG.",
    "........GPGYGGGYYGAGGGGGGYP.",
    "........GPPGYYYYGAAGGYYYYPP.",
    "........GAAAGGGKAAAAGGGGGPG.",
    "........GAAAAKAAAAAAAAGAAG..",
    ".........GGGGAAAAAAAAAAAK...",
    "...........WWKGGGGGKKGGG....",
    ".............KKKKYYKKKKK....",
    "............KKKKKYYKKKKK....",
    "............KAAAAAAAAAAAK...",
    "...........KAAAAAAAAAAAAK...",
    ".........KKAAAAAAAAAAAAAAK..",
    ".........KAAAAAAAAAAAAAAAK..",
    ".........KAKAAAKAAAKAAAKAKK.",
    "........KKAKAAAKAAAKAAAKAAK.",
    "........KKAKAAAKAAAKAAAKAAK.",
    "........KAAKAAAKAAAKAAAKAAK.",
]

# Color map for pixels
CAT_COLORS = {
    '.': None,           # transparent
    'K': "\033[48;5;16m",   # black
    'G': "\033[48;5;234m",  # dark gray (#121212)
    'A': "\033[48;5;239m",  # gray (#454545)
    'W': "\033[48;5;231m",  # white
    'Y': "\033[48;5;220m",  # yellow (#ffc231)
    'P': "\033[48;5;132m",  # pink (#76374c)
}

# Sprite dimensions (using every 2nd row and col for terminal display)
CAT_SPRITE_WIDTH = 28   # pixels wide (each pixel = 2 terminal cols)
CAT_SPRITE_HEIGHT = 14  # displayed rows (sampling every 2nd row)


def get_cat_frame_data(mood: str, blinking: bool, frame: int, tail_frame: int = 0) -> list[str]:
    """Get the pixel data for the cat, with mood-based eye variations and tail wag."""
    # Sample every 2nd row for terminal-friendly size
    rows = [CAT_PIXEL_DATA[i] for i in range(0, 28, 2)]
    
    # Apply mood-based eye modifications
    if blinking or mood == "sleepy":
        # Close eyes - replace W (white eye) with G (gray/closed)
        rows = [row.replace('W', 'G') for row in rows]
    
    # Tail wag animation - modify rows 0-2 (the tail area at top right)
    # The tail is in the top-right corner (around columns 23-27, rows 1-4)
    tail_phase = tail_frame % 4
    
    # Tail positions for wagging effect
    if tail_phase == 0:
        # Tail up-right (default position from pixel data)
        pass
    elif tail_phase == 1:
        # Tail more upright
        rows[0] = rows[0][:24] + "KK.." 
        rows[1] = rows[1][:23] + "GKAK."
    elif tail_phase == 2:
        # Tail straight up
        rows[0] = rows[0][:25] + "K.."
        rows[1] = rows[1][:24] + "KAK."
    elif tail_phase == 3:
        # Tail tilted other way
        rows[0] = rows[0][:26] + "K."
        rows[1] = rows[1][:25] + "KK."
    
    return rows


def render_mochi_sprite(mood: str, blinking: bool, frame: int, tail_frame: int = 0) -> tuple[list[str], int]:
    """
    Render custom cat sprite as a list of strings with ANSI codes.
    Returns (lines, display_width_in_cols).
    Display width = 28 pixels × 1 col each = 28 cols.
    """
    rows = get_cat_frame_data(mood, blinking, frame, tail_frame)
    
    lines = []
    for row in rows:
        parts = []
        for pixel in row:
            color = CAT_COLORS.get(pixel)
            if color:
                parts.append(f"{color} {RESET}")
            else:
                parts.append(" ")
        lines.append("".join(parts))
    
    return lines, CAT_SPRITE_WIDTH  # 28 cols (1 char per pixel)


# ═══════════════════════════════════════════════════════════════════════════════
# HERO RENDERER - Stationary cat with speech bubble and tail wag
# ═══════════════════════════════════════════════════════════════════════════════

def render_speech_bubble(message: str, width: int) -> list[str]:
    """Render a speech bubble with the given message."""
    # Bubble components
    padding = 2
    inner_width = len(message) + padding * 2
    
    top = f"╭{'─' * inner_width}╮"
    middle = f"│{' ' * padding}{message}{' ' * padding}│"
    bottom = f"╰{'─' * inner_width}╯"
    pointer = f" ╲"
    
    return [top, middle, bottom, pointer]


def render_hero_nyan(state: AppState, width: int, height: int) -> list[str]:
    """
    Render the hero area with:
    - Stationary pixel cat centered on screen
    - Tail wagging animation
    - Speech bubble with random messages
    """
    HERO_HEIGHT = min(18, max(14, height // 3))
    SPRITE_WIDTH = CAT_SPRITE_WIDTH   # 28 cols
    SPRITE_HEIGHT = CAT_SPRITE_HEIGHT  # 14 rows

    # Update tail wag (every 8 frames)
    if state.frame % 8 == 0:
        state.tail_frame = (state.tail_frame + 1) % 4
    
    # Update message (every ~100 frames)
    state.message_timer += 1
    if state.message_timer > 80 + random.randint(0, 40):
        state.current_message = random.choice(CAT_MESSAGES)
        state.message_timer = 0

    # Cat position - centered
    cat_x = (width - SPRITE_WIDTH) // 2
    cat_y = (HERO_HEIGHT - SPRITE_HEIGHT) // 2 + 2  # Slightly lower to make room for bubble

    # Build the output lines
    now = time.time()
    blinking = now < state.blink_until
    sprite_lines, sw = render_mochi_sprite(state.mood, blinking, state.frame, state.tail_frame)

    # Speech bubble
    bubble_lines = render_speech_bubble(state.current_message, width)
    bubble_width = len(bubble_lines[0])
    bubble_x = cat_x + SPRITE_WIDTH // 2 - bubble_width // 2  # Center above cat

    # Render line by line
    output_lines = []
    
    # Bubble rows (above the cat)
    bubble_start_row = cat_y - len(bubble_lines) - 1
    
    for row in range(HERO_HEIGHT):
        line = " " * width
        
        # Draw speech bubble
        bubble_row_idx = row - bubble_start_row
        if 0 <= bubble_row_idx < len(bubble_lines):
            bubble_str = bubble_lines[bubble_row_idx]
            bx = max(0, min(bubble_x, width - len(bubble_str)))
            line = line[:bx] + f"{fg(TEXT_DIM)}{bubble_str}{RESET}" + line[bx + len(bubble_str):]
        
        # Draw cat sprite
        sprite_row_idx = row - cat_y
        if 0 <= sprite_row_idx < len(sprite_lines):
            sprite_row_str = sprite_lines[sprite_row_idx]
            col = max(0, min(cat_x, width - SPRITE_WIDTH))
            # Need to carefully splice since sprite has ANSI codes
            prefix = line[:col]
            suffix_start = col + SPRITE_WIDTH
            suffix = line[suffix_start:] if suffix_start < len(line) else ""
            line = prefix + sprite_row_str + suffix
        
        output_lines.append(line)

    # Bottom floor line
    output_lines.append(f"{fg(BORDER_COLOR)}{'─' * width}{RESET}")

    return output_lines


# ═══════════════════════════════════════════════════════════════════════════════
# REST OF RENDERING (unchanged from original)
# ═══════════════════════════════════════════════════════════════════════════════

def render_status_line(state: AppState, width: int) -> str:
    total_agents = len(MOCK_AGENTS)
    hot_agents = sum(1 for a in MOCK_AGENTS if a["status"] == "HOT")
    alert_count = len(MOCK_ALERTS)
    total_tok = sum(a["tok"] for a in MOCK_AGENTS)

    parts = []
    parts.append(f"{fg(PINK)}{bold()}Mochi{RESET}")
    parts.append(f"{fg(TEXT_DIM)}|{RESET}")
    parts.append(f"{fg(TEXT_DIM)}{state.mode}{RESET}")
    parts.append(f"{fg(TEXT_DIM)}|{RESET}")
    parts.append(f"{fg(GREEN)}{bold()}{total_agents} agents{RESET}")
    parts.append(f"{fg(TEXT_DIM)}|{RESET}")
    if hot_agents > 0:
        parts.append(f"{fg(HOT)}{bold()}{hot_agents} hot{RESET}")
    else:
        parts.append(f"{fg(TEXT_DIM)}0 hot{RESET}")
    parts.append(f"{fg(TEXT_DIM)}|{RESET}")
    if alert_count > 0:
        parts.append(f"{fg(HOT)}{alert_count} alert{RESET}")
    else:
        parts.append(f"{fg(TEXT_DIM)}0 alerts{RESET}")
    parts.append(f"{fg(TEXT_DIM)}|{RESET}")
    parts.append(f"{fg(TEXT_DIM)}{total_tok} tok/min{RESET}")
    parts.append(f"{fg(TEXT_DIM)}|{RESET}")
    parts.append(f"{fg(TEXT_DIM)}{state.model_name}{RESET}")
    parts.append(f"{fg(TEXT_DIM)}|{RESET}")
    parts.append(f"{fg(GREEN)}d: dashboard{RESET}")

    line = " ".join(parts)
    return f"{bg(BG_SURFACE2)}{line}{RESET}"


def render_welcome(width: int) -> list[str]:
    lines = []
    line1 = "Hi, I'm Mochi."
    line2 = "I explain edge-agent behavior and optimization."
    line3 = "Type /agents, /inspect camera-agent, or ask me anything."
    line4 = f"Dashboard running at {DASHBOARD_URL}"

    pad1 = (width - len(line1)) // 2
    pad2 = (width - len(line2)) // 2
    pad3 = (width - len(line3)) // 2
    pad4 = (width - len(line4)) // 2

    lines.append("")
    lines.append(f"{' ' * pad1}{fg(PINK)}{bold()}{line1}{RESET}")
    lines.append(f"{' ' * pad2}{fg(TEXT_DIM)}{line2}{RESET}")
    lines.append(f"{' ' * pad3}{fg(TEXT_DIM)}{line3}{RESET}")
    lines.append(f"{' ' * pad4}{fg(GREEN)}{line4}{RESET}")
    lines.append("")

    return lines


def render_divider(width: int) -> str:
    dots = "·" * min(width - 4, 60)
    padding = (width - len(dots)) // 2
    return f"{' ' * padding}{fg(BORDER_COLOR)}{dots}{RESET}"


def expand_transcript_entries(state: AppState, width: int) -> list[str]:
    all_lines = []
    for entry in state.transcript:
        entry_type, prefix, text, card_data = entry
        prefix_str = prefix.ljust(8)
        if entry_type == "user":
            all_lines.append(f"  {fg(GREEN)}{bold()}{prefix_str}{RESET}{fg(TEXT_MAIN)}{text}{RESET}")
        elif entry_type == "mochi":
            all_lines.append(f"  {fg(PINK)}{bold()}{prefix_str}{RESET}{fg(TEXT_MAIN)}{text}{RESET}")
        elif entry_type == "system":
            all_lines.append(f"  {fg(TEXT_DIMMER)}{prefix_str}{text}{RESET}")
        elif entry_type == "warning":
            all_lines.append(f"  {fg(HOT)}{bold()}{prefix_str}{RESET}{fg(HOT)}{text}{RESET}")
        elif entry_type == "ok":
            all_lines.append(f"  {fg(GREEN)}{bold()}{prefix_str}{RESET}{fg(MINT)}{text}{RESET}")
        if card_data:
            card_lines = render_card(card_data, width - 4)
            all_lines.extend(card_lines)
    return all_lines


def render_transcript(state: AppState, width: int, max_lines: int) -> list[str]:
    all_lines = expand_transcript_entries(state, width)
    total_lines = len(all_lines)
    scroll = state.transcript_scroll
    if total_lines <= max_lines - 1:
        visible_lines = all_lines
    else:
        end_idx = total_lines - scroll
        start_idx = max(0, end_idx - (max_lines - 1))
        end_idx = min(total_lines, start_idx + max_lines - 1)
        visible_lines = all_lines[start_idx:end_idx]
    lines = visible_lines.copy()
    if scroll > 0:
        lines.append(f"  {fg(TEXT_DIMMER)}↓ {scroll} more lines below (press ↓ or End to scroll){RESET}")
    elif total_lines > max_lines - 1:
        lines.append(f"  {fg(TEXT_DIMMER)}─ {total_lines} lines total ─{RESET}")
    while len(lines) < max_lines:
        lines.append("")
    return lines[:max_lines]


def render_card(card_data: dict, width: int) -> list[str]:
    lines = []
    card_type = card_data.get("type", "")
    if card_type == "roster":
        lines.append("")
        header = f"{'NAME':<16} {'STATUS':<8} {'CPU':>5} {'MEM':>6} {'TOK/MIN':>8} {'LATENCY':>8} {'OPTIMIZER':<12}"
        lines.append(f"  {fg(TEXT_DIM)}{header}{RESET}")
        lines.append(f"  {fg(BORDER_COLOR)}{'─' * len(header)}{RESET}")
        for agent in card_data.get("agents", []):
            status_color = HOT if agent["status"] == "HOT" else GREEN
            name = agent["name"][:16].ljust(16)
            status = agent["status"].ljust(8)
            cpu = f"{agent['cpu']}%".rjust(5)
            mem = f"{agent['mem']}M".rjust(6)
            tok = str(agent["tok"]).rjust(8)
            lat = f"{agent.get('latency', 0)}ms".rjust(8)
            opt = agent.get("optimizer", "none")[:12].ljust(12)
            lines.append(f"  {fg(TEXT_MAIN)}{name}{RESET} {fg(status_color)}{status}{RESET} {fg(TEXT_DIM)}{cpu} {mem} {tok} {lat}{RESET} {fg(TEXT_DIM)}{opt}{RESET}")
        lines.append("")
    elif card_type == "detail":
        agent = card_data.get("agent", {})
        status_color = HOT if agent.get("status") == "HOT" else GREEN
        lines.append("")
        lines.append(f"  {fg(PINK)}{bold()}Agent: {agent.get('name', 'Unknown')}{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}Status:{RESET}    {fg(status_color)}{agent.get('status', 'OK')}{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}CPU:{RESET}       {fg(TEXT_MAIN)}{agent.get('cpu', 0)}%{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}Memory:{RESET}    {fg(TEXT_MAIN)}{agent.get('mem', 0)}MB{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}Temp:{RESET}      {fg(TEXT_MAIN)}{agent.get('temp', 0)}C{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}Tokens/min:{RESET} {fg(TEXT_MAIN)}{agent.get('tok', 0)}{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}Latency:{RESET}   {fg(TEXT_MAIN)}{agent.get('latency', 0)}ms{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}Optimizer:{RESET} {fg(TEXT_MAIN)}{agent.get('optimizer', 'none')}{RESET}")
        lines.append("")
    elif card_type == "summary":
        total = len(MOCK_AGENTS)
        hot = sum(1 for a in MOCK_AGENTS if a["status"] == "HOT")
        alerts = len(MOCK_ALERTS)
        total_tok = sum(a["tok"] for a in MOCK_AGENTS)
        avg_cpu = sum(a["cpu"] for a in MOCK_AGENTS) // total
        most_active = max(MOCK_AGENTS, key=lambda a: a["tok"])
        lines.append("")
        lines.append(f"  {fg(PINK)}{bold()}System Summary{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}Agents:{RESET}      {fg(GREEN)}{total}{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}Hot:{RESET}         {fg(HOT if hot > 0 else TEXT_DIM)}{hot}{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}Alerts:{RESET}      {fg(HOT if alerts > 0 else TEXT_DIM)}{alerts}{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}Total tok/min:{RESET} {fg(TEXT_MAIN)}{total_tok}{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}Avg CPU:{RESET}     {fg(TEXT_MAIN)}{avg_cpu}%{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}Most active:{RESET} {fg(PINK)}{most_active['name']}{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}Last action:{RESET} {fg(MINT)}prompt compression{RESET}")
        lines.append("")
    elif card_type == "alerts":
        lines.append("")
        lines.append(f"  {fg(PINK)}{bold()}Active Alerts{RESET}")
        for i, alert in enumerate(MOCK_ALERTS, 1):
            lines.append(f"  {fg(HOT)}{i}. {alert}{RESET}")
        lines.append("")
    elif card_type == "compare":
        agent = card_data.get("agent", {})
        lines.append("")
        lines.append(f"  {fg(PINK)}{bold()}{agent.get('name', 'Unknown')} Optimization Compare{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}Before:{RESET} CPU 92% | Tokens 2450/min | Latency 610ms")
        lines.append(f"  {fg(GREEN)}After:{RESET}  CPU {agent.get('cpu', 85)}% | Tokens {agent.get('tok', 1997)}/min | Latency {agent.get('latency', 540)}ms")
        lines.append(f"  {fg(MINT)}Savings: 7% CPU | 18% tokens | 11% latency{RESET}")
        lines.append("")
    elif card_type == "dashboard":
        lines.append("")
        lines.append(f"  {fg(PINK)}{bold()}Dashboard{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}URL:{RESET} {fg(GREEN)}{DASHBOARD_URL}{RESET}")
        lines.append(f"  {fg(TEXT_DIM)}Open in browser for charts and trends.{RESET}")
        lines.append("")
    return lines


def render_prompt(state: AppState, width: int) -> str:
    prompt = f"  {fg(GREEN)}{bold()}>{RESET} "
    if state.input_buffer:
        return f"{prompt}{fg(TEXT_MAIN)}{state.input_buffer}{RESET}"
    else:
        return f"{prompt}{fg(TEXT_DIMMER)}Ask Mochi or type /help{RESET}"


def render_hints(width: int) -> str:
    hints = [
        (f"{fg(GREEN)}{bold()}Enter{RESET}", f"{fg(TEXT_DIMMER)}send{RESET}"),
        (f"{fg(GREEN)}↑↓{RESET}", f"{fg(TEXT_DIMMER)}scroll{RESET}"),
        (f"{fg(GREEN)}/agents{RESET}", f"{fg(TEXT_DIMMER)}list{RESET}"),
        (f"{fg(GREEN)}/dashboard{RESET}", f"{fg(TEXT_DIMMER)}open{RESET}"),
        (f"{fg(GREEN)}q{RESET}", f"{fg(TEXT_DIMMER)}quit{RESET}"),
    ]
    parts = ["  "]
    for key, desc in hints:
        parts.append(f"{key} {desc}  ")
    return f"{bg(BG_SURFACE2)}{''.join(parts)}{RESET}"


def render_screen(state: AppState) -> str:
    rows, cols = get_terminal_size()
    output = []

    output.append(render_status_line(state, cols))
    hero_lines = render_hero_nyan(state, cols, rows)
    output.extend(hero_lines)
    welcome_lines = render_welcome(cols)
    output.extend(welcome_lines)
    output.append(render_divider(cols))
    output.append("")

    used_rows = len(output) + 3
    transcript_rows = max(4, rows - used_rows)
    transcript_lines = render_transcript(state, cols, transcript_rows)
    output.extend(transcript_lines)
    output.append(render_prompt(state, cols))
    output.append(render_hints(cols))

    while len(output) < rows:
        output.append("")
    output = output[:rows]

    padded_output = [clear_line() + line for line in output]
    return "\033[H" + hide_cursor() + "\n".join(padded_output)


# ═══════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLING
# ═══════════════════════════════════════════════════════════════════════════════

def handle_command(state: AppState, cmd: str) -> None:
    cmd_lower = cmd.lower().strip()
    if cmd_lower == "/help":
        state.transcript.append(("mochi", "Mochi", "Here are the available commands:", None))
        for c in ["/agents", "/inspect <name>", "/alerts", "/summary",
                  "/compare <name>", "/dashboard", "/replay", "/clear"]:
            state.transcript.append(("system", "·", c, None))
        state.mood = "happy"; state.mood_timer = 90
    elif cmd_lower == "/agents":
        state.transcript.append(("mochi", "Mochi", "Here are your agents:",
                                 {"type": "roster", "agents": MOCK_AGENTS}))
        state.mood = "thinking"; state.mood_timer = 60
    elif cmd_lower.startswith("/inspect"):
        parts = cmd.split(maxsplit=1)
        if len(parts) > 1:
            name = parts[1].lower()
            agent = next((a for a in MOCK_AGENTS if name in a["name"].lower()), None)
            if agent:
                state.transcript.append(("mochi", "Mochi", f"Details for {agent['name']}:",
                                        {"type": "detail", "agent": agent}))
                if agent["status"] == "HOT":
                    state.transcript.append(("mochi", "Mochi",
                        "This one is the busiest agent right now!", None))
                state.mood = "thinking"
            else:
                state.transcript.append(("warning", "alert", f"Agent '{parts[1]}' not found", None))
                state.mood = "sad"
        else:
            state.transcript.append(("mochi", "Mochi", "Usage: /inspect <agent_name>", None))
        state.mood_timer = 60
    elif cmd_lower == "/alerts":
        state.transcript.append(("mochi", "Mochi", "Active alerts:", {"type": "alerts"}))
        state.transcript.append(("mochi", "Mochi",
            "Most pressure is coming from camera-agent.", None))
        state.mood = "warning"; state.mood_timer = 100
    elif cmd_lower == "/summary":
        state.transcript.append(("mochi", "Mochi", "Here's the latest system summary:",
                                {"type": "summary"}))
        state.mood = "celebrate"; state.mood_timer = 90
    elif cmd_lower.startswith("/compare"):
        parts = cmd.split(maxsplit=1)
        if len(parts) > 1:
            name = parts[1].lower()
            agent = next((a for a in MOCK_AGENTS if name in a["name"].lower()), None)
            if agent:
                state.transcript.append(("mochi", "Mochi", "Optimization comparison:",
                                        {"type": "compare", "agent": agent}))
                state.mood = "celebrate"
            else:
                state.transcript.append(("warning", "alert", f"Agent '{parts[1]}' not found", None))
                state.mood = "sad"
        else:
            state.transcript.append(("mochi", "Mochi", "Usage: /compare <agent_name>", None))
        state.mood_timer = 90
    elif cmd_lower == "/dashboard":
        import subprocess, webbrowser, urllib.request
        state.transcript.append(("mochi", "Mochi", "Opening dashboard...", None))
        try:
            response = urllib.request.urlopen(DASHBOARD_URL, timeout=2)
            if response.code == 200:
                state.transcript.append(("ok", "ok", "Dashboard already running!", None))
                webbrowser.open(DASHBOARD_URL)
        except:
            state.transcript.append(("warning", "alert", "Dashboard not reachable. Try ./start_dashboard_bg.sh", None))
        state.transcript.append(("mochi", "Mochi", "Dashboard shows charts and trends!", {"type": "dashboard"}))
        state.mood = "happy"; state.mood_timer = 60
    elif cmd_lower == "/replay":
        state.transcript.append(("mochi", "Mochi", "Replaying last optimization event...", None))
        state.mood = "celebrate"; state.mood_timer = 120
    elif cmd_lower == "/clear":
        state.transcript.clear()
        state.transcript.append(("system", "[system]", "Transcript cleared.", None))
        state.mood = "idle"; state.mood_timer = 0
    else:
        state.transcript.append(("mochi", "Mochi", f"Unknown command: {cmd}. Try /help", None))
        state.mood = "thinking"; state.mood_timer = 60


def handle_natural_language(state: AppState, text: str) -> None:
    text_lower = text.lower()
    if re.search(r"camera|vision|hot", text_lower):
        agent = next(a for a in MOCK_AGENTS if "Camera" in a["name"])
        state.transcript.append(("mochi", "Mochi", "Camera Vision is the hottest agent!", None))
        state.transcript.append(("mochi", "Mochi", "Details:", {"type": "detail", "agent": agent}))
        state.mood = "warning"; state.mood_timer = 100
    elif re.search(r"token|tok", text_lower):
        total_tok = sum(a["tok"] for a in MOCK_AGENTS)
        state.transcript.append(("mochi", "Mochi", f"Total token rate: {total_tok} tok/min", None))
        state.mood = "thinking"; state.mood_timer = 60
    elif re.search(r"optimi", text_lower):
        state.transcript.append(("mochi", "Mochi", "Optimizer already reduced waste from Camera Vision!", None))
        state.transcript.append(("ok", "ok", "Prompt compression saved 38% tokens in the last run.", None))
        state.mood = "celebrate"; state.mood_timer = 90
    elif re.search(r"hello|hi|hey", text_lower):
        state.transcript.append(("mochi", "Mochi", "Hello! I'm here to help you understand your edge agents. ✦", None))
        state.mood = "happy"; state.mood_timer = 90
    elif re.search(r"dashboard|web|browser", text_lower):
        state.transcript.append(("mochi", "Mochi", "Here's your dashboard link:", {"type": "dashboard"}))
        state.mood = "happy"; state.mood_timer = 60
    else:
        state.transcript.append(("mochi", "Mochi", "I'm not sure about that. Try /help for available commands.", None))
        state.mood = "thinking"; state.mood_timer = 60


def handle_input(state: AppState, text: str) -> None:
    state.transcript.append(("user", ">", text, None))
    if text.startswith("/"):
        handle_command(state, text)
    else:
        handle_natural_language(state, text)


# ═══════════════════════════════════════════════════════════════════════════════
# KEYBOARD INPUT
# ═══════════════════════════════════════════════════════════════════════════════

class KeyReader:
    def __enter__(self):
        if os.name == "nt":
            import msvcrt
            self._msvcrt = msvcrt
            return self
        import termios, tty, select
        self._select = select
        self._termios = termios
        self._stdin_fd = sys.stdin.fileno()
        self._old_settings = termios.tcgetattr(self._stdin_fd)
        tty.setcbreak(self._stdin_fd)
        return self

    def __exit__(self, *args):
        if os.name != "nt":
            self._termios.tcsetattr(self._stdin_fd, self._termios.TCSADRAIN, self._old_settings)

    def read_key(self) -> Optional[str]:
        if os.name == "nt":
            if self._msvcrt.kbhit():
                key = self._msvcrt.getwch()
                if key in ("\x00", "\xe0"):
                    self._msvcrt.getwch()
                    return None
                return key
            return None
        ready, _, _ = self._select.select([sys.stdin], [], [], 0)
        if ready:
            return sys.stdin.read(1)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    state = AppState()
    state.mochi_x = 0.1  # start near left

    import signal
    def handle_resize(signum, frame):
        pass
    if hasattr(signal, 'SIGWINCH'):
        signal.signal(signal.SIGWINCH, handle_resize)

    state.transcript.append(("system", "[system]", "Terminal session started.", None))
    state.transcript.append(("system", "[system]", f"Dashboard: {DASHBOARD_URL} (use /dashboard to start)", None))

    tick_interval = 0.033  # ~30fps
    last_render = 0
    last_size = (0, 0)

    sys.stdout.write(enter_alt_screen() + clear_screen())
    sys.stdout.flush()

    try:
        with KeyReader() as reader:
            while state.running:
                now = time.time()
                current_size = get_terminal_size()
                if current_size != last_size:
                    last_render = 0
                    last_size = current_size

                state.frame += 1

                # Random blink
                if random.random() < 0.015 and now > state.blink_until:
                    state.blink_until = now + 0.18

                # Mood timer
                if state.mood_timer > 0:
                    state.mood_timer -= 1
                    if state.mood_timer == 0:
                        state.mood = "idle"

                # Read input
                key = reader.read_key()
                if key:
                    if key == "\x03" or (key == "q" and not state.input_buffer):
                        state.running = False
                    elif key in ("\r", "\n"):
                        if state.input_buffer.strip():
                            handle_input(state, state.input_buffer.strip())
                            state.transcript_scroll = 0
                            state.input_buffer = ""
                    elif key in ("\x7f", "\b"):
                        state.input_buffer = state.input_buffer[:-1]
                    elif key == "\x1b":
                        time.sleep(0.01)
                        next_key = reader.read_key()
                        if next_key == "[":
                            arrow_key = reader.read_key()
                            if arrow_key == "A":
                                rows, cols = get_terminal_size()
                                used_rows = 1 + 13 + 5 + 2 + 3
                                transcript_rows = max(4, rows - used_rows)
                                total_lines = len(expand_transcript_entries(state, cols))
                                max_scroll = max(0, total_lines - transcript_rows + 1)
                                state.transcript_scroll = min(state.transcript_scroll + 3, max_scroll)
                            elif arrow_key == "B":
                                state.transcript_scroll = max(0, state.transcript_scroll - 3)
                            elif arrow_key == "F":
                                state.transcript_scroll = 0
                        else:
                            state.input_buffer = ""
                    elif key.isprintable():
                        state.input_buffer += key

                if now - last_render > tick_interval:
                    screen = render_screen(state)
                    sys.stdout.write(screen)
                    sys.stdout.flush()
                    last_render = now

                time.sleep(0.01)

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(exit_alt_screen() + show_cursor() + RESET)
        sys.stdout.flush()
        print("Mochi says goodbye! ✦")


if __name__ == "__main__":
    main()