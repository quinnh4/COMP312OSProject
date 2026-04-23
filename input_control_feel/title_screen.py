from __future__ import annotations
from dataclasses import dataclass
import math
import random
import pygame




# palette (arcade/pixel-art vibe)
BG_TOP        = (12, 8, 20)
BG_BOTTOM     = (40, 14, 24)
MOON_COLOR    = (240, 230, 200)
MOON_GLOW     = (180, 140, 120)
GROUND_COLOR  = (28, 20, 24)
GROUND_DARK   = (16, 10, 14)
GRAVE_COLOR   = (70, 68, 78)
GRAVE_DARK    = (40, 38, 48)
BLOOD_RED     = (170, 20, 20)
BLOOD_BRIGHT  = (220, 30, 30)
TITLE_YELLOW  = (255, 210, 60)
TITLE_RED     = (200, 30, 30)
TEXT_LIGHT    = (230, 220, 200)
TEXT_DIM      = (150, 140, 130)
BTN_FILL      = (60, 20, 24)
BTN_FILL_HOVER= (120, 30, 36)
BTN_BORDER    = (180, 40, 40)
BTN_BORDER_HOVER = (255, 210, 60)


# pixel size for the chunky arcade look
PIXEL = 4




@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: str  # "start", "quit", "restart", "menu", "resume"


    def is_hover(self, mouse_pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(mouse_pos)




def _draw_pixel_rect(surf: pygame.Surface, color: tuple, x: int, y: int, w: int, h: int) -> None:
    # snap to the pixel grid so everything stays chunky
    px = (x // PIXEL) * PIXEL
    py = (y // PIXEL) * PIXEL
    pw = max(PIXEL, (w // PIXEL) * PIXEL)
    ph = max(PIXEL, (h // PIXEL) * PIXEL)
    pygame.draw.rect(surf, color, (px, py, pw, ph))




def _draw_gradient_background(surf: pygame.Surface) -> None:
    # vertical gradient — dark purple sky into a blood-red horizon
    w, h = surf.get_size()
    for y in range(0, h, PIXEL):
        t = y / h
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        pygame.draw.rect(surf, (r, g, b), (0, y, w, PIXEL))




def _draw_stars(surf: pygame.Surface, stars: list[tuple[int, int, int]], twinkle: float) -> None:
    # tiny pixel stars, some of which twinkle via sine phase
    for (x, y, seed) in stars:
        phase = (twinkle + seed) % (math.pi * 2)
        brightness = 0.5 + 0.5 * math.sin(phase * 2)
        if brightness > 0.4:
            c = int(180 + 75 * brightness)
            pygame.draw.rect(surf, (c, c, c - 20), (x, y, PIXEL, PIXEL))




def _draw_moon(surf: pygame.Surface, cx: int, cy: int, radius: int, pulse: float) -> None:
    # blood moon with a soft glow halo
    for i in range(6, 0, -1):
        alpha = int(20 + pulse * 15)
        glow_surf = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*MOON_GLOW, alpha), (radius * 2, radius * 2), radius + i * 4)
        surf.blit(glow_surf, (cx - radius * 2, cy - radius * 2))
    # moon body drawn pixel-by-pixel so it stays chunky
    for dx in range(-radius, radius + 1, PIXEL):
        for dy in range(-radius, radius + 1, PIXEL):
            if dx * dx + dy * dy <= radius * radius:
                shade = MOON_COLOR
                # stipple the rim for some texture
                if (dx + dy) % (PIXEL * 3) == 0 and dx * dx + dy * dy > (radius - 8) ** 2:
                    shade = MOON_GLOW
                pygame.draw.rect(surf, shade, (cx + dx, cy + dy, PIXEL, PIXEL))
    # a couple of darker craters
    for (ox, oy, rr) in [(-10, -6, 5), (6, 8, 4), (-4, 10, 3)]:
        for dx in range(-rr, rr + 1, PIXEL):
            for dy in range(-rr, rr + 1, PIXEL):
                if dx * dx + dy * dy <= rr * rr:
                    pygame.draw.rect(surf, MOON_GLOW, (cx + ox + dx, cy + oy + dy, PIXEL, PIXEL))




def _draw_ground(surf: pygame.Surface, ground_y: int) -> None:
    w, h = surf.get_size()
    # main dirt
    pygame.draw.rect(surf, GROUND_COLOR, (0, ground_y, w, h - ground_y))
    # jagged top edge so it doesn't look like a flat table
    random.seed(7)
    x = 0
    while x < w:
        bump_h = random.choice([0, PIXEL, PIXEL, PIXEL * 2])
        pygame.draw.rect(surf, GROUND_DARK, (x, ground_y - bump_h, PIXEL * 3, PIXEL))
        x += PIXEL * 3
    # scattered pebbles for ground detail
    random.seed(42)
    for _ in range(18):
        px = random.randint(0, w)
        py = ground_y + random.randint(4, 30)
        pygame.draw.rect(surf, GROUND_DARK, (px, py, PIXEL * 2, PIXEL))




def _draw_gravestone(surf: pygame.Surface, x: int, y: int, big: bool = False) -> None:
    scale = 2 if big else 1
    w = PIXEL * 6 * scale
    h = PIXEL * 8 * scale
    # main stone body
    _draw_pixel_rect(surf, GRAVE_COLOR, x, y + PIXEL * 2 * scale, w, h - PIXEL * 2 * scale)
    # rounded top — two pixel rows narrowing toward the top
    _draw_pixel_rect(surf, GRAVE_COLOR, x + PIXEL * scale, y + PIXEL * scale, w - PIXEL * 2 * scale, PIXEL * scale)
    _draw_pixel_rect(surf, GRAVE_COLOR, x + PIXEL * 2 * scale, y, w - PIXEL * 4 * scale, PIXEL * scale)
    # darker right side for a bit of shading
    _draw_pixel_rect(surf, GRAVE_DARK, x + w - PIXEL * scale, y + PIXEL * 2 * scale, PIXEL * scale, h - PIXEL * 2 * scale)
    # RIP cross
    cx = x + w // 2
    cy = y + PIXEL * 4 * scale
    _draw_pixel_rect(surf, GRAVE_DARK, cx - PIXEL // 2, cy, PIXEL, PIXEL * 3 * scale)
    _draw_pixel_rect(surf, GRAVE_DARK, cx - PIXEL * scale, cy + PIXEL * scale, PIXEL * 3 * scale, PIXEL)




def _draw_zombie(surf: pygame.Surface, x: int, y: int, shuffle: float, flip: bool = False) -> None:
    # chunky pixel-art zombie — shuffle animates the arm sway
    skin     = (100, 140, 80)
    skin_drk = (70, 100, 55)
    shirt    = (80, 45, 55)
    shirt_drk= (55, 25, 35)
    pants    = (40, 35, 60)
    blood    = (160, 20, 20)
    eye      = (255, 230, 60)


    s = PIXEL  # one pixel unit
    sway = int(math.sin(shuffle) * 1) * s


    def px(dx, dy, w=1, h=1, color=skin):
        xx = x + (dx if not flip else (9 - dx - w)) * s
        yy = y + dy * s
        pygame.draw.rect(surf, color, (xx, yy, w * s, h * s))


    # head
    px(2, 0, 5, 3, skin)
    px(2, 0, 5, 1, skin_drk)       # top shadow row
    # glowing eyes
    px(3, 1, 1, 1, eye)
    px(5, 1, 1, 1, eye)
    # mouth + blood drip
    px(4, 2, 2, 1, blood)
    px(4, 3, 1, 1, blood)


    # neck / torso
    px(3, 3, 3, 1, skin_drk)
    px(2, 4, 5, 3, shirt)
    px(2, 6, 5, 1, shirt_drk)
    # torn shirt hole showing skin
    px(4, 5, 1, 1, skin)


    # arms outstretched — sway is opposite on each side
    px(0, 4 + sway // s, 2, 1, skin)
    px(1, 5 + sway // s, 1, 1, skin_drk)
    px(7, 4 - sway // s, 2, 1, skin)
    px(7, 5 - sway // s, 1, 1, skin_drk)


    # pants + legs
    px(2, 7, 5, 2, pants)
    px(4, 7, 1, 2, shirt_drk)  # leg split
    # feet
    px(2, 9, 2, 1, (20, 20, 20))
    px(5, 9, 2, 1, (20, 20, 20))




def _draw_blood_splat(surf: pygame.Surface, x: int, y: int, size: int = 3) -> None:
    s = PIXEL
    # main blob
    pygame.draw.rect(surf, BLOOD_RED, (x, y, s * size, s * size))
    # droplets around it
    pygame.draw.rect(surf, BLOOD_RED, (x - s, y + s, s, s))
    pygame.draw.rect(surf, BLOOD_RED, (x + s * size, y + s * 2, s, s))
    pygame.draw.rect(surf, BLOOD_BRIGHT, (x + s, y + s, s, s))




def _draw_title_text(surf: pygame.Surface, font: pygame.font.Font, flicker: float) -> None:
    # big chunky title with drop shadow + blood drips
    w, _ = surf.get_size()


    line1 = "CALL OF"
    line2 = "ZOMBIE DUTY"


    # slight jitter for the horror vibe
    jitter_x = int(math.sin(flicker * 3) * 1)
    jitter_y = int(math.cos(flicker * 2) * 1)


    # stacked drop-shadow layers — gives the chunky 3D poster feel
    for (ox, oy, col) in [(6, 6, (0, 0, 0)),
                          (4, 4, (40, 0, 0)),
                          (2, 2, (120, 10, 10))]:
        s1 = font.render(line1, True, col)
        s2 = font.render(line2, True, col)
        surf.blit(s1, (w // 2 - s1.get_width() // 2 + ox + jitter_x, 56 + oy + jitter_y))
        surf.blit(s2, (w // 2 - s2.get_width() // 2 + ox, 110 + oy))


    # main face — occasionally flickers brighter like a neon sign
    face_color = TITLE_YELLOW if int(flicker * 20) % 40 != 0 else (255, 240, 120)
    s1 = font.render(line1, True, face_color)
    s2 = font.render(line2, True, TITLE_RED)
    surf.blit(s1, (w // 2 - s1.get_width() // 2 + jitter_x, 56 + jitter_y))
    surf.blit(s2, (w // 2 - s2.get_width() // 2, 110))


    # blood drips hanging off the red title line
    x2 = w // 2 - s2.get_width() // 2
    for i, (dx, dlen) in enumerate([(30, 14), (90, 8), (150, 18), (210, 10), (260, 22)]):
        drip_y = 110 + s2.get_height() - 4
        pygame.draw.rect(surf, BLOOD_RED, (x2 + dx, drip_y, PIXEL, dlen))
        pygame.draw.rect(surf, BLOOD_BRIGHT, (x2 + dx, drip_y + dlen, PIXEL, PIXEL))




def _draw_button(surf: pygame.Surface, btn: Button, font: pygame.font.Font,
                 mouse_pos: tuple[int, int]) -> None:
    hover = btn.is_hover(mouse_pos)
    fill   = BTN_FILL_HOVER if hover else BTN_FILL
    border = BTN_BORDER_HOVER if hover else BTN_BORDER


    # drop shadow
    shadow = btn.rect.move(4, 4)
    pygame.draw.rect(surf, (0, 0, 0), shadow)


    # body
    pygame.draw.rect(surf, fill, btn.rect)
    # chunky pixel border — no rounded corners so it keeps the arcade look
    pygame.draw.rect(surf, border, btn.rect, width=PIXEL)


    # inner highlight on hover
    inner = btn.rect.inflate(-PIXEL * 2, -PIXEL * 2)
    if hover:
        pygame.draw.rect(surf, (180, 60, 60), inner, width=1)


    label_surf = font.render(btn.label, True, TEXT_LIGHT if not hover else TITLE_YELLOW)
    surf.blit(label_surf,
              (btn.rect.centerx - label_surf.get_width() // 2,
               btn.rect.centery - label_surf.get_height() // 2))


    # little arrow indicator when hovered
    if hover:
        tri_x = btn.rect.left + 12
        tri_y = btn.rect.centery
        pygame.draw.polygon(surf, TITLE_YELLOW,
                            [(tri_x, tri_y - 6), (tri_x, tri_y + 6), (tri_x + 8, tri_y)])




class TitleScreen:


    def __init__(self, screen_w: int, screen_h: int,
                 title_font: pygame.font.Font,
                 button_font: pygame.font.Font,
                 small_font: pygame.font.Font) -> None:
        self.w = screen_w
        self.h = screen_h
        self.title_font = title_font
        self.button_font = button_font
        self.small_font = small_font


        self.time = 0.0


        # pre-generate star positions so they don't jitter between frames
        random.seed(1234)
        self.stars = [
            (random.randint(0, screen_w), random.randint(0, int(screen_h * 0.55)),
             random.random() * math.pi * 2)
            for _ in range(60)
        ]


        # gravestone positions along the ground
        self.graves: list[tuple[int, int, bool]] = []
        random.seed(99)
        gy = int(screen_h * 0.72)
        for gx in range(40, screen_w, 90):
            if random.random() < 0.7:
                offset_x = random.randint(-12, 12)
                offset_y = random.randint(-4, 8)
                big = random.random() < 0.3
                self.graves.append((gx + offset_x, gy + offset_y, big))


        # zombies shambling across — two going each direction
        self.zombies = [
            {"x": 120.0, "y": screen_h * 0.78, "speed": 18.0, "flip": False, "phase": 0.0},
            {"x": 320.0, "y": screen_h * 0.82, "speed": 14.0, "flip": False, "phase": 1.5},
            {"x": 620.0, "y": screen_h * 0.76, "speed": 16.0, "flip": True,  "phase": 3.0},
            {"x": 780.0, "y": screen_h * 0.80, "speed": 12.0, "flip": True,  "phase": 0.8},
        ]


        # buttons centered horizontally, lower-middle of the screen
        btn_w, btn_h = 280, 54
        cx = screen_w // 2
        base_y = int(screen_h * 0.64)
        self.buttons: list[Button] = [
            Button(pygame.Rect(cx - btn_w // 2, base_y,                 btn_w, btn_h), "START GAME", "start"),
            Button(pygame.Rect(cx - btn_w // 2, base_y + btn_h + 14,    btn_w, btn_h), "QUIT",       "quit"),
        ]


    def update(self, dt: float) -> None:
        self.time += dt
        for z in self.zombies:
            z["phase"] += dt * 6.0
            z["x"] += z["speed"] * dt * (-1 if z["flip"] else 1)
            # wrap around the screen edges
            if not z["flip"] and z["x"] > self.w + 40:
                z["x"] = -40
            elif z["flip"] and z["x"] < -40:
                z["x"] = self.w + 40


    def handle_click(self, mouse_pos: tuple[int, int]) -> str | None:
        for btn in self.buttons:
            if btn.is_hover(mouse_pos):
                return btn.action
        return None


    def draw(self, surf: pygame.Surface) -> None:
        mouse_pos = pygame.mouse.get_pos()


        # background + stars + moon
        _draw_gradient_background(surf)
        _draw_stars(surf, self.stars, self.time)


        moon_pulse = 0.5 + 0.5 * math.sin(self.time * 1.5)
        _draw_moon(surf, int(self.w * 0.82), int(self.h * 0.22), 32, moon_pulse)


        # distant skyline silhouette — just dark blocks of varying heights
        skyline_y = int(self.h * 0.70)
        for bx in range(0, self.w, 64):
            bh = 20 + int(abs(math.sin(bx * 0.07)) * 30) + ((bx // 32) % 3) * 6
            pygame.draw.rect(surf, (14, 10, 18), (bx, skyline_y - bh, 48, bh))
            # a few lit windows for atmosphere
            if (bx // 32) % 3 == 0:
                pygame.draw.rect(surf, (180, 40, 40),
                                 (bx + 12, skyline_y - bh + 10, PIXEL, PIXEL))


        # ground
        ground_y = int(self.h * 0.70)
        _draw_ground(surf, ground_y)


        # gravestones go before zombies so the zombies can walk in front of them
        for (gx, gy, big) in self.graves:
            _draw_gravestone(surf, gx, gy, big=big)


        # shambling zombies
        for z in self.zombies:
            _draw_zombie(surf, int(z["x"]), int(z["y"]), z["phase"], flip=z["flip"])


        # blood splats scattered on the ground
        random.seed(17)
        for _ in range(6):
            bx = random.randint(40, self.w - 40)
            by = random.randint(ground_y + 10, self.h - 20)
            _draw_blood_splat(surf, bx, by, size=random.choice([2, 3]))


        # title text on top of everything
        _draw_title_text(surf, self.title_font, self.time)


        # tagline
        tag = self.small_font.render("~ A TOP-DOWN ZOMBIE SHOOTER ~", True, TEXT_DIM)
        surf.blit(tag, (self.w // 2 - tag.get_width() // 2, 176))


        # buttons
        for btn in self.buttons:
            _draw_button(surf, btn, self.button_font, mouse_pos)


        # footer hints
        hint = self.small_font.render(
            "WASD move  /  SPACE shoot  /  SHIFT dash  /  R reload  /  P pause",
            True, TEXT_DIM)
        surf.blit(hint, (self.w // 2 - hint.get_width() // 2, self.h - 28))


        # blinking prompt above the hint
        blink = "PRESS ENTER OR CLICK START" if int(self.time * 2) % 2 == 0 else ""
        if blink:
            b = self.small_font.render(blink, True, TITLE_YELLOW)
            surf.blit(b, (self.w // 2 - b.get_width() // 2, self.h - 48))




class PauseMenu:


    def __init__(self, screen_w: int, screen_h: int,
                 title_font: pygame.font.Font,
                 button_font: pygame.font.Font,
                 small_font: pygame.font.Font) -> None:
        self.w = screen_w
        self.h = screen_h
        self.title_font = title_font
        self.button_font = button_font
        self.small_font = small_font


        # panel centered on screen
        panel_w, panel_h = 360, 340
        self.panel = pygame.Rect(
            (screen_w - panel_w) // 2, (screen_h - panel_h) // 2,
            panel_w, panel_h)


        btn_w, btn_h = 260, 46
        cx = screen_w // 2
        base_y = self.panel.top + 96
        gap = btn_h + 12
        self.buttons: list[Button] = [
            Button(pygame.Rect(cx - btn_w // 2, base_y,             btn_w, btn_h), "RESUME",    "resume"),
            Button(pygame.Rect(cx - btn_w // 2, base_y + gap,       btn_w, btn_h), "RESTART",   "restart"),
            Button(pygame.Rect(cx - btn_w // 2, base_y + gap * 2,   btn_w, btn_h), "MAIN MENU", "menu"),
            Button(pygame.Rect(cx - btn_w // 2, base_y + gap * 3,   btn_w, btn_h), "QUIT",      "quit"),
        ]


    def handle_click(self, mouse_pos: tuple[int, int]) -> str | None:
        for btn in self.buttons:
            if btn.is_hover(mouse_pos):
                return btn.action
        return None


    def draw(self, surf: pygame.Surface) -> None:
        mouse_pos = pygame.mouse.get_pos()


        # dim overlay so the gameplay behind it reads as "paused"
        dim = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        surf.blit(dim, (0, 0))


        # panel shadow
        shadow = self.panel.move(6, 6)
        pygame.draw.rect(surf, (0, 0, 0), shadow)


        # panel body + outer border
        pygame.draw.rect(surf, (28, 20, 28), self.panel)
        pygame.draw.rect(surf, BTN_BORDER, self.panel, width=PIXEL)
        # inner thin border — gives a double-bordered arcade feel
        inner = self.panel.inflate(-PIXEL * 3, -PIXEL * 3)
        pygame.draw.rect(surf, (60, 20, 24), inner, width=1)


        # PAUSED title with shadow
        title_surf = self.title_font.render("PAUSED", True, TITLE_YELLOW)
        shadow_surf = self.title_font.render("PAUSED", True, (60, 10, 10))
        tx = self.panel.centerx - title_surf.get_width() // 2
        ty = self.panel.top + 26
        surf.blit(shadow_surf, (tx + 3, ty + 3))
        surf.blit(title_surf, (tx, ty))


        # blood drip accents under the title
        for (dx, dlen) in [(-40, 8), (0, 14), (36, 6)]:
            pygame.draw.rect(surf, BLOOD_RED,
                             (self.panel.centerx + dx, ty + title_surf.get_height() - 2, PIXEL, dlen))


        # buttons
        for btn in self.buttons:
            _draw_button(surf, btn, self.button_font, mouse_pos)


        # footer hint
        hint = self.small_font.render("P or ESC to resume", True, TEXT_DIM)
        surf.blit(hint, (self.panel.centerx - hint.get_width() // 2,
                         self.panel.bottom - 24))