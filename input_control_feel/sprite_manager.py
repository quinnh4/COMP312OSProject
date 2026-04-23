import pygame
from enum import Enum
import os


class AnimationState(str, Enum):
    IDLE = "idle"
    MOVE = "move"
    ATTACK = "attack"


class PlayerDirection(str, Enum):
    """Player directional states."""
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class SpriteAnimator:
    """Manages sprite sheet frame extraction and animation timing."""
    
    def __init__(self, sprite_sheet_path: str, frame_width: int, frame_height: int, 
                 frames_per_row: int, animations: dict[str, tuple[int, int]]):
        """
        Args:
            sprite_sheet_path: Path to sprite sheet image
            frame_width: Width of each frame in pixels
            frame_height: Height of each frame in pixels
            frames_per_row: How many frames per row in the sprite sheet
            animations: Dict mapping animation name to (start_frame, frame_count)
                       e.g., {"idle": (0, 1), "move": (0, 8), "attack": (8, 7)}
        """
        self.sprite_sheet_path = sprite_sheet_path
        self.sheet = pygame.image.load(sprite_sheet_path).convert_alpha()
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.frames_per_row = frames_per_row
        self.animations = animations
        
        # Extract all frames from sheet
        self.frames = self._extract_frames()
        
        # Animation state
        self.current_animation = AnimationState.IDLE
        self.animation_index = 0
        self.animation_timer = 0
        self.frame_duration = 0.1  # seconds per frame (adjust for speed)
    
    def _extract_frames(self) -> list[pygame.Surface]:
        """Extract individual frames from sprite sheet."""
        frames = []
        
        for row in range(self.sheet.get_height() // self.frame_height):
            for col in range(self.frames_per_row):
                x = col * self.frame_width
                y = row * self.frame_height
                
                # Check bounds
                if x + self.frame_width > self.sheet.get_width():
                    continue
                if y + self.frame_height > self.sheet.get_height():
                    break
                
                rect = pygame.Rect(x, y, self.frame_width, self.frame_height)
                frame = self.sheet.subsurface(rect).copy()
                frames.append(frame)
            
            # Stop if we've gone past the sheet
            if row * self.frame_height >= self.sheet.get_height():
                break
        
        return frames
    
    def set_animation(self, animation_name: str) -> None:
        """Switch to a new animation."""
        if animation_name in self.animations and self.current_animation != animation_name:
            self.current_animation = animation_name
            self.animation_index = 0
            self.animation_timer = 0
    
    def update(self, dt: float) -> pygame.Surface:
        """Update animation and return current frame."""
        self.animation_timer += dt
        
        # Get animation frame range
        start_frame, frame_count = self.animations.get(
            self.current_animation, 
            self.animations.get("idle", (0, 1))
        )
        
        # Advance frame if timer exceeds duration
        if self.animation_timer >= self.frame_duration:
            self.animation_timer = 0
            self.animation_index = (self.animation_index + 1) % frame_count
        
        # Return current frame
        frame_num = start_frame + self.animation_index
        if frame_num < len(self.frames):
            return self.frames[frame_num]
        else:
            return self.frames[0]  # Fallback to first frame
    
    def get_current_frame(self) -> pygame.Surface:
        """Get current frame without updating."""
        start_frame, frame_count = self.animations.get(
            self.current_animation,
            self.animations.get("idle", (0, 1))
        )
        frame_num = start_frame + self.animation_index
        if frame_num < len(self.frames):
            return self.frames[frame_num]
        else:
            return self.frames[0]  # Fallback to first frame
    
    def set_frame_speed(self, frame_duration: float) -> None:
        """Adjust animation speed. Lower = faster."""
        self.frame_duration = frame_duration


class PlayerSpriteAnimator:
    """Manages directional player sprites with multiple animation states."""
    
    def __init__(self, sprites_base_path: str, player_size: int):
        """
        Args:
            sprites_base_path: Path to Player folder (e.g., "input_control_feel/sprites/Player")
            player_size: Display size for player sprite
        """
        self.sprites_base_path = sprites_base_path
        self.player_size = player_size
        self.death_size = int(player_size * 1.25)
        self.weapon_size = int(player_size * 0.74)
        self.reload_weapon_size = int(player_size * 0.90)
        
        # Load all directional animators
        self.animators: dict[str, dict[str, SpriteAnimator | None]] = {
            "idle": {},
            "run": {},
            "death": {},
            "weapon_idle": {},
            "weapon_shoot": {},
            "weapon_fire": {},
            "weapon_reload": {},
        }
        
        self._load_animators()
        
        # Current state
        self.current_animation = "idle"
        self.current_direction = PlayerDirection.DOWN
        self.animation_timer = 0
        self.frame_duration = 0.08
        self.weapon_shoot_timer = 0.0
        self.weapon_shoot_duration = 0.12
        self.weapon_reloading = False
    
    def _load_animators(self) -> None:
        """Load all sprite sheets for player animations."""
        # Idle - single sheet
        idle_path = os.path.join(self.sprites_base_path, "Idle", "Character_down_idle_no-hands-Sheet6.png")
        self.animators["idle"]["all"] = self._load_animator_safe(
            idle_path,
            frame_width=11,  # 66 / 6
            frame_height=16,
            frames_per_row=6,
            animations={"idle": (0, 6)}  # All 6 frames for idle loop
        )
        
        # Death - single sheet
        death_path = os.path.join(self.sprites_base_path, "Death", "Character_side_death1_NoHands-Sheet6.png")
        self.animators["death"]["all"] = self._load_animator_safe(
            death_path,
            frame_width=21,  # 126 / 6
            frame_height=16,
            frames_per_row=6,
            animations={"death": (0, 6)}
        )
        
        # Run - directional sheets
        run_configs = {
            "down": ("Character_down_run-Sheet6.png", 13, 17),    # 78 / 6
            "up": ("Character_up_run-Sheet6.png", 13, 17),
            "left": ("Character_side-left_run-Sheet6.png", 14, 17), # 84 / 6
            "right": ("Character_side-right_run-Sheet6.png", 14, 17),
        }
        
        for direction, (filename, frame_w, frame_h) in run_configs.items():
            run_path = os.path.join(self.sprites_base_path, "Run", filename)
            self.animators["run"][direction] = self._load_animator_safe(
                run_path,
                frame_width=frame_w,
                frame_height=frame_h,
                frames_per_row=6,
                animations={"run": (0, 6)}
            )

        weapon_base = os.path.join(self.sprites_base_path, "Weapon")
        weapon_idle_files = {
            "down": "Pistol_down_idle-and-run-Sheet6.png",
            "up": "Pistol_up_idle-and-run-Sheet6.png",
            "left": "Pistol_side-left_idle-and-run-Sheet6.png",
            "right": "Pistol_side_idle-and-run-Sheet6.png",
        }
        weapon_shoot_files = {
            "down": "Pistol_down_shoot-Sheet3.png",
            "up": "Pistol_up_shoot-Sheet3.png",
            "left": "Pistol_side-left_shoot-Sheet3.png",
            "right": "Pistol_side_shoot-Sheet3.png",
        }
        weapon_reload_files = {
            "down": "Pistol_down_Reload-Sheet11.png",
            "up": "Pistol_up_Reload-Sheet11.png",
            "left": "Pistol_side-left_Reload-Sheet11.png",
            "right": "Pistol_side_Reload-Sheet11.png",
        }
        weapon_fire_files = {
            "down": "Fire_Down-Sheet3.png",
            "up": "Fire_Up-Sheet3.png",
            "left": "Fire_side-left-Sheet3.png",
            "right": "Fire_side-Sheet3.png",
        }

        for direction, filename in weapon_idle_files.items():
            self.animators["weapon_idle"][direction] = self._load_animator_from_sheet_count(
                os.path.join(weapon_base, filename),
                frame_count=6,
                anim_key="idle",
            )
        for direction, filename in weapon_shoot_files.items():
            self.animators["weapon_shoot"][direction] = self._load_animator_from_sheet_count(
                os.path.join(weapon_base, filename),
                frame_count=3,
                anim_key="shoot",
            )
        for direction, filename in weapon_reload_files.items():
            self.animators["weapon_reload"][direction] = self._load_animator_from_sheet_count(
                os.path.join(weapon_base, filename),
                frame_count=11,
                anim_key="reload",
            )
        for direction, filename in weapon_fire_files.items():
            self.animators["weapon_fire"][direction] = self._load_animator_from_sheet_count(
                os.path.join(weapon_base, filename),
                frame_count=3,
                anim_key="fire",
            )
    
    def _load_animator_safe(self, path: str, frame_width: int, frame_height: int,
                           frames_per_row: int, animations: dict) -> SpriteAnimator | None:
        """Safely load animator, returning None if file not found."""
        if not os.path.exists(path):
            print(f"[PlayerSpriteAnimator] Warning: Sprite not found: {path}")
            return None
        try:
            return SpriteAnimator(path, frame_width, frame_height, frames_per_row, animations)
        except Exception as e:
            print(f"[PlayerSpriteAnimator] Failed to load {path}: {e}")
            return None

    def _load_animator_from_sheet_count(self, path: str, frame_count: int, anim_key: str) -> SpriteAnimator | None:
        if not os.path.exists(path):
            print(f"[PlayerSpriteAnimator] Warning: Sprite not found: {path}")
            return None
        try:
            sheet = pygame.image.load(path).convert_alpha()
            sheet_w, sheet_h = sheet.get_size()
            if frame_count <= 0:
                return None
            frame_w = max(1, sheet_w // frame_count)
            animator = SpriteAnimator(
                path,
                frame_width=frame_w,
                frame_height=sheet_h,
                frames_per_row=frame_count,
                animations={anim_key: (0, frame_count)},
            )
            return animator
        except Exception as e:
            print(f"[PlayerSpriteAnimator] Failed to load {path}: {e}")
            return None
    
    def set_animation(self, animation_state: str, direction: PlayerDirection | None = None) -> None:
        """Switch animation state. Direction is ignored for idle/death."""
        if animation_state != self.current_animation:
            self.current_animation = animation_state
            self.animation_timer = 0
        
        if direction is not None:
            self.current_direction = direction
    
    def update(self, dt: float) -> None:
        """Update animation state."""
        self.animation_timer += dt
        if self.weapon_shoot_timer > 0:
            self.weapon_shoot_timer = max(0.0, self.weapon_shoot_timer - dt)
        
        # Update frame for current animator
        animator = self._get_current_animator()
        if animator:
            anim_key = self._animation_key_for_state(self.current_animation)
            if anim_key:
                animator.set_animation(anim_key)
            animator.update(dt)

        self._update_weapon(dt)
    
    def get_current_frame(self) -> pygame.Surface | None:
        """Get current frame, scaled for the active animation state."""
        animator = self._get_current_animator()
        if not animator:
            return None
        
        frame = animator.get_current_frame()
        if frame is None:
            return None
        
        target_size = self.player_size
        if self.current_animation == "death":
            target_size = self.death_size

        if frame.get_width() != target_size or frame.get_height() != target_size:
            frame = pygame.transform.scale(frame, (target_size, target_size))
        
        return frame
    
    def _get_current_animator(self) -> SpriteAnimator | None:
        """Get the current active animator based on state."""
        if self.current_animation == "idle":
            return self.animators["idle"].get("all")
        elif self.current_animation == "death":
            return self.animators["death"].get("all")
        elif self.current_animation == "run":
            # Use directional animator for running
            direction_key = self.current_direction.value
            return self.animators["run"].get(direction_key)
        
        return None

    def trigger_shoot(self, direction: PlayerDirection | None = None) -> None:
        if direction is not None:
            self.current_direction = direction
        self.weapon_shoot_timer = self.weapon_shoot_duration
        self._reset_weapon_burst_frames()

    def set_weapon_reloading(self, is_reloading: bool, direction: PlayerDirection | None = None) -> None:
        if direction is not None:
            self.current_direction = direction

        if is_reloading and not self.weapon_reloading:
            direction_key = self.current_direction.value
            animator = self.animators["weapon_reload"].get(direction_key)
            if animator:
                animator.set_animation("reload")

        self.weapon_reloading = is_reloading

    def get_weapon_frames(self) -> tuple[pygame.Surface | None, pygame.Surface | None]:
        direction_key = self.current_direction.value

        if self.weapon_reloading:
            reload_anim = self.animators["weapon_reload"].get(direction_key)
            return self._scaled_weapon_frame(reload_anim, use_reload_size=True), None

        if self.weapon_shoot_timer > 0:
            weapon_anim = self.animators["weapon_shoot"].get(direction_key)
            fire_anim = self.animators["weapon_fire"].get(direction_key)
            return self._scaled_weapon_frame(weapon_anim), self._scaled_fire_frame(fire_anim)

        idle_anim = self.animators["weapon_idle"].get(direction_key)
        return self._scaled_weapon_frame(idle_anim), None

    def _update_weapon(self, dt: float) -> None:
        direction_key = self.current_direction.value

        if self.weapon_reloading:
            reload_anim = self.animators["weapon_reload"].get(direction_key)
            if reload_anim:
                reload_anim.set_animation("reload")
                reload_anim.update(dt)
            return

        idle_anim = self.animators["weapon_idle"].get(direction_key)
        if idle_anim:
            idle_anim.set_animation("idle")
            idle_anim.update(dt)

        if self.weapon_shoot_timer > 0:
            shoot_anim = self.animators["weapon_shoot"].get(direction_key)
            fire_anim = self.animators["weapon_fire"].get(direction_key)
            if shoot_anim:
                shoot_anim.set_animation("shoot")
                shoot_anim.update(dt)
            if fire_anim:
                fire_anim.set_animation("fire")
                fire_anim.update(dt)

    def _reset_weapon_burst_frames(self) -> None:
        direction_key = self.current_direction.value
        for key, anim_name in (("weapon_shoot", "shoot"), ("weapon_fire", "fire")):
            animator = self.animators[key].get(direction_key)
            if animator:
                animator.set_animation(anim_name)

    def _scaled_weapon_frame(
        self,
        animator: SpriteAnimator | None,
        use_reload_size: bool = False,
    ) -> pygame.Surface | None:
        if not animator:
            return None
        frame = animator.get_current_frame()
        target_size = self.reload_weapon_size if use_reload_size else self.weapon_size
        if frame.get_width() != target_size or frame.get_height() != target_size:
            frame = pygame.transform.scale(frame, (target_size, target_size))
        return frame

    def _scaled_fire_frame(self, animator: SpriteAnimator | None) -> pygame.Surface | None:
        if not animator:
            return None
        frame = animator.get_current_frame()
        fire_size = int(self.player_size * 1.12)
        if frame.get_width() != fire_size or frame.get_height() != fire_size:
            frame = pygame.transform.scale(frame, (fire_size, fire_size))
        return frame

    @staticmethod
    def _animation_key_for_state(state: str) -> str | None:
        if state == "idle":
            return "idle"
        if state == "run":
            return "run"
        if state == "death":
            return "death"
        return None
