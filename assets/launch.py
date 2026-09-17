#!/usr/bin/env python3
"""Render assets/launch.gif + assets/launch.txt - the ASCII rocket launch on the profile README.

Run:  python3 assets/launch.py     (needs Pillow and the font path below)

The scene is composed on a character grid, one frame at a time, then drawn with a
monospace font. Ascent is sold by scrolling the world downward while the rocket
holds near the top of the frame.
"""
import os, random
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
FONT = "/mnt/skills/examples/canvas-design/canvas-fonts/JetBrainsMono-Regular.ttf"

# ------------------------------------------------------------------ palette --
# Single source of truth - editing these hex values re-skins the whole animation.
P = {
    "bg":     "#211d1b",
    "chrome": "#2b2523",
    "fg":     "#d8c9ac",   # rocket + tower line art
    "dim":    "#8d7f68",   # ground, pads, gantry, faded stars
    "star":   "#a99a80",
    "cyan":   "#6fd3e8",   # prompt user, porthole, cursor
    "gold":   "#e6b450",   # the name, "V M"
    "red":    "#e2665a",
    "f1":     "#ffd166",   # flame core
    "f2":     "#ff9d3c",   # flame mid
    "f3":     "#e2665a",   # flame tip
    "smoke":  "#60564c",
}

W, H = 62, 26              # art grid, in characters
PAD_ROW, GND_ROW = 23, 24
TOWER_C = 13               # tower occupies cols 13..15
RX, REST_RY = 28, 6        # rocket sprite origin (col, row) on the pad
CRUISE_RY = 2              # row the rocket holds at while the world scrolls

# frame timeline
TYPE_END, IGN, LIFT, CLIMB, EXIT, WHOAMI, NAME_AT = 14, 16, 26, 34, 58, 62, 71
N = 80

ROCKET = [
    "       /\\",
    "      /  \\",
    "     /    \\",
    "    /  __  \\",
    "   /________\\",
    "   |        |",
    "   |  .---. |",
    "   |  ( o ) |",
    "   |  `---' |",
    "   |        |",
    "   |  V M   |",
    "   |        |",
    "   |________|",
    "  /|  |  |  |\\",
    " / |  |  |  | \\",
    "/__|__|__|__|__\\",
    "   \\________/",
]
MOON = ["  .---.  ", " /     \\ ", "|   o   |", " \\     / ", "  `---'  "]
MOON_R, MOON_C = 1, 49

# ---------------------------------------------------------------- starfield --
random.seed(11)
_block = set()
for r in range(H):
    for c in range(TOWER_C - 2, TOWER_C + 5):
        _block.add((r, c))
for r in range(-1, PAD_ROW + 2):
    for c in range(RX - 3, RX + 19):
        _block.add((r, c))
for i in range(len(MOON)):
    for j in range(len(MOON[0])):
        _block.add((MOON_R + i, MOON_C + j))
STARS = []
for _ in range(600):
    r, c = random.randrange(0, PAD_ROW), random.randrange(0, W)
    if (r, c) in _block or any(abs(r - sr) + abs(c - sc) < 3 for sr, sc, _, _ in STARS):
        continue
    STARS.append((r, c, random.choice([".", ".", ".", "+", "*", "'"]), random.random()))
    if len(STARS) >= 44:
        break


class Grid:
    def __init__(self):
        self.ch = [[" "] * W for _ in range(H)]
        self.co = [["fg"] * W for _ in range(H)]

    def put(self, r, c, s, color="fg"):
        if not (0 <= r < H):
            return
        for i, x in enumerate(s):
            cc = c + i
            if 0 <= cc < W and x != " ":
                self.ch[r][cc] = x
                self.co[r][cc] = color

    def blit(self, r0, c0, sprite, color="fg"):
        for i, line in enumerate(sprite):
            self.put(r0 + i, c0, line, color)


def world_dy(i):
    """How far the ground has fallen away, in rows."""
    if i < CLIMB:
        return 0.0
    k = (i - CLIMB) / float(EXIT - CLIMB)
    return (k ** 1.35) * 34.0


def rocket_row(i):
    if i < LIFT:
        return REST_RY
    if i < CLIMB:
        k = (i - LIFT) / float(CLIMB - LIFT)
        return int(round(REST_RY - k * (REST_RY - CRUISE_RY)))
    if i < EXIT:
        return CRUISE_RY
    return int(round(CRUISE_RY - ((i - EXIT) / 4.0) ** 1.9))


