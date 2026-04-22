"""
Quick sprite sheet analyzer and animator creator.

Run this script to:
1. Measure your sprite sheet dimensions
2. Calculate frame sizes
3. Set up animation configuration
"""

import pygame
import os
from input_control_feel.sprite_manager import SpriteAnimator


def analyze_sprite_sheet(image_path: str) -> None:
    """Analyze a sprite sheet and print useful info."""
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return
    
    # Initialize pygame just for image loading
    pygame.init()
    try:
        image = pygame.image.load(image_path)
        width, height = image.get_size()
        
        print(f"\n=== Sprite Sheet Analysis ===")
        print(f"File: {image_path}")
        print(f"Total dimensions: {width}x{height} pixels")
        
        # Calculate common frame sizes
        print(f"\nPossible frame configurations (assuming uniform grid):")
        print(f"  If 8 frames per row: {width // 8}x{height} pixels per frame")
        print(f"  If 4 frames per row: {width // 4}x{height} pixels per frame")
        print(f"  If 6 frames per row: {width // 6}x{height} pixels per frame")
        
        print(f"\nNumber of rows (if each frame is square):")
        for frame_size in [32, 48, 64, 72, 96]:
            cols = width // frame_size
            rows = height // frame_size
            if cols > 0 and rows > 0:
                print(f"  {frame_size}x{frame_size}: {cols} columns, {rows} rows")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        pygame.quit()


def create_animator_interactive() -> None:
    """Interactive guide to create a sprite animator."""
    print("\n=== Sprite Animator Setup ===\n")
    
    sprite_path = input("Enter sprite sheet path (e.g., 'input_control_feel/sprites/enemy.png'): ").strip()
    
    if not os.path.exists(sprite_path):
        print(f"File not found: {sprite_path}")
        return
    
    frame_width = int(input("Frame width (pixels): "))
    frame_height = int(input("Frame height (pixels): "))
    frames_per_row = int(input("Frames per row: "))
    
    idle_start = int(input("Idle animation start frame: "))
    idle_count = int(input("Idle animation frame count: "))
    
    move_start = int(input("Move animation start frame: "))
    move_count = int(input("Move animation frame count: "))
    
    attack_start = int(input("Attack animation start frame: "))
    attack_count = int(input("Attack animation frame count: "))
    
    # Test creation
    try:
        pygame.init()
        animator = SpriteAnimator(
            sprite_sheet_path=sprite_path,
            frame_width=frame_width,
            frame_height=frame_height,
            frames_per_row=frames_per_row,
            animations={
                "idle": (idle_start, idle_count),
                "move": (move_start, move_count),
                "attack": (attack_start, attack_count),
            }
        )
        print(f"\n✓ Successfully created animator!")
        print(f"  Total frames extracted: {len(animator.frames)}")
        print(f"\nUpdate wave_manager.py _load_sprite_animator() with:")
        print(f"""
animator = SpriteAnimator(
    sprite_sheet_path="{sprite_path}",
    frame_width={frame_width},
    frame_height={frame_height},
    frames_per_row={frames_per_row},
    animations={{
        "idle": ({idle_start}, {idle_count}),
        "move": ({move_start}, {move_count}),
        "attack": ({attack_start}, {attack_count}),
    }}
)
""")
    except Exception as e:
        print(f"Error creating animator: {e}")
    finally:
        pygame.quit()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        sprite_path = sys.argv[1]
        analyze_sprite_sheet(sprite_path)
    else:
        print("Sprite Sheet Setup Helper")
        print("=" * 50)
        print("1. Analyze existing sprite sheet")
        print("2. Interactive animator setup")
        print("3. Exit")
        
        choice = input("\nChoose option (1-3): ").strip()
        
        if choice == "1":
            sprite_path = input("Enter sprite sheet path: ").strip()
            analyze_sprite_sheet(sprite_path)
        elif choice == "2":
            create_animator_interactive()
        else:
            print("Exiting.")
