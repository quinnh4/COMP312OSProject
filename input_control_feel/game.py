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

        # sound effects + music — missing files are skipped silently
        self._init_audio()
        self._play_music("menu")

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

        self.shake_timer = 0.0
        self.red_flash_timer = 0.0
        self.victory_fade_timer = 0.0

        self.control_scheme = ControlScheme.WASD
        self.debug = False
        self.invincible = False   # dev toggle — press I in-game

        # name, accel, max_speed, friction, projectile_speed, fire_rate, ammo_max, reload_time
        # rapid-fire trades power for volume, heavy-cannon trades speed for punch
        self.presets = [
            FeelPreset("BALANCED",     2400.0, 440.0, 10.0, 950.0,  0.28, 10, 2.0),
            FeelPreset("RAPID-FIRE",   3200.0, 560.0, 14.0, 800.0,  0.10, 18, 1.3),
            FeelPreset("HEAVY-CANNON", 1500.0, 280.0, 6.0,  1300.0, 0.70, 4,  3.0),
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
        if not any(self.player_rect.colliderect(o.hit_rect) for o in self.obstacles):
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
                if any(test.colliderect(o.hit_rect) for o in self.obstacles):
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
            self.presets[0].ammo_max = 10
            self.presets[1].ammo_max = 18
            self.presets[2].ammo_max = 4

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

        if event.key == pygame.K_i:
            self.invincible = not self.invincible
            print(f"[dev] invincible={'ON' if self.invincible else 'OFF'}")
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
        if self.control_scheme == ControlScheme.ARROWS:
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
        self._play_sfx("gun")

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

    # audio — loaded once, missing files are skipped
    def _init_audio(self) -> None:
        import os
        try:
            pygame.mixer.init()
        except pygame.error as e:
            print(f"[audio] mixer init failed: {e}")
            self.sfx = {}
            self.music_paths = {"menu": None, "level": None}
            self.current_music = None
            return

        sfx_files = {
            "gun":          "input_control_feel/sounds/gun.mp3",
            "zombie_death": "input_control_feel/sounds/zombie_death.mp3",
            "boss_death":   "input_control_feel/sounds/boss_zombie.mp3",
            "death":        "input_control_feel/sounds/death.mp3",
            "hurt":         "input_control_feel/sounds/hurt.mp3",
            "powerup":      "input_control_feel/sounds/powerup.mp3",
        }
        self.sfx: dict[str, pygame.mixer.Sound] = {}
        for key, path in sfx_files.items():
            if not os.path.exists(path):
                print(f"[audio] missing: {path}")
                continue
            try:
                snd = pygame.mixer.Sound(path)
                self.sfx[key] = snd
            except pygame.error as e:
                print(f"[audio] failed to load {path}: {e}")

        # per-sound volume tweaks — gun fires a lot so keep it quieter
        if "gun" in self.sfx:
            self.sfx["gun"].set_volume(0.35)
        if "zombie_death" in self.sfx:
            self.sfx["zombie_death"].set_volume(0.6)
        if "boss_death" in self.sfx:
            self.sfx["boss_death"].set_volume(0.9)
        if "death" in self.sfx:
            self.sfx["death"].set_volume(0.8)
        if "hurt" in self.sfx:
            self.sfx["hurt"].set_volume(0.7)
        if "powerup" in self.sfx:
            self.sfx["powerup"].set_volume(0.7)

        # music tracks — menu plays on title/pause, level plays during gameplay
        menu_path = "input_control_feel/music/main_menu.mp3"
        level_path = "input_control_feel/music/level_music.mp3"
        self.music_paths = {
            "menu":  menu_path if os.path.exists(menu_path) else None,
            "level": level_path if os.path.exists(level_path) else None,
        }
        for label, path in (("menu", menu_path), ("level", level_path)):
            if self.music_paths[label] is None:
                print(f"[audio] missing: {path}")
        self.current_music: str | None = None

    def _play_sfx(self, key: str) -> None:
        snd = self.sfx.get(key) if hasattr(self, "sfx") else None
        if snd:
            snd.play()

    def _play_music(self, track: str) -> None:
        # track is "menu" or "level" — swap only when needed, loop forever
        if self.current_music == track:
            return
        path = self.music_paths.get(track)
        if not path:
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0.4)
            pygame.mixer.music.play(-1)
            self.current_music = track
        except pygame.error as e:
            print(f"[audio] music play failed: {e}")

    def _stop_music(self) -> None:
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        self.current_music = None

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
        self._play_sfx("boss_death" if enemy.is_boss else "zombie_death")
        self.powerup_manager.maybe_drop_from_enemy(enemy.position, enemy.is_boss, self.obstacles)

    def update(self, dt: float) -> None:
        # menu track on title/pause, level track during play, stop on death/end screens
        if self.state in ("title", "paused"):
            self._play_music("menu")
        elif self.state == "play":
            self._play_music("level")
        else:
            self._stop_music()

        # animate the title screen even when not playing
        if self.state == "title":
            self.title_screen.update(dt)
            return

        # death animation phase before game-over screen
        if self.state == "dying":
            self.shake_timer = max(0.0, self.shake_timer - dt)
            self.red_flash_timer = max(0.0, self.red_flash_timer - dt)
            self.player_sprite_animator.set_animation("death")
            self.player_sprite_animator.update(dt)
            self.death_anim_timer = max(0.0, self.death_anim_timer - dt)
            if self.death_anim_timer <= 0:
                self.state = "game_over"
            return

        # pause + game over + victory: no simulation
        if self.state != "play":
            if self.state == "victory":
                self.victory_fade_timer = min(2.0, self.victory_fade_timer + dt)
            return

        self.shake_timer = max(0.0, self.shake_timer - dt)
        self.red_flash_timer = max(0.0, self.red_flash_timer - dt)

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

        # damage calc: weapon base × wave-5 boost × damage-boost power-up
        if self.preset.name == "HEAVY-CANNON":
            proj_damage = 2.0
        elif self.preset.name == "RAPID-FIRE":
            proj_damage = 0.6
        else:
            proj_damage = 1.0
        if self.wave_manager.wave_number >= 5:
            proj_damage *= 1.25
        proj_damage *= self.powerup_manager.damage_multiplier()

        self.projectiles = self.wave_manager.check_projectile_hits(
            self.projectiles, damage=proj_damage, impulse=200.0,
        )

        self.wave_manager.update(dt, self.player_pos, on_enemy_killed=self._on_enemy_killed)

        # watch for any powerup pickup — timer resets to 1.5 on every pickup type
        prev_pickup_timer = self.powerup_manager.last_pickup_timer
        self.powerup_manager.update(dt, self.player_rect, self._on_powerup_pickup, self.obstacles)
        if self.powerup_manager.last_pickup_timer > prev_pickup_timer:
            self._play_sfx("powerup")

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

        # enemy contact damage (shield absorbs first) — skipped when invincible
        hit_rect = self.player_rect
        if not self.invincible and self.damage_cooldown_left <= 0:
            for enemy in self.wave_manager.enemies:
                if enemy.alive and enemy.rect.colliderect(hit_rect):
                    if self.powerup_manager.absorb_shield_hit():
                        self.damage_cooldown_left = self.DAMAGE_COOLDOWN
                        break

                    if enemy.is_boss:
                        damage = 10.0
                    else:
                        wave_num = self.wave_manager.wave_number
                        wave_scaling = 1.0 + 0.5 * (wave_num - 1)
                        damage = enemy.contact_damage * wave_scaling
                    self.player_hp -= damage
                    self.damage_cooldown_left = self.DAMAGE_COOLDOWN
                    if self.player_hp <= 0:
                        self.player_hp = 0
                        self.shake_timer = 0.4
                        self.red_flash_timer = 0.5
                        self.death_anim_timer = self.DEATH_ANIM_DURATION
                        self.state = "dying"
                        self._play_sfx("death")
                    else:
                        self._play_sfx("hurt")
                    break

    # ------------------------------------------------------------------ HUD

    def _draw_health_bar(self) -> None:
        bar_x = 36
        bar_y = 8
        bar_w = 160
        bar_h = 12

        hp_ratio = max(0, self.player_hp / self.PLAYER_MAX_HP)

        # trough
        pygame.draw.rect(self.screen, (28, 6, 6), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
        # fill — blood red always; darkens as HP falls
        fill_w = int(bar_w * hp_ratio)
        if hp_ratio > 0.5:
            bar_color = (180, 20, 20)
        elif hp_ratio > 0.25:
            bar_color = (160, 10, 10)
        else:
            bar_color = (220, 0, 0)   # bright warning red near death
        if fill_w > 0:
            pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, fill_w, bar_h), border_radius=2)
        # engraved border
        pygame.draw.rect(self.screen, (90, 30, 30), (bar_x, bar_y, bar_w, bar_h), width=1, border_radius=2)

        # LIFE label to the left of the bar
        life_lbl = self.small_font.render("LIFE", True, (160, 30, 30))
        self.screen.blit(life_lbl, (bar_x - life_lbl.get_width() - 4, bar_y))

        # numeric label below bar
        display_hp = max(0.0, float(self.player_hp))
        hp_label = self.small_font.render(f"{display_hp:.0f} / {self.PLAYER_MAX_HP}", True, (140, 100, 100))
        self.screen.blit(hp_label, (bar_x, bar_y + bar_h + 2))

    def _draw_bullet_pips(self, x: int, y: int) -> None:
        """Draw individual bullet pips instead of a numeric ammo count."""
        cap = self.preset.ammo_max
        current = self.ammo_current
        pip_w, pip_h, gap = 6, 12, 3
        total_w = cap * (pip_w + gap) - gap
        cx = x - total_w  # right-align from x
        for i in range(cap):
            color = (200, 180, 60) if i < current else (50, 40, 20)
            rect = pygame.Rect(cx + i * (pip_w + gap), y, pip_w, pip_h)
            pygame.draw.rect(self.screen, color, rect, border_radius=1)
            pygame.draw.rect(self.screen, (80, 70, 30), rect, width=1, border_radius=1)

    def _draw_boss_bar(self) -> None:
        """A prominent boss HP bar drawn at the bottom of the screen."""
        wm = self.wave_manager
        if not wm.cfg.is_boss_wave:
            return
        boss = wm.boss_enemy
        if boss is None or not boss.alive:
            return

        bar_h = 14
        bar_w = self.SCREEN_W - 120
        bar_x = 60
        bar_y = self.SCREEN_H - bar_h - 8

        ratio = max(0.0, boss.hp / boss.max_hp)

        # background
        pygame.draw.rect(self.screen, (20, 4, 28), (bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4), border_radius=3)
        # trough
        pygame.draw.rect(self.screen, (30, 8, 40), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
        # fill — deep purple that shifts redder at low HP
        fill_w = int(bar_w * ratio)
        if ratio > 0.5:
            boss_color = (120, 20, 160)
        elif ratio > 0.25:
            boss_color = (160, 10, 100)
        else:
            boss_color = (200, 10, 30)
        if fill_w > 0:
            pygame.draw.rect(self.screen, boss_color, (bar_x, bar_y, fill_w, bar_h), border_radius=2)
        # border
        pygame.draw.rect(self.screen, (180, 60, 220), (bar_x, bar_y, bar_w, bar_h), width=1, border_radius=2)

        # phase dots — show which minion phases have triggered
        phase = wm.boss_phase
        for i, threshold in enumerate([0.75, 0.25]):
            dot_x = bar_x + int(bar_w * threshold)
            color = (80, 80, 80) if phase <= i else (220, 60, 60)
            pygame.draw.line(self.screen, color, (dot_x, bar_y - 3), (dot_x, bar_y + bar_h + 3), 1)

        # label centred above bar
        label = self.font.render("ZOMBIUS MAXIMUS XI", True, (200, 80, 220))
        self.screen.blit(label, (self.SCREEN_W // 2 - label.get_width() // 2, bar_y - 18))

    def _draw_hud(self) -> None:
        # --- stone slab background ---
        pygame.draw.rect(self.screen, (22, 18, 16), pygame.Rect(0, 0, self.SCREEN_W, self.HUD_H))
        # top engraved highlight
        pygame.draw.line(self.screen, (50, 42, 38), (0, 0), (self.SCREEN_W, 0))
        # bottom border — looks like a stone ledge
        pygame.draw.rect(self.screen, (10, 8, 6), pygame.Rect(0, self.HUD_H - 3, self.SCREEN_W, 3))
        pygame.draw.rect(self.screen, (60, 40, 30), pygame.Rect(0, self.HUD_H - 4, self.SCREEN_W, 1))

        # --- LIFE bar (left) ---
        self._draw_health_bar()

        # --- active power-up icons ---
        self.powerup_manager.draw_hud_effects(self.screen, self.small_font, 220, 6)

        # --- NIGHT label (centre) ---
        roman = ["I", "II", "III", "IV", "V"]
        wave_num = self.wave_manager.wave_number
        total = self.wave_manager.total_waves
        wave_roman = roman[wave_num - 1] if wave_num <= len(roman) else str(wave_num)
        total_roman = roman[total - 1] if total <= len(roman) else str(total)
        is_boss = self.wave_manager.cfg.is_boss_wave
        night_color = (180, 60, 220) if is_boss else (140, 160, 120)
        night_surf = self.font.render(f"NIGHT  {wave_roman} / {total_roman}", True, night_color)
        self.screen.blit(night_surf, (self.SCREEN_W // 2 - night_surf.get_width() // 2, 6))

        # --- enemies remaining (below night label) ---
        wm = self.wave_manager
        alive_count = len(wm.enemies)
        pending = wm.spawn_queue + wm.minion_queue
        remaining = alive_count + pending
        remain_color = (160, 60, 60) if remaining > 0 else (60, 120, 60)
        remain_surf = self.small_font.render(
            f"{remaining} remaining", True, remain_color)
        self.screen.blit(remain_surf, (self.SCREEN_W // 2 - remain_surf.get_width() // 2, 22))

        # --- equipped weapon label (below "remaining") ---
        weapon_names = {
            "RAPID-FIRE":   "RAPID FIRE",
            "BALANCED":     "BALANCED",
            "HEAVY-CANNON": "HEAVY CANNON",
        }
        weapon_colors = {
            "RAPID-FIRE":   (255, 210, 80),
            "BALANCED":     (180, 190, 170),
            "HEAVY-CANNON": (200, 80, 60),
        }
        weapon_text = weapon_names.get(self.preset.name, self.preset.name)
        weapon_color = weapon_colors.get(self.preset.name, (180, 180, 180))
        weapon_surf = self.small_font.render(weapon_text, True, weapon_color)
        self.screen.blit(weapon_surf,
                         (self.SCREEN_W // 2 - weapon_surf.get_width() // 2, 36))

        # --- bullet pips (top-right) ---
        pip_y = 8
        self._draw_bullet_pips(self.SCREEN_W - 14, pip_y)
        ammo_label = self.small_font.render("AMMO", True, (80, 80, 60))
        self.screen.blit(ammo_label, (self.SCREEN_W - ammo_label.get_width() - 14, pip_y + 14))

        # --- reload progress bar (replaces ammo pips while reloading) ---
        if self.is_reloading:
            prog = max(0.0, 1.0 - self.reload_cooldown_left / self.preset.reload_time)
            bar_w = self.preset.ammo_max * (6 + 3) - 3   # match pip row width
            bar_x = self.SCREEN_W - 14 - bar_w
            pygame.draw.rect(self.screen, (40, 30, 10), (bar_x, pip_y, bar_w, 12), border_radius=2)
            pygame.draw.rect(self.screen, (180, 140, 40),
                             (bar_x, pip_y, int(bar_w * prog), 12), border_radius=2)
            pygame.draw.rect(self.screen, (100, 80, 20), (bar_x, pip_y, bar_w, 12), width=1, border_radius=2)
            rl_label = self.small_font.render("RELOADING", True, (180, 140, 40))
            self.screen.blit(rl_label, (self.SCREEN_W - rl_label.get_width() - 14, pip_y + 14))

        # --- skull kill counter ---
        kills_surf = self.small_font.render(
            f"KILLS  {self.wave_manager.total_kills}", True, (100, 80, 80))
        self.screen.blit(kills_surf, (self.SCREEN_W - kills_surf.get_width() - 14, 40))

        # --- active power-up icons (left of centre) ---
        self.powerup_manager.draw_hud_effects(self.screen, self.small_font, 220, 6)

        # --- invincible dev badge ---
        if self.invincible:
            inv_surf = self.font.render("[ INVINCIBLE ]", True, (60, 220, 100))
            self.screen.blit(inv_surf, (self.SCREEN_W * 3 // 4 - inv_surf.get_width() // 2, 8))


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

    def _draw_center_message(self, title: str, subtitle: str,
                             title_color: tuple = (255, 210, 60),
                             use_big_panel: bool = True) -> None:
        # themed panel — matches the title and pause screens
        title_surf = self.pause_title_font.render(title, True, title_color)
        shadow_surf = self.pause_title_font.render(title, True, (40, 0, 0))
        sub_surf = self.font.render(subtitle, True, (200, 180, 160))

        tw = title_surf.get_width()
        th = title_surf.get_height()
        sw = sub_surf.get_width()
        sh = sub_surf.get_height()

        panel_w = max(tw, sw) + 80
        panel_h = th + (sh + 18 if subtitle else 0) + 48
        panel = pygame.Rect(0, 0, panel_w, panel_h)
        panel.center = (self.SCREEN_W // 2, self.SCREEN_H // 2 - 20)

        # drop shadow
        shadow_rect = panel.move(6, 6)
        pygame.draw.rect(self.screen, (0, 0, 0), shadow_rect)

        # panel body + double border for the arcade look
        pygame.draw.rect(self.screen, (28, 20, 24), panel)
        pygame.draw.rect(self.screen, (180, 40, 40), panel, width=4)
        inner = panel.inflate(-10, -10)
        pygame.draw.rect(self.screen, (60, 20, 24), inner, width=1)

        # title with shadow
        tx = panel.centerx - tw // 2
        ty = panel.top + 20
        self.screen.blit(shadow_surf, (tx + 3, ty + 3))
        self.screen.blit(title_surf, (tx, ty))

        # blood drips under the title
        drip_y = ty + th - 4
        for (dx, dlen) in [(-tw // 3, 10), (0, 16), (tw // 3, 8)]:
            pygame.draw.rect(self.screen, (170, 20, 20),
                             (panel.centerx + dx, drip_y, 4, dlen))
            pygame.draw.rect(self.screen, (220, 30, 30),
                             (panel.centerx + dx, drip_y + dlen, 4, 4))

        if subtitle:
            self.screen.blit(sub_surf,
                             (panel.centerx - sw // 2, ty + th + 24))

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

        self._draw_boss_bar()
        self._draw_hud()
        self._draw_pickup_toast()

        if self.debug:
            self._draw_debug()

        if self.red_flash_timer > 0:
            flash = pygame.Surface((self.SCREEN_W, self.SCREEN_H), pygame.SRCALPHA)
            alpha = int(255 * min(1.0, self.red_flash_timer / 0.5))
            flash.fill((200, 0, 0, alpha))
            self.screen.blit(flash, (0, 0))

        if self.state == "victory":
            fade = pygame.Surface((self.SCREEN_W, self.SCREEN_H), pygame.SRCALPHA)
            alpha = int(200 * min(1.0, self.victory_fade_timer / 2.0))
            fade.fill((200, 160, 40, alpha))
            self.screen.blit(fade, (0, 0))

        if self.wave_manager.wave_complete and not self.wave_manager.all_waves_done:
            roman = ["I", "II", "III", "IV", "V"]
            wave_num = self.wave_manager.wave_number
            wave_roman = roman[wave_num - 1] if wave_num <= len(roman) else str(wave_num)

            if self.wave_manager.wave_number >= self.wave_manager.total_waves:
                self._draw_center_message("THE BEAST FALLS", "",
                                          title_color=(255, 210, 60))
            else:
                if self.wave_manager.wave_number == 4:
                    subtitle = f"+3 Max Ammo  +25% Power    Next night in {self.wave_manager.transition_timer:.1f}s"
                else:
                    subtitle = f"+3 Max Ammo    Next night in {self.wave_manager.transition_timer:.1f}s"

                self._draw_center_message(
                    f"NIGHT {wave_roman} SURVIVED",
                    subtitle,
                    title_color=(255, 210, 60),
                )

        if self.state == "victory":
            self._draw_center_message(
                "YOU SURVIVED",
                f"{self.wave_manager.total_kills} undead slain   —   ENTER to hunt again",
                title_color=(255, 210, 60),
            )

        if self.state == "game_over":
            self._draw_center_message(
                "YOU ARE DEAD",
                f"{self.wave_manager.total_kills} undead slain   —   ENTER to rise again",
                title_color=(200, 30, 30),
            )

    def draw(self) -> None:
        if self.state == "title":
            self.title_screen.draw(self.screen)
            return
        # shudder effect when the player dies
        if self.shake_timer > 0:
            import random
            offset_x = random.randint(-12, 12)
            offset_y = random.randint(-12, 12)
            self._draw_gameplay()
            copy_surf = self.screen.copy()
            self.screen.fill((0, 0, 0))
            self.screen.blit(copy_surf, (offset_x, offset_y))
        else:
            self._draw_gameplay()

        # overlay the pause menu on top
        if self.state == "paused":
            self.pause_menu.draw(self.screen)