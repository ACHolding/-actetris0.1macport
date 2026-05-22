#!/usr/bin/env python3
"""ac's tetris 0.1.1 — Famicom rules @ 60 FPS + Korobeiniki (math.sin, FILES=OFF)."""
from __future__ import annotations

import array
import math
import random
import sys

import pygame

# ==================== Configuration ====================
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 640
GRID_WIDTH = 10
GRID_HEIGHT = 20
CELL_SIZE = 28
PLAY_WIDTH = GRID_WIDTH * CELL_SIZE
PLAY_HEIGHT = GRID_HEIGHT * CELL_SIZE
TOP_LEFT_X = (SCREEN_WIDTH - PLAY_WIDTH) // 2
TOP_LEFT_Y = 40
HUD_X = 12

# Famicom (NES) Tetris @ 60 FPS (NTSC hardware is ~60.098Hz; one tick = one frame)
FAMICOM_FPS = 60
FPS = FAMICOM_FPS

# Frames per row — Famicom / NES NTSC Timing Table
FAMICOM_GRAVITY_FRAMES = (
    48, 43, 38, 33, 28, 23, 18, 13, 8, 6,
    5, 5, 5, 4, 4, 4, 3, 3, 3, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 1
)
# Famicom DAS values: 16 frames initialization, repeating every 6 frames
FAMICOM_DAS_DELAY = 16
FAMICOM_DAS_REPEAT = 6
FAMICOM_ARE_FRAMES = 10  # Famicom has a longer entry delay (10-18f depending on height)
FAMICOM_LINE_CLEAR_FRAMES = 20 # Strikingly faster animation delay than GB's 93f!
SPEED_MODE = "FAMICOM"


def famicom_drop_frames(level: int) -> int:
    lv = min(max(level, 0), len(FAMICOM_GRAVITY_FRAMES) - 1)
    return FAMICOM_GRAVITY_FRAMES[lv]


def famicom_soft_drop_frames(level: int) -> int:
    """Famicom soft drop forces a drop every 1/2G or every 1 frame if pressed."""
    return 1

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (80, 80, 80)
CYAN = (0, 255, 255)
BLUE = (0, 120, 255)
ORANGE = (255, 165, 0)
YELLOW = (255, 255, 0)
GREEN = (0, 220, 0)
PURPLE = (180, 0, 255)
RED = (255, 0, 0)
COLORS = [CYAN, YELLOW, PURPLE, GREEN, BLUE, ORANGE, RED]

