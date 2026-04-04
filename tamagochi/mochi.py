import os
import random
import sys
import time
from dataclasses import dataclass

TICK_SECONDS = 0.12
DECAY_SECONDS = 1.2


@dataclass
class MochiState:
    affection: int = 58
    fullness: int = 62
    energy: int = 72
    fun: int = 55
    hygiene: int = 85
    health: int = 84
    discipline: int = 60
    weight: int = 16
    poop: int = 0
    age_ticks: int = 0
    sick: bool = False
    sleeping: bool = False
    alive: bool = True
    jump_until: float = 0.0
    blink_until: float = 0.0


def clear_screen() -> None:
    sys.stdout.write("\033[H\033[J")
    sys.stdout.flush()


def clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


def pet_age_label(age_ticks: int) -> str:
    hours = age_ticks // 20
    days = hours // 24
    rem_hours = hours % 24
    return f"day {days}  {rem_hours:02d}:00"


def mood(state: MochiState) -> str:
    if not state.alive:
        return "gone"
    if state.sick:
        return "sick"
    if state.sleeping:
        return "sleeping"
    if state.fullness < 25:
        return "hungry"
    if state.hygiene < 30 or state.poop >= 3:
        return "gross"
    if state.energy < 25:
        return "sleepy"
    if state.fun > 75 and state.affection > 70:
        return "excited"
    return "happy"


def bar(label: str, value: int, width: int = 22) -> str:
    filled = round((value / 100) * width)
    return f"{label:<10}[{'#' * filled}{'-' * (width - filled)}] {value:>3}%"


RESET = "\033[0m"


def pixel(code: str) -> str:
    return f"\033[{code}m  "


def sprite_rows(current_mood: str, blinking: bool, state: MochiState) -> list[str]:
    left_eye = "D"  # normal  " O"
    right_eye = "d"  #         "O "
    mouth = "M"
    body = "B"
    shine = "P"
    cheek = "C"
    arms = "A"

    if current_mood in ("sleeping", "sleepy") or blinking:
        left_eye = "L"  # closed  "--"
        right_eye = "l"  #         "--"
    if current_mood == "excited":
        left_eye = "H"  # happy   " >"
        right_eye = "h"  #         "< "
    if current_mood == "hungry":
        mouth = "W"
    if current_mood == "sick":
        left_eye = "S"  # sick    " @"
        right_eye = "s"  #         "@ "
        body = "Q"
    if current_mood == "gone":
        left_eye = "Y"  # dead    " X"
        right_eye = "y"  #         "X "
        mouth = "X"
        body = "G"
        shine = "G"
        cheek = "G"
        arms = "G"

    # 16-wide round frog sprite
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
    # (ansi_codes, display_chars)
    # Eyes render ASCII glyphs; everything else uses background blocks.
    cells = {
        ".": ("", "  "),
        # body
        "B": ("48;5;114", "  "),
        "Q": ("48;5;108", "  "),
        "G": ("48;5;240", "  "),
        # head details
        "P": ("48;5;231", "  "),
        "C": ("48;5;217", "  "),
        # left eye
        "D": ("1;38;5;232;48;5;114", " O"),  # normal
        "H": ("1;38;5;232;48;5;114", " >"),  # excited
        "L": ("38;5;65;48;5;114", "--"),  # sleeping / blink
        "S": ("1;38;5;161;48;5;108", " @"),  # sick
        "Y": ("1;38;5;52;48;5;240", " X"),  # dead
        # right eye
        "d": ("1;38;5;232;48;5;114", "O "),  # normal
        "h": ("1;38;5;232;48;5;114", "< "),  # excited
        "l": ("38;5;65;48;5;114", "--"),  # sleeping / blink
        "s": ("1;38;5;161;48;5;108", "@ "),  # sick
        "y": ("1;38;5;52;48;5;240", "X "),  # dead
        # mouth
        "M": ("48;5;210", "  "),
        "W": ("48;5;203", "  "),
        "J": ("48;5;196", "  "),
        "X": ("48;5;236", "  "),
        # limbs
        "A": ("48;5;228", "  "),
    }

    lines = []
    for row in rows:
        out = []
        for cell in row:
            code, chars = cells[cell]
            if code:
                out.append(f"\033[{code}m{chars}")
            else:
                out.append(f"{RESET}  ")
        lines.append("".join(out) + RESET)
    return lines


def render(state: MochiState, show_help: bool, last_event: str) -> None:
    now = time.time()
    current_mood = mood(state)
    jumping = now < state.jump_until and state.alive and not state.sleeping
    blinking = now < state.blink_until
    pad = "   " if jumping else " "
    sprite = colorize_sprite(sprite_rows(current_mood, blinking, state))

    lines = [
        "Mochi - Realistic Tamagotchi Mode",
        "=" * 42,
        *(f"{pad}{line}" for line in sprite),
        "",
        f"age       : {pet_age_label(state.age_ticks)}",
        f"mood      : {current_mood}",
        f"condition : {'SICK' if state.sick else 'stable'} | poop: {state.poop} | weight: {state.weight}",
        bar("health", state.health),
        bar("energy", state.energy),
        bar("fullness", state.fullness),
        bar("fun", state.fun),
        bar("hygiene", state.hygiene),
        bar("love", state.affection),
        bar("discipline", state.discipline),
        "",
        f"last event: {last_event}",
    ]

    if show_help:
        lines += [
            "",
            "controls",
            "  p pet   f feed   t treat   g game   c clean",
            "  n nap   m medicine   j jump   h help   q quit",
        ]

    sys.stdout.write("\033[H\033[J" + "\n".join(lines) + "\n")
    sys.stdout.flush()


