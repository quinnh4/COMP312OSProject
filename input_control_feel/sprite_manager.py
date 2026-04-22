import pygame
from enum import Enum


class AnimationState(str, Enum):
    IDLE = "idle"
    MOVE = "move"
    ATTACK = "attack"


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
