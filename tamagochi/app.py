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

DASHBOARD_URL = "http://localhost:8086"

RAINBOW_COLORS = ["196", "208", "226", "46", "27", "57", "129"]
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

CAT_MESSAGES = {
    "idle":      ["meow~", "purrrr...", "*yawn*", "nyaa~", "...", "*blink*", "uwu", "~nya", "*purr*", "hmm?", "♪♫", "*tail wag*", "?_?"],
    "happy":     ["nyaa~!!", "purrrr~", "♥", "uwu", "*happy squirm*", "meow!!"],
    "thinking":  ["hmm...", "...", "calculating...", "*stare*", "processing~"],
    "warning":   ["!!!", "*ears back*", "hisss!", "danger!", "mrrp?!"],
    "sad":       ["...", "*sigh*", "meh", "lonely...", "*droopy ears*"],
    "celebrate": ["NYAA~!", "✦✦✦", "yay!!", "purrr!!", "*spin*", "meow!!"],
    "sleepy":    ["zzz...", "*yawn*", "tired...", "...zzz", "zz~"],
    "sleeping":  ["zzz...", "...zzz", "zz~", "Zzz"],
    "excited":   ["!!", "nyaa!!", "*zoom*", "yay!!!", "♥♥"],
    "treat":     ["nom nom!", "yummy~", "*chomp*", "more plz", "mew!!"],
    "pet":       ["purrr~", "♥", "uwu", "*leans in*", "soft..."],
}

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
    current_message: str = "meow~"
    message_timer: int = 0
    tail_frame: int = 0
    # Walking animation
    walk_until: float = 0.0
    walk_offset: int = 0
    walk_direction: int = 1  # 1 for right, -1 for left


# ═══════════════════════════════════════════════════════════════════════════════
# PIXEL ART CAT - 28x28
# ═══════════════════════════════════════════════════════════════════════════════

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

# Pixel color map → ANSI 256 background codes
CAT_COLORS = {
    '.': None,
    'K': "\033[48;5;16m",    # black
    'G': "\033[48;5;234m",   # dark gray (#121212)
    'A': "\033[48;5;239m",   # gray (#454545)
    'W': "\033[48;5;231m",   # white  (normal eye)
    'Y': "\033[48;5;220m",   # yellow (#ffc231)
    'P': "\033[48;5;132m",   # pink (#76374c)
    # Expression overrides (added below)
    'C': "\033[48;5;175m",   # rosy cheek pink
    'H': "\033[48;5;196m",   # heart red  (excited eye)
    'Z': "\033[48;5;111m",   # zzz blue   (sleep pixel)
    'S': "\033[48;5;239m",   # closed eye = dark gray
}

CAT_SPRITE_WIDTH = 28
CAT_SPRITE_HEIGHT = 14


# Eye pixel positions (row, col) in the SAMPLED (every-2nd-row) grid
# Sampled rows = original rows 0,2,4,6,8,10,12,14,16,18,20,22,24,26
# Left eye cluster:  sampled rows 4-5, cols 11-13
# Right eye cluster: sampled rows 4-5, cols 20-22
EYE_LEFT  = {(4,11),(4,12),(4,13),(5,10),(5,11),(5,12)}
EYE_RIGHT = {(4,20),(4,21),(4,22),(5,19),(5,20),(5,21)}

# Cheek positions (sampled rows 6, cols 9 and 19  — just inside the face)
CHEEK_LEFT  = {(6,9),(6,10)}
CHEEK_RIGHT = {(6,19),(6,20)}


def _get_eye_pixel(mood: str, blinking: bool, side: str) -> str:
    """Return the pixel character to use for eye cells based on mood/blink."""
    if blinking or mood in ("sleepy", "sleeping"):
        return 'S'   # closed / dark gray line
    if mood == "excited" or mood == "celebrate":
        return 'H'   # heart / red  (bright)
    if mood == "sad":
        return 'S'   # sad eyes closed slightly
    # default: normal white
    return 'W'


