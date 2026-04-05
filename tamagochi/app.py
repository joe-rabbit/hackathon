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
import json
import glob
import urllib.request
import urllib.parse
from types import SimpleNamespace
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

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

# Optimize policy constants for O hotkey
CO2_THRESHOLD_KG = 0.5
GRID_KG_CO2E_PER_KWH = 0.384
WH_PER_500_TOKENS = 15.0
AUTO_OPTIMIZE_INTERVAL_S = 30.0
AUTO_OPTIMIZE_COOLDOWN_S = 90.0

RAINBOW_COLORS = ["196", "208", "226", "46", "27", "57", "129"]
SPARKLE_CHARS = ["✦", "✧", "★", "☆", "·", "✸", "✺", "⋆", "*"]

TOKEN_KEY_SETS = (
    ("promptTokens", "completionTokens", "totalTokens"),
    ("prompt_tokens", "completion_tokens", "total_tokens"),
    ("inputTokens", "outputTokens", "totalTokens"),
    ("input_tokens", "output_tokens", "total_tokens"),
)

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
    next_auto_optimize_check: float = 0.0
    auto_optimize_cooldown_until: float = 0.0


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


def load_cat_from_css(html_path=None):
    """Parse CSS box-shadow and return pixel dict."""
    if html_path is None:
        html_path = os.path.join(os.path.dirname(__file__), 'cat.html')
    try:
        with open(html_path, 'r') as f:
            html = f.read()
    except Exception:
        return {}
    
    match = re.search(r'box-shadow:\s*(.*?);', html, re.DOTALL)
    if not match:
        return {}
    box_shadow = match.group(1)
    
    pattern = r'(\d+)px\s+(\d+)px\s+(#[0-9a-fA-F]+|rgb\([^)]+\)|transparent|white)'
    matches = re.findall(pattern, box_shadow)
    
    pixels = {}
    for x_str, y_str, color in matches:
        x, y = int(x_str), int(y_str)
        
        if color == 'transparent':
            continue
        elif color == 'white':
            r, g, b = 255, 255, 255
        elif color.startswith('#'):
            color = color.lstrip('#')
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
        elif color.startswith('rgb'):
            nums = re.findall(r'\d+', color)
            r, g, b = int(nums[0]), int(nums[1]), int(nums[2])
        else:
            continue
        
        if y not in pixels:
            pixels[y] = {}
        pixels[y][x] = (r, g, b)
    
    return pixels

_CSS_PIXELS = None

# Mochi Animation Overrides
_C = (220, 130, 150) # rosy cheek pink
_H = (220, 40, 40)   # heart red
_Z = (130, 170, 230) # zzz blue
_S = (40,  40,  40)  # closed-eye dark gray

EYE_L = {(8,11),(8,12),(9,11),(9,12),(9,13),(10,11),(10,12)}
EYE_R = {(8,21),(9,20),(9,21),(9,22),(10,20),(10,21)}
CHEEK_L = {(12,9),(13,9),(13,10)}
CHEEK_R = {(12,26),(13,25),(13,26)}

