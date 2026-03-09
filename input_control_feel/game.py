from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

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

@dataclass(frozen=True)
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
    #seconds between each shot
    fire_rate: float
    # max ammo capacity  
    ammo_max: int
    # seconds to reload 
    reload_time: float


class Game:
    fps = 60

    SCREEN_W, SCREEN_H = 960, 540
    HUD_H = 54
    PLAYFIELD_PADDING = 10

    PLAYER_SIZE = 32

    DASH_IMPULSE = 760.0
    DASH_COOLDOWN = 0.65

    def __init__(self) -> None:
        self.screen = pygame.display.set_mode((self.SCREEN_W, self.SCREEN_H))
        self.font = pygame.font.SysFont(None, 22)
        self.big_font = pygame.font.SysFont(None, 48)

        self.screen_rect = pygame.Rect(0, 0, self.SCREEN_W, self.SCREEN_H)
        self.playfield = pygame.Rect(
            self.PLAYFIELD_PADDING,
            self.HUD_H + self.PLAYFIELD_PADDING,
            self.SCREEN_W - 2 * self.PLAYFIELD_PADDING,
            self.SCREEN_H - self.HUD_H - 2 * self.PLAYFIELD_PADDING,
        )

        self.boundary_mode = BoundaryMode.CLAMP
        self.platformer_mode = False
        self.state = "title"  # title | play

        self.player_rect = pygame.Rect(0, 0, self.PLAYER_SIZE, self.PLAYER_SIZE)
        self.player_pos = pygame.Vector2(self.playfield.center)
        self.player_vel = pygame.Vector2(0, 0)
        self.player_rect.center = self.player_pos

        self.on_ground = True
        self.jump_requested = False

        self.control_scheme = ControlScheme.WASD
        self.debug = False

        self.presets = [
            FeelPreset(
                name="BALANCED",
                accel=2500.0,
                max_speed=480.0,
                friction=10.0,
                gravity=2200.0,
                jump_speed=800.0,
                projectile_speed=950.0,
                fire_rate=0.25,
                ammo_max=8,
                reload_time=2.0,
            ),
            FeelPreset(
                name="RAPID-FIRE",
                accel=3200.0,
                max_speed=520.0,
                friction=14.0,
                gravity=2600.0,
                jump_speed=860.0,
                projectile_speed=800.0,
                # fast shooting
                fire_rate=0.15,
                ammo_max=12,
                reload_time=1.5,
            ),
            FeelPreset(
                name="HEAVY-CANNON",
                accel=1900.0,
                # slowing the movement
                max_speed=400.0,
                friction=6.0,
                gravity=1700.0,
                jump_speed=760.0,
                # faster projectile
                projectile_speed=1200.0,
                # slow shooting
                fire_rate=0.5,
                # less ammo for heavier cannon
                ammo_max=5,
                # heavier cannon needs longer reload
                reload_time=2.5,
            ),
        ]
        self.preset_idx = 0

        self.dash_cooldown_left = 0.0
        self.last_move_dir = pygame.Vector2(1, 0)

        #shooting system
        self.projectiles: list[Projectile] = []
        # current ammo
        self.ammo_current = self.preset.ammo_max
        self.fire_cooldown_left = 0.0
        self.reload_cooldown_left = 0.0
        self.is_reloading = False

    @property
    def preset(self) -> FeelPreset:
        return self.presets[self.preset_idx]

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

        # reset shooting system
        self.projectiles.clear()
        self.ammo_current = self.preset.ammo_max
        self.fire_cooldown_left = 0.0
        self.reload_cooldown_left = 0.0
        self.is_reloading = False

        if not keep_state:
            self.state = "play"

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_ESCAPE:
            pygame.event.post(pygame.event.Event(pygame.QUIT))
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

        if event.key == pygame.K_p:
            self.platformer_mode = not self.platformer_mode
            if self.state != "title":
                self._reset(keep_state=True)
            return

        if event.key == pygame.K_r and event.mod & pygame.KMOD_CTRL:
            self._reset(keep_state=(self.state == "title"))
            return

        # changed to start game with ENTER key to avoid conflict with shooting key
        if self.state == "title" and event.key in {pygame.K_RETURN, pygame.K_KP_ENTER}:
            self.state = "play"
            self._reset(keep_state=True)
            return

        if event.key == pygame.K_1:
            self.preset_idx = 0
            # had to update ammo when changing preset because of different max ammo
            self._update_ammo_for_preset()
            return
        if event.key == pygame.K_2:
            self.preset_idx = 1
            # had to update ammo when changing preset because of different max ammo
            self._update_ammo_for_preset()
            return
        if event.key == pygame.K_3:
            self.preset_idx = 2
            # had to update ammo when changing preset because of different max ammo
            self._update_ammo_for_preset()
            return

        if self.state != "play":
            return

        # Discrete actions
        if event.key in {pygame.K_LSHIFT, pygame.K_RSHIFT}:
            self._try_dash()
            return
        
        # shooting action
        if event.key == pygame.K_SPACE:
            self._try_shoot()
            return
        
        # reload action which will avoid conflicts with the reset key
        if event.key == pygame.K_r and not event.mod & pygame.KMOD_CTRL:
            self._try_reload()
            return

        if self.platformer_mode and event.key in {pygame.K_UP, pygame.K_w, pygame.K_SPACE, pygame.K_i}:
            self.jump_requested = True

    def _scheme_keys(self) -> dict[str, set[int]]:
        if self.control_scheme == ControlScheme.WASD:
            return {
                "left": {pygame.K_a},
                "right": {pygame.K_d},
                "up": {pygame.K_w},
                "down": {pygame.K_s},
            }
        if self.control_scheme == ControlScheme.IJKL:
            return {
                "left": {pygame.K_j},
                "right": {pygame.K_l},
                "up": {pygame.K_i},
                "down": {pygame.K_k},
            }
        return {
            "left": {pygame.K_LEFT},
            "right": {pygame.K_RIGHT},
            "up": {pygame.K_UP},
            "down": {pygame.K_DOWN},
        }

    def _read_direction(self) -> pygame.Vector2:
        keys = pygame.key.get_pressed()
        mapping = self._scheme_keys()

        x = 0
        y = 0

        if any(keys[k] for k in mapping["left"]):
            x -= 1
        if any(keys[k] for k in mapping["right"]):
            x += 1
        if any(keys[k] for k in mapping["up"]):
            y -= 1
        if any(keys[k] for k in mapping["down"]):
            y += 1

        direction = pygame.Vector2(x, y)
        if direction.length_squared() > 0:
            direction = direction.normalize()
            self.last_move_dir.update(direction)

        # Always allow arrows as an alternate scheme (accessibility / convenience)
        if direction.length_squared() == 0:
            x2 = 0
            y2 = 0
            if keys[pygame.K_LEFT]:
                x2 -= 1
            if keys[pygame.K_RIGHT]:
                x2 += 1
            if keys[pygame.K_UP]:
                y2 -= 1
            if keys[pygame.K_DOWN]:
                y2 += 1
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
        # Treat the bottom of the playfield as "ground".
        if self.player_rect.bottom >= self.playfield.bottom:
            self.player_rect.bottom = self.playfield.bottom
            self.player_vel.y = 0
            self.on_ground = True

        # Prevent leaving the top of the playfield.
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

        # Impulse dash: a discrete action that modifies velocity once.
        self.player_vel += dash_dir * self.DASH_IMPULSE
        self.dash_cooldown_left = self.DASH_COOLDOWN

    # try to fire projectile
    def _try_shoot(self) -> None:
        # not going to be able to shoot while reloading
        if self.is_reloading:
            return
        # not going to be able to shoot in cooldown
        if self.fire_cooldown_left > 0:
            return
        if self.ammo_current <= 0:
            # this will auto reload when trying to shoot with no ammo
            self._try_reload()
            return

        # fire projectile in the last move direction
        direction = pygame.Vector2(self.last_move_dir)
        # if no movement then it shoots in default position
        if direction.length_squared() == 0:
            direction = pygame.Vector2(1, 0)
        # normalizes the direction
        direction = direction.normalize() 

        # creates and adds projectile
        projectile = Projectile(
            position=pygame.Vector2(self.player_pos),
            velocity=direction * self.preset.projectile_speed,
        )
        # adds projectile to the list
        self.projectiles.append(projectile) 
        
        # decreases ammo and set cooldown
        self .ammo_current -= 1
        self.fire_cooldown_left = self.preset.fire_rate

    # try to reload ammo
    def _try_reload(self) -> None:
        # not going to be able to reload while already reloading
        if self.is_reloading:
            return
        # not going to be able to reload if ammo is full
        if self.ammo_current >= self.preset.ammo_max:
            return

        # start reloading
        self.is_reloading = True
        # set reload cooldown
        self.reload_cooldown_left = self.preset.reload_time

    # had to update ammo when changing preset because of different max ammo
    def _update_ammo_for_preset(self) -> None:
        self.ammo_current = self.preset.ammo_max
        self.is_reloading = False
        self.reload_cooldown_left = 0.0

    def update(self, dt: float) -> None:
        if self.state != "play":
            return

        if self.dash_cooldown_left > 0:
            self.dash_cooldown_left = max(0.0, self.dash_cooldown_left - dt)

        # update shooting cooldowns
        if self.fire_cooldown_left > 0:
            self.fire_cooldown_left = max(0.0, self.fire_cooldown_left - dt)

        if self.is_reloading:
            # update reload cooldown
            self.reload_cooldown_left -= dt
            # finish reloading when cooldown is up
            if self.reload_cooldown_left <= 0:
                self.ammo_current = self.preset.ammo_max
                self.is_reloading = False
                self.reload_cooldown_left = 0.0

        p = self.preset

        if self.platformer_mode:
            x = self._read_horizontal()

            # Horizontal accel; no vertical input (gravity handles Y).
            self.player_vel.x += x * p.accel * dt
            if x == 0:
                self.player_vel.x -= self.player_vel.x * min(1.0, p.friction * dt)
            self.player_vel.x = max(-p.max_speed, min(p.max_speed, self.player_vel.x))

            # Jump is a discrete action.
            if self.jump_requested and self.on_ground:
                self.player_vel.y = -p.jump_speed
                self.on_ground = False
            self.jump_requested = False

            # Gravity.
            self.player_vel.y += p.gravity * dt

            self.player_pos += self.player_vel * dt
            self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))

            # Use the existing boundary mode for horizontal bounds.
            prev_y = self.player_rect.centery
            self._apply_bounds_player()
            self.player_rect.centery = prev_y
            self.player_pos.y = prev_y

            # Then apply platformer-specific vertical bounds.
            self._apply_platformer_vertical_bounds()
        else:
            direction = self._read_direction()

            # Accelerate toward direction.
            self.player_vel += direction * p.accel * dt

            # Friction: nudge velocity toward zero when no input.
            if direction.length_squared() == 0:
                self.player_vel -= self.player_vel * min(1.0, p.friction * dt)

            if self.player_vel.length() > p.max_speed:
                self.player_vel.scale_to_length(p.max_speed)

            self.player_pos += self.player_vel * dt
            self.player_rect.center = (int(self.player_pos.x), int(self.player_pos.y))

            self._apply_bounds_player()

        # update projectiles
        for projectile in self.projectiles[:]:
            projectile.update(dt)
            # remove projectile if it goes out of playfield
            if not self.playfield.collidepoint(projectile.position.x, projectile.position.y):
                self.projectiles.remove(projectile)

    def _draw_hud(self) -> None:
        pygame.draw.rect(self.screen, (46, 52, 64), pygame.Rect(0, 0, self.SCREEN_W, self.HUD_H))

        control = "PLATFORMER" if self.platformer_mode else "TOPDOWN"
        left = (
            f"Bounds: {self.boundary_mode.value.upper()}   Control: {control}   "
            f"Scheme: {self.control_scheme.value}   Feel: {self.preset.name}"
        )

        dash = "READY" if self.dash_cooldown_left <= 0 else f"CD {self.dash_cooldown_left:0.2f}s"

        # display reload status
        if self.is_reloading:
            ammo_display = f"RELOADING {self.reload_cooldown_left: .1f}s" 
        # current ammo / max ammo
        else:
            ammo_display = f"Ammo: {self.ammo_current}/{self.preset.ammo_max}" 

        right = f"Dash: {dash}   {ammo_display}"

        left_surf = self.font.render(left, True, (216, 222, 233))
        right_surf = self.font.render(right, True, (216, 222, 233))

        self.screen.blit(left_surf, (14, 16))
        self.screen.blit(right_surf, (self.SCREEN_W - right_surf.get_width() - 14, 16))

    def _draw_debug(self) -> None:
        p = self.preset
        lines = [
            f"vel=({self.player_vel.x:0.1f}, {self.player_vel.y:0.1f})",
            f"accel={p.accel:0.1f}  friction={p.friction:0.1f}  max={p.max_speed:0.1f}",
            f"gravity={p.gravity:0.1f}  jump={p.jump_speed:0.1f}",
            f"last_dir=({self.last_move_dir.x:0.2f},{self.last_move_dir.y:0.2f})",
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

        self.screen.blit(
            title_surf,
            (
                self.SCREEN_W // 2 - title_surf.get_width() // 2,
                self.SCREEN_H // 2 - 60,
            ),
        )
        self.screen.blit(
            sub_surf,
            (
                self.SCREEN_W // 2 - sub_surf.get_width() // 2,
                self.SCREEN_H // 2,
            ),
        )

    def draw(self) -> None:
        self.screen.fill((20, 24, 30))

        # Playfield
        pygame.draw.rect(self.screen, (10, 12, 16), self.playfield)
        pygame.draw.rect(self.screen, (76, 86, 106), self.playfield, width=2)

        # projectiles
        for projectile in self.projectiles:
            projectile.draw(self.screen)

        # Player
        pygame.draw.rect(self.screen, (136, 192, 208), self.player_rect, border_radius=6)

        self._draw_hud()

        if self.debug:
            self._draw_debug()

        if self.state == "title":
            # edited title screen to show controls including new shooting and reloading mechanics
            self._draw_center_message(
                "Projectile Shooter",
                "ENTER: start   ESC: QUIT  SPACE: shoot   R: reload   1/2/3: feel   SHIFT: dash   C: scheme   P: mode   F1: debug",
            )
