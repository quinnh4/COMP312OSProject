# Call of Zombie Duty

This project is a 2D top-down zombie shooter focused on wave-based survival and dynamic gameplay. Players fight through five increasingly difficult waves of enemies, ending in a final boss battle.

The game features procedurally generated obstacles, creating a unique playfield each run and encouraging adaptability. Players can choose between three distinct weapon types—balanced, rapid fire, and heavy cannon—each offering different trade-offs in speed, damage, and ammo capacity.

Throughout the game, collectible power-ups such as health, ammo, shields, damage boosts, and fire rate enhancements spawn randomly, providing strategic advantages and increasing survivability.

The project is built using a modular Python architecture, with separate systems for enemy management, player control, rendering, and game logic, making the codebase scalable and maintainable.

## Features
- Wave-based enemy system with increasing difficulty
- Final boss battle on wave 5
- Procedurally generated obstacles for unique gameplay
- Three weapon types with distinct playstyles:
    - Balanced – moderate speed, fire rate, and damage
    - Rapid Fire – high speed and fire rate, low damage
    - Heavy Cannon – high damage, slower movement and fire rate
- Randomly spawning power-ups:
    - Health
    - Ammo
    - Shield
    - Damage boost
    - Fire rate boost
    - Sprite-based animations using sprite sheets

## Setup
1. Make sure Python is installed on your device
2. Install dependencies
- pip install pygame
2. Clone the repo
- git clone https://github.com/quinnh4/COMP312OSProject
- cd OMP312OSProject
3. python main.py

## Technologies Used
- Python
- Pygame

## Controls
- Arrow keys / `WASD` / `IJKL`: move (top-down)
- `Space`: shoot projectile
- `R`: reload
- `1` / `2` / `3`: weapon choice (Balanced / Rapid Fire / Heavy Cannon)
- `P` / `Esc`: pause / resume
- Left Mouse Click: interact with UI (pause menu, title screen)
- `Enter`: start game (from title screen)
- `C`: cycle control scheme (WASD / arrows / IJKL)
- `Ctrl` + `R`: reset game
- `F1`: toggle debug overlay

## Authors
- Quinn Hasselgren
- Ryan Compas
- Khumoyun Abdulpattoev


