from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import math
import random
import pygame


class PowerUpType(str, Enum):
    HEALTH      = "HEALTH"
    SHIELD      = "SHIELD"
    RAPID_FIRE  = "RAPID_FIRE"
    AMMO        = "AMMO"
    DAMAGE      = "DAMAGE"
    SPEED       = "SPEED"


# visual + gameplay config for each power-up type
POWERUP_INFO = {
    PowerUpType.HEALTH:     {"color": (80, 220, 100),  "label": "+HP",   "weight": 25},
    PowerUpType.SHIELD:     {"color": (80, 160, 255),  "label": "SHLD",  "weight": 15},
    PowerUpType.RAPID_FIRE: {"color": (255, 230, 60),  "label": "RAPID", "weight": 15},
    PowerUpType.AMMO:       {"color": (255, 160, 60),  "label": "AMMO",  "weight": 20},
    PowerUpType.DAMAGE:     {"color": (230, 60, 80),   "label": "DMG",   "weight": 15},
    PowerUpType.SPEED:      {"color": (80, 230, 230),  "label": "SPD",   "weight": 10},
}


# duration / magnitude constants
HEALTH_AMOUNT      = 30
SHIELD_DURATION    = 8.0
SHIELD_HITS        = 3
RAPID_DURATION     = 10.0
RAPID_MULTIPLIER   = 0.5   
DAMAGE_DURATION    = 8.0
DAMAGE_MULTIPLIER  = 2.0
SPEED_DURATION     = 6.0
SPEED_MULTIPLIER   = 1.4

POWERUP_SIZE       = 24
POWERUP_LIFETIME   = 12.0   


def pick_random_type() -> PowerUpType:
    types   = list(POWERUP_INFO.keys())
    weights = [POWERUP_INFO[t]["weight"] for t in types]
    return random.choices(types, weights=weights, k=1)[0]


