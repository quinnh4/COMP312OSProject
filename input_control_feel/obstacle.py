from __future__ import annotations
from dataclasses import dataclass, field
import os
import random
import pygame


# fallback colors if sprite files are missing
GRAVE_COLOR  = (120, 125, 135)
GRAVE_DARK   = (70, 74, 82)
GRAVE_SHADOW = (40, 42, 48)


# tombstone sprites are loaded on first use and cached here
_TOMBSTONE_SPRITES: list[pygame.Surface] | None = None
_SPRITE_PATHS = [
    "input_control_feel/sprites/tombstones/tombstone1.png",
    "input_control_feel/sprites/tombstones/tombstone2.png",
    "input_control_feel/sprites/tombstones/tombstone3.png",
]

# tight pixel bounds for each sprite as (left_frac, top_frac, right_frac, bot_frac)
# where each value is a fraction of the full image size (0.0–1.0).
# computed once in _load_tombstone_sprites and used by Obstacle.hit_rect.
_SPRITE_TIGHT_FRACS: list[tuple[float, float, float, float]] = []


def _compute_tight_fracs(img: pygame.Surface) -> tuple[float, float, float, float]:
    """
    Returns (left, top, right, bottom) as fractions of image size for
    the bounding box of all pixels with alpha > 10.
    """
    w, h = img.get_size()
    min_x, min_y = w, h
    max_x, max_y = 0, 0
    for y in range(h):
        for x in range(w):
            if img.get_at((x, y))[3] > 10:
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y

    if max_x < min_x:
        return (0.0, 0.0, 1.0, 1.0)
    return (min_x / w, min_y / h, (max_x + 1) / w, (max_y + 1) / h)


def _load_tombstone_sprites() -> list[pygame.Surface]:
    # try to load all three tombstone sprites once and cache them.
    global _TOMBSTONE_SPRITES, _SPRITE_TIGHT_FRACS
    if _TOMBSTONE_SPRITES is not None:
        return _TOMBSTONE_SPRITES

    sprites: list[pygame.Surface] = []
    _SPRITE_TIGHT_FRACS = []
    for path in _SPRITE_PATHS:
        if os.path.exists(path):
            try:
                img = pygame.image.load(path).convert_alpha()
                w, h = img.get_size()
                for y in range(h):
                    for x in range(w):
                        r, g, b, _ = img.get_at((x, y))
                        if r < 20 and g < 20 and b < 20:
                            img.set_at((x, y), (0, 0, 0, 0))
                fracs = _compute_tight_fracs(img)
                sprites.append(img)
                _SPRITE_TIGHT_FRACS.append(fracs)
                print(f"[obstacle] Loaded {path}, tight fracs={fracs}")
            except Exception as e:
                print(f"[obstacle] Failed to load {path}: {e}")
        else:
            print(f"[obstacle] Sprite not found: {path}")

    _TOMBSTONE_SPRITES = sprites
    return sprites


# cache scaled versions so we don't re-scale every frame
_SCALED_CACHE: dict[tuple[int, int, int], pygame.Surface] = {}


def _get_scaled_sprite(sprite_idx: int, w: int, h: int) -> pygame.Surface | None:
    sprites = _load_tombstone_sprites()
    if not sprites:
        return None
    sprite_idx = sprite_idx % len(sprites)
    key = (sprite_idx, w, h)
    cached = _SCALED_CACHE.get(key)
    if cached is None:
        cached = pygame.transform.scale(sprites[sprite_idx], (w, h))
        _SCALED_CACHE[key] = cached
    return cached