def get_cat_frame_data(mood: str, blinking: bool, frame: int, tail_frame: int = 0) -> list[str]:
    """
    Build the 14-row sampled pixel grid with:
      - mood-driven eye expression
      - rosy cheeks (happy / celebrate / excited)
      - zzz pixel in top-right when sleeping
      - tail wag animation
    """
    rows = [list(CAT_PIXEL_DATA[i]) for i in range(0, 28, 2)]   # 14 rows, each a list

    # ── Eye expression ────────────────────────────────────────────────────────
    eye_pixel = _get_eye_pixel(mood, blinking, "left")
    for (r, c) in EYE_LEFT:
        if 0 <= r < len(rows) and 0 <= c < len(rows[r]):
            if rows[r][c] == 'W':
                rows[r][c] = eye_pixel
    for (r, c) in EYE_RIGHT:
        if 0 <= r < len(rows) and 0 <= c < len(rows[r]):
            if rows[r][c] == 'W':
                rows[r][c] = eye_pixel

    # ── Rosy cheeks ───────────────────────────────────────────────────────────
    if mood in ("happy", "celebrate", "excited", "pet", "treat"):
        for (r, c) in CHEEK_LEFT | CHEEK_RIGHT:
            if 0 <= r < len(rows) and 0 <= c < len(rows[r]):
                if rows[r][c] == 'A':   # only paint over the gray face body
                    rows[r][c] = 'C'

    # ── Sleeping Zzz above the cat's head ────────────────────────────────────
    if mood == "sleeping":
        zzz_phase = (frame // 20) % 3
        # Place zzz above the cat's head (around column 13-15, starting from row 0)
        z_positions = [
            (0, 13),  # First z
            (0, 15),  # Second z (if phase >= 1)  
            (1, 14),  # Third z (if phase >= 2)
        ]
        for i in range(min(zzz_phase + 1, 3)):
            r, c = z_positions[i]
            if 0 <= r < len(rows) and 0 <= c < len(rows[r]):
                rows[r][c] = 'Z'

    # ── Tail wag ──────────────────────────────────────────────────────────────
    tail_phase = tail_frame % 4
    # Convert rows back to strings for tail manipulation (only top rows)
    str_rows = ["".join(r) for r in rows]

    if tail_phase == 1:
        str_rows[0] = str_rows[0][:24] + "KK.."
        str_rows[1] = str_rows[1][:23] + "GKAK."
    elif tail_phase == 2:
        str_rows[0] = str_rows[0][:25] + "K.."
        str_rows[1] = str_rows[1][:24] + "KAK."
    elif tail_phase == 3:
        str_rows[0] = str_rows[0][:26] + "K."
        str_rows[1] = str_rows[1][:25] + "KK."

    return str_rows


def render_mochi_sprite(mood: str, blinking: bool, frame: int, tail_frame: int = 0) -> tuple[list[str], int]:
    rows = get_cat_frame_data(mood, blinking, frame, tail_frame)
    lines = []
    for row in rows:
        parts = []
        for pixel in row:
            color = CAT_COLORS.get(pixel)
            if color:
                parts.append(f"{color} {RESET}")   # 1 space per pixel - smaller
            else:
                parts.append(" ")
        lines.append("".join(parts))
    return lines, CAT_SPRITE_WIDTH   # each pixel = 1 terminal col now




# ═══════════════════════════════════════════════════════════════════════════════
# HERO RENDERER - Simple centered cat
# ═══════════════════════════════════════════════════════════════════════════════

def render_hero_nyan(state: AppState, width: int, height: int) -> list[str]:
    """Render cat centered in the screen."""
    HERO_HEIGHT = min(20, max(16, height // 3))
    SPRITE_COLS = CAT_SPRITE_WIDTH
    SPRITE_ROWS = CAT_SPRITE_HEIGHT
    
    # Tail wag cadence
    if state.frame % 8 == 0:
        state.tail_frame = (state.tail_frame + 1) % 4
    
    # Cat positioning - center (with walking animation)
    cat_x = (width - SPRITE_COLS) // 2
    cat_y = (HERO_HEIGHT - SPRITE_ROWS) // 2
    
    now = time.time()
    blinking = now < state.blink_until
    
    # Walking animation
    if now < state.walk_until:
        # Calculate walk progress (0.0 to 1.0 over 3 seconds)
        walk_progress = 1.0 - (state.walk_until - now) / 3.0
        
        if walk_progress < 0.5:
            # First half: walk to the right
            state.walk_offset = int(walk_progress * 2 * 8)  # Move 8 units right (reduced from 20)
            state.walk_direction = 1
        else:
            # Second half: walk back to center
            reverse_progress = (walk_progress - 0.5) * 2
            state.walk_offset = int(8 * (1.0 - reverse_progress))  # Move back from 8 to 0
            state.walk_direction = -1
        
        cat_x += state.walk_offset
    else:
        # Walking finished, reset
        state.walk_offset = 0
    
    # Jump animation
    jump_offset = 0
    if now < state.jump_until:
        progress = (state.jump_until - now) / 0.4
        jump_offset = int(math.sin(progress * math.pi) * 3)
    
    sprite_lines, sw = render_mochi_sprite(state.mood, blinking, state.frame, state.tail_frame)
    
    output_lines = []
    
    # Top border
    output_lines.append(f"{fg(BORDER_COLOR)}{'─' * width}{RESET}")
    
    for row in range(HERO_HEIGHT):
        line_parts = []
        
        # Check if we should render sprite on this row
        sprite_row = row - cat_y + jump_offset
        if 0 <= sprite_row < len(sprite_lines):
            # Calculate left padding to position the cat
            sprite_line = sprite_lines[sprite_row]
            # Use visual width for positioning
            effective_cat_x = max(0, min(cat_x, width - sw))  # sw is visual sprite width
            left_pad = effective_cat_x
            right_pad = width - left_pad - sw  # Calculate based on visual width
            
            # Build the line: padding + sprite + padding
            # Don't add extra padding to compensate for ANSI codes
            line_parts.append(" " * left_pad)
            line_parts.append(sprite_line)
            if right_pad > 0:
                line_parts.append(" " * right_pad)
        else:
            # Empty row
            line_parts.append(" " * width)
        
        output_lines.append("".join(line_parts))
    
    # Bottom border
    output_lines.append(f"{fg(BORDER_COLOR)}{'─' * width}{RESET}")
    
    return output_lines

# ═══════════════════════════════════════════════════════════════════════════════
# REST OF RENDERING 
# ═══════════════════════════════════════════════════════════════════════════════

def render_status_line(state: AppState, width: int) -> str:
    total_agents = len(MOCK_AGENTS)
    hot_agents   = sum(1 for a in MOCK_AGENTS if a["status"] == "HOT")
    alert_count  = len(MOCK_ALERTS)
    total_tok    = sum(a["tok"] for a in MOCK_AGENTS)

    parts = [
        f"{fg(PINK)}{bold()}Mochi{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(TEXT_DIM)}{state.mode}{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(GREEN)}{bold()}{total_agents} agents{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(HOT)}{bold()}{hot_agents} hot{RESET}" if hot_agents else f"{fg(TEXT_DIM)}0 hot{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(HOT)}{alert_count} alert{RESET}" if alert_count else f"{fg(TEXT_DIM)}0 alerts{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(TEXT_DIM)}{total_tok} tok/min{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(TEXT_DIM)}{state.model_name}{RESET}",
        f"{fg(TEXT_DIM)}|{RESET}",
        f"{fg(GREEN)}d: dashboard{RESET}",
    ]
    return f"{bg(BG_SURFACE2)}{' '.join(parts)}{RESET}"


def render_welcome(width: int) -> list[str]:
    lines_text = [
        ("Hi, I'm Mochi.", PINK, True),
        ("I explain edge-agent behavior and optimization.", TEXT_DIM, False),
        ("Type /agents, /inspect camera-agent, or ask me anything.", TEXT_DIM, False),
        (f"Dashboard running at {DASHBOARD_URL}", GREEN, False),
    ]
    out = [""]
    for text, color, is_bold in lines_text:
        pad = (width - len(text)) // 2
        b = bold() if is_bold else ""
        out.append(f"{' ' * pad}{fg(color)}{b}{text}{RESET}")
    out.append("")
    return out


def render_divider(width: int) -> str:
    dots    = "·" * min(width - 4, 60)
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
            all_lines.extend(render_card(card_data, width - 4))
    return all_lines


def render_transcript(state: AppState, width: int, max_lines: int) -> list[str]:
    all_lines = expand_transcript_entries(state, width)
    total     = len(all_lines)
    scroll    = state.transcript_scroll
    if total <= max_lines - 1:
        visible = all_lines
    else:
        end   = total - scroll
        start = max(0, end - (max_lines - 1))
        end   = min(total, start + max_lines - 1)
        visible = all_lines[start:end]
    lines = visible.copy()
    if scroll > 0:
        lines.append(f"  {fg(TEXT_DIMMER)}↓ {scroll} more lines below (press ↓ or End){RESET}")
    elif total > max_lines - 1:
        lines.append(f"  {fg(TEXT_DIMMER)}─ {total} lines total ─{RESET}")
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
            sc   = HOT if agent["status"] == "HOT" else GREEN
            name = agent["name"][:16].ljust(16)
            st   = agent["status"].ljust(8)
            cpu  = f"{agent['cpu']}%".rjust(5)
            mem  = f"{agent['mem']}M".rjust(6)
            tok  = str(agent["tok"]).rjust(8)
            lat  = f"{agent.get('latency',0)}ms".rjust(8)
            opt  = agent.get("optimizer","none")[:12].ljust(12)
            lines.append(f"  {fg(TEXT_MAIN)}{name}{RESET} {fg(sc)}{st}{RESET} {fg(TEXT_DIM)}{cpu} {mem} {tok} {lat}{RESET} {fg(TEXT_DIM)}{opt}{RESET}")
        lines.append("")
    elif card_type == "detail":
        agent = card_data.get("agent", {})
        sc    = HOT if agent.get("status") == "HOT" else GREEN
        lines += [
            "",
            f"  {fg(PINK)}{bold()}Agent: {agent.get('name','Unknown')}{RESET}",
            f"  {fg(TEXT_DIM)}Status:{RESET}     {fg(sc)}{agent.get('status','OK')}{RESET}",
            f"  {fg(TEXT_DIM)}CPU:{RESET}        {fg(TEXT_MAIN)}{agent.get('cpu',0)}%{RESET}",
            f"  {fg(TEXT_DIM)}Memory:{RESET}     {fg(TEXT_MAIN)}{agent.get('mem',0)}MB{RESET}",
            f"  {fg(TEXT_DIM)}Temp:{RESET}       {fg(TEXT_MAIN)}{agent.get('temp',0)}C{RESET}",
            f"  {fg(TEXT_DIM)}Tokens/min:{RESET} {fg(TEXT_MAIN)}{agent.get('tok',0)}{RESET}",
            f"  {fg(TEXT_DIM)}Latency:{RESET}    {fg(TEXT_MAIN)}{agent.get('latency',0)}ms{RESET}",
            f"  {fg(TEXT_DIM)}Optimizer:{RESET}  {fg(TEXT_MAIN)}{agent.get('optimizer','none')}{RESET}",
            "",
        ]
    elif card_type == "summary":
        total       = len(MOCK_AGENTS)
        hot         = sum(1 for a in MOCK_AGENTS if a["status"] == "HOT")
        alerts      = len(MOCK_ALERTS)
        total_tok   = sum(a["tok"] for a in MOCK_AGENTS)
        avg_cpu     = sum(a["cpu"] for a in MOCK_AGENTS) // total
        most_active = max(MOCK_AGENTS, key=lambda a: a["tok"])
        lines += [
            "",
            f"  {fg(PINK)}{bold()}System Summary{RESET}",
            f"  {fg(TEXT_DIM)}Agents:{RESET}       {fg(GREEN)}{total}{RESET}",
            f"  {fg(TEXT_DIM)}Hot:{RESET}          {fg(HOT if hot else TEXT_DIM)}{hot}{RESET}",
            f"  {fg(TEXT_DIM)}Alerts:{RESET}       {fg(HOT if alerts else TEXT_DIM)}{alerts}{RESET}",
            f"  {fg(TEXT_DIM)}Total tok/min:{RESET} {fg(TEXT_MAIN)}{total_tok}{RESET}",
            f"  {fg(TEXT_DIM)}Avg CPU:{RESET}      {fg(TEXT_MAIN)}{avg_cpu}%{RESET}",
            f"  {fg(TEXT_DIM)}Most active:{RESET}  {fg(PINK)}{most_active['name']}{RESET}",
            f"  {fg(TEXT_DIM)}Last action:{RESET}  {fg(MINT)}prompt compression{RESET}",
            "",
        ]
    elif card_type == "alerts":
        lines.append("")
        lines.append(f"  {fg(PINK)}{bold()}Active Alerts{RESET}")
        for i, alert in enumerate(MOCK_ALERTS, 1):
            lines.append(f"  {fg(HOT)}{i}. {alert}{RESET}")
        lines.append("")
    elif card_type == "compare":
        agent = card_data.get("agent", {})
        lines += [
            "",
            f"  {fg(PINK)}{bold()}{agent.get('name','Unknown')} Optimization Compare{RESET}",
            f"  {fg(TEXT_DIM)}Before:{RESET} CPU 92% | Tokens 2450/min | Latency 610ms",
            f"  {fg(GREEN)}After:{RESET}  CPU {agent.get('cpu',85)}% | Tokens {agent.get('tok',1997)}/min | Latency {agent.get('latency',540)}ms",
            f"  {fg(MINT)}Savings: 7% CPU | 18% tokens | 11% latency{RESET}",
            "",
        ]
    elif card_type == "dashboard":
        lines += [
            "",
            f"  {fg(PINK)}{bold()}Dashboard{RESET}",
            f"  {fg(TEXT_DIM)}URL:{RESET} {fg(GREEN)}{DASHBOARD_URL}{RESET}",
            f"  {fg(TEXT_DIM)}Open in browser for charts and trends.{RESET}",
            "",
        ]
    return lines


def render_prompt(state: AppState, width: int) -> str:
    prompt = f"  {fg(GREEN)}{bold()}>{RESET} "
    if state.input_buffer:
        return f"{prompt}{fg(TEXT_MAIN)}{state.input_buffer}{RESET}"
    return f"{prompt}{fg(TEXT_DIMMER)}Ask Mochi or type /help{RESET}"


def render_hints(width: int) -> str:
    hints = [
        (f"{fg(GREEN)}{bold()}Enter{RESET}", f"{fg(TEXT_DIMMER)}send{RESET}"),
        (f"{fg(GREEN)}↑↓{RESET}",           f"{fg(TEXT_DIMMER)}scroll{RESET}"),
        (f"{fg(PINK)}W{RESET}",             f"{fg(TEXT_DIMMER)}walk{RESET}"),
        (f"{fg(PINK)}P{RESET}",             f"{fg(TEXT_DIMMER)}party{RESET}"),
        (f"{fg(PINK)}N{RESET}",             f"{fg(TEXT_DIMMER)}nap{RESET}"),
        (f"{fg(GREEN)}/agents{RESET}",      f"{fg(TEXT_DIMMER)}list{RESET}"),
        (f"{fg(GREEN)}/dashboard{RESET}",   f"{fg(TEXT_DIMMER)}open{RESET}"),
        (f"{fg(GREEN)}q{RESET}",            f"{fg(TEXT_DIMMER)}quit{RESET}"),
    ]
    parts = ["  "]
    for key, desc in hints:
        parts.append(f"{key} {desc}  ")
    return f"{bg(BG_SURFACE2)}{''.join(parts)}{RESET}"


def render_screen(state: AppState) -> str:
    rows, cols = get_terminal_size()
    output = []

    output.append(render_status_line(state, cols))
    output.extend(render_hero_nyan(state, cols, rows))
    output.extend(render_welcome(cols))
    output.append(render_divider(cols))
    output.append("")

    used_rows     = len(output) + 3
    transcript_rows = max(4, rows - used_rows)
    output.extend(render_transcript(state, cols, transcript_rows))
    output.append(render_prompt(state, cols))
    output.append(render_hints(cols))

    while len(output) < rows:
        output.append("")
    output = output[:rows]

    padded = [clear_line() + line for line in output]
    return "\033[H" + hide_cursor() + "\n".join(padded)


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMATION TRIGGERS - W, P, N keys
# ═══════════════════════════════════════════════════════════════════════════════

def trigger_walk(state: AppState) -> None:
    """W key - Trigger walking animation."""
    state.mood = "happy"
    state.mood_timer = 180  # Walk takes a bit less time
    state.walk_until = time.time() + 3.0  # 3 seconds walk (reduced from 4)
    state.walk_offset = 0
    state.walk_direction = 1

def trigger_party(state: AppState) -> None:
    """P key - Trigger party mood with jump."""
    state.mood = "celebrate"
    state.mood_timer = 90
    state.jump_until = time.time() + 0.4

def trigger_nap(state: AppState) -> None:
    """N key - Trigger sleep mode."""
    state.mood = "sleeping"
    state.mood_timer = 200


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
        state.transcript.append(("system", "·", "W=walk  P=party  N=nap  (hotkeys)", None))
        state.mood = "happy"; state.mood_timer = 90
    elif cmd_lower == "/agents":
        state.transcript.append(("mochi", "Mochi", "Here are your agents:",
                                  {"type": "roster", "agents": MOCK_AGENTS}))
        state.mood = "thinking"; state.mood_timer = 60
    elif cmd_lower.startswith("/inspect"):
        parts = cmd.split(maxsplit=1)
        if len(parts) > 1:
            name  = parts[1].lower()
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
        state.transcript.append(("mochi", "Mochi", "Most pressure is coming from camera-agent.", None))
        state.mood = "warning"; state.mood_timer = 100
    elif cmd_lower == "/summary":
        state.transcript.append(("mochi", "Mochi", "Here's the latest system summary:",
                                  {"type": "summary"}))
        state.mood = "celebrate"; state.mood_timer = 90
    elif cmd_lower.startswith("/compare"):
        parts = cmd.split(maxsplit=1)
        if len(parts) > 1:
            name  = parts[1].lower()
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
        import webbrowser, urllib.request
        state.transcript.append(("mochi", "Mochi", "Opening dashboard...", None))
        try:
            r = urllib.request.urlopen(DASHBOARD_URL, timeout=2)
            if r.code == 200:
                state.transcript.append(("ok", "ok", "Dashboard already running!", None))
                webbrowser.open(DASHBOARD_URL)
        except:
            state.transcript.append(("warning", "alert",
                                      "Dashboard not reachable. Try ./start_dashboard_bg.sh", None))
        state.transcript.append(("mochi", "Mochi", "Dashboard shows charts and trends!",
                                  {"type": "dashboard"}))
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
        state.transcript.append(("mochi", "Mochi",
                                  "Optimizer already reduced waste from Camera Vision!", None))
        state.transcript.append(("ok", "ok",
                                  "Prompt compression saved 38% tokens in the last run.", None))
        state.mood = "celebrate"; state.mood_timer = 90
    elif re.search(r"hello|hi|hey", text_lower):
        state.transcript.append(("mochi", "Mochi",
                                  "Hello! I'm here to help you understand your edge agents. ✦", None))
        state.mood = "happy"; state.mood_timer = 90
    elif re.search(r"dashboard|web|browser", text_lower):
        state.transcript.append(("mochi", "Mochi", "Here's your dashboard link:",
                                  {"type": "dashboard"}))
        state.mood = "happy"; state.mood_timer = 60
    else:
        state.transcript.append(("mochi", "Mochi",
                                  "I'm not sure about that. Try /help for available commands.", None))
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
        self._select   = select
        self._termios  = termios
        self._stdin_fd = sys.stdin.fileno()
        self._old      = termios.tcgetattr(self._stdin_fd)
        tty.setcbreak(self._stdin_fd)
        return self

    def __exit__(self, *args):
        if os.name != "nt":
            self._termios.tcsetattr(self._stdin_fd, self._termios.TCSADRAIN, self._old)

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

    import signal
    def handle_resize(signum, frame):
        pass
    if hasattr(signal, 'SIGWINCH'):
        signal.signal(signal.SIGWINCH, handle_resize)

    state.transcript.append(("system", "[system]", "Terminal session started.", None))
    state.transcript.append(("system", "[system]",
                              f"Dashboard: {DASHBOARD_URL} (use /dashboard to start)", None))

    tick_interval = 0.033   # ~30 fps
    last_render   = 0.0
    last_size     = (0, 0)

    sys.stdout.write(enter_alt_screen() + clear_screen())
    sys.stdout.flush()

    try:
        with KeyReader() as reader:
            while state.running:
                now          = time.time()
                current_size = get_terminal_size()
                if current_size != last_size:
                    last_render = 0
                    last_size   = current_size

                state.frame += 1

                # Random blink
                if random.random() < 0.015 and now > state.blink_until:
                    state.blink_until = now + 0.18

                # Mood timer countdown
                if state.mood_timer > 0:
                    state.mood_timer -= 1
                    if state.mood_timer == 0:
                        state.mood = "idle"

                # ── Key handling ──────────────────────────────────────────────
                key = reader.read_key()
                if key:
                    # Global quit
                    if key == "\x03" or (key == "q" and not state.input_buffer):
                        state.running = False

                    # ── Animation hotkeys (only when input buffer is empty) ───────
                    elif key.lower() == "w" and not state.input_buffer:
                        trigger_walk(state)

                    elif key.lower() == "p" and not state.input_buffer:
                        trigger_party(state)

                    elif key.lower() == "n" and not state.input_buffer:
                        trigger_nap(state)

                    # ── Normal text input ────────────────────────────────────
                    elif key in ("\r", "\n"):
                        if state.input_buffer.strip():
                            handle_input(state, state.input_buffer.strip())
                            state.transcript_scroll = 0
                            state.input_buffer = ""

                    elif key in ("\x7f", "\b"):
                        state.input_buffer = state.input_buffer[:-1]

                    elif key == "\x1b":
                        time.sleep(0.01)
                        nk = reader.read_key()
                        if nk == "[":
                            ak = reader.read_key()
                            if ak == "A":   # up arrow — scroll up
                                r, c = get_terminal_size()
                                used  = 1 + 16 + 5 + 2 + 3
                                trows = max(4, r - used)
                                total = len(expand_transcript_entries(state, c))
                                mx    = max(0, total - trows + 1)
                                state.transcript_scroll = min(state.transcript_scroll + 3, mx)
                            elif ak == "B":  # down arrow — scroll down
                                state.transcript_scroll = max(0, state.transcript_scroll - 3)
                            elif ak == "F":  # End key
                                state.transcript_scroll = 0
                        else:
                            state.input_buffer = ""

                    elif key.isprintable():
                        state.input_buffer += key

                # ── Render ────────────────────────────────────────────────────
                if now - last_render > tick_interval:
                    sys.stdout.write(render_screen(state))
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