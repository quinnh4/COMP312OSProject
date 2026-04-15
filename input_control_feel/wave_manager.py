from __future__ import annotations
from dataclasses import dataclass
import random
import pygame

from input_control_feel.enemy import Enemy


@dataclass(frozen=True)
class WaveConfig:
    wave_number: int
    enemy_count: int
    enemy_hp: int
    enemy_speed: float
    enemy_size: int
    enemy_color: tuple
    spawn_interval: float
    is_boss_wave: bool = False


WAVE_CONFIGS: list[WaveConfig] = [
    WaveConfig(
        wave_number=1,
        enemy_count=6,
        enemy_hp=2,
        enemy_speed=30.0,
        enemy_size=22,
        enemy_color=(80, 140, 80),
        spawn_interval=1.2,
    ),
    WaveConfig(
        wave_number=2,
        enemy_count=10,
        enemy_hp=3,
        enemy_speed=40.0,
        enemy_size=24,
        enemy_color=(60, 160, 60),
        spawn_interval=0.9,
    ),
    WaveConfig(
        wave_number=3,
        enemy_count=14,
        enemy_hp=4,
        enemy_speed=50.0,
        enemy_size=26,
        enemy_color=(180, 120, 30),
        spawn_interval=0.7,
    ),
    WaveConfig(
        wave_number=4,
        enemy_count=18,
        enemy_hp=6,
        enemy_speed=60.0,
        enemy_size=28,
        enemy_color=(160, 60, 60),
        spawn_interval=0.55,
    ),
    WaveConfig(
        wave_number=5,
        enemy_count=1,
        enemy_hp=120,
        enemy_speed=35.0,
        enemy_size=72,
        enemy_color=(100, 20, 140),
        spawn_interval=0.0,
        is_boss_wave=True,
    ),
]

BOSS_MINION_COUNT  = 6
BOSS_MINION_HP     = 3
BOSS_MINION_SPEED  = 85.0
BOSS_MINION_SIZE   = 20
BOSS_MINION_COLOR  = (130, 40, 170)
WAVE_TRANSITION_DELAY = 3.0


# spawning and tracking progress for each wave
class WaveManager:

    def __init__(self, playfield: pygame.Rect) -> None:
        self.playfield = playfield
        self.current_wave_idx = 0
        self.enemies: list[Enemy] = []
        self.spawn_queue = 0
        self.minion_queue = 0
        self.spawn_timer = 0.0
        self.transition_timer = 0.0  # counts down between waves
        self.total_kills = 0
        self.wave_complete = False
        self.all_waves_done = False

    @property
    def cfg(self) -> WaveConfig:
        return WAVE_CONFIGS[self.current_wave_idx]

    @property
    def wave_number(self) -> int:
        return self.current_wave_idx + 1

    @property
    def total_waves(self) -> int:
        return len(WAVE_CONFIGS)

    def start_wave(self) -> None:
        self.enemies.clear()
        self.spawn_queue = self.cfg.enemy_count
        self.spawn_timer = 0.0
        self.wave_complete = False

        if self.cfg.is_boss_wave:
            self._spawn(is_boss=True)
            self.spawn_queue = 0
            self.minion_queue = BOSS_MINION_COUNT
        else:
            self.minion_queue = 0

    def _spawn_point(self) -> pygame.Vector2:
        pf = self.playfield
        edge = random.randint(0, 3)
        if edge == 0:
            return pygame.Vector2(random.uniform(pf.left, pf.right), pf.top + 2)
        elif edge == 1:
            return pygame.Vector2(random.uniform(pf.left, pf.right), pf.bottom - 2)
        elif edge == 2:
            return pygame.Vector2(pf.left + 2, random.uniform(pf.top, pf.bottom))
        else:
            return pygame.Vector2(pf.right - 2, random.uniform(pf.top, pf.bottom))

    def _spawn(self, is_boss=False, is_minion=False) -> None:
        cfg = self.cfg
        pos = self._spawn_point()

        if is_boss:
            e = Enemy(pos, cfg.enemy_hp, cfg.enemy_hp, cfg.enemy_speed,
                      cfg.enemy_size, cfg.enemy_color,
                      is_boss=True, contact_damage=2, knockback_resistance=4.0)
        elif is_minion:
            e = Enemy(pos, BOSS_MINION_HP, BOSS_MINION_HP, BOSS_MINION_SPEED,
                      BOSS_MINION_SIZE, BOSS_MINION_COLOR,
                      is_boss=False, contact_damage=1, knockback_resistance=1.0)
        else:
            e = Enemy(pos, cfg.enemy_hp, cfg.enemy_hp, cfg.enemy_speed,
                      cfg.enemy_size, cfg.enemy_color,
                      is_boss=False, contact_damage=1, knockback_resistance=1.0)

        self.enemies.append(e)

    def update(self, dt: float, player_pos: pygame.Vector2) -> None:
        # Spawn regular enemies
        if self.spawn_queue > 0:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                self._spawn()
                self.spawn_queue -= 1
                self.spawn_timer = self.cfg.spawn_interval

        # Spawn boss-wave minions
        if self.minion_queue > 0:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                self._spawn(is_minion=True)
                self.minion_queue -= 1
                self.spawn_timer = 1.0

        # Update each enemy
        for e in self.enemies:
            e.update(dt, player_pos, self.playfield, self.enemies)  

        # Remove dead enemies
        before = len(self.enemies)
        self.enemies = [e for e in self.enemies if e.alive]
        self.total_kills += before - len(self.enemies)

        # Check wave clear
        all_spawned = self.spawn_queue == 0 and self.minion_queue == 0
        if all_spawned and len(self.enemies) == 0 and not self.wave_complete:
            self.wave_complete = True
            self.transition_timer = WAVE_TRANSITION_DELAY

    # call once transition_timer has expired. returns True if more waves remain
    def advance_wave(self) -> bool:
        self.current_wave_idx += 1
        if self.current_wave_idx >= len(WAVE_CONFIGS):
            self.all_waves_done = True
            return False
        self.start_wave()
        return True

    # check each projectile against all enemies. removes projectiles that hit and applies damage. returns the surviving projectile list.
    def check_projectile_hits(self, projectiles: list, damage: int, impulse: float) -> list:
        surviving = []
        for proj in projectiles:
            hit = False
            for e in self.enemies:
                if not e.alive:
                    continue
                if e.rect.collidepoint(proj.position.x, proj.position.y):
                    kb = proj.velocity.normalize() if proj.velocity.length_squared() > 0 else pygame.Vector2(1, 0)
                    e.take_hit(damage, kb, impulse)
                    hit = True
                    break
            if not hit:
                surviving.append(proj)
        return surviving

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        for e in self.enemies:
            e.draw(screen, font)