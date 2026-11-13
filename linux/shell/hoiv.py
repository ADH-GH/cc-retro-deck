#!/usr/bin/env python3
"""Wien im Einschaltbildschirm: LOAD "HOIV",8,1, die Fassung fuer das HOIV in Wien.

Ablauf und Kopf wie nyc.py (links LOAD "HOIV",8,1, SEARCHING FOR HOIV ...), eigenes Bild: Wien in
der Abenddaemmerung, der Stephansdom mit Turm und gemustertem Ziegeldach, die Karlskirche mit
Kuppel und zwei Saeulen, das Riesenrad im Prater, Donauturm und DC Tower, darunter die Donau mit
Spiegelbild; als C64-Bild auf Bildschirmblau, die Abtastzeile laedt den Himmel in 24 Bit nach.
Ladebalken in Orange, Weiss und Schwarz. Bei READY. dreht sich das Riesenrad und der Rahmen wird
orange; bei RUN baut sich das HOIV-Zeichen auf: erst die vier Rahmen des Zeichens, dann die
Buchstaben H O I V, darunter HOME OF INNOVATION als echte Terminalschrift. Kopf
"HACKATHON @ HOIV VIENNA", am Ende "WELCOME TO HOIV!  A PLACE THAT DRIVES YOUR CREATIVITY.".

Das Zeichen ist dem Logo HOIV-logo-full-black-1.png der HOIV-Website (homeofinnovationx.com)
nachgebaut, Orange #F68B1E, auf ganze Zellen gelegt: waagrechte Striche eine Zelle hoch.

    hoiv.py               Animation, etwa 12 s und 3 s Stand; Rueckgabe 2, wenn das
                          Fenster zu klein ist (dann boot.py nehmen)
    hoiv.py --png N f     Bild N des Feldes als PNG, zur Kontrolle ohne Terminal
"""
import math
import os
import random
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402
import nyc  # noqa: E402
from boot import at, RESET  # noqa: E402
from nyc import h32  # noqa: E402
from trek import (SCR, quantize, mix, add, smooth, geometry, write_png, bg, fg,  # noqa: E402
                  F_SWEEP0, F_SWEEP1, F_READY, F_RUN)

ORANGE, LIGHT, BLACK = (246, 139, 30), (243, 243, 244), (0, 0, 0)
WHITE = (250, 250, 250)
NAME = 'HOIV'
SUBTITLE = 'H O M E   O F   I N N O V A T I O N'
F_SYM = [F_RUN + 1, F_RUN + 4, F_RUN + 7, F_RUN + 10]    # die vier Teile des Zeichens
F_LET = [F_RUN + 13, F_RUN + 15, F_RUN + 17, F_RUN + 19]  # H, O, I, V
F_SUB = F_RUN + 21                                        # HOME OF INNOVATION tippt sich ein

# Zeichen: Rechtecke (x0, y0, x1, y1), x in Pixeln, y in Zellen (je 2 Pixel), Ende exklusiv.
# Strich 2 Pixel breit und eine Zelle hoch; 24 Pixel breit, 11 Zellen hoch.
SYMBOL = [
    [(0, 0, 10, 1), (0, 0, 2, 5), (8, 0, 10, 5), (0, 4, 16, 5)],          # oben links, Steg nach rechts
    [(8, 5, 10, 6), (0, 6, 16, 7)],                                         # Mitte und unterer Steg
    [(0, 6, 2, 11), (8, 6, 10, 11), (0, 10, 10, 11)],                       # unten links
    [(14, 0, 24, 1), (14, 0, 16, 11), (22, 0, 24, 11), (14, 10, 24, 11)],   # rechts, hoch
]
SYM_W, SYM_H = 24, 11
LET_H = 7                                                 # Buchstabenhoehe in Zellen


def letters():
    """H O I V als Pixelmengen {(x, zelle)}, Strich 3 Pixel, Abstand 2; Breite 48."""
    out, x0 = [], 0
    h = {(x, r) for r in range(LET_H) for x in (0, 1, 2, 9, 10, 11)} | {(x, 3) for x in range(3, 9)}
    out.append({(x0 + x, r) for x, r in h})
    x0 += 12 + 2
    o = set()
    for r in range(LET_H):
        cy = (r + 0.5 - LET_H / 2) * 2
        for x in range(14):
            cx = x + 0.5 - 7
            if (cx / 7) ** 2 + (cy / 7) ** 2 <= 1 and (cx / 4) ** 2 + (cy / 4.6) ** 2 > 1:
                o.add((x0 + x, r))
    out.append(o)
    x0 += 14 + 2
    out.append({(x0 + x, r) for r in range(LET_H) for x in range(3)})
    x0 += 3 + 2
    v = set()
    for r in range(LET_H):
        t = (r + 0.5) / LET_H
        a = t * 5.2
        for x in range(13):
            if a - 0.2 <= x < a + 3.2 or 12 - a - 3.2 < x <= 12 - a + 0.2:
                v.add((x0 + x, r))
    out.append(v)
    return out, x0 + 13


