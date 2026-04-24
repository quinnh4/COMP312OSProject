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
    - cd COMP312OSProject
3. python main.py

## Technologies Used
- Python
- Pygame

## Controls
- Arrow keys / `WASD`: move (top-down)
- `Space`: shoot projectile
- `R`: reload
- `1` / `2` / `3`: weapon choice (Balanced / Rapid Fire / Heavy Cannon)
- `P` / `Esc`: pause / resume
- Left Mouse Click: interact with UI (pause menu, title screen)
- `Enter`: start game (from title screen)
- `Ctrl` + `R`: reset game
- `I`: invincibilty for debug
- `F1`: toggle debug overlay

## Authors
- Quinn Hasselgren
- Ryan Compas
- Khumoyun Abdulpattoev

## Tombstone PNG Credit:
- tombstone1.png: https://www.shutterstock.com/image-vector/gravestone-pixel-art-set-objects-tombstone-2683992699
- tombstone2.png: https://www.shutterstock.com/image-vector/gravestone-pixel-art-set-objects-tombstone-2683992699
- tombstone3.png: https://www.shutterstock.com/image-vector/gravestone-pixel-art-set-objects-tombstone-2683992699
- tombstone4.png: https://www.shutterstock.com/image-vector/gravestone-pixel-art-set-objects-tombstone-2683992699
- tombstone5.png: https://www.shutterstock.com/image-vector/gravestone-pixel-art-set-objects-tombstone-2683992699

## Sound Effect Credits (Royalty-Free)
- main_music.mp3: https://pixabay.com/music/mystery-electro-zombies-371569/
- level_music.mp3: https://pixabay.com/music/fantasy-dreamy-childrens-plagued-bastion-survival-undead-haven-477915/
- boss_zombie.mp3: https://pixabay.com/sound-effects/horror-zombie-3-106344/
- zombie_death.mp3: https://pixabay.com/sound-effects/zombie-15965/
- death.mp3: https://pixabay.com/sound-effects/horror-male-death-sound-128357/
- powerup.mp3: https://pixabay.com/sound-effects/film-special-effects-video-game-power-up-sound-effect-384657/
- gun.mp3: https://pixabay.com/sound-effects/film-special-effects-single-pistol-gunshot-42-40781/
- hurt.mp3: https://pixabay.com/sound-effects/film-special-effects-retro-hurt-2-236675/