@dataclass
class PowerUp:
    position: pygame.Vector2
    kind: PowerUpType
    lifetime: float = POWERUP_LIFETIME
    alive: bool = True
    # pulsing animation phase
    _phase: float = 0.0

    @property
    def rect(self) -> pygame.Rect:
        r = pygame.Rect(0, 0, POWERUP_SIZE, POWERUP_SIZE)
        r.center = (int(self.position.x), int(self.position.y))
        return r

    def update(self, dt: float) -> None:
        self.lifetime -= dt
        self._phase += dt * 4.0
        if self.lifetime <= 0:
            self.alive = False

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        info  = POWERUP_INFO[self.kind]
        color = info["color"]
        label = info["label"]

        # pulsing outer glow
        pulse = 0.5 + 0.5 * math.sin(self._phase)
        glow_size = int(POWERUP_SIZE + 6 + pulse * 4)
        glow_rect = pygame.Rect(0, 0, glow_size, glow_size)
        glow_rect.center = self.rect.center

        # flicker when about to expire
        about_to_expire = self.lifetime < 3.0
        if about_to_expire and int(self.lifetime * 6) % 2 == 0:
            return

        glow_color = (color[0] // 3, color[1] // 3, color[2] // 3)
        pygame.draw.rect(screen, glow_color, glow_rect, border_radius=8)
        pygame.draw.rect(screen, color, self.rect, border_radius=6)
        pygame.draw.rect(screen, (20, 24, 30), self.rect, width=2, border_radius=6)

        # label
        lbl = font.render(label, True, (20, 24, 30))
        screen.blit(lbl, (self.rect.centerx - lbl.get_width() // 2,
                          self.rect.centery - lbl.get_height() // 2))


class PowerUpManager:

    def __init__(self, playfield: pygame.Rect) -> None:
        self.playfield = playfield
        self.powerups: list[PowerUp] = []

        # random ambient spawns
        self.spawn_timer = 8.0
        self.spawn_interval_min = 10.0
        self.spawn_interval_max = 16.0

        # active effects on the player (seconds remaining, or hits remaining for shield)
        self.shield_time_left   = 0.0
        self.shield_hits_left   = 0
        self.rapid_time_left    = 0.0
        self.damage_time_left   = 0.0
        self.speed_time_left    = 0.0

        # recent pickup for floating text
        self.last_pickup_text   = ""
        self.last_pickup_timer  = 0.0
        self.last_pickup_color  = (255, 255, 255)


    @property
    def shield_active(self) -> bool:
        return self.shield_time_left > 0 and self.shield_hits_left > 0

    @property
    def rapid_active(self) -> bool:
        return self.rapid_time_left > 0

    @property
    def damage_active(self) -> bool:
        return self.damage_time_left > 0

    @property
    def speed_active(self) -> bool:
        return self.speed_time_left > 0

    def fire_rate_multiplier(self) -> float:
        return RAPID_MULTIPLIER if self.rapid_active else 1.0

    def damage_multiplier(self) -> float:
        return DAMAGE_MULTIPLIER if self.damage_active else 1.0

    def speed_multiplier(self) -> float:
        return SPEED_MULTIPLIER if self.speed_active else 1.0


    def _random_spawn_point(self, obstacles: list | None = None) -> pygame.Vector2:
        pf = self.playfield
        for _ in range(20):
            pos = pygame.Vector2(
                random.uniform(pf.left + 40, pf.right - 40),
                random.uniform(pf.top + 40, pf.bottom - 40),
            )
            test = pygame.Rect(0, 0, POWERUP_SIZE, POWERUP_SIZE)
            test.center = (int(pos.x), int(pos.y))
            if obstacles and any(o.rect.colliderect(test) for o in obstacles):
                continue
            return pos
        # fallback
        return pygame.Vector2(pf.center)

    def spawn_at(self, pos: pygame.Vector2, kind: PowerUpType | None = None) -> None:
        kind = kind or pick_random_type()
        self.powerups.append(PowerUp(pygame.Vector2(pos), kind))

    def maybe_drop_from_enemy(self, pos: pygame.Vector2, is_boss: bool, obstacles: list | None = None) -> None:
        if is_boss:
            # boss drops 2 goodies
            for _ in range(2):
                drop_pos = pygame.Vector2(pos) + pygame.Vector2(random.uniform(-30, 30),
                                                                 random.uniform(-30, 30))
                self._clamp_inside(drop_pos)
                self.spawn_at(drop_pos)
            return
        if random.random() < 0.08:  # 8% chance per kill
            self.spawn_at(pos)

    def _clamp_inside(self, pos: pygame.Vector2) -> None:
        pf = self.playfield
        pos.x = max(pf.left + 20, min(pf.right - 20, pos.x))
        pos.y = max(pf.top + 20, min(pf.bottom - 20, pos.y))


    def update(self, dt: float, player_rect: pygame.Rect, on_pickup, obstacles: list | None = None) -> None:
        # countdown effects
        self.shield_time_left  = max(0.0, self.shield_time_left - dt)
        self.rapid_time_left   = max(0.0, self.rapid_time_left - dt)
        self.damage_time_left  = max(0.0, self.damage_time_left - dt)
        self.speed_time_left   = max(0.0, self.speed_time_left - dt)
        self.last_pickup_timer = max(0.0, self.last_pickup_timer - dt)

        # shield expires cleanly when time or hits run out
        if self.shield_time_left <= 0:
            self.shield_hits_left = 0

        # ambient spawn
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            pos = self._random_spawn_point(obstacles)
            self.spawn_at(pos)
            self.spawn_timer = random.uniform(self.spawn_interval_min, self.spawn_interval_max)

        # update + pickup check
        for pu in self.powerups:
            pu.update(dt)
            if pu.alive and pu.rect.colliderect(player_rect):
                self._apply(pu.kind, on_pickup)
                pu.alive = False

        self.powerups = [p for p in self.powerups if p.alive]

    def _apply(self, kind: PowerUpType, on_pickup) -> None:
        info = POWERUP_INFO[kind]
        self.last_pickup_text  = info["label"]
        self.last_pickup_color = info["color"]
        self.last_pickup_timer = 1.5

        if kind == PowerUpType.HEALTH:
            on_pickup("heal", HEALTH_AMOUNT)
        elif kind == PowerUpType.AMMO:
            on_pickup("ammo_refill", None)
        elif kind == PowerUpType.SHIELD:
            self.shield_time_left = SHIELD_DURATION
            self.shield_hits_left = SHIELD_HITS
        elif kind == PowerUpType.RAPID_FIRE:
            self.rapid_time_left = RAPID_DURATION
        elif kind == PowerUpType.DAMAGE:
            self.damage_time_left = DAMAGE_DURATION
        elif kind == PowerUpType.SPEED:
            self.speed_time_left = SPEED_DURATION

    def absorb_shield_hit(self) -> bool:
        if not self.shield_active:
            return False
        self.shield_hits_left -= 1
        if self.shield_hits_left <= 0:
            self.shield_time_left = 0.0
        return True

    def reset(self) -> None:
        self.powerups.clear()
        self.spawn_timer = 8.0
        self.shield_time_left = 0.0
        self.shield_hits_left = 0
        self.rapid_time_left  = 0.0
        self.damage_time_left = 0.0
        self.speed_time_left  = 0.0
        self.last_pickup_timer = 0.0
        self.last_pickup_text = ""


    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        for pu in self.powerups:
            pu.draw(screen, font)

    def draw_shield_ring(self, screen: pygame.Surface, center: tuple[int, int]) -> None:
        if not self.shield_active:
            return
        radius = 28
        # thicker ring when more hits remain
        thickness = max(2, self.shield_hits_left)
        # flicker when time almost out
        if self.shield_time_left < 1.5 and int(self.shield_time_left * 8) % 2 == 0:
            return
        pygame.draw.circle(screen, (80, 160, 255), center, radius, thickness)

    def draw_hud_effects(self, screen: pygame.Surface, font: pygame.font.Font, x: int, y: int) -> None:
        entries = []
        if self.shield_active:
            entries.append((f"SHIELD {self.shield_hits_left}x", (80, 160, 255)))
        if self.rapid_active:
            entries.append((f"RAPID {self.rapid_time_left:.0f}s", (255, 230, 60)))
        if self.damage_active:
            entries.append((f"DMGx2 {self.damage_time_left:.0f}s", (230, 60, 80)))
        if self.speed_active:
            entries.append((f"SPEED {self.speed_time_left:.0f}s", (80, 230, 230)))

        cx = x
        for text, color in entries:
            surf = font.render(text, True, color)
            pad  = 6
            box  = pygame.Rect(cx - pad, y - 2, surf.get_width() + pad * 2, surf.get_height() + 4)
            pygame.draw.rect(screen, (30, 36, 46), box, border_radius=4)
            pygame.draw.rect(screen, color, box, width=1, border_radius=4)
            screen.blit(surf, (cx, y))
            cx += box.width + 8