class KeyReader:
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

    def read_key(self):
        if os.name == "nt":
            if self._msvcrt.kbhit():
                key = self._msvcrt.getwch()
                if key in ("\x00", "\xe0"):
                    self._msvcrt.getwch()
                    return None
                return key.lower()
            return None

        ready, _, _ = self._select.select([sys.stdin], [], [], 0)
        if ready:
            return sys.stdin.read(1).lower()
        return None


def passive_decay(state: MochiState) -> str | None:
    state.age_ticks += 1

    if state.sleeping:
        state.energy = clamp(state.energy + 2)
        state.fullness = clamp(state.fullness - 1)
        state.fun = clamp(state.fun - 1)
        if state.energy >= 100:
            state.sleeping = False
            return "Mochi woke up fully rested!"
    else:
        state.energy = clamp(state.energy - 1)
        state.fullness = clamp(state.fullness - 2)
        state.fun = clamp(state.fun - 1)

    if state.poop > 0:
        state.hygiene = clamp(state.hygiene - state.poop)
    else:
        state.hygiene = clamp(state.hygiene - 1)

    state.affection = clamp(state.affection - 1)
    state.discipline = clamp(state.discipline - 1)

    if random.random() < 0.15 + max(0, state.fullness - 70) / 180:
        state.poop = min(5, state.poop + 1)
        return "Mochi made a tiny mess."

    risk = 0.0
    if state.hygiene < 35:
        risk += 0.08
    if state.fullness < 20:
        risk += 0.05
    if state.energy < 15:
        risk += 0.05
    if state.poop >= 3:
        risk += 0.10
    if random.random() < risk:
        state.sick = True

    if state.sick:
        state.health = clamp(state.health - 2)
    if state.fullness <= 5 or state.energy <= 5:
        state.health = clamp(state.health - 2)
    if state.hygiene < 20:
        state.health = clamp(state.health - 1)

    if state.sleeping and not state.sick and state.hygiene > 60 and state.fullness > 35:
        state.health = clamp(state.health + 1)

    if state.health <= 0:
        state.alive = False
        return "Mochi faded away from neglect..."

    return None


def handle_action(state: MochiState, key: str, now: float) -> str | None:
    if key == "p":
        state.affection = clamp(state.affection + 8)
        state.fun = clamp(state.fun + 3)
        state.energy = clamp(state.energy - 1)
        return "You pet Mochi. Soft squish noises."

    if key == "f":
        state.fullness = clamp(state.fullness + 18)
        state.weight = min(35, state.weight + 1)
        state.energy = clamp(state.energy + 2)
        if state.fullness > 90:
            state.health = clamp(state.health - 1)
            return "Overfed a bit. Mochi is stuffed and wobbly."
        return "Mochi had a nice meal."

    if key == "t":
        state.fullness = clamp(state.fullness + 8)
        state.fun = clamp(state.fun + 5)
        state.discipline = clamp(state.discipline - 2)
        state.weight = min(35, state.weight + 1)
        return "Sweet treat delivered. Mochi is thrilled."

    if key == "g":
        if state.sleeping:
            return "Mochi is sleeping. Games can wait."
        state.fun = clamp(state.fun + 18)
        state.affection = clamp(state.affection + 6)
        state.energy = clamp(state.energy - 7)
        state.fullness = clamp(state.fullness - 4)
        state.jump_until = now + 0.22
        return "Playtime! Mochi zoomed in circles."

    if key == "c":
        if state.poop == 0:
            return "Already clean. Mochi smells like vanilla mochi."
        removed = state.poop
        state.poop = 0
        state.hygiene = clamp(state.hygiene + 20 + removed * 5)
        state.affection = clamp(state.affection + 4)
        return "Cleanup complete. Fresh and cozy again."

    if key == "n":
        state.sleeping = not state.sleeping
        if state.sleeping:
            return "Mochi curled up for sleep."
        return "Mochi woke up and stretched."

    if key == "m":
        if not state.sick:
            state.discipline = clamp(state.discipline + 1)
            return "No medicine needed right now."
        state.sick = False
        state.health = clamp(state.health + 12)
        state.affection = clamp(state.affection - 2)
        return "Medicine worked. Mochi feels better."

    if key == "j":
        if state.sleeping:
            return "Shh... Mochi is asleep."
        state.jump_until = now + 0.20
        state.fun = clamp(state.fun + 4)
        state.energy = clamp(state.energy - 4)
        return "Boing! Mochi jumped."

    return None


def main() -> None:
    state = MochiState()
    show_help = True
    last_event = "Mochi hatched. Keep it alive and thriving."
    last_decay = time.time()

    with KeyReader() as reader:
        dirty = True
        while True:
            now = time.time()

            if random.random() < 0.04:
                state.blink_until = now + 0.16
                dirty = True

            if state.alive and (now - last_decay) >= DECAY_SECONDS:
                decay_event = passive_decay(state)
                last_decay = now
                dirty = True
                if decay_event:
                    last_event = decay_event

            key = reader.read_key()
            if key:
                dirty = True
                if key == "q":
                    clear_screen()
                    print("Mochi says bye bye.")
                    break

                if key == "h":
                    show_help = not show_help
                    last_event = "Toggled help."
                elif state.alive:
                    action_event = handle_action(state, key, now)
                    if action_event:
                        last_event = action_event

            if now >= state.jump_until and now < state.jump_until + TICK_SECONDS:
                dirty = True
            if now >= state.blink_until and now < state.blink_until + TICK_SECONDS:
                dirty = True

            if dirty:
                render(state, show_help, last_event)
                dirty = False

            time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        clear_screen()
        print("Mochi got interrupted but still loves you.")
