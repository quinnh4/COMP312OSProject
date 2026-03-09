import pygame

from input_control_feel.game import Game


def main() -> None:
    pygame.init()
    pygame.display.set_caption("Week 3 Input + Control Feel (Pygame)")

    game = Game()
    clock = pygame.time.Clock()

    running = True
    while running:
        dt = clock.tick(game.fps) / 1000.0
        dt = min(dt, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                game.handle_event(event)

        game.update(dt)
        game.draw()
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
