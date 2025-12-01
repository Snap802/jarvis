import sys
import math
import random
import pygame

# ---------------- CONFIG ----------------
DOT_COUNT = 7000
WIDTH, HEIGHT = 1280, 720
BG_COLOR = (0, 0, 0)
DOT_COLOR = (255, 255, 255)
FPS = 400

# Physics tuning — magnetic swarm feel
CENTER_PULL = 0.015       # soft attraction to center
MAG_REPULSION = 0.1     # magnetic push when too close
MAG_RANGE = 55            # how far magnetic repulsion reaches
VELOCITY_DAMP = 0.985     # smooth motion

PARTICLE_RADIUS = 2

# ----------------------------------------
class Dot:
    __slots__ = ("x", "y", "vx", "vy")

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = (random.random() - 0.5) * 0.2
        self.vy = (random.random() - 0.5) * 0.2

    def update(self, cx, cy):
        # --- soft attraction to center (magnetic field pull) ---
        dx = cx - self.x
        dy = cy - self.y
        dist = math.sqrt(dx*dx + dy*dy) + 0.0001
        self.vx += (dx/dist) * CENTER_PULL
        self.vy += (dy/dist) * CENTER_PULL

        # apply velocity damping
        self.vx *= VELOCITY_DAMP
        self.vy *= VELOCITY_DAMP

        self.x += self.vx
        self.y += self.vy

    def magnet_collide(self, other):
        dx = other.x - self.x
        dy = other.y - self.y
        dist = math.sqrt(dx*dx + dy*dy)
        if dist == 0 or dist > MAG_RANGE:
            return

        # normalized direction
        nx = dx / dist
        ny = dy / dist

        # magnetic inverse-square repulsion
        force = MAG_REPULSION * (1 - dist / MAG_RANGE)

        # apply equally
        self.vx -= nx * force
        self.vy -= ny * force
        other.vx += nx * force
        other.vy += ny * force


# ----------------------------------------
def init_dots(count, w, h):
    dots = []
    spacing = math.sqrt((w * h) / count)
    cols = int(w / spacing)
    rows = int(h / spacing)
    i = 0
    for r in range(rows):
        for c in range(cols):
            if i >= count:
                break
            x = c * spacing + spacing * 0.5
            y = r * spacing + spacing * 0.5
            dots.append(Dot(x, y))
            i += 1
        if i >= count:
            break
    return dots


# ----------------------------------------
def main():
    global WIDTH, HEIGHT
    pygame.init()

    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("Magnetic Swarm HUD — Python")
    clock = pygame.time.Clock()

    dots = init_dots(DOT_COUNT, WIDTH, HEIGHT)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                WIDTH, HEIGHT = event.w, event.h
                screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)

        cx, cy = WIDTH/2, HEIGHT/2

        # --- update particles ---
        for d in dots:
            d.update(cx, cy)

        # --- magnetic repulsion (local interactions only) ---
        for i in range(len(dots)):
            a = dots[i]
            # only check neighbors up to some range in index for perf
            for j in range(i+1, min(len(dots), i+25)):
                b = dots[j]
                a.magnet_collide(b)

        # --- drawing ---
        screen.fill(BG_COLOR)

        for d in dots:
            screen.fill(DOT_COLOR, (int(d.x), int(d.y), 2, 2))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()