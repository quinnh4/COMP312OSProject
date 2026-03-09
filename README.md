# Week 3 Projectile Shooter

Extended week 3 example by adding shooting mechanics, ammo system, and tuned the feel presets.

## Learning goals
- Use events for discrete actions (dash/jump/toggles)
- Use key-state for continuous movement intent
- Normalize 8-direction movement to avoid diagonal speed bugs
- Tune feel with small parameter presets

## Run
From this folder:

- `python3 -m pip install pygame`
- `python3 main.py`

## Controls
- Arrow keys / WASD: move (top-down)
- `P`: toggle platformer mode (jump + gravity)
- `Up` / `W` / `I`: jump (platformer mode)
- `Space`: shoot projectile
- `R`: reload 
- `Left Shift`: dash (cooldown)
- `1` / `2` / `3`: feel preset (BALANCED/RAPID-FIRE/HEAVY-CANNON)
- `C`: cycle control scheme (WASD / arrows / IJKL)
- `F1`: toggle debug overlay
- `Tab`: cycle boundary mode (clamp/wrap/bounce)
- `CTRL+R`: reset
- `Enter`: start (from title)
- `Esc`: quit

## What I Added
1. I had to remap start game from SPACE to ENTER, so I could use SPACE for the shooting mechanics. I also remapped reset from R to CTRL+R, so I could use R for reload. These changes also prevent conflicts.
2. I created the `Projectile` class to handle shooting mechanics, and added shoot action which was mapped to SPACE through `_try_shoot()` while also adding a reload action which was mapped to R through `_try_reload`. Projectiles will be shot in the last movement direction. 
3. Shoot action (SPACE) is constrained by a fire rate cooldown, ammo capacity, and reload blocking. Reload action (R) is constrained by reload time and the amount of current ammo.
4. I tuned the preset feels to coincide with a balanced, rapid-fire, and heavy-cannon type guns. Balanced is just medium level stats. Rapid-Fire has fast shooting, high ammo, and a quick reload. Heavy-Cannon has slow shooting, low ammo, long reload, and faster projectiles.
5. HUD will show ammo counter which shows current ammo in comparison to max ammo. Also, it will show reload status with a countdown timer, similar to the dash cool down. On-screen projectiles will also be rendered.
6. Ammo will reload automatically if wanting to change to a different preset. Ammo will also auto-reload if player attempts to shoot with 0 ammo.

## Tuning Notes
1. Balanced Preset: Fire rate -> 0.25s, Max ammo -> 8, Reload -> 2.0s, Projectile speed -> 950, and Max speed -> 480. 
    These parameters have the movements of the user feel predictable, comfortable, and the ammo count is also forgiving. After playing with this preset, it shows to be consistent and simple, which makes it lack some identity.
2. Rapid-Fire Preset: Fire rate -> 0.15s, Ammo -> 12, Reload -> 1.5s, Projectile speed -> 800, Max speed -> 520. 
    These parameters create a spam friendly shooting style which also has high mobility that encourages combat within close range; however, with slower projectiles it requires leading targets at distance. After playing with this preset, it was fun to use the rapid fire and have a large max ammo count, but it also frequently depleted ammo despite the capacity, which would require users to use tactical retreats to reload.
3. Heavy-Cannon: Fire rate -> 0.5s, Ammo -> 5, Reload -> 2.5s, Projectile speed -> 1200, Max speed -> 400. 
    These parameters create a need for smart shooting tactics where every shot matters because of the reduced mobility. This preset makes where the player is located on the field critical with fast projectiles doing best at long range. After playing with the preset, the weight of each shot was pretty satisfying, but the 2.5s reload and slower movement could create problems for players in moments where they run out of ammo.

