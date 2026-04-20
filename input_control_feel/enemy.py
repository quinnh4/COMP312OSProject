from __future__ import annotations
from dataclasses import dataclass, field
import pygame


@dataclass
class Enemy:
    position: pygame.Vector2
    hp: int
    max_hp: int
    speed: float
    size: int
    color: tuple
    is_boss: bool = False
    contact_damage: int = 1
    knockback_resistance: float = 1.0
    velocity: pygame.Vector2 = field(default_factory=lambda: pygame.Vector2(0, 0))

    @property
    def rect(self) -> pygame.Rect:
        r = pygame.Rect(0, 0, self.size, self.size)
        r.center = (int(self.position.x), int(self.position.y))
        return r

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def take_hit(self, damage: float, knockback_dir: pygame.Vector2, impulse: float) -> None:
        self.hp = max(0, self.hp - damage)
        if knockback_dir.length_squared() > 0:
            self.velocity += knockback_dir.normalize() * (impulse / self.knockback_resistance)

    def update(self, dt: float, target_pos: pygame.Vector2, playfield: pygame.Rect,
               neighbours: list[Enemy] | None = None, obstacles: list | None = None) -> None:
        to_target = target_pos - self.position
        if to_target.length_squared() > 0:
            chase = to_target.normalize() * self.speed
        else:
            chase = pygame.Vector2(0, 0)

        # separation steering from other enemies
        separation = pygame.Vector2(0, 0)
        if neighbours:
            for other in neighbours:
                if other is self:
                    continue
                diff = self.position - other.position
                dist = diff.length()
                min_dist = (self.size + other.size) / 2
                if 0 < dist < min_dist:
                    separation += diff.normalize() * (min_dist - dist)

        self.velocity -= self.velocity * min(1.0, 8.0 * dt)
        self.velocity += chase * dt * 60
        self.velocity += separation * 12
        max_v = self.speed * 3.5
        if self.velocity.length() > max_v:
            self.velocity.scale_to_length(max_v)

        # store previous position and attempt move
        prev_pos = pygame.Vector2(self.position)
        self.position += self.velocity * dt

        # obstacle collision: axis-separated so enemies can slide along walls
        if obstacles:
            # X axis
            test_rect = pygame.Rect(0, 0, self.size, self.size)
            test_rect.center = (int(self.position.x), int(prev_pos.y))
            for ob in obstacles:
                if test_rect.colliderect(ob.rect):
                    if self.position.x > prev_pos.x:
                        test_rect.right = ob.rect.left
                    elif self.position.x < prev_pos.x:
                        test_rect.left = ob.rect.right
                    self.position.x = test_rect.centerx
                    self.velocity.x = 0

            # Y axis
            test_rect = pygame.Rect(0, 0, self.size, self.size)
            test_rect.center = (int(self.position.x), int(self.position.y))
            for ob in obstacles:
                if test_rect.colliderect(ob.rect):
                    if self.position.y > prev_pos.y:
                        test_rect.bottom = ob.rect.top
                    elif self.position.y < prev_pos.y:
                        test_rect.top = ob.rect.bottom
                    self.position.y = test_rect.centery
                    self.velocity.y = 0

        # hard position correction so enemies cannot overlap each other
        if neighbours:
            for other in neighbours:
                if other is self:
                    continue
                diff = self.position - other.position
                dist = diff.length()
                min_dist = (self.size + other.size) / 2
                if 0 < dist < min_dist:
                    self.position += diff.normalize() * (min_dist - dist) * 0.5

        # hard position correction so enemies cannot overlap the player
        player_diff = self.position - target_pos
        player_dist = player_diff.length()
        player_min_dist = (self.size + 32) / 2  # 32 is PLAYER_SIZE
        if 0 < player_dist < player_min_dist:
            self.position += player_diff.normalize() * (player_min_dist - player_dist)

        half = self.size // 2
        self.position.x = max(playfield.left + half, min(playfield.right - half, self.position.x))
        self.position.y = max(playfield.top + half,  min(playfield.bottom - half, self.position.y))

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        r = self.rect
        pygame.draw.rect(screen, self.color, r, border_radius=4)
        outline = (255, 80, 80) if self.is_boss else (200, 60, 60)
        pygame.draw.rect(screen, outline, r, width=2, border_radius=4)

        # health bar
        bar_h = 5
        bar_y = r.top - bar_h - 3
        pygame.draw.rect(screen, (60, 0, 0), (r.left, bar_y, self.size, bar_h))
        fill_w = int(self.size * (self.hp / self.max_hp))
        pygame.draw.rect(screen, (220, 50, 50), (r.left, bar_y, fill_w, bar_h))

        if self.is_boss:
            lbl = font.render("BOSS", True, (255, 30, 200))
            screen.blit(lbl, (r.centerx - lbl.get_width() // 2, bar_y - 18))