def raster(cols, rows, f):
    """Ladebalken im Rahmen wie beim Schnelllader, in Orange, Weiss und Schwarz."""
    rng = random.Random(f * 7919)
    palette = (ORANGE, ORANGE, WHITE, (120, 60, 10), BLACK)
    out = []
    for r in range(1, rows + 1):
        c = rng.choice(palette)
        if r <= boot.BORDER_ROWS or r > rows - boot.BORDER_ROWS:
            out.append(at(r, 1) + bg(c) + ' ' * cols)
        else:
            out.append(at(r, 1) + bg(c) + ' ' * boot.BORDER_COLS + at(r, cols - boot.BORDER_COLS + 1) + ' ' * boot.BORDER_COLS)
    return ''.join(out) + RESET


class Panel:
    def __init__(self, W, H):
        self.W, self.H = W, H
        yh = self.yh = int(H * 0.80) // 2 * 2             # Donauufer, auf ganzer Zelle
        rng = random.Random(1365)                         # Gruendung der Universitaet Wien
        # Logo oben mittig; bei schmalem Feld nur der Schriftzug
        self.lets, lw = letters()
        gap = 6
        self.with_sym = SYM_W + gap + lw <= W - 4
        total = SYM_W + gap + lw if self.with_sym else lw
        self.lx = (W - total) // 2
        self.wx = self.lx + (SYM_W + gap if self.with_sym else 0)
        self.lrow = 1                                     # Zellzeile des Logos
        self.sub_row = self.lrow + 9 if self.with_sym else self.lrow + LET_H + 1
        # Altstadt: niedrige Haeuser
        self.top = [yh] * W
        x = 0
        while x < W:
            w = rng.randint(max(2, W // 30), max(3, W // 16))
            h = int(H * rng.uniform(0.05, 0.11))
            for i in range(x, min(W, x + w)):
                self.top[i] = yh - h
            x += w
        self.parts = {}
        sky_top = (max(self.sub_row + 1, self.lrow + SYM_H) + 1) * 2   # nichts ragt ins Logo
        # Stephansdom: Suedturm spitz, Langhaus mit steilem, gemustertem Dach
        sx = int(W * 0.14)
        tw = max(3, round(W / 30))
        spire0 = sky_top + int((yh - sky_top) * 0.35)
        for y in range(sky_top, yh):
            k = min(1.0, (y - sky_top) / max(1, spire0 - sky_top))
            hw = (tw - 1) / 2 * k if y < spire0 else (tw - 1) / 2
            cx = sx + (tw - 1) / 2
            for x in range(round(cx - hw), round(cx + hw) + 1):
                self.parts[(x, y)] = 'stone'
        roof0 = yh - int((yh - sky_top) * 0.48)
        r0, r1 = sx + tw, sx + tw + int(W * 0.13)
        for x in range(r0, r1):
            for y in range(roof0, yh):
                self.parts.setdefault((x, y), 'roof' if y < yh - 3 else 'stone')
        self.roof = (r0, r1, roof0)
        # Karlskirche: Kuppel mit Laterne, zwei Saeulen
        kx = int(W * 0.40)
        kw = max(8, int(W * 0.10))
        base = yh - int((yh - sky_top) * 0.22)
        for x in range(kx, kx + kw):
            for y in range(base, yh):
                self.parts[(x, y)] = 'stone'
        dc, dr = kx + kw / 2 - 0.5, kw * 0.32
        for x in range(kx, kx + kw):
            for y in range(base - int(dr) - 2, base):
                if ((x - dc) / dr) ** 2 + ((y - base) / (dr * 0.9)) ** 2 <= 1:
                    self.parts[(x, y)] = 'dome'
        lat = base - int(dr * 0.9) - 1
        for y in range(lat - 3, lat + 1):
            self.parts[(round(dc), y)] = 'stone'
        for px in (kx - 2, kx + kw + 1):
            for y in range(base - int(dr), yh):
                self.parts[(px, y)] = 'stone'
            self.parts[(px, base - int(dr) - 1)] = 'gold'
        # Riesenrad im Prater
        self.rr = (int(W * 0.68), yh - int((yh - sky_top) * 0.45), max(5, (yh - sky_top) * 0.40))
        # Donauturm und DC Tower
        self.dt = (int(W * 0.86), sky_top + 1)
        self.dc = (int(W * 0.93), sky_top + int((yh - sky_top) * 0.15))
        # Himmel: Daemmerung, unten das HOIV-Orange
        self.sky = []
        for y in range(H):
            t = y / max(1, yh)
            c = mix((10, 14, 42), (52, 40, 96), t / 0.6) if t < 0.6 else mix((52, 40, 96), (240, 140, 60), (t - 0.6) / 0.4)
            self.sky.append([c] * W)
        self.stars = [(rng.randrange(W), rng.randrange(max(1, int(yh * 0.5))), rng.random()) for _ in range(max(8, W * H // 150))]

    def logo_pixels(self, f):
        """{(x, y): farbe} fuer den Teil des Logos, der bei Bild f schon steht."""
        px = {}
        if self.with_sym:
            for i, rects in enumerate(SYMBOL):
                if f < F_SYM[i]:
                    continue
                c = ORANGE if f > F_SYM[i] else WHITE    # Teil blitzt beim Erscheinen auf
                for x0, y0, x1, y1 in rects:
                    for x in range(x0, x1):
                        for r in range(y0, y1):
                            for d in (0, 1):
                                px[(self.lx + x, (self.lrow + r) * 2 + d)] = c
        for i, let in enumerate(self.lets):
            if f < F_LET[i]:
                continue
            c = LIGHT if f > F_LET[i] else ORANGE
            for x, r in let:
                for d in (0, 1):
                    px[(self.wx + x, (self.lrow + 1 + r) * 2 + d)] = c
        return px

    def frame(self, f):
        W, H, yh = self.W, self.H, self.yh
        sweep = H * smooth((f - F_SWEEP0) / (F_SWEEP1 - F_SWEEP0)) if f >= F_SWEEP0 else -1
        buf = [[(self.sky[y][x] if y < sweep else SCR) for x in range(W)] for y in range(yh)]
        for sx, sy, tw in self.stars:
            a = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(f * 0.35 + tw * 6.3))
            buf[sy][sx] = add(buf[sy][sx], WHITE, a * 0.6)
        for (x, y), c in self.logo_pixels(f).items():
            if 0 <= x < W and 0 <= y < yh:
                buf[y][x] = c
        # Donauturm: Schaft, Korb, Spitze mit Blinklicht
        dx, dtop = self.dt
        for y in range(dtop + 3, yh):
            buf[y][dx] = (150, 150, 165)
        for x in range(dx - 1, dx + 2):
            for y in (dtop + 3, dtop + 4):
                buf[y][x] = (170, 170, 185)
        for y in range(dtop, dtop + 3):
            buf[y][dx] = (150, 150, 165)
        if (f // 6) % 2 == 0:
            buf[dtop - 1][dx] = (255, 50, 50)
        # DC Tower: schwarzes Glas mit Knick
        cx, ctop = self.dc
        for y in range(ctop, yh):
            for x in range(cx - 1, cx + 2):
                if x < W:
                    lit = h32(x, y) % 5 == 0 and f >= F_READY
                    buf[y][x] = (255, 214, 140) if lit else ((26, 30, 44) if x != cx + 1 or y % 4 < 2 else (40, 46, 66))
        # Riesenrad: Felge, Speichen, Gondeln; dreht ab READY
        rx, ry, rr = self.rr
        ang0 = (f - F_READY) * 0.08 if f >= F_READY else 0
        for k in range(160):
            a = k / 160 * 2 * math.pi
            x, y = round(rx + math.cos(a) * rr), round(ry + math.sin(a) * rr)
            if 0 <= x < W and 0 <= y < yh:
                buf[y][x] = (200, 70, 60)
        for s in range(15):
            a = ang0 + s / 15 * 2 * math.pi
            if s % 2 == 0:                                 # acht Speichen, die Nabe in der Mitte
                for k in range(1, int(rr)):
                    x, y = round(rx + math.cos(a) * k), round(ry + math.sin(a) * k)
                    if 0 <= x < W and 0 <= y < yh:
                        buf[y][x] = mix(buf[y][x], (200, 70, 60), 0.45)
            x, y = round(rx + math.cos(a) * rr), round(ry + math.sin(a) * rr) + 1
            if 0 <= x < W and 0 <= y < yh:
                buf[y][x] = (255, 214, 140) if f >= F_READY and (s + f // 3) % 3 else (180, 40, 40)
        buf[round(ry)][rx] = (230, 200, 120)
        for d in range(int(rr) + 1):                       # Stuetzen
            for x in (round(rx - d * 0.45), round(rx + d * 0.45)):
                y = round(ry + d)
                if 0 <= x < W and y < yh:
                    buf[y][x] = (150, 50, 50)
        # Altstadt
        for x in range(W):
            for y in range(self.top[x], yh):
                lit = (x + y) % 3 == 0 and h32(x, y) % 3 != 0 and y > self.top[x]
                buf[y][x] = (255, 214, 140) if lit else (34, 32, 48)
        # Stephansdom und Karlskirche
        r0, r1, roof0 = self.roof
        for (x, y), part in self.parts.items():
            if not (0 <= x < W and 0 <= y < yh):
                continue
            if part == 'roof':                             # Zickzack in Gelb, Gruen, Schwarz
                if y < roof0:
                    continue
                band = ((x - r0) + (y - roof0) * 2 + (f // 4 if f >= F_RUN else 0)) % 6
                buf[y][x] = ((214, 170, 40), (214, 170, 40), (40, 110, 60), (40, 110, 60), (20, 20, 24), (230, 220, 200))[band]
            elif part == 'dome':
                buf[y][x] = (70, 140, 110)
            elif part == 'gold':
                buf[y][x] = (232, 190, 90)
            else:
                shade = 0.8 + 0.2 * ((x + y // 2) % 2)
                c = (170, 150, 120) if f >= F_READY else (88, 84, 96)
                buf[y][x] = (int(c[0] * shade), int(c[1] * shade), int(c[2] * shade))
        # Donau mit Spiegelbild
        for y in range(yh, H):
            depth = (y - yh) / max(1, H - yh)
            src = max(0, 2 * yh - y - 1)
            row = []
            for x in range(W):
                off = int(round(math.sin(y * 1.7 + f * 0.45 + x * 0.17) * 1.3))
                c = buf[src][min(W - 1, max(0, x + off))]
                row.append(mix(c, (10, 16, 50) if y < sweep else (20, 26, 120), 0.45 + 0.4 * depth))
            buf.append(row)
        for y in range(H):
            if y < sweep:
                continue
            row = buf[y]
            for x in range(0, W, 2):
                q = quantize(row[x], x, y)
                row[x] = q
                if x + 1 < W:
                    row[x + 1] = q
        if 0 <= sweep < H:
            y = int(sweep)
            for x in range(W):
                buf[y][x] = mix(WHITE, ORANGE, x / W)
        return buf

    def overlay(self, f, top, left):
        """HOME OF INNOVATION unter dem Schriftzug, als echte Terminalschrift."""
        if f < F_SUB:
            return ''
        y = self.sub_row * 2
        n = min(len(SUBTITLE), (f - F_SUB + 1) * 4)
        text = SUBTITLE[:n][:self.W - (self.wx - 0) - 1]
        return at(top + self.sub_row, left + self.wx) + bg(self.sky[y][0]) + fg(LIGHT) + boot.BOLD + text + RESET


if __name__ == '__main__':
    if '--png' in sys.argv:
        i = sys.argv.index('--png')
        n, path = int(sys.argv[i + 1]), sys.argv[i + 2]
        cols, rows = (int(v) for v in os.environ.get('HOIV_SIZE', '110x34').split('x'))
        g = geometry(cols, rows)
        W, H = g[10] - g[9] + 1, 2 * (g[12] - g[11] + 1)
        p = Panel(W, H)
        for f in range(n + 1):
            buf = p.frame(f)
        write_png(path, buf)
    else:
        sys.exit(nyc.main(NAME, Panel, 'HACKATHON @ HOIV VIENNA', ORANGE, WHITE,
                          finale='WELCOME TO HOIV!  A PLACE THAT DRIVES YOUR CREATIVITY.',
                          finale_border=ORANGE, finale_at=F_SUB + 3, border_at=F_READY, raster=raster) or 0)