def engine_power(i):
    if i < IGN:
        return 0.0
    if i < LIFT:
        return 0.25 + 0.75 * (i - IGN) / float(LIFT - IGN)
    return 1.0


def tower(g, dy, arm_len, lit):
    g.put(5 + dy, TOWER_C + 1, "o", "red" if lit else "dim")
    g.put(6 + dy, TOWER_C, "/^\\", "dim")
    for r in range(7, PAD_ROW):
        g.put(r + dy, TOWER_C, "|X|" if r % 2 else "|/|", "fg")
    g.put(PAD_ROW + dy, TOWER_C - 1, "[===]", "dim")
    for r in (11, 17):                     # gantry arms retract at ignition
        if arm_len > 0:
            g.put(r + dy, TOWER_C + 3, "=" * arm_len + "+", "dim")


def plume(g, base_r, power, flying):
    """Exhaust below the rocket: a tapering cone, fading to a smoke trail."""
    if power <= 0:
        return
    length = H if flying else int(2 + power * 8)
    for i in range(length):
        r = base_r + i
        if r >= H:
            break
        taper = 1.0 - min(1.0, i / 9.0)
        half = max(0, int(taper * 3.6 * (0.5 + power * 0.7)))
        if i < 7:
            color = "f1" if i < 2 else ("f2" if i < 4 else "f3")
            row = []
            for k in range(-half, half + 1):
                if k < 0:
                    row.append("\\" if (i + k) % 2 else "|")
                elif k > 0:
                    row.append("/" if (i + k) % 2 else "|")
                else:
                    row.append("|" if i % 2 else "^")
            g.put(r, RX + 8 - half, "".join(row), color)
        elif flying:                        # dispersing trail behind the rocket
            for k in range(-4, 5):
                if random.random() < 0.34 - abs(k) * 0.05:
                    g.put(r, RX + 8 + k, random.choice(".o" + chr(176)), "smoke")


def splash(g, dy, power):
    """Exhaust hitting the pad and rolling sideways."""
    for side in (-1, 1):
        w = int(4 + power * 7)
        s = "".join(random.choice("~-=") for _ in range(w))
        g.put(PAD_ROW - 1 + dy, (RX + 3 - w) if side < 0 else (RX + 14), s, "f2")


def smoke(g, dy, age):
    """Billowing cloud at the pad: dense at the centre, thinning outward."""
    grow = min(1.0, age / 20.0)
    for r in range(PAD_ROW - 1, GND_ROW + 2):
        half = int(5 + 15 * grow)
        for c in range(RX + 8 - half, RX + 9 + half):
            if not (0 <= c < W):
                continue
            d = abs(c - (RX + 8)) / float(half)
            if random.random() < (0.55 - 0.42 * d) * (1.0 - 0.3 * grow):
                g.put(r + dy, c, random.choice(".oO" if d < 0.5 else ".o" + chr(176)), "smoke")