def render_mochi_sprite(mood: str, blinking: bool, frame: int, tail_frame: int = 0) -> tuple[list[str], int]:
    global _CSS_PIXELS
    if _CSS_PIXELS is None:
        _CSS_PIXELS = load_cat_from_css()
    
    pixels = _CSS_PIXELS
    if not pixels:
        return ["  Cat HTML not found  "], 20

    max_y = max(pixels.keys()) if pixels else 0
    max_x = max(max(row.keys()) for row in pixels.values()) if pixels else 0
    
    # ── MUTATE PIXELS FOR ANIMATION ──
    rendered_pixels = {}
    for y in range(max_y + 1):
        rendered_pixels[y] = {}
        if y in pixels:
            for x in pixels[y]:
                rendered_pixels[y][x] = pixels[y][x]
    
    # Eyes
    if blinking or mood in ("sleepy", "sleeping", "sad"):
        eye_color = _S
    elif mood in ("excited", "celebrate"):
        eye_color = _H
    else:
        eye_color = (255, 255, 255)
        
    for r, c in EYE_L | EYE_R:
        if r in rendered_pixels and c in rendered_pixels[r]:
            if rendered_pixels[r][c] == (255, 255, 255):
                rendered_pixels[r][c] = eye_color

    # Cheeks
    if mood in ("happy", "celebrate", "excited", "pet", "treat"):
        for r, c in CHEEK_L | CHEEK_R:
            if r in rendered_pixels and c in rendered_pixels[r]:
                if rendered_pixels[r][c] not in ((255, 255, 255), (0, 0, 0)):
                    rendered_pixels[r][c] = _C

    # Sleeping Zzz
    if mood == "sleeping":
        zzz_phase = (frame // 20) % 4
        zzz_pos = [(0, 9), (1, 7), (2, 5)]
        for i in range(min(zzz_phase, 3)):
            r, c = zzz_pos[i]
            if r not in rendered_pixels: rendered_pixels[r] = {}
            rendered_pixels[r][c] = _Z
            
    # ── RENDER WITH HALF-BLOCKS ──
    lines = []
    for y in range(0, max_y + 1, 2):
        line = ""
        for x in range(max_x + 1):
            top_p = rendered_pixels.get(y, {}).get(x)
            bot_p = rendered_pixels.get(y + 1, {}).get(x)
            
            if top_p and bot_p:
                tr, tg, tb = top_p
                br, bg, bb = bot_p
                line += f"\033[38;2;{tr};{tg};{tb}m\033[48;2;{br};{bg};{bb}m▀\033[0m"
            elif top_p:
                tr, tg, tb = top_p
                line += f"\033[38;2;{tr};{tg};{tb}m▀\033[0m"
            elif bot_p:
                br, bg, bb = bot_p
                line += f"\033[38;2;{br};{bg};{bb}m▄\033[0m"
            else:
                line += " "
        lines.append(line)
    
    return lines, max_x + 1





# ═══════════════════════════════════════════════════════════════════════════════
# HERO RENDERER - Simple centered cat
# ═══════════════════════════════════════════════════════════════════════════════

def render_hero_nyan(state: AppState, width: int, height: int) -> list[str]:
    """Render cat centered in the screen."""
    now = time.time()
    blinking = now < state.blink_until

    # Tail wag cadence
    if state.frame % 8 == 0:
        state.tail_frame = (state.tail_frame + 1) % 4

    sprite_lines, sw = render_mochi_sprite(state.mood, blinking, state.frame, state.tail_frame)
    
    SPRITE_COLS = sw
    SPRITE_ROWS = len(sprite_lines)
    HERO_HEIGHT = max(SPRITE_ROWS + 6, min(30, height // 3))
    
    # Cat positioning - center (with walking animation)
    cat_x = (width - SPRITE_COLS) // 2
    cat_y = (HERO_HEIGHT - SPRITE_ROWS) // 2
    
    # Walking animation
    if now < state.walk_until:
        # Calculate walk progress (0.0 to 1.0 over 3 seconds)
        walk_progress = 1.0 - (state.walk_until - now) / 3.0
        
        if walk_progress < 0.5:
            state.walk_offset = int(walk_progress * 2 * 8)
            state.walk_direction = 1
        else:
            reverse_progress = (walk_progress - 0.5) * 2
            state.walk_offset = int(8 * (1.0 - reverse_progress))
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
            effective_cat_x = max(0, min(cat_x, width - sw))
            left_pad = effective_cat_x
            right_pad = max(0, width - left_pad - sw)
            
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
        (f"{fg(PINK)}O{RESET}",             f"{fg(TEXT_DIMMER)}optimize{RESET}"),
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


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _tokens_from_node(node) -> int:
    if isinstance(node, dict):
        for prompt_key, completion_key, total_key in TOKEN_KEY_SETS:
            if total_key in node:
                return _safe_int(node.get(total_key), 0)
            if prompt_key in node and completion_key in node:
                return _safe_int(node.get(prompt_key), 0) + _safe_int(node.get(completion_key), 0)

        subtotal = 0
        for value in node.values():
            subtotal += _tokens_from_node(value)
        return subtotal

    if isinstance(node, list):
        subtotal = 0
        for item in node:
            subtotal += _tokens_from_node(item)
        return subtotal

    return 0


def _tail_jsonl_records(path: Path, max_lines: int = 250) -> list[dict]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception:
        return []

    records = []
    for line in lines[-max_lines:]:
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def _estimate_kg_from_tokens(total_tokens: int) -> float:
    watt_hours = (max(total_tokens, 0) / 500.0) * WH_PER_500_TOKENS
    return (watt_hours / 1000.0) * GRID_KG_CO2E_PER_KWH


def get_latest_copilot_emission_kg() -> tuple[float, int, str]:
    """Get latest CO2 estimate via dashboard token analyzer from VS Code user logs."""
    try:
        from dashboard import agent_token_analyszer as token_analyzer

        workspace_storage_root = Path.home() / ".config" / "Code" / "User" / "workspaceStorage"
        analyzer_args = SimpleNamespace(
            session_file=[],
            sessions_dir=None,
            workspace_storage_root=workspace_storage_root,
        )
        session_files = token_analyzer.discover_session_files(analyzer_args)
        if not session_files:
            return 0.0, 0, "none"

        summary, _ = token_analyzer.summarize(session_files)
        totals = token_analyzer.aggregate_totals(summary)
        if totals.total_tokens <= 0:
            return 0.0, 0, "none"

        _, energy_kwh = token_analyzer.compute_energy(totals.total_tokens, WH_PER_500_TOKENS)
        co2_kg = energy_kwh * GRID_KG_CO2E_PER_KWH
        return co2_kg, totals.total_tokens, "token_analyzer"
    except Exception:
        # Fallback to direct session payload parsing from VS Code user logs.
        chat_glob = os.path.expanduser("~/.config/Code/User/workspaceStorage/*/chatSessions/*.jsonl")
        chat_files = [Path(p) for p in glob.glob(chat_glob)]
        chat_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for session_file in chat_files[:5]:
            session_records = _tail_jsonl_records(session_file, max_lines=400)
            for record in reversed(session_records):
                total_tokens = _tokens_from_node(record)
                if total_tokens > 0:
                    return _estimate_kg_from_tokens(total_tokens), total_tokens, "vscode_chat_sessions"

    return 0.0, 0, "none"


def trigger_optimize(state: AppState) -> None:
    """O key - walk first, then branch to nap/party by CO2 threshold."""
    trigger_walk(state)
    co2_kg, total_tokens, source = get_latest_copilot_emission_kg()

    if source == "none":
        trigger_party(state)
        state.transcript.append((
            "warning",
            "optimize",
            "Optimize: no Copilot usage logs found, defaulting to WALK -> PARTY.",
            None,
        ))
        return

    if co2_kg >= CO2_THRESHOLD_KG:
        trigger_nap(state)
        state.transcript.append((
            "warning",
            "optimize",
            f"Optimize: WALK -> NAP (CO2={co2_kg:.4f}kg, tokens={total_tokens}, source={source}).",
            None,
        ))
    else:
        trigger_party(state)
        state.transcript.append((
            "ok",
            "optimize",
            f"Optimize: WALK -> PARTY (CO2={co2_kg:.4f}kg, tokens={total_tokens}, source={source}).",
            None,
        ))


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
        state.transcript.append(("system", "·", "W=walk  O=optimize  P=party  N=nap  (hotkeys)", None))
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


def call_ollama(model: str, prompt: str, system_prompt: str = None) -> str:
    """Call Ollama API to get LLM response."""
    try:
        ollama_base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        url = f"{ollama_base_url}/api/generate"
        data = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        if system_prompt:
            data["system"] = system_prompt
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('response', '').strip()
    except urllib.error.URLError:
        return "✦ Ollama API is not reachable. Check OLLAMA_HOST or start Ollama on the host."
    except TimeoutError:
        return "✦ LLM is loading... please try again in a moment."
    except Exception as e:
        return f"✦ Error: {str(e)[:100]}"


def handle_natural_language(state: AppState, text: str) -> None:
    """Handle natural language input using Gemma3 LLM."""
    
    # System prompt for Mochii's personality - cute but precise
    system_prompt = """You are Mochii, a cute AI assistant for edge-agent monitoring.
Be direct and specific. Answer in 1-2 sentences max.
No fluff, no emojis. Just the facts, cutely stated.
Your name is Mochii (two i's).
Focus: agents, tokens, performance, optimization."""
    
    # Add context
    agent_context = f"\n\nCurrent agents: {', '.join(a['name'] for a in MOCK_AGENTS)}"
    full_prompt = text + agent_context
    
    # Show thinking state
    state.mood = "thinking"
    state.mood_timer = 30
    
    # Call Ollama/Gemma3
    response = call_ollama(state.model_name, full_prompt, system_prompt)
    
    # Add response to transcript
    state.transcript.append(("mochi", "Mochii", response, None))
    
    # Set mood based on response sentiment
    if any(word in response.lower() for word in ["great", "excellent", "perfect", "good", "nice", "optimized", "efficient"]):
        state.mood = "happy"
        state.mood_timer = 90
    elif any(word in response.lower() for word in ["warning", "hot", "high", "issue", "problem", "concern"]):
        state.mood = "warning"
        state.mood_timer = 100
    elif any(word in response.lower() for word in ["success", "improved", "reduced", "saved"]):
        state.mood = "celebrate"
        state.mood_timer = 90
    else:
        state.mood = "idle"
        state.mood_timer = 60


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

                # Auto-optimize when emissions cross threshold.
                if now >= state.next_auto_optimize_check and now >= state.auto_optimize_cooldown_until:
                    state.next_auto_optimize_check = now + AUTO_OPTIMIZE_INTERVAL_S
                    co2_kg, total_tokens, source = get_latest_copilot_emission_kg()
                    if source != "none" and co2_kg >= CO2_THRESHOLD_KG:
                        trigger_optimize(state)
                        state.auto_optimize_cooldown_until = now + AUTO_OPTIMIZE_COOLDOWN_S
                        state.transcript.append((
                            "warning",
                            "optimize",
                            f"Auto optimize triggered: CO2={co2_kg:.3f}kg (tokens={total_tokens}) >= {CO2_THRESHOLD_KG:.3f}kg.",
                            None,
                        ))

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

                    elif key.lower() == "o" and not state.input_buffer:
                        trigger_optimize(state)

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