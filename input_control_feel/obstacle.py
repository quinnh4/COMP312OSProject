from __future__ import annotations
from dataclasses import dataclass
import pygame


@dataclass
class Obstacle:
    rect: pygame.Rect
    color: tuple = (90, 100, 120)
    border_color: tuple = (150, 160, 180)

    def draw(self, screen: pygame.Surface) -> None:
        pygame.draw.rect(screen, self.color, self.rect, border_radius=4)
        pygame.draw.rect(screen, self.border_color, self.rect, width=2, border_radius=4)


def _rect(pf: pygame.Rect, rel_x: float, rel_y: float, w: int, h: int) -> pygame.Rect:
    cx = pf.left + int(pf.width * rel_x)
    cy = pf.top  + int(pf.height * rel_y)
    r = pygame.Rect(0, 0, w, h)
    r.center = (cx, cy)
    return r


def build_layout_for_wave(wave_number: int, pf: pygame.Rect) -> list[Obstacle]:
    if wave_number == 1:
        # sparse cover — introduces the idea
        rects = [
            _rect(pf, 0.25, 0.40, 80, 24),
            _rect(pf, 0.75, 0.60, 80, 24),
            _rect(pf, 0.50, 0.50, 24, 80),
        ]
    elif wave_number == 2:
        # four corners of cover — encourages kiting around them
        rects = [
            _rect(pf, 0.20, 0.25, 70, 30),
            _rect(pf, 0.80, 0.25, 70, 30),
            _rect(pf, 0.20, 0.75, 70, 30),
            _rect(pf, 0.80, 0.75, 70, 30),
            _rect(pf, 0.50, 0.50, 40, 40),
        ]
    elif wave_number == 3:
        # corridors — two vertical walls create funnels
        rects = [
            _rect(pf, 0.33, 0.30, 24, 140),
            _rect(pf, 0.67, 0.70, 24, 140),
            _rect(pf, 0.15, 0.50, 60, 24),
            _rect(pf, 0.85, 0.50, 60, 24),
        ]
    elif wave_number == 4:
        # cross pattern + arena perimeter cover
        rects = [
            _rect(pf, 0.50, 0.30, 120, 20),
            _rect(pf, 0.50, 0.70, 120, 20),
            _rect(pf, 0.25, 0.50, 20, 100),
            _rect(pf, 0.75, 0.50, 20, 100),
        ]
    else:
        # boss arena — pillars to break line-of-sight with the boss
        rects = [
            _rect(pf, 0.25, 0.35, 40, 40),
            _rect(pf, 0.75, 0.35, 40, 40),
            _rect(pf, 0.25, 0.65, 40, 40),
            _rect(pf, 0.75, 0.65, 40, 40),
        ]

    return [Obstacle(r) for r in rects]


def resolve_rect_collision(rect: pygame.Rect, obstacles: list[Obstacle],
                           prev_rect: pygame.Rect) -> pygame.Rect:
    new_rect = rect.copy()

    # resolve X axis
    test_x = prev_rect.copy()
    test_x.x = new_rect.x
    for ob in obstacles:
        if test_x.colliderect(ob.rect):
            if new_rect.x > prev_rect.x:
                test_x.right = ob.rect.left
            elif new_rect.x < prev_rect.x:
                test_x.left = ob.rect.right

    # resolve Y axis using x-resolved rect
    test_y = test_x.copy()
    test_y.y = new_rect.y
    for ob in obstacles:
        if test_y.colliderect(ob.rect):
            if new_rect.y > prev_rect.y:
                test_y.bottom = ob.rect.top
            elif new_rect.y < prev_rect.y:
                test_y.top = ob.rect.bottom

    return test_y


def projectile_hits_obstacle(point: pygame.Vector2, obstacles: list[Obstacle]) -> bool:
    for ob in obstacles:
        if ob.rect.collidepoint(point.x, point.y):
            return True
    return False


def draw_obstacles(screen: pygame.Surface, obstacles: list[Obstacle]) -> None:
    for ob in obstacles:
        ob.draw(screen)