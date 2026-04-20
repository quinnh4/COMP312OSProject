from __future__ import annotations
from dataclasses import dataclass
import random
import pygame

from input_control_feel.enemy import Enemy
from input_control_feel.obstacle import Obstacle


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
    WaveConfig(1,  6, 2, 30.0, 22, (80, 140, 80),  1.2),
    WaveConfig(2, 10, 3, 40.0, 24, (60, 160, 60),  0.9),
    WaveConfig(3, 14, 4, 50.0, 26, (180, 120, 30), 0.7),
    WaveConfig(4, 18, 6, 60.0, 28, (160, 60, 60),  0.55),
    WaveConfig(5,  1, 120, 35.0, 72, (100, 20, 140), 0.0, is_boss_wave=True),
]


BOSS_MINION_COUNT     = 6
BOSS_MINION_HP        = 3
BOSS_MINION_SPEED     = 85.0
BOSS_MINION_SIZE      = 20
BOSS_MINION_COLOR     = (130, 40, 170)
WAVE_TRANSITION_DELAY = 3.0


class WaveManager:
    def __init__(self, playfield: pygame.Rect) -> None:
        self.playfield = playfield
        self.current_wave_idx = 0
        self.enemies: list[Enemy] = []
        self.spawn_queue = 0
        self.minion_queue = 0
        self.spawn_timer = 0.0
        self.transition_timer = 0.0
        self.total_kills = 0
        self.wave_complete = False
        self.all_waves_done = False
        # obstacles for the current wave (set by Game)
        self.obstacles: list[Obstacle] = []

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

    def update(self, dt: float, player_pos: pygame.Vector2, on_enemy_killed=None) -> None:
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

        # Update each enemy (now with obstacles awareness)
        for e in self.enemies:
            e.update(dt, player_pos, self.playfield, self.enemies, self.obstacles)

        # Remove dead enemies, notifying callback for each so power-ups can drop
        survivors = []
        for e in self.enemies:
            if e.alive:
                survivors.append(e)
            else:
                self.total_kills += 1
                if on_enemy_killed is not None:
                    on_enemy_killed(e)
        self.enemies = survivors

        # Check wave clear
        all_spawned = self.spawn_queue == 0 and self.minion_queue == 0
        if all_spawned and len(self.enemies) == 0 and not self.wave_complete:
            self.wave_complete = True
            self.transition_timer = WAVE_TRANSITION_DELAY

    def advance_wave(self) -> bool:
        self.current_wave_idx += 1
        if self.current_wave_idx >= len(WAVE_CONFIGS):
            self.all_waves_done = True
            return False
        self.start_wave()
        return True

    def check_projectile_hits(self, projectiles: list, damage: float, impulse: float) -> list:
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