def frame(i):
    g = Grid()
    dyf = world_dy(i)
    dy = int(round(dyf))
    ry = rocket_row(i)
    power = engine_power(i)
    arms = 12 if i < IGN else max(0, int(12 * (1 - ((i - IGN) / float(LIFT - IGN)) * 1.5)))
    on_pad = i < LIFT + 3

    # stars: fixed while grounded, flowing downward (and wrapping) once climbing
    for sr, sc, s, ph in STARS:
        tw = (i / float(N) * 2.4 + ph) % 1.0
        g.put(int(sr + dyf) % H if dy else sr, sc, s, "star" if tw > 0.35 else "dim")
    g.blit(MOON_R + dy, MOON_C, MOON, "dim")
    g.put(MOON_R + 2 + dy, MOON_C + 4, "o", "cyan")

    tower(g, dy, arms, i >= IGN and i % 4 < 2)
    g.put(PAD_ROW + dy, RX - 1, "[" + "=" * 16 + "]", "dim")
    g.put(GND_ROW + dy, 0, "- " * (W // 2), "dim")

    if ry + len(ROCKET) > -1:
        jitter = 1 if (IGN <= i < LIFT and i % 2) else 0
        g.blit(ry, RX + jitter, ROCKET, "fg")
        g.put(ry + 7, RX + 8 + jitter, "o", "cyan")
        g.put(ry + 10, RX + 6 + jitter, "V M", "gold")
        plume(g, ry + len(ROCKET), power, i >= LIFT)
    if power > 0:
        if on_pad:
            splash(g, dy, power)
        if dy < H:
            smoke(g, dy, i - IGN)
    return g


# ------------------------------------------------------------------- render --
FS, LH = 15, 20
font = ImageFont.truetype(FONT, FS)
CW = font.getlength("M")
X0, Y0 = 22, 78
CHROME_H = 34
IMG_W = int(X0 * 2 + CW * W)
IMG_H = int(Y0 + LH * (H + 3) + 18)
CMD, NAME = "./launch.sh", "Vivek Murali"
BLOCK = chr(9608)


def draw_frame(i):
    g = frame(i)
    im = Image.new("RGB", (IMG_W, IMG_H), P["bg"])
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, IMG_W, CHROME_H], fill=P["chrome"])
    for k, col in enumerate(("#e0685d", "#e3ad4a", "#63b95a")):
        d.ellipse([16 + k * 18, 12, 26 + k * 18, 22], fill=col)
    title = "vivek@github: ~$ ./launch.sh"
    d.text((IMG_W / 2 - font.getlength(title) / 2, 10), title, font=font, fill=P["dim"])

    y, x = CHROME_H + 14, X0
    d.text((x, y), "vivek@github", font=font, fill=P["cyan"]); x += CW * 12
    d.text((x, y), ":~$ ", font=font, fill=P["dim"]); x += CW * 4
    shown = CMD if i >= TYPE_END else CMD[: max(0, i - 2)]
    d.text((x, y), shown, font=font, fill=P["fg"]); x += CW * len(shown)
    if i < TYPE_END or i % 4 < 2:
        d.text((x, y), BLOCK, font=font, fill=P["cyan"])

    for r in range(H):
        row, col, start = g.ch[r], g.co[r], 0
        for c in range(1, W + 1):
            if c == W or col[c] != col[start]:
                chunk = "".join(row[start:c])
                if chunk.strip():
                    d.text((X0 + CW * start, Y0 + LH * r), chunk, font=font, fill=P[col[start]])
                start = c

    y, x = Y0 + LH * (H + 1.4), X0
    d.text((x, y), "vivek@github", font=font, fill=P["cyan"]); x += CW * 12
    d.text((x, y), ":~$ ", font=font, fill=P["dim"]); x += CW * 4
    if i >= WHOAMI:
        typed = "whoami"[: max(0, i - WHOAMI)]
        d.text((x, y), typed, font=font, fill=P["fg"]); x += CW * len(typed)
        if i >= NAME_AT:
            shown_name = NAME[: max(0, (i - NAME_AT) * 3)]
            d.text((x + CW * 2, y), shown_name, font=font, fill=P["gold"])
            x += CW * (2 + len(shown_name))
    if i % 4 < 2 or i == N - 1:          # always end on a visible cursor
        d.text((x, y), BLOCK, font=font, fill=P["cyan"])
    return im


random.seed(5)
os.makedirs(OUT, exist_ok=True)
frames = [draw_frame(i) for i in range(N)]
pal = frames[0].quantize(colors=32, method=Image.MEDIANCUT)
frames = [f.quantize(palette=pal, dither=Image.NONE) for f in frames]
durs = [80] * N
durs[0] = 900          # a beat on the pad before the count
durs[N - 1] = 1400     # hold on the name
frames[0].save(os.path.join(OUT, "launch.gif"), save_all=True, append_images=frames[1:],
               duration=durs, loop=0, optimize=True, disposal=2)

# static ASCII source, for anyone who wants to paste it somewhere else
g = frame(0)
with open(os.path.join(OUT, "launch.txt"), "w") as f:
    f.write("vivek@github:~$ ./launch.sh\n\n")
    f.write("\n".join("".join(r).rstrip() for r in g.ch))
    f.write("\n\nvivek@github:~$ whoami  Vivek Murali\n")

sz = os.path.getsize(os.path.join(OUT, "launch.gif"))
print("frames=%d  size=%dx%d  gif=%.0fKB  duration=%.1fs" % (N, IMG_W, IMG_H, sz / 1024, sum(durs) / 1000))