@dataclass
class Obstacle:
    rect: pygame.Rect
    # which of the loaded tombstone sprites to render with
    sprite_idx: int = 0

    @property
    def hit_rect(self) -> pygame.Rect:
        """
        Tight collision rect matching only the visible (non-transparent)
        pixels of the sprite and scaled to this obstacle's draw rect.
        """
        _load_tombstone_sprites()  # ensure fracs are computed
        if _SPRITE_TIGHT_FRACS:
            idx = self.sprite_idx % len(_SPRITE_TIGHT_FRACS)
            lf, tf, rf, bf = _SPRITE_TIGHT_FRACS[idx]
        else:
            lf, tf, rf, bf = 0.0, 0.0, 1.0, 1.0  # fallback: full rect
        w, h = self.rect.width, self.rect.height
        left   = self.rect.left + int(lf * w)
        top    = self.rect.top  + int(tf * h)
        right  = self.rect.left + int(rf * w)
        bottom = self.rect.top  + int(bf * h)
        return pygame.Rect(left, top, right - left, bottom - top)

    def draw(self, screen: pygame.Surface) -> None:
        sprite = _get_scaled_sprite(self.sprite_idx, self.rect.width, self.rect.height)
        if sprite:
            screen.blit(sprite, self.rect.topleft)
        else:
            # fallback if sprites failed to load
            pygame.draw.rect(screen, GRAVE_COLOR, self.rect, border_radius=4)
            pygame.draw.rect(screen, GRAVE_SHADOW, self.rect, width=2, border_radius=4)


# keep the area around player spawn clear so the player never starts inside a wall
_SPAWN_CLEARANCE = 90

# minimum gap between obstacles so the player can always squeeze between
_MIN_GAP = 46

# keep obstacles off the arena border
_EDGE_MARGIN = 20

# how many times to try placing a single obstacle before giving up
_MAX_PLACE_ATTEMPTS = 60

# hard floor — every wave must have at least this many obstacles
_MIN_OBSTACLES = 3

# playfield is split into a 3x3 grid — we track how many obstacles land in each
# cell and avoid over-stuffing any single cell so layouts stay spread out
_GRID_COLS = 3
_GRID_ROWS = 3