# Four rotation states per piece (I, O, T, J, L, S, Z)
SHAPES: list[list[list[list[int]]]] = [
    [  # I
        [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
        [[0, 0, 1, 0], [0, 0, 1, 0], [0, 0, 1, 0], [0, 0, 1, 0]],
        [[0, 0, 0, 0], [0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0]],
        [[0, 1, 0, 0], [0, 1, 0, 0], [0, 1, 0, 0], [0, 1, 0, 0]],
    ],
    [[[1, 1], [1, 1]]],  # O
    [  # T
        [[0, 1, 0], [1, 1, 1], [0, 0, 0]],
        [[0, 1, 0], [0, 1, 1], [0, 1, 0]],
        [[0, 0, 0], [1, 1, 1], [0, 1, 0]],
        [[0, 1, 0], [1, 1, 0], [0, 1, 0]],
    ],
    [  # J
        [[1, 0, 0], [1, 1, 1], [0, 0, 0]],
        [[0, 1, 1], [0, 1, 0], [0, 1, 0]],
        [[0, 0, 0], [1, 1, 1], [0, 0, 1]],
        [[0, 1, 0], [0, 1, 0], [1, 1, 0]],
    ],
    [  # L
        [[0, 0, 1], [1, 1, 1], [0, 0, 0]],
        [[0, 1, 0], [0, 1, 0], [0, 1, 1]],
        [[0, 0, 0], [1, 1, 1], [1, 0, 0]],
        [[1, 1, 0], [0, 1, 0], [0, 1, 0]],
    ],
    [  # S
        [[0, 1, 1], [1, 1, 0], [0, 0, 0]],
        [[0, 1, 0], [0, 1, 1], [0, 0, 1]],
        [[0, 0, 0], [0, 1, 1], [1, 1, 0]],
        [[1, 0, 0], [1, 1, 0], [0, 1, 0]],
    ],
    [  # Z
        [[1, 1, 0], [0, 1, 1], [0, 0, 0]],
        [[0, 0, 1], [0, 1, 1], [0, 1, 0]],
        [[0, 0, 0], [1, 1, 0], [0, 1, 1]],
        [[0, 1, 0], [1, 1, 0], [1, 0, 0]],
    ],
]

SCORE_TABLE = {1: 40, 2: 100, 3: 300, 4: 1200}

# --- Korobeiniki Synthesizer Settings ---
_SAMPLE_RATE = 22050
_FAMICOM_BPM = 150
_TICK_SEC = 60.0 / _FAMICOM_BPM / 4.0

_NAME_MIDI: dict[str, int] = {
    "E3": 52, "G#3": 56, "A3": 57, "B3": 59, "C4": 60, "D4": 62, "E4": 64,
    "F4": 65, "G4": 67, "A4": 69, "B4": 71, "C5": 72, "D5": 74, "E5": 76,
    "F5": 77, "G5": 79, "A5": 81, "B5": 83, "P": 0,
}


def _eighths_to_ticks(events: list[tuple[str, float]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for name, eighths in events:
        mid = _NAME_MIDI.get(name, 0)
        ticks = max(1, int(round(eighths * 2)))
        out.append((mid, ticks))
    return out


_GB_PHRASE: list[tuple[str, float]] = [
    ("E5", 1), ("B4", 1), ("C5", 1), ("D5", 1), ("E5", 1), ("D5", 1), ("C5", 1), ("B4", 1),
    ("A4", 1), ("A4", 1), ("C5", 1), ("E5", 1), ("E5", 1), ("D5", 1), ("C5", 1), ("B4", 2),
    ("C5", 1), ("D5", 1), ("E5", 1), ("C5", 1), ("A4", 1), ("A4", 1), ("A4", 1), ("B4", 1),
    ("C5", 1), ("D5", 1), ("E5", 1), ("D5", 1), ("C5", 1), ("B4", 1), ("A4", 2), ("A4", 2),
    ("E5", 1), ("E5", 1), ("E5", 1), ("C5", 1), ("D5", 1), ("E5", 1), ("D5", 1), ("C5", 1),
    ("B4", 1), ("B4", 1), ("C5", 1), ("D5", 1), ("E5", 1), ("C5", 1), ("A4", 1), ("A4", 2),
]

_GB_BRIDGE: list[tuple[str, float]] = [
    ("E5", 2), ("C5", 2), ("D5", 2), ("B4", 2), ("C5", 2), ("A4", 2), ("G#3", 2), ("E3", 2),
    ("E4", 2), ("C4", 2), ("D4", 2), ("B3", 2), ("C4", 2), ("E4", 2), ("A4", 2), ("G#4", 2),
    ("E5", 2), ("B4", 1), ("C5", 1), ("D5", 1), ("E5", 1), ("D5", 1), ("C5", 1), ("B4", 1),
    ("A4", 1), ("A4", 1), ("C5", 1), ("E5", 1), ("D5", 1), ("C5", 1), ("B4", 2),
    ("C5", 1), ("D5", 1), ("E5", 1), ("C5", 1), ("A4", 2), ("P", 2),
]

_THEME_MELODY = _eighths_to_ticks(_GB_PHRASE * 2 + _GB_BRIDGE)
_THEME_HARMONY = [
    (0 if mid == 0 else max(40, mid - 3), dur) for mid, dur in _THEME_MELODY
]
_THEME_BASS: list[tuple[int, int]] = [
    (40, 8), (47, 8), (40, 8), (47, 8), (45, 8), (52, 8), (45, 8), (52, 8),
    (40, 8), (47, 8), (40, 8), (47, 8), (45, 8), (52, 8), (45, 8), (52, 8),
    (43, 8), (50, 8), (43, 8), (50, 8), (40, 8), (47, 8), (40, 8), (47, 8),
    (45, 8), (52, 8), (45, 8), (52, 8), (40, 8), (47, 8), (40, 8), (47, 8),
    (38, 8), (45, 8), (38, 8), (45, 8), (40, 8), (47, 8), (40, 16),
]


def _midi_hz(mid: int) -> float:
    if mid == 0:
        return 0.0
    return 440.0 * (2.0 ** ((mid - 69) / 12.0))


def _synth_track(
    track: list[tuple[int, int]],
    *,
    duty: float = 0.25,
    peak: float = 1.0,
) -> list[float]:
    samples: list[float] = []
    phase = 0.0
    for note, dur in track:
        n = int(dur * _TICK_SEC * _SAMPLE_RATE)
        freq = _midi_hz(note)
        if freq <= 0.0 or n <= 0:
            samples.extend([0.0] * max(0, n))
            continue
        step = freq / _SAMPLE_RATE
        for i in range(n):
            phase = (phase + step) % 1.0
            raw = 1.0 if phase < duty else -1.0
            t = i / max(1, n - 1)
            attack = min(1.0, i / 80.0)
            release = (1.0 - t) ** 1.35
            samples.append(raw * attack * release * peak)
    return samples


def _build_korobeiniki_sound() -> pygame.mixer.Sound | None:
    try:
        lead = _synth_track(_THEME_MELODY, duty=0.25, peak=0.55)
        harm = _synth_track(_THEME_HARMONY, duty=0.50, peak=0.22)
        bass = _synth_track(_THEME_BASS, duty=0.50, peak=0.30)
        length = len(lead)
        if length == 0:
            return None
        mixed = array.array("h")
        for idx in range(length):
            m = lead[idx] if idx < len(lead) else 0.0
            h = harm[idx % len(harm)] if harm else 0.0
            b = bass[idx % len(bass)] if bass else 0.0
            val = int(m * 5200.0 + h * 3200.0 + b * 3800.0)
            mixed.append(max(-32768, min(32767, val)))
        return pygame.mixer.Sound(buffer=mixed)
    except (pygame.error, ValueError, OSError):
        return None


class Piece:
    def __init__(self, shape_idx: int):
        self.shape_idx = shape_idx
        self.rotations = SHAPES[shape_idx]
        self.rotation = 0
        self.shape = [row[:] for row in self.rotations[0]]
        self.color = COLORS[shape_idx]
        self.x = GRID_WIDTH // 2 - len(self.shape[0]) // 2
        self.y = 0

    def rotated_matrix(self, step: int = 1) -> list[list[int]]:
        n = len(self.rotations)
        if n <= 1:
            return self.shape
        idx = (self.rotation + step) % n
        return [row[:] for row in self.rotations[idx]]


class Tetris:
    def __init__(self) -> None:
        pygame.mixer.pre_init(_SAMPLE_RATE, -16, 1, 512)
        pygame.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("ac's tetris 0.1.1 (Famicom Mode)")
        self.clock = pygame.time.Clock()
        
        # Explicit integers for Python 3.14 stability
        self.font = pygame.font.Font(None, 32)
        self.big_font = pygame.font.Font(None, 64)
        
        self.state = "menu"
        self.music = _build_korobeiniki_sound()
        self.music_channel: pygame.mixer.Channel | None = None
        self.reset_game()

    def reset_game(self) -> None:
        self.board = [[0] * GRID_WIDTH for _ in range(GRID_HEIGHT)]
        self.score = 0
        self.lines = 0
        self.level = 0
        self.bag: list[int] = []
        self.current_piece = self._next_piece()
        self.next_piece_obj = self._next_piece()
        self.drop_timer = 0
        self.soft_drop_timer = 0
        self.das_counter = 0
        self.das_dir = 0
        self.freeze_frames = 0
        self.freeze_reason: str | None = None
        self.pending_lines: list[int] = []
        self.game_over = False
        self._start_are()

    def _input_frozen(self) -> bool:
        return self.freeze_frames > 0 and not self.game_over

    def _start_are(self) -> None:
        self.freeze_frames = FAMICOM_ARE_FRAMES
        self.freeze_reason = "are"
        self.drop_timer = 0
        self.soft_drop_timer = 0
        self.das_counter = 0
        self.das_dir = 0

    def _next_piece(self) -> Piece:
        if not self.bag:
            self.bag = list(range(7))
            random.shuffle(self.bag)
        return Piece(self.bag.pop())

    def check_collision(
        self,
        piece: Piece,
        dx: int = 0,
        dy: int = 0,
        shape: list[list[int]] | None = None,
    ) -> bool:
        matrix = shape if shape is not None else piece.shape
        for y, row in enumerate(matrix):
            for x, cell in enumerate(row):
                if not cell:
                    continue
                nx = piece.x + x + dx
                ny = piece.y + y + dy
                if nx < 0 or nx >= GRID_WIDTH or ny >= GRID_HEIGHT:
                    return True
                if ny >= 0 and self.board[ny][nx]:
                    return True
        return False

    def try_rotate(self, clockwise: bool = True) -> None:
        step = 1 if clockwise else -1
        test = self.current_piece.rotated_matrix(step)
        for kick in ((0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0)):
            if not self.check_collision(
                self.current_piece, kick[0], kick[1], test
            ):
                self.current_piece.rotation = (
                    self.current_piece.rotation + step
                ) % len(self.current_piece.rotations)
                self.current_piece.shape = test
                self.current_piece.x += kick[0]
                self.current_piece.y += kick[1]
                return

    def lock_piece(self) -> None:
        piece = self.current_piece
        for y, row in enumerate(piece.shape):
            for x, cell in enumerate(row):
                if not cell:
                    continue
                bx = piece.x + x
                by = piece.y + y
                if by < 0:
                    self.game_over = True
                    return
                self.board[by][bx] = piece.shape_idx + 1
        lines_to_clear = [i for i, row in enumerate(self.board) if all(row)]
        if lines_to_clear:
            self.pending_lines = lines_to_clear
            self.freeze_frames = FAMICOM_LINE_CLEAR_FRAMES
            self.freeze_reason = "line_clear"
            self.das_counter = 0
            self.das_dir = 0
            return
        self._spawn_next_piece()

    def _spawn_next_piece(self) -> None:
        self.current_piece = self.next_piece_obj
        self.next_piece_obj = self._next_piece()
        if self.check_collision(self.current_piece):
            self.game_over = True
            return
        self._start_are()

    def _apply_line_clear(self) -> None:
        self.clear_lines()
        self._spawn_next_piece()

    def clear_lines(self) -> None:
        cleared = 0
        y = GRID_HEIGHT - 1
        while y >= 0:
            if all(self.board[y]):
                del self.board[y]
                self.board.insert(0, [0] * GRID_WIDTH)
                cleared += 1
            else:
                y -= 1
        if cleared:
            self.lines += cleared
            self.level = min(self.lines // 10, len(FAMICOM_GRAVITY_FRAMES) - 1)
            self.score += SCORE_TABLE.get(cleared, 0) * (self.level + 1)

    def _cell_color(self, val: int) -> tuple[int, int, int] | None:
        if val <= 0:
            return None
        return COLORS[val - 1]

    def _draw_cells(
        self,
        matrix: list[list[int]],
        ox: int,
        oy: int,
        color: tuple[int, int, int],
        cell: int = CELL_SIZE,
    ) -> None:
        for y, row in enumerate(matrix):
            for x, filled in enumerate(row):
                if not filled:
                    continue
                rx = ox + x * cell
                ry = oy + y * cell
                pygame.draw.rect(self.screen, color, (rx, ry, cell - 1, cell - 1))
                pygame.draw.rect(self.screen, WHITE, (rx, ry, cell - 1, cell - 1), 1)

    def draw_grid(self) -> None:
        pygame.draw.rect(
            self.screen,
            WHITE,
            (TOP_LEFT_X - 2, TOP_LEFT_Y - 2, PLAY_WIDTH + 4, PLAY_HEIGHT + 4),
            2,
        )
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                color = self._cell_color(self.board[y][x])
                if color:
                    rx = TOP_LEFT_X + x * CELL_SIZE
                    ry = TOP_LEFT_Y + y * CELL_SIZE
                    pygame.draw.rect(
                        self.screen, color, (rx, ry, CELL_SIZE - 1, CELL_SIZE - 1)
                    )
                    pygame.draw.rect(
                        self.screen, WHITE, (rx, ry, CELL_SIZE - 1, CELL_SIZE - 1), 1
                    )
        if (
            self.current_piece
            and not self.game_over
            and self.freeze_reason != "line_clear"
        ):
            p = self.current_piece
            self._draw_cells(
                p.shape,
                TOP_LEFT_X + p.x * CELL_SIZE,
                TOP_LEFT_Y + p.y * CELL_SIZE,
                p.color,
            )

    def draw_hud(self) -> None:
        y = TOP_LEFT_Y
        self.screen.blit(self.font.render("NEXT", True, GRAY), (HUD_X, y))
        y += 28
        if self.next_piece_obj:
            self._draw_cells(
                self.next_piece_obj.shape,
                HUD_X,
                y,
                self.next_piece_obj.color,
                cell=22,
            )
        y += 100
        for label, val in (
            ("SCORE", f"{self.score:06d}"),
            ("LINES", f"{self.lines:03d}"),
            ("LEVEL", f"{self.level:02d}"),
            ("SPD", f"NES {FAMICOM_FPS}"),
            ("G", f"{famicom_drop_frames(self.level)}f"),
        ):
            self.screen.blit(self.font.render(label, True, GRAY), (HUD_X, y))
            self.screen.blit(self.font.render(val, True, WHITE), (HUD_X, y + 22))
            y += 56

    def draw_menu(self) -> None:
        self.screen.fill(BLACK)
        title = self.big_font.render("AC's Tetris", True, CYAN)
        self.screen.blit(
            title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 120)
        )
        for i, text in enumerate(
            ("ENTER — Play", "H — Help", "ESC — Exit")
        ):
            surf = self.font.render(text, True, WHITE)
            self.screen.blit(
                surf,
                (SCREEN_WIDTH // 2 - surf.get_width() // 2, 320 + i * 40),
            )

    def draw_help(self) -> None:
        self.screen.fill(BLACK)
        lines = (
            "FAMICOM NTSC @ 60 FPS",
            "← → move (DAS 16/6f)",
            "↑ rotate   Z CCW",
            "↓ soft drop (Max G)",
            "SPACE hard drop",
            "ESC back to menu",
        )
        for i, line in enumerate(lines):
            surf = self.font.render(line, True, WHITE)
            self.screen.blit(surf, (40, 200 + i * 36))
        back = self.font.render("Press ESC", True, GRAY)
        self.screen.blit(back, (40, 520))

    def draw_game_over(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        go = self.big_font.render("GAME OVER", True, RED)
        self.screen.blit(go, (SCREEN_WIDTH // 2 - go.get_width() // 2, 240))
        sc = self.font.render(f"Score: {self.score}", True, WHITE)
        self.screen.blit(sc, (SCREEN_WIDTH // 2 - sc.get_width() // 2, 340))
        pr = self.font.render("ENTER — Menu", True, WHITE)
        self.screen.blit(pr, (SCREEN_WIDTH // 2 - pr.get_width() // 2, 400))

    def handle_input(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise SystemExit
            if event.type != pygame.KEYDOWN:
                continue
            if self.state == "menu":
                if event.key == pygame.K_RETURN:
                    self.state = "playing"
                    self.reset_game()
                    self.play_music()
                elif event.key == pygame.K_h:
                    self.state = "help"
                elif event.key == pygame.K_ESCAPE:
                    raise SystemExit
            elif self.state == "help":
                if event.key == pygame.K_ESCAPE:
                    self.state = "menu"
            elif self.state == "game_over":
                if event.key == pygame.K_RETURN:
                    self.state = "menu"
                    self.stop_music()
                elif event.key == pygame.K_ESCAPE:
                    self.state = "menu"
                    self.stop_music()
            elif self.state == "playing" and not self.game_over:
                if self._input_frozen():
                    continue
                if event.key == pygame.K_ESCAPE:
                    self.state = "menu"
                    self.stop_music()
                elif event.key == pygame.K_LEFT:
                    if not self.check_collision(self.current_piece, dx=-1):
                        self.current_piece.x -= 1
                elif event.key == pygame.K_RIGHT:
                    if not self.check_collision(self.current_piece, dx=1):
                        self.current_piece.x += 1
                elif event.key == pygame.K_DOWN:
                    if not self.check_collision(self.current_piece, dy=1):
                        self.current_piece.y += 1
                        self.score += 1
                elif event.key == pygame.K_UP:
                    self.try_rotate(True)
                elif event.key == pygame.K_z:
                    self.try_rotate(False)
                elif event.key == pygame.K_SPACE:
                    while not self.check_collision(self.current_piece, dy=1):
                        self.current_piece.y += 1
                        self.score += 2
                    self.lock_piece()
                    if self.game_over:
                        self.state = "game_over"
                        self.stop_music()

    def play_music(self) -> None:
        if self.music and self.music_channel is None:
            try:
                self.music.set_volume(0.4)
                self.music_channel = self.music.play(loops=-1)
            except pygame.error:
                self.music_channel = None

    def stop_music(self) -> None:
        if self.music_channel is not None:
            try:
                self.music_channel.stop()
            except pygame.error:
                pass
            self.music_channel = None

    def _famicom_das(self) -> None:
        if self.freeze_frames > 0:
            return
        keys = pygame.key.get_pressed()
        direction = 0
        if keys[pygame.K_LEFT]:
            direction = -1
        elif keys[pygame.K_RIGHT]:
            direction = 1
        if direction == 0:
            self.das_dir = 0
            self.das_counter = 0
            return
        if direction != self.das_dir:
            self.das_dir = direction
            self.das_counter = 0
            if not self.check_collision(self.current_piece, dx=direction):
                self.current_piece.x += direction
            return
        self.das_counter += 1
        if self.das_counter >= FAMICOM_DAS_DELAY:
            if (self.das_counter - FAMICOM_DAS_DELAY) % FAMICOM_DAS_REPEAT == 0:
                if not self.check_collision(self.current_piece, dx=direction):
                    self.current_piece.x += direction

    def update_playing(self) -> None:
        if self.game_over:
            return
        if self.freeze_frames > 0:
            self.freeze_frames -= 1
            if self.freeze_frames == 0:
                if self.freeze_reason == "line_clear":
                    self._apply_line_clear()
                else:
                    self.freeze_reason = None
            return

        self._famicom_das()
        keys = pygame.key.get_pressed()
        if keys[pygame.K_DOWN] and not self.check_collision(
            self.current_piece, dy=1
        ):
            self.soft_drop_timer += 1
            if self.soft_drop_timer >= famicom_soft_drop_frames(self.level):
                self.soft_drop_timer = 0
                self.current_piece.y += 1
                self.score += 1
            return

        self.soft_drop_timer = 0
        self.drop_timer += 1
        if self.drop_timer >= famicom_drop_frames(self.level):
            self.drop_timer = 0
            if not self.check_collision(self.current_piece, dy=1):
                self.current_piece.y += 1
            else:
                self.lock_piece()
                if self.game_over:
                    self.state = "game_over"
                    self.stop_music()

    def run(self) -> None:
        try:
            while True:
                self.clock.tick(FPS)
                self.handle_input()
                if self.state == "menu":
                    self.draw_menu()
                elif self.state == "help":
                    self.draw_help()
                elif self.state in ("playing", "game_over"):
                    if self.state == "playing":
                        self.update_playing()
                    self.screen.fill(BLACK)
                    self.draw_grid()
                    self.draw_hud()
                    if self.state == "game_over" or self.game_over:
                        self.draw_game_over()
                pygame.display.flip()
        finally:
            self.stop_music()
            pygame.quit()


if __name__ == "__main__":
    Tetris().run()
