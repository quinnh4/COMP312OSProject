from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from input_control_feel.wave_manager import WaveManager
from input_control_feel.powerup import PowerUpManager
from input_control_feel.obstacle import (
    build_layout_for_wave, resolve_rect_collision, projectile_hits_obstacle, draw_obstacles
)
from input_control_feel.title_screen import TitleScreen, PauseMenu
from input_control_feel.sprite_manager import PlayerSpriteAnimator, PlayerDirection

import pygame


class BoundaryMode(str, Enum):
    CLAMP = "clamp"
    WRAP = "wrap"
    BOUNCE = "bounce"


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

    # Top-down feel
    accel: float
    max_speed: float
    friction: float

    # Platformer feel
    gravity: float
    jump_speed: float

    # shooting feel
    projectile_speed: float
    fire_rate: float
    ammo_max: int
    reload_time: float


class Game:
    fps = 60

    SCREEN_W, SCREEN_H = 960, 540
    HUD_H = 54
    PLAYFIELD_PADDING = 10

    PLAYER_MAX_HP = 100
    DAMAGE_COOLDOWN = 0.5
    DEATH_ANIM_DURATION = 0.6

    PLAYER_SIZE = 32

    DASH_IMPULSE = 760.0
    DASH_COOLDOWN = 0.65

    @staticmethod
    def _approach_zero(value: float, decel: float, dt: float) -> float:
        step = decel * dt
        if value > 0:
            return max(0.0, value - step)
        if value < 0:
            return min(0.0, value + step)
        return 0.0

    def __init__(self) -> None:
        self.screen = pygame.display.set_mode((self.SCREEN_W, self.SCREEN_H))
        self.font = pygame.font.SysFont(None, 22)
        self.small_font = pygame.font.SysFont(None, 16)
        self.big_font = pygame.font.SysFont(None, 48)
        # chunky pixel-ish font for the title and buttons
        self.title_font = pygame.font.SysFont("couriernew,consolas,monospace", 56, bold=True)
        self.pause_title_font = pygame.font.SysFont("couriernew,consolas,monospace", 42, bold=True)
        self.button_font = pygame.font.SysFont("couriernew,consolas,monospace", 22, bold=True)

        self.screen_rect = pygame.Rect(0, 0, self.SCREEN_W, self.SCREEN_H)
        self.playfield = pygame.Rect(
            self.PLAYFIELD_PADDING,
            self.HUD_H + self.PLAYFIELD_PADDING,
            self.SCREEN_W - 2 * self.PLAYFIELD_PADDING,
            self.SCREEN_H - self.HUD_H - 2 * self.PLAYFIELD_PADDING,
        )

        self.boundary_mode = BoundaryMode.CLAMP
        self.platformer_mode = False
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

        self.on_ground = True
        self.jump_requested = False

        self.control_scheme = ControlScheme.WASD
        self.debug = False

        self.presets = [
            FeelPreset("BALANCED",    2500.0, 480.0, 10.0, 2200.0, 800.0, 950.0,  0.25, 8,  2.0),
            FeelPreset("RAPID-FIRE",  3200.0, 520.0, 14.0, 2600.0, 860.0, 800.0,  0.15, 12, 1.5),
            FeelPreset("HEAVY-CANNON", 1900.0, 400.0, 6.0,  1700.0, 760.0, 1200.0, 0.5,  5,  2.5),
        ]
        self.preset_idx = 0

        self.dash_cooldown_left = 0.0
        self.last_move_dir = pygame.Vector2(1, 0)
        
        # Player sprite animator
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
        obstacles = build_layout_for_wave(self.wave_manager.wave_number, self.playfield)
        self.wave_manager.obstacles = obstacles
        self.obstacles = obstacles

    def _ensure_player_not_in_obstacle(self) -> None:
        """If the player's spawn position overlaps an obstacle, push them to a safe nearby spot."""
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

    def _cycle_boundary_mode(self) -> None:
        modes = list(BoundaryMode)
        idx = modes.index(self.boundary_mode)
        self.boundary_mode = modes[(idx + 1) % len(modes)]

    def _cycle_control_scheme(self) -> None:
        schemes = list(ControlScheme)
        idx = schemes.index(self.control_scheme)
        self.control_scheme = schemes[(idx + 1) % len(schemes)]

    def _reset(self, keep_state: bool = False) -> None:
        self.player_pos = pygame.Vector2(self.playfield.center)
        self.player_vel = pygame.Vector2(0, 0)
        self.player_rect.center = self.player_pos
        self.on_ground = True
        self.jump_requested = False
        self.dash_cooldown_left = 0.0
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

        # escape now toggles pause during play instead of hard-quitting,
        # and backs out to title from paused / game_over / victory
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

        # p toggles pause during play — keeps the old platformer-toggle behavior elsewhere
        if event.key == pygame.K_p:
            if self.state == "play":
                self.state = "paused"
                return
            if self.state == "paused":
                self.state = "play"
                return
            # on title / game over / victory keep the old platformer toggle
            self.platformer_mode = not self.platformer_mode
            if self.state != "title":
                self._reset(keep_state=True)
            return

        if event.key == pygame.K_F1:
            self.debug = not self.debug
            return

        if event.key == pygame.K_TAB:
            self._cycle_boundary_mode()
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

        if event.key in {pygame.K_LSHIFT, pygame.K_RSHIFT}:
            self._try_dash()
            return

        if event.key == pygame.K_SPACE:
            self._try_shoot()
            return

        if event.key == pygame.K_r and not event.mod & pygame.KMOD_CTRL:
            self._try_reload()
            return

        if self.platformer_mode and event.key in {pygame.K_UP, pygame.K_w, pygame.K_SPACE, pygame.K_i}:
            self.jump_requested = True

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

    def _read_horizontal(self) -> float:
        keys = pygame.key.get_pressed()
        mapping = self._scheme_keys()

        x = 0
        if any(keys[k] for k in mapping["left"]) or keys[pygame.K_LEFT]:
            x -= 1
        if any(keys[k] for k in mapping["right"]) or keys[pygame.K_RIGHT]:
            x += 1

        if x != 0:
            self.last_move_dir.update(pygame.Vector2(x, 0).normalize())

        return float(x)

    def _apply_platformer_vertical_bounds(self) -> None:
        if self.player_rect.bottom >= self.playfield.bottom:
            self.player_rect.bottom = self.playfield.bottom
            self.player_vel.y = 0
            self.on_ground = True

        if self.player_rect.top < self.playfield.top:
            self.player_rect.top = self.playfield.top
            if self.player_vel.y < 0:
                self.player_vel.y = 0

        self.player_pos.update(self.player_rect.center)

    def _apply_bounds_player(self) -> None:
        if self.boundary_mode == BoundaryMode.CLAMP:
            self.player_rect.clamp_ip(self.playfield)
            self.player_pos.update(self.player_rect.center)
            return

        if self.boundary_mode == BoundaryMode.WRAP:
            if self.player_rect.right < self.playfield.left:
                self.player_rect.left = self.playfield.right
            elif self.player_rect.left > self.playfield.right:
                self.player_rect.right = self.playfield.left

            if self.player_rect.bottom < self.playfield.top:
                self.player_rect.top = self.playfield.bottom
            elif self.player_rect.top > self.playfield.bottom:
                self.player_rect.bottom = self.playfield.top

            self.player_pos.update(self.player_rect.center)
            return

        # BOUNCE
        bounced = False
        if self.player_rect.left < self.playfield.left:
            self.player_rect.left = self.playfield.left
            self.player_vel.x *= -1
            bounced = True
        elif self.player_rect.right > self.playfield.right:
            self.player_rect.right = self.playfield.right
            self.player_vel.x *= -1
            bounced = True

        if self.player_rect.top < self.playfield.top:
            self.player_rect.top = self.playfield.top
            self.player_vel.y *= -1
            bounced = True
        elif self.player_rect.bottom > self.playfield.bottom:
            self.player_rect.bottom = self.playfield.bottom
            self.player_vel.y *= -1
            bounced = True

        if bounced:
            self.player_pos.update(self.player_rect.center)

    def _try_dash(self) -> None:
        if self.dash_cooldown_left > 0:
            return

        dash_dir = pygame.Vector2(self.last_move_dir)
        if dash_dir.length_squared() == 0:
            dash_dir = pygame.Vector2(1, 0)
        dash_dir = dash_dir.normalize()

        self.player_vel += dash_dir * self.DASH_IMPULSE
        self.dash_cooldown_left = self.DASH_COOLDOWN

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

    def _update_ammo_for_preset(self) -> None:
        self.ammo_current = self.preset.ammo_max
        self.is_reloading = False
        self.reload_cooldown_left = 0.0

    # --- callback for power-up pickups ---
    def _on_powerup_pickup(self, action: str, value) -> None:
        if action == "heal":
            self.player_hp = min(self.PLAYER_MAX_HP, self.player_hp + int(value))
        elif action == "ammo_refill":
            self.ammo_current = self.preset.ammo_max
            self.is_reloading = False
            self.reload_cooldown_left = 0.0

    # --- callback when wave_manager kills an enemy ---
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

        if self.dash_cooldown_left > 0:
            self.dash_cooldown_left = max(0.0, self.dash_cooldown_left - dt)

        if self.damage_cooldown_left > 0:
            self.damage_cooldown_left = max(0.0, self.damage_cooldown_left - dt)

        if self.fire_cooldown_left > 0:
            self.fire_cooldown_left = max(0.0, self.fire_cooldown_left - dt)

        if self.is_reloading:
            self.reload_cooldown_left -= dt
            if self.reload_cooldown_left <= 0:
                self.ammo_current = self.preset.ammo_max
                self.is_reloading = False
                self.reload_cooldown_left = 0.0

        if self.ammo_current <= 0 and not self.is_reloading:
            self._try_reload()

        p = self.preset
        speed_mult = self.powerup_manager.speed_multiplier()

        if self.platformer_mode:
            x = self._read_horizontal()

            self.player_vel.x += x * p.accel * dt
            if x == 0:
                self.player_vel.x = self._approach_zero(
                    self.player_vel.x, p.friction * p.max_speed, dt,
                )
            cap = p.max_speed * speed_mult
            self.player_vel.x = max(-cap, min(cap, self.player_vel.x))

            if self.jump_requested and self.on_ground:
                self.player_vel.y = -p.jump_speed
                self.on_ground = False
            self.jump_requested = False

            self.player_vel.y += p.gravity * dt

            prev_rect = self.player_rect.copy()
            self.player_pos += self.player_vel * dt
            self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))

            # obstacle collision in platformer: land on tops, block sides
            resolved = resolve_rect_collision(self.player_rect, self.obstacles, prev_rect)
            if resolved.bottom < self.player_rect.bottom:
                self.on_ground = True
                self.player_vel.y = 0
            if resolved.x != self.player_rect.x:
                self.player_vel.x = 0
            self.player_rect = resolved
            self.player_pos.update(self.player_rect.center)

            prev_y = self.player_rect.centery
            self._apply_bounds_player()
            self.player_rect.centery = prev_y
            self.player_pos.y = prev_y

            self._apply_platformer_vertical_bounds()
        else:
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

            # obstacle collision (top-down): slide along walls
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

        # Update player sprite animation based on movement state
        if self.player_hp > 0:
            # Determine direction from last_move_dir
            if self.last_move_dir.length_squared() > 0:
                normalized_dir = self.last_move_dir.normalize()
                # Determine which direction the player is facing
                if abs(normalized_dir.x) > abs(normalized_dir.y):
                    direction = PlayerDirection.RIGHT if normalized_dir.x > 0 else PlayerDirection.LEFT
                else:
                    direction = PlayerDirection.DOWN if normalized_dir.y > 0 else PlayerDirection.UP
            else:
                direction = PlayerDirection.DOWN
            
            # Check if player is moving
            is_moving = self.player_vel.length_squared() > 100
            
            if is_moving:
                self.player_sprite_animator.set_animation("run", direction)
            else:
                self.player_sprite_animator.set_animation("idle")
            
            self.player_sprite_animator.update(dt)
        else:
            # Player is dead
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

        control = "PLATFORMER" if self.platformer_mode else "TOPDOWN"
        left = (
            f"Bounds: {self.boundary_mode.value.upper()}   Control: {control}   "
            f"Scheme: {self.control_scheme.value}   Weapon: {self.preset.name}   "
            f"Wave: {self.wave_manager.wave_number}/{self.wave_manager.total_waves}"
        )

        dash = "READY" if self.dash_cooldown_left <= 0 else f"CD {self.dash_cooldown_left:0.2f}s"

        if self.is_reloading:
            ammo_display = f"RELOADING {self.reload_cooldown_left: .1f}s"
        else:
            ammo_display = f"Ammo: {self.ammo_current}/{self.preset.ammo_max}"

        right = f"Dash: {dash}   {ammo_display}"

        left_surf = self.font.render(left, True, (216, 222, 233))
        right_surf = self.font.render(right, True, (216, 222, 233))

        self.screen.blit(left_surf, (14, 20))
        self.screen.blit(right_surf, (self.SCREEN_W - right_surf.get_width() - 14, 20))

    def _draw_debug(self) -> None:
        p = self.preset
        lines = [
            f"vel=({self.player_vel.x:0.1f}, {self.player_vel.y:0.1f})",
            f"accel={p.accel:0.1f}  friction={p.friction:0.1f}  max={p.max_speed:0.1f}",
            f"gravity={p.gravity:0.1f}  jump={p.jump_speed:0.1f}",
            f"last_dir=({self.last_move_dir.x:0.2f},{self.last_move_dir.y:0.2f})",
            f"powerups_on_field={len(self.powerup_manager.powerups)}  obstacles={len(self.obstacles)}",
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

    def _draw_gameplay(self) -> None:
        # draws the playfield + HUD — used by both play and paused states
        self.screen.fill((20, 24, 30))

        pygame.draw.rect(self.screen, (10, 12, 16), self.playfield)
        pygame.draw.rect(self.screen, (76, 86, 106), self.playfield, width=2)

        # obstacles drawn before enemies so enemies/player visually appear "on top"
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

        # Draw player sprite if available, otherwise fallback to colored rectangle
        player_frame = self.player_sprite_animator.get_current_frame()
        if player_frame:
            player_dest = player_frame.get_rect(center=self.player_rect.center)
            self.screen.blit(player_frame, player_dest.topleft)
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