def _grid_cell(rect: pygame.Rect, pf: pygame.Rect) -> tuple[int, int]:
    # which grid cell does the center of this rect fall into
    col = min(_GRID_COLS - 1, max(0, (rect.centerx - pf.left) * _GRID_COLS // pf.width))
    row = min(_GRID_ROWS - 1, max(0, (rect.centery - pf.top) * _GRID_ROWS // pf.height))
    return col, row


def _cell_counts(placed: list[pygame.Rect], pf: pygame.Rect) -> dict[tuple[int, int], int]:
    counts: dict[tuple[int, int], int] = {}
    for r in placed:
        key = _grid_cell(r, pf)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _cell_cap(total_target: int) -> int:
    # max obstacles allowed in a single grid cell — scales with total count
    return max(1, (total_target + 3) // 4)


def _rand_rect_in_cell(rng: random.Random, pf: pygame.Rect,
                       col: int, row: int,
                       size_range: tuple[int, int]) -> pygame.Rect:
    # roll a square-ish tombstone-shaped rect inside the given grid cell
    cell_w = pf.width // _GRID_COLS
    cell_h = pf.height // _GRID_ROWS
    cell_left = pf.left + col * cell_w
    cell_top = pf.top + row * cell_h

    size = rng.randint(*size_range)
    # clamp to fit cell
    size = min(size, cell_w - 10, cell_h - 10)
    size = max(size, size_range[0])

    lo_x = cell_left + size // 2 + 4
    hi_x = cell_left + cell_w - size // 2 - 4
    lo_y = cell_top + size // 2 + 4
    hi_y = cell_top + cell_h - size // 2 - 4
    if hi_x <= lo_x:
        hi_x = lo_x
    if hi_y <= lo_y:
        hi_y = lo_y
    cx = rng.randint(lo_x, hi_x)
    cy = rng.randint(lo_y, hi_y)
    r = pygame.Rect(0, 0, size, size)
    r.center = (cx, cy)
    return r


def _rect_around(cx: int, cy: int, w: int, h: int) -> pygame.Rect:
    r = pygame.Rect(0, 0, w, h)
    r.center = (cx, cy)
    return r


def _spawn_safe_zone(pf: pygame.Rect) -> pygame.Rect:
    # box around player spawn that must stay empty
    return _rect_around(pf.centerx, pf.centery,
                        _SPAWN_CLEARANCE * 2, _SPAWN_CLEARANCE * 2)


def _fits(candidate: pygame.Rect, placed: list[pygame.Rect],
          safe_zone: pygame.Rect, pf: pygame.Rect) -> bool:
    # inside playfield with edge margin
    if candidate.left < pf.left + _EDGE_MARGIN or candidate.right > pf.right - _EDGE_MARGIN:
        return False
    if candidate.top < pf.top + _EDGE_MARGIN or candidate.bottom > pf.bottom - _EDGE_MARGIN:
        return False
    # clear of spawn
    if candidate.colliderect(safe_zone):
        return False
    # gap check against everything already placed
    inflated = candidate.inflate(_MIN_GAP, _MIN_GAP)
    for r in placed:
        if inflated.colliderect(r):
            return False
    return True


def _pick_under_used_cell(rng: random.Random, placed: list[pygame.Rect],
                          pf: pygame.Rect, cap: int) -> tuple[int, int]:
    # pick a grid cell that still has room, preferring empty cells
    counts = _cell_counts(placed, pf)
    all_cells = [(c, r) for c in range(_GRID_COLS) for r in range(_GRID_ROWS)]

    # skip the dead-center cell when possible so spawn zone isn't constantly fighting us
    center_cell = (_GRID_COLS // 2, _GRID_ROWS // 2)

    empty = [cell for cell in all_cells if counts.get(cell, 0) == 0 and cell != center_cell]
    if empty:
        return rng.choice(empty)

    under_cap = [cell for cell in all_cells if counts.get(cell, 0) < cap and cell != center_cell]
    if under_cap:
        return rng.choice(under_cap)

    return rng.choice(all_cells)


def _try_place_spread(rng: random.Random, pf: pygame.Rect, placed: list[pygame.Rect],
                      safe_zone: pygame.Rect,
                      size_range: tuple[int, int],
                      total_target: int) -> pygame.Rect | None:
    # try to place a tombstone in a currently under-used cell so layouts spread out
    cap = _cell_cap(total_target)
    for _ in range(_MAX_PLACE_ATTEMPTS):
        col, row = _pick_under_used_cell(rng, placed, pf, cap)
        r = _rand_rect_in_cell(rng, pf, col, row, size_range)
        if _fits(r, placed, safe_zone, pf):
            return r
    return None


def _layout_scattered(rng: random.Random, pf: pygame.Rect, count: int) -> list[pygame.Rect]:
    # loose scattered tombstones across the yard
    placed: list[pygame.Rect] = []
    safe = _spawn_safe_zone(pf)
    for _ in range(count):
        r = _try_place_spread(rng, pf, placed, safe, (66, 105), count)
        if r:
            placed.append(r)
    return placed


def _layout_rows(rng: random.Random, pf: pygame.Rect, count: int) -> list[pygame.Rect]:
    # tombstones loosely arranged in rows like an actual graveyard
    placed: list[pygame.Rect] = []
    safe = _spawn_safe_zone(pf)
    # pick 2-3 rows positioned vertically
    row_count = rng.randint(2, 3)
    per_row = max(2, count // row_count)
    for ri in range(row_count):
        row_y_rel = (ri + 1) / (row_count + 1)
        row_y = pf.top + int(pf.height * row_y_rel)
        for ci in range(per_row):
            x_rel = (ci + 0.5) / per_row
            x = pf.left + int(pf.width * x_rel) + rng.randint(-20, 20)
            y = row_y + rng.randint(-15, 15)
            size = rng.randint(72, 96)
            r = _rect_around(x, y, size, size)
            if _fits(r, placed, safe, pf):
                placed.append(r)
    return placed


def _layout_clusters(rng: random.Random, pf: pygame.Rect, count: int) -> list[pygame.Rect]:
    # 2-3 small clusters of tombstones in different parts of the yard
    placed: list[pygame.Rect] = []
    safe = _spawn_safe_zone(pf)
    cluster_count = rng.randint(2, 3)
    per_cluster = max(2, count // cluster_count)

    # pick cluster centers in different grid cells
    cells = [(c, r) for c in range(_GRID_COLS) for r in range(_GRID_ROWS)
             if (c, r) != (_GRID_COLS // 2, _GRID_ROWS // 2)]
    rng.shuffle(cells)

    for i in range(cluster_count):
        if i >= len(cells):
            break
        col, row = cells[i]
        cell_w = pf.width // _GRID_COLS
        cell_h = pf.height // _GRID_ROWS
        center_x = pf.left + col * cell_w + cell_w // 2
        center_y = pf.top + row * cell_h + cell_h // 2

        for _ in range(per_cluster):
            # try a few positions near the cluster center
            for _ in range(8):
                size = rng.randint(60, 87)
                x = center_x + rng.randint(-40, 40)
                y = center_y + rng.randint(-30, 30)
                r = _rect_around(x, y, size, size)
                if _fits(r, placed, safe, pf):
                    placed.append(r)
                    break
    return placed


def _layout_perimeter(rng: random.Random, pf: pygame.Rect, count: int) -> list[pygame.Rect]:
    # tombstones around the edges of the playfield, leaving a clear middle ring
    placed: list[pygame.Rect] = []
    safe = _spawn_safe_zone(pf)
    edge_cells = [(c, r) for c in range(_GRID_COLS) for r in range(_GRID_ROWS)
                  if c == 0 or c == _GRID_COLS - 1 or r == 0 or r == _GRID_ROWS - 1]
    rng.shuffle(edge_cells)
    for (col, row) in edge_cells:
        if len(placed) >= count:
            break
        for _ in range(8):
            r = _rand_rect_in_cell(rng, pf, col, row, (66, 96))
            if _fits(r, placed, safe, pf):
                placed.append(r)
                break
    return placed


def _layout_boss_arena(rng: random.Random, pf: pygame.Rect, count: int) -> list[pygame.Rect]:
    # four corner tombstones for boss line-of-sight cover
    placed: list[pygame.Rect] = []
    safe = _spawn_safe_zone(pf)
    positions = [(0.22, 0.28), (0.78, 0.28), (0.22, 0.72), (0.78, 0.72)]
    rng.shuffle(positions)
    for rel_x, rel_y in positions:
        jitter_x = rng.randint(-18, 18)
        jitter_y = rng.randint(-14, 14)
        size = rng.randint(84, 108)
        cx = pf.left + int(pf.width * rel_x) + jitter_x
        cy = pf.top + int(pf.height * rel_y) + jitter_y
        r = _rect_around(cx, cy, size, size)
        if _fits(r, placed, safe, pf):
            placed.append(r)

    # sometimes add an off-center stone to really split the arena
    if rng.random() < 0.5 and len(placed) < count:
        side = rng.choice([-1, 1])
        size = rng.randint(72, 90)
        r = _rect_around(pf.centerx + side * (_SPAWN_CLEARANCE + rng.randint(10, 40)),
                         pf.centery + rng.randint(-30, 30),
                         size, size)
        if _fits(r, placed, safe, pf):
            placed.append(r)
    return placed


# map archetype name to its generator
_LAYOUT_FUNCS = {
    "scattered": _layout_scattered,
    "rows": _layout_rows,
    "clusters": _layout_clusters,
    "perimeter": _layout_perimeter,
    "boss_arena": _layout_boss_arena,
}


def _pick_layout_and_count(rng: random.Random, wave_number: int,
                           is_boss_wave: bool) -> tuple[str, int]:
    # boss wave always gets the boss arena
    if is_boss_wave:
        return "boss_arena", rng.randint(4, 6)

    # early waves use simpler archetypes, later waves unlock more variety
    if wave_number <= 1:
        pool = ["scattered", "perimeter"]
    elif wave_number == 2:
        pool = ["scattered", "perimeter", "rows"]
    elif wave_number == 3:
        pool = ["scattered", "perimeter", "rows", "clusters"]
    else:
        pool = ["scattered", "rows", "clusters", "perimeter"]

    layout = rng.choice(pool)

    # count ramps up gently with wave number, with a little randomness
    base = 4 + wave_number  # wave 1 -> 5, wave 4 -> 8
    count = base + rng.randint(-1, 2)
    count = max(_MIN_OBSTACLES + 1, min(count, 9))
    return layout, count


def _stylize(rng: random.Random, rects: list[pygame.Rect]) -> list[Obstacle]:
    # randomly assign one of the loaded tombstone sprites to each rect
    sprite_count = max(1, len(_load_tombstone_sprites()))
    return [Obstacle(rect=r, sprite_idx=rng.randrange(sprite_count)) for r in rects]


def _top_up_to_minimum(rng: random.Random, pf: pygame.Rect,
                      placed: list[pygame.Rect], count_target: int) -> list[pygame.Rect]:
    # if generation came up short, keep placing small scattered stones until we have at least 3
    safe = _spawn_safe_zone(pf)
    attempts = 0
    while len(placed) < max(_MIN_OBSTACLES, count_target) and attempts < 300:
        r = _try_place_spread(rng, pf, placed, safe, (66, 90), count_target)
        if r:
            placed.append(r)
        attempts += 1
    return placed


def build_layout_for_wave(wave_number: int, pf: pygame.Rect,
                          seed: int | None = None,
                          is_boss_wave: bool = False) -> list[Obstacle]:
    # seed the rng so the same (seed, wave_number) always gives the same layout
    if seed is None:
        rng = random.Random()
    else:
        rng = random.Random((seed * 1_000_003) ^ wave_number)

    # fallback boss detection in case the caller forgot to flag it
    if not is_boss_wave and wave_number >= 5:
        is_boss_wave = True

    layout_name, count = _pick_layout_and_count(rng, wave_number, is_boss_wave)
    rects = _LAYOUT_FUNCS[layout_name](rng, pf, count)

    # guarantee minimum count
    rects = _top_up_to_minimum(rng, pf, rects, count)

    # absolute safety net if placement completely failed
    if len(rects) < _MIN_OBSTACLES:
        rects = _layout_scattered(rng, pf, _MIN_OBSTACLES + 1)
        rects = _top_up_to_minimum(rng, pf, rects, _MIN_OBSTACLES)

    return _stylize(rng, rects)


def resolve_rect_collision(rect: pygame.Rect, obstacles: list[Obstacle],
                           prev_rect: pygame.Rect) -> pygame.Rect:
    new_rect = rect.copy()

    # resolve X axis
    test_x = prev_rect.copy()
    test_x.x = new_rect.x
    for ob in obstacles:
        hr = ob.hit_rect
        if test_x.colliderect(hr):
            if new_rect.x > prev_rect.x:
                test_x.right = hr.left
            elif new_rect.x < prev_rect.x:
                test_x.left = hr.right

    # resolve Y axis using x-resolved rect
    test_y = test_x.copy()
    test_y.y = new_rect.y
    for ob in obstacles:
        hr = ob.hit_rect
        if test_y.colliderect(hr):
            if new_rect.y > prev_rect.y:
                test_y.bottom = hr.top
            elif new_rect.y < prev_rect.y:
                test_y.top = hr.bottom

    return test_y


def projectile_hits_obstacle(point: pygame.Vector2, obstacles: list[Obstacle]) -> bool:
    for ob in obstacles:
        if ob.hit_rect.collidepoint(point.x, point.y):
            return True
    return False


def draw_obstacles(screen: pygame.Surface, obstacles: list[Obstacle]) -> None:
    for ob in obstacles:
        ob.draw(screen)