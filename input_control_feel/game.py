from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import random

from input_control_feel.wave_manager import WaveManager
from input_control_feel.powerup import PowerUpManager
from input_control_feel.obstacle import (
    build_layout_for_wave, resolve_rect_collision, projectile_hits_obstacle, draw_obstacles
)
from input_control_feel.title_screen import TitleScreen, PauseMenu
from input_control_feel.sprite_manager import PlayerSpriteAnimator, PlayerDirection

import pygame


class ControlScheme(str, Enum):
    WASD = "WASD"
    ARROWS = "ARROWS"
    IJKL = "IJKL"


# projectile class for shooting mechanics
@dataclass
class Projectile:
    position: pygame.Vector2
    velocity: pygame.Vector2
    radius: float = 4
    color: tuple = (255, 255, 255)

    def update(self, dt: float) -> None:
        self.position += self.velocity * dt

    def draw(self, screen: pygame.Surface) -> None:
        pygame.draw.circle(screen, self.color, (int(self.position.x), int(self.position.y)), self.radius)


@dataclass
class FeelPreset:
    name: str

    # movement feel
    accel: float
    max_speed: float
    friction: float

    # shooting feel
    projectile_speed: float
    fire_rate: float
    ammo_max: int
    reload_time: float


class Game:
    fps = 60

    SCREEN_W, SCREEN_H = 960, 540
    MIN_SCREEN_W, MIN_SCREEN_H = 720, 420
    HUD_H = 54
    PLAYFIELD_PADDING = 10

    PLAYER_MAX_HP = 100
    DAMAGE_COOLDOWN = 0.5
    DEATH_ANIM_DURATION = 0.6

    PLAYER_SIZE = 32

    @staticmethod
    def _approach_zero(value: float, decel: float, dt: float) -> float:
        step = decel * dt
        if value > 0:
            return max(0.0, value - step)
        if value < 0:
            return min(0.0, value + step)
        return 0.0

    def _apply_window_size(self, width: int, height: int, recreate_surface: bool = True) -> None:
        self.SCREEN_W = max(self.MIN_SCREEN_W, int(width))
        self.SCREEN_H = max(self.MIN_SCREEN_H, int(height))

        if recreate_surface:
            self.screen = pygame.display.set_mode((self.SCREEN_W, self.SCREEN_H), pygame.RESIZABLE)

        self.screen_rect = pygame.Rect(0, 0, self.SCREEN_W, self.SCREEN_H)
        self.playfield = pygame.Rect(
            self.PLAYFIELD_PADDING,
            self.HUD_H + self.PLAYFIELD_PADDING,
            self.SCREEN_W - 2 * self.PLAYFIELD_PADDING,
            self.SCREEN_H - self.HUD_H - 2 * self.PLAYFIELD_PADDING,
        )

        if hasattr(self, "wave_manager"):
            self.wave_manager.playfield = self.playfield
            self._load_obstacles_for_current_wave()
            if hasattr(self, "player_rect"):
                self._apply_bounds_player()
                self._ensure_player_not_in_obstacle()

        # rebuild menus so button hitboxes match the new size
        if hasattr(self, "title_font") and hasattr(self, "button_font") and hasattr(self, "small_font"):
            self.title_screen = TitleScreen(
                self.SCREEN_W, self.SCREEN_H,
                self.title_font, self.button_font, self.small_font,
            )
            self.pause_menu = PauseMenu(
                self.SCREEN_W, self.SCREEN_H,
                self.pause_title_font, self.button_font, self.small_font,
            )

    def __init__(self) -> None:
        self.screen = pygame.display.set_mode((self.SCREEN_W, self.SCREEN_H), pygame.RESIZABLE)
        self.font = pygame.font.SysFont(None, 22)
        self.small_font = pygame.font.SysFont(None, 16)
        self.big_font = pygame.font.SysFont(None, 48)
        # chunky pixel-ish font for the title and buttons
        self.title_font = pygame.font.SysFont("couriernew,consolas,monospace", 56, bold=True)
        self.pause_title_font = pygame.font.SysFont("couriernew,consolas,monospace", 42, bold=True)
        self.button_font = pygame.font.SysFont("couriernew,consolas,monospace", 22, bold=True)
        self._apply_window_size(self.SCREEN_W, self.SCREEN_H, recreate_surface=False)

        # states: "title", "play", "dying", "paused", "game_over", "victory"
        self.state = "title"
        # main loop watches this to know when a quit button was clicked
        self.should_quit = False

        self.player_rect = pygame.Rect(0, 0, self.PLAYER_SIZE, self.PLAYER_SIZE)
        self.player_pos = pygame.Vector2(self.playfield.center)
        self.player_vel = pygame.Vector2(0, 0)
        self.player_rect.center = self.player_pos

        self.player_hp = self.PLAYER_MAX_HP
        self.damage_cooldown_left = 0.0
        self.death_anim_timer = 0.0

        self.control_scheme = ControlScheme.WASD
        self.debug = False

        self.presets = [
            FeelPreset("BALANCED",     2500.0, 480.0, 10.0, 950.0,  0.25, 8,  2.0),
            FeelPreset("RAPID-FIRE",   3200.0, 520.0, 14.0, 800.0,  0.15, 12, 1.5),
            FeelPreset("HEAVY-CANNON", 1900.0, 400.0, 6.0,  1200.0, 0.5,  5,  2.5),
        ]
        self.preset_idx = 0

        self.last_move_dir = pygame.Vector2(1, 0)

        # player sprite animator
        self.player_sprite_animator = PlayerSpriteAnimator(
            "input_control_feel/sprites/Player",
            player_size=self.PLAYER_SIZE
        )

        self.projectiles: list[Projectile] = []
        self.ammo_current = self.preset.ammo_max
        self.fire_cooldown_left = 0.0
        self.reload_cooldown_left = 0.0
        self.is_reloading = False

        self.wave_manager = WaveManager(self.playfield)
        self.powerup_manager = PowerUpManager(self.playfield)
        # fresh seed per run so every game has different obstacle layouts
        self.run_seed = random.randint(0, 2**31 - 1)
        self._load_obstacles_for_current_wave()
        self._ensure_player_not_in_obstacle()
        self.wave_manager.start_wave()
        self.reward_given_for_wave = False

        # title + pause UI
        self.title_screen = TitleScreen(
            self.SCREEN_W, self.SCREEN_H,
            self.title_font, self.button_font, self.small_font,
        )
        self.pause_menu = PauseMenu(
            self.SCREEN_W, self.SCREEN_H,
            self.pause_title_font, self.button_font, self.small_font,
        )

    @property
    def preset(self) -> FeelPreset:
        return self.presets[self.preset_idx]

    def _load_obstacles_for_current_wave(self) -> None:
        # procedural layout driven by run_seed + wave number — same seed + wave
        # always makes the same layout, so things stay stable across redraws
        is_boss = self.wave_manager.cfg.is_boss_wave
        obstacles = build_layout_for_wave(
            self.wave_manager.wave_number,
            self.playfield,
            seed=self.run_seed,
            is_boss_wave=is_boss,
        )
        self.wave_manager.obstacles = obstacles
        self.obstacles = obstacles

    def _ensure_player_not_in_obstacle(self) -> None:
        # if the player's spawn overlaps an obstacle, nudge them to a safe spot
        if not any(self.player_rect.colliderect(o.rect) for o in self.obstacles):
            return

        import math
        cx, cy = self.player_rect.center
        for radius in range(40, 400, 20):
            for angle_deg in range(0, 360, 30):
                a = math.radians(angle_deg)
                test = self.player_rect.copy()
                test.center = (int(cx + radius * math.cos(a)),
                               int(cy + radius * math.sin(a)))
                if not self.playfield.contains(test):
                    continue
                if any(test.colliderect(o.rect) for o in self.obstacles):
                    continue
                self.player_rect = test
                self.player_pos.update(self.player_rect.center)
                return

    def _cycle_control_scheme(self) -> None:
        schemes = list(ControlScheme)
        idx = schemes.index(self.control_scheme)
        self.control_scheme = schemes[(idx + 1) % len(schemes)]

    def _reset(self, keep_state: bool = False) -> None:
        self.player_pos = pygame.Vector2(self.playfield.center)
        self.player_vel = pygame.Vector2(0, 0)
        self.player_rect.center = self.player_pos
        self.last_move_dir = pygame.Vector2(1, 0)

        self.player_hp = self.PLAYER_MAX_HP
        self.damage_cooldown_left = 0.0
        self.death_anim_timer = 0.0

        if hasattr(self, 'presets') and len(self.presets) == 3:
            self.presets[0].ammo_max = 8
            self.presets[1].ammo_max = 12
            self.presets[2].ammo_max = 5

        self.projectiles.clear()
        self.ammo_current = self.preset.ammo_max
        self.fire_cooldown_left = 0.0
        self.reload_cooldown_left = 0.0
        self.is_reloading = False

        self.wave_manager = WaveManager(self.playfield)
        self.powerup_manager.reset()
        # new seed so restarting gives a whole new set of layouts
        self.run_seed = random.randint(0, 2**31 - 1)
        self._load_obstacles_for_current_wave()
        self._ensure_player_not_in_obstacle()
        self.wave_manager.start_wave()
        self.reward_given_for_wave = False

        if not keep_state:
            self.state = "play"

    # menu button dispatch (title + pause)
    def _handle_menu_action(self, action: str) -> None:
        if action == "start":
            self._reset(keep_state=False)  # fresh game
            self.state = "play"
        elif action == "resume":
            if self.state == "paused":
                self.state = "play"
        elif action == "restart":
            self._reset(keep_state=False)
            self.state = "play"
        elif action == "menu":
            self.state = "title"
            # reset so coming back from title is clean
            self._reset(keep_state=True)
            self.state = "title"
        elif action == "quit":
            self.should_quit = True

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.VIDEORESIZE:
            self._apply_window_size(event.w, event.h)
            return

        # mouse clicks (title + pause)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.state == "title":
                action = self.title_screen.handle_click(event.pos)
                if action:
                    self._handle_menu_action(action)
                return
            if self.state == "paused":
                action = self.pause_menu.handle_click(event.pos)
                if action:
                    self._handle_menu_action(action)
                return

        if event.type != pygame.KEYDOWN:
            return

        # escape toggles pause during play, backs out to title from other menus
        if event.key == pygame.K_ESCAPE:
            if self.state == "play":
                self.state = "paused"
            elif self.state == "paused":
                self.state = "play"
            elif self.state in {"game_over", "victory"}:
                self.state = "title"
            elif self.state == "title":
                self.should_quit = True
            return

        # p toggles pause during play
        if event.key == pygame.K_p:
            if self.state == "play":
                self.state = "paused"
                return
            if self.state == "paused":
                self.state = "play"
                return
            return

        if event.key == pygame.K_F1:
            self.debug = not self.debug
            return

        if event.key == pygame.K_c:
            self._cycle_control_scheme()
            return

        if event.key == pygame.K_r and event.mod & pygame.KMOD_CTRL:
            self._reset(keep_state=(self.state == "title"))
            return

        if self.state in {"title", "game_over", "victory"} and event.key in {pygame.K_RETURN, pygame.K_KP_ENTER}:
            self.state = "play"
            self._reset(keep_state=True)
            return

        if event.key == pygame.K_1:
            self.preset_idx = 0
            self._update_ammo_for_preset()
            return
        if event.key == pygame.K_2:
            self.preset_idx = 1
            self._update_ammo_for_preset()
            return
        if event.key == pygame.K_3:
            self.preset_idx = 2
            self._update_ammo_for_preset()
            return

        if self.state != "play":
            return

        if event.key == pygame.K_SPACE:
            self._try_shoot()
            return

        if event.key == pygame.K_r and not event.mod & pygame.KMOD_CTRL:
            self._try_reload()
            return

    def _scheme_keys(self) -> dict[str, set[int]]:
        if self.control_scheme == ControlScheme.WASD:
            return {"left": {pygame.K_a}, "right": {pygame.K_d}, "up": {pygame.K_w}, "down": {pygame.K_s}}
        if self.control_scheme == ControlScheme.IJKL:
            return {"left": {pygame.K_j}, "right": {pygame.K_l}, "up": {pygame.K_i}, "down": {pygame.K_k}}
        return {"left": {pygame.K_LEFT}, "right": {pygame.K_RIGHT}, "up": {pygame.K_UP}, "down": {pygame.K_DOWN}}

    def _read_direction(self) -> pygame.Vector2:
        keys = pygame.key.get_pressed()
        mapping = self._scheme_keys()

        x = 0
        y = 0
        if any(keys[k] for k in mapping["left"]):  x -= 1
        if any(keys[k] for k in mapping["right"]): x += 1
        if any(keys[k] for k in mapping["up"]):    y -= 1
        if any(keys[k] for k in mapping["down"]):  y += 1

        direction = pygame.Vector2(x, y)
        if direction.length_squared() > 0:
            direction = direction.normalize()
            self.last_move_dir.update(direction)

        # fallback to arrow keys even when the active scheme isn't ARROWS
        if direction.length_squared() == 0:
            x2 = 0
            y2 = 0
            if keys[pygame.K_LEFT]:  x2 -= 1
            if keys[pygame.K_RIGHT]: x2 += 1
            if keys[pygame.K_UP]:    y2 -= 1
            if keys[pygame.K_DOWN]:  y2 += 1
            direction2 = pygame.Vector2(x2, y2)
            if direction2.length_squared() > 0:
                direction2 = direction2.normalize()
                self.last_move_dir.update(direction2)
                return direction2

        return direction

    def _apply_bounds_player(self) -> None:
        # clamp player inside the playfield
        self.player_rect.clamp_ip(self.playfield)
        self.player_pos.update(self.player_rect.center)

    @staticmethod
    def _vector_to_direction(vec: pygame.Vector2) -> PlayerDirection:
        if vec.length_squared() == 0:
            return PlayerDirection.DOWN
        v = vec.normalize()
        if abs(v.x) > abs(v.y):
            return PlayerDirection.RIGHT if v.x > 0 else PlayerDirection.LEFT
        return PlayerDirection.DOWN if v.y > 0 else PlayerDirection.UP

    def _try_shoot(self) -> None:
        if self.is_reloading:
            return
        if self.fire_cooldown_left > 0:
            return
        if self.ammo_current <= 0:
            self._try_reload()
            return

        direction = pygame.Vector2(self.last_move_dir)
        if direction.length_squared() == 0:
            direction = pygame.Vector2(1, 0)
        direction = direction.normalize()

        self.player_sprite_animator.trigger_shoot(self._vector_to_direction(direction))

        projectile = Projectile(
            position=pygame.Vector2(self.player_pos),
            velocity=direction * self.preset.projectile_speed,
        )
        self.projectiles.append(projectile)

        self.ammo_current -= 1
        # rapid-fire power-up reduces effective fire cooldown
        self.fire_cooldown_left = self.preset.fire_rate * self.powerup_manager.fire_rate_multiplier()

    def _try_reload(self) -> None:
        if self.is_reloading:
            return
        if self.ammo_current >= self.preset.ammo_max:
            return

        self.is_reloading = True
        self.reload_cooldown_left = self.preset.reload_time
        self.player_sprite_animator.set_weapon_reloading(
            True,
            self._vector_to_direction(self.last_move_dir),
        )

    def _update_ammo_for_preset(self) -> None:
        self.ammo_current = self.preset.ammo_max
        self.is_reloading = False
        self.player_sprite_animator.set_weapon_reloading(False)
        self.reload_cooldown_left = 0.0

    # callback for power-up pickups
    def _on_powerup_pickup(self, action: str, value) -> None:
        if action == "heal":
            self.player_hp = min(self.PLAYER_MAX_HP, self.player_hp + int(value))
        elif action == "ammo_refill":
            self.ammo_current = self.preset.ammo_max
            self.is_reloading = False
            self.player_sprite_animator.set_weapon_reloading(False)
            self.reload_cooldown_left = 0.0

    # callback when wave_manager kills an enemy
    def _on_enemy_killed(self, enemy) -> None:
        self.powerup_manager.maybe_drop_from_enemy(enemy.position, enemy.is_boss, self.obstacles)

    def update(self, dt: float) -> None:
        # animate the title screen even when not playing
        if self.state == "title":
            self.title_screen.update(dt)
            return

        # death animation phase before game-over screen
        if self.state == "dying":
            self.player_sprite_animator.set_animation("death")
            self.player_sprite_animator.update(dt)
            self.death_anim_timer = max(0.0, self.death_anim_timer - dt)
            if self.death_anim_timer <= 0:
                self.state = "game_over"
            return

        # pause + game over + victory: no simulation
        if self.state != "play":
            return

        if self.damage_cooldown_left > 0:
            self.damage_cooldown_left = max(0.0, self.damage_cooldown_left - dt)

        if self.fire_cooldown_left > 0:
            self.fire_cooldown_left = max(0.0, self.fire_cooldown_left - dt)

        if self.is_reloading:
            self.reload_cooldown_left -= dt
            if self.reload_cooldown_left <= 0:
                self.ammo_current = self.preset.ammo_max
                self.is_reloading = False
                self.player_sprite_animator.set_weapon_reloading(False)
                self.reload_cooldown_left = 0.0

        if self.ammo_current <= 0 and not self.is_reloading:
            self._try_reload()

        p = self.preset
        speed_mult = self.powerup_manager.speed_multiplier()

        # top-down movement
        direction = self._read_direction()

        self.player_vel += direction * p.accel * dt

        if direction.length_squared() == 0:
            decel = p.friction * p.max_speed
            self.player_vel.x = self._approach_zero(self.player_vel.x, decel, dt)
            self.player_vel.y = self._approach_zero(self.player_vel.y, decel, dt)

        cap = p.max_speed * speed_mult
        if self.player_vel.length() > cap:
            self.player_vel.scale_to_length(cap)

        prev_rect = self.player_rect.copy()
        self.player_pos += self.player_vel * dt
        self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))

        # obstacle collision — slide along walls
        resolved = resolve_rect_collision(self.player_rect, self.obstacles, prev_rect)
        if resolved.x != self.player_rect.x:
            self.player_vel.x = 0
        if resolved.y != self.player_rect.y:
            self.player_vel.y = 0
        self.player_rect = resolved
        self.player_pos.update(self.player_rect.center)

        self._apply_bounds_player()

        # update projectiles: motion, out-of-bounds, obstacle hits
        surviving_projectiles = []
        for projectile in self.projectiles:
            projectile.update(dt)
            if not self.playfield.collidepoint(projectile.position.x, projectile.position.y):
                continue
            if projectile_hits_obstacle(projectile.position, self.obstacles):
                continue  # projectile absorbed by obstacle
            surviving_projectiles.append(projectile)
        self.projectiles = surviving_projectiles

        # damage calc: heavy cannon × wave-5 boost × damage-boost power-up
        proj_damage = 2.0 if self.preset.name == "HEAVY-CANNON" else 1.0
        if self.wave_manager.wave_number >= 5:
            proj_damage *= 1.25
        proj_damage *= self.powerup_manager.damage_multiplier()

        self.projectiles = self.wave_manager.check_projectile_hits(
            self.projectiles, damage=proj_damage, impulse=200.0,
        )

        self.wave_manager.update(dt, self.player_pos, on_enemy_killed=self._on_enemy_killed)
        self.powerup_manager.update(dt, self.player_rect, self._on_powerup_pickup, self.obstacles)

        if self.wave_manager.wave_complete:
            if not getattr(self, "reward_given_for_wave", False) and not self.wave_manager.all_waves_done:
                self.reward_given_for_wave = True
                for p in self.presets:
                    p.ammo_max += 3
                self.ammo_current = min(self.preset.ammo_max, self.ammo_current + 3)

            self.wave_manager.transition_timer -= dt
            if self.wave_manager.transition_timer <= 0:
                still_going = self.wave_manager.advance_wave()
                if not still_going:
                    self.state = "victory"
                else:
                    self.reward_given_for_wave = False
                    # load fresh obstacle layout for new wave
                    self._load_obstacles_for_current_wave()
                    self._ensure_player_not_in_obstacle()

        if self.wave_manager.all_waves_done:
            self.state = "victory"

        # update player sprite animation based on movement state
        if self.player_hp > 0:
            # determine direction from last_move_dir
            direction = self._vector_to_direction(self.last_move_dir)

            # check if player is moving
            is_moving = self.player_vel.length_squared() > 100

            if is_moving:
                self.player_sprite_animator.set_animation("run", direction)
            else:
                self.player_sprite_animator.set_animation("idle")

            self.player_sprite_animator.update(dt)
        else:
            # player is dead
            self.player_sprite_animator.set_animation("death")
            self.player_sprite_animator.update(dt)

        # enemy contact damage (shield absorbs first)
        hit_rect = self.player_rect
        if self.damage_cooldown_left <= 0:
            for enemy in self.wave_manager.enemies:
                if enemy.alive and enemy.rect.colliderect(hit_rect):
                    if self.powerup_manager.absorb_shield_hit():
                        # shield ate the hit — still apply i-frames so we don't drain all stacks in one overlap
                        self.damage_cooldown_left = self.DAMAGE_COOLDOWN
                        break

                    if enemy.is_boss:
                        damage = 10.0
                    else:
                        wave_num = self.wave_manager.wave_number
                        wave_scaling = 1.5 * (wave_num - 1)
                        damage = enemy.contact_damage * wave_scaling
                    self.player_hp -= damage
                    self.damage_cooldown_left = self.DAMAGE_COOLDOWN
                    if self.player_hp <= 0:
                        self.player_hp = 0
                        self.death_anim_timer = self.DEATH_ANIM_DURATION
                        self.state = "dying"
                    break

    def _draw_health_bar(self) -> None:
        bar_x = 14
        bar_y = 4
        bar_w = 200
        bar_h = 10

        hp_ratio = max(0, self.player_hp / self.PLAYER_MAX_HP)

        pygame.draw.rect(self.screen, (40, 10, 10), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        fill_w = int(bar_w * hp_ratio)
        if hp_ratio > 0.6:
            bar_color = (80, 200, 80)
        elif hp_ratio > 0.3:
            bar_color = (220, 180, 40)
        else:
            bar_color = (220, 50, 50)
        if fill_w > 0:
            pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, fill_w, bar_h), border_radius=3)
        pygame.draw.rect(self.screen, (180, 180, 180), (bar_x, bar_y, bar_w, bar_h), width=1, border_radius=3)
        display_hp = max(0.0, float(self.player_hp))
        hp_label = self.font.render(f"HP {display_hp:.1f}/{self.PLAYER_MAX_HP}", True, (216, 222, 233))
        self.screen.blit(hp_label, (bar_x + bar_w + 8, bar_y - 2))

    def _draw_hud(self) -> None:
        pygame.draw.rect(self.screen, (46, 52, 64), pygame.Rect(0, 0, self.SCREEN_W, self.HUD_H))

        self._draw_health_bar()

        # active power-up effects shown just right of the HP bar
        self.powerup_manager.draw_hud_effects(self.screen, self.small_font, 340, 4)

        left = (
            f"Scheme: {self.control_scheme.value}   "
            f"Weapon: {self.preset.name}   "
            f"Wave: {self.wave_manager.wave_number}/{self.wave_manager.total_waves}"
        )

        if self.is_reloading:
            right = f"RELOADING {self.reload_cooldown_left: .1f}s"
        else:
            right = f"Ammo: {self.ammo_current}/{self.preset.ammo_max}"

        left_surf = self.font.render(left, True, (216, 222, 233))
        right_surf = self.font.render(right, True, (216, 222, 233))

        self.screen.blit(left_surf, (14, 20))
        self.screen.blit(right_surf, (self.SCREEN_W - right_surf.get_width() - 14, 20))

    def _draw_debug(self) -> None:
        p = self.preset
        lines = [
            f"vel=({self.player_vel.x:0.1f}, {self.player_vel.y:0.1f})",
            f"accel={p.accel:0.1f}  friction={p.friction:0.1f}  max={p.max_speed:0.1f}",
            f"last_dir=({self.last_move_dir.x:0.2f},{self.last_move_dir.y:0.2f})",
            f"powerups_on_field={len(self.powerup_manager.powerups)}  obstacles={len(self.obstacles)}",
            f"run_seed={self.run_seed}",
        ]

        x = 14
        y = self.HUD_H + 10
        for line in lines:
            surf = self.font.render(line, True, (229, 233, 240))
            self.screen.blit(surf, (x, y))
            y += 18

    def _draw_center_message(self, title: str, subtitle: str) -> None:
        title_surf = self.big_font.render(title, True, (236, 239, 244))
        sub_surf = self.font.render(subtitle, True, (216, 222, 233))

        self.screen.blit(title_surf,
            (self.SCREEN_W // 2 - title_surf.get_width() // 2, self.SCREEN_H // 2 - 60))
        self.screen.blit(sub_surf,
            (self.SCREEN_W // 2 - sub_surf.get_width() // 2, self.SCREEN_H // 2))

    def _draw_pickup_toast(self) -> None:
        pm = self.powerup_manager
        if pm.last_pickup_timer <= 0:
            return
        alpha = min(1.0, pm.last_pickup_timer / 1.5)
        text = f"+{pm.last_pickup_text}"
        surf = self.big_font.render(text, True, pm.last_pickup_color)
        # ease up a bit
        lift = int((1.0 - alpha) * 30)
        self.screen.blit(surf,
            (self.SCREEN_W // 2 - surf.get_width() // 2,
             self.HUD_H + 30 - lift))

    def _draw_ground_detail(self) -> None:
        # pebbles and grass tufts scattered across the graveyard floor.
        # seeded by run_seed so they stay put between frames.
        import random as _r
        rng = _r.Random(self.run_seed ^ 0xA11CE)
        pf = self.playfield

        # small pebbles
        for _ in range(40):
            px = rng.randint(pf.left + 8, pf.right - 8)
            py = rng.randint(pf.top + 8, pf.bottom - 8)
            shade = rng.choice([(58, 52, 46), (68, 62, 54), (48, 42, 38)])
            pygame.draw.rect(self.screen, shade, (px, py, 3, 2))

        # grass tufts
        for _ in range(22):
            gx = rng.randint(pf.left + 10, pf.right - 10)
            gy = rng.randint(pf.top + 10, pf.bottom - 10)
            tuft = rng.choice([(70, 88, 54), (58, 78, 48), (80, 100, 62)])
            pygame.draw.line(self.screen, tuft, (gx, gy), (gx - 1, gy - 3), 1)
            pygame.draw.line(self.screen, tuft, (gx + 1, gy), (gx + 1, gy - 4), 1)
            pygame.draw.line(self.screen, tuft, (gx + 2, gy), (gx + 3, gy - 3), 1)

        # occasional dead leaves / dirt patches
        for _ in range(8):
            dx = rng.randint(pf.left + 20, pf.right - 20)
            dy = rng.randint(pf.top + 20, pf.bottom - 20)
            patch = pygame.Rect(dx, dy, rng.randint(10, 22), rng.randint(6, 12))
            pygame.draw.ellipse(self.screen, (32, 28, 24), patch)

    def _draw_gameplay(self) -> None:
        # draws the playfield + HUD — used by both play and paused states
        self.screen.fill((14, 12, 16))

        # graveyard dirt ground
        pygame.draw.rect(self.screen, (42, 38, 34), self.playfield)
        # darker fence-like border around the yard
        pygame.draw.rect(self.screen, (26, 22, 20), self.playfield, width=3)

        # scatter pebbles and grass tufts — seeded by run_seed so they don't jitter
        self._draw_ground_detail()

        # obstacles (gravestones) drawn before enemies so enemies/player visually appear "on top"
        draw_obstacles(self.screen, self.obstacles)

        # power-ups under enemies (feels right — enemies can step over them visually)
        self.powerup_manager.draw(self.screen, self.small_font)

        self.wave_manager.draw(self.screen, self.font)

        for projectile in self.projectiles:
            projectile.draw(self.screen)

        if self.damage_cooldown_left > 0 and int(self.damage_cooldown_left * 10) % 2 == 0:
            player_color = (255, 80, 80)
        else:
            player_color = (136, 192, 208)

        # draw player sprite if available, otherwise fallback to colored rectangle
        player_frame = self.player_sprite_animator.get_current_frame()
        if player_frame:
            weapon_frame, fire_frame = self.player_sprite_animator.get_weapon_frames()
            facing = self._vector_to_direction(self.last_move_dir)
            weapon_offsets = {
                PlayerDirection.UP: (0, -10),
                PlayerDirection.DOWN: (0, 10),
                PlayerDirection.LEFT: (-11, 1),
                PlayerDirection.RIGHT: (11, 1),
            }
            fire_offsets = {
                PlayerDirection.UP: (0, -17),
                PlayerDirection.DOWN: (0, 17),
                PlayerDirection.LEFT: (-18, 1),
                PlayerDirection.RIGHT: (18, 1),
            }

            # facing up: draw weapon under the player body so it doesn't cover the head
            if weapon_frame and facing == PlayerDirection.UP:
                wx, wy = weapon_offsets[facing]
                weapon_dest = weapon_frame.get_rect(
                    center=(self.player_rect.centerx + wx, self.player_rect.centery + wy)
                )
                self.screen.blit(weapon_frame, weapon_dest.topleft)

            player_dest = player_frame.get_rect(center=self.player_rect.center)
            self.screen.blit(player_frame, player_dest.topleft)

            if weapon_frame and facing != PlayerDirection.UP:
                wx, wy = weapon_offsets[facing]
                weapon_dest = weapon_frame.get_rect(
                    center=(self.player_rect.centerx + wx, self.player_rect.centery + wy)
                )
                self.screen.blit(weapon_frame, weapon_dest.topleft)

            if fire_frame and facing == PlayerDirection.UP:
                fx, fy = fire_offsets[facing]
                fire_dest = fire_frame.get_rect(
                    center=(self.player_rect.centerx + fx, self.player_rect.centery + fy)
                )
                self.screen.blit(fire_frame, fire_dest.topleft)

            # re-draw player body on top when facing up so muzzle flash stays behind head
            if facing == PlayerDirection.UP:
                self.screen.blit(player_frame, player_dest.topleft)

            if fire_frame and facing != PlayerDirection.UP:
                fx, fy = fire_offsets[facing]
                fire_dest = fire_frame.get_rect(
                    center=(self.player_rect.centerx + fx, self.player_rect.centery + fy)
                )
                self.screen.blit(fire_frame, fire_dest.topleft)
        else:
            pygame.draw.rect(self.screen, player_color, self.player_rect, border_radius=6)

        # shield ring on top of player
        self.powerup_manager.draw_shield_ring(self.screen, self.player_rect.center)

        self._draw_hud()
        self._draw_pickup_toast()

        if self.debug:
            self._draw_debug()

        if self.wave_manager.wave_complete and not self.wave_manager.all_waves_done:
            if self.wave_manager.wave_number == 4:
                msg1 = f"Wave {self.wave_manager.wave_number} Clear! +3 Max Ammo! +25% Power!"
            else:
                msg1 = f"Wave {self.wave_manager.wave_number} Clear! +3 Max Ammo!"

            self._draw_center_message(
                msg1,
                f"Next wave in {self.wave_manager.transition_timer:.1f}s...",
            )

        if self.state == "victory":
            self._draw_center_message("YOU WIN!", f"Kills: {self.wave_manager.total_kills}   ENTER to restart")

        if self.state == "game_over":
            self._draw_center_message("GAME OVER", f"Kills: {self.wave_manager.total_kills}   ENTER to restart")

    def draw(self) -> None:
        if self.state == "title":
            self.title_screen.draw(self.screen)
            return

        # always draw the gameplay scene first
        self._draw_gameplay()

        # overlay the pause menu on top
        if self.state == "paused":
            self.pause_menu.draw(self.screen)