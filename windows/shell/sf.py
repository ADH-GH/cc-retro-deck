#!/usr/bin/env python3
"""San Francisco im Einschaltbildschirm: LOAD "EDUARDO",8,1, die Fassung fuer Eduardo Ordax, im
Stil der Sommer-Sportspiele auf dem C64 (California Summer Games).

Ablauf und Kopf wie nyc.py (links LOAD "EDUARDO",8,1, SEARCHING FOR EDUARDO ...), eigenes Bild:
Sonnenuntergang ueber der Bucht, die Golden Gate Bridge in Internationalem Orange, eine
Retro-Sonne mit Streifen, Marin Headlands, links eine Palme; als C64-Bild auf Bildschirmblau,
die Abtastzeile laedt den Himmel in 24 Bit nach. Ladebalken in Sonnenfarben. Bei READY. paddelt
ein Surfer als Sprite hinaus und der Rahmen wird orange; bei RUN baut sich eine Welle auf und er
reitet sie quer durchs Bild. Dann gehen die Lichter der Bruecke an, und am Himmel haengt eine
Goldmedaille wie bei der Siegerehrung. Kopf "CALIFORNIA SUMMER GAMES", am Ende
"WELCOME, EDUARDO!  SURF'S UP IN SAN FRANCISCO." Kein Spiel-Logo, kein Originaltitel.

    sf.py               Animation, etwa 12 s und 3 s Stand; Rueckgabe 2, wenn das
                        Fenster zu klein ist (dann boot.py nehmen)
    sf.py --png N f     Bild N des Feldes als PNG, zur Kontrolle ohne Terminal
"""
import math
import os
import random
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402
import nyc  # noqa: E402
from boot import at, RESET  # noqa: E402
from trek import (SCR, quantize, mix, add, smooth, geometry, write_png, bg,  # noqa: E402
                  F_SWEEP0, F_SWEEP1, F_READY, F_RUN, F_END)

ORANGE = (192, 54, 44)        # International Orange der Golden Gate
SUN = (255, 196, 70)
GOLD = (255, 205, 60)
SKY_TOP, SKY_MID, SKY_LOW = (38, 30, 110), (214, 84, 120), (255, 170, 90)
NAME = 'EDUARDO'
F_RIDE0, F_RIDE1 = F_RUN, F_RUN + 22                      # der Surfer reitet die Welle
F_LIGHTS = F_RIDE1 - 4
F_MEDAL = F_RIDE1 + 2

# Sprites (je Zeichen ein Pixel): Surfer auf dem Brett, Palmenkrone, Medaille
SURFER = ['....HH...',
          '....FF...',
          '.AA.BB.AA',
          '...ABBA..',
          '....SS...',
          '...F..F..',
          '..F....F.',
          'YYYRYYYYY']
SURF_COL = {'H': (90, 50, 30), 'F': (235, 175, 125), 'A': (235, 175, 125), 'B': (230, 60, 60),
            'S': (40, 70, 170), 'Y': (255, 215, 50), 'R': (230, 60, 60)}
MEDAL = ['R...R',
         '.R.R.',
         '..R..',
         '.GGG.',
         'GGYGG',
         'GYGYG',
         'GGYGG',
         '.GGG.']
MEDAL_COL = {'R': (40, 90, 200), 'G': GOLD, 'Y': (255, 245, 180)}


def raster(cols, rows, f):
    """Ladebalken im Rahmen wie beim Schnelllader, in Sonnenfarben."""
    rng = random.Random(f * 7919)
    palette = (ORANGE, SUN, (255, 120, 80), (240, 90, 140), (90, 200, 230), (255, 255, 255))
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
        yh = self.yh = int(H * 0.66)                      # Wasserlinie
        self.deck = int(H * 0.56)                         # Fahrbahn der Bruecke
        # Bruecke: zwei Tuerme, Haupt- und Seitenkabel, Haenger
        self.t1, self.t2 = int(W * 0.40), int(W * 0.80)
        self.ttop = max(2, int(H * 0.16))
        self.bridge = {}
        for tx in (self.t1, self.t2):
            for y in range(self.ttop, yh):
                for xx in (tx - 1, tx + 1):
                    self.bridge[(xx, y)] = 'tower'
            for y in (self.ttop, self.ttop + (self.deck - self.ttop) // 3, self.ttop + 2 * (self.deck - self.ttop) // 3):
                self.bridge[(tx, y)] = 'tower'
        sag = self.deck - 2

        def cable(x):
            if self.t1 <= x <= self.t2:                    # Hauptfeld: Kettenlinie
                u = (x - self.t1) / (self.t2 - self.t1) * 2 - 1
                return self.ttop + (sag - self.ttop) * (1 - u * u)
            if x < self.t1:                                # Seitenfeld zum Ufer
                return self.ttop + (self.deck - self.ttop) * (self.t1 - x) / max(1, self.t1 - int(W * 0.12))
            return self.ttop + (self.deck - self.ttop) * (x - self.t2) / max(1, W - self.t2)
        self.cable = {}
        for x in range(int(W * 0.12), W):
            cy = cable(x)
            if cy < self.deck:
                self.cable[x] = int(round(cy))
        self.lights = [x for x in range(int(W * 0.12), W) if x % 3 == 0]
        # Sonne hinter der Bruecke, auf dem Horizont
        self.sun = (W * 0.60, yh - 1, H * 0.36)
        # Huegel: Marin links, Stadt rechts
        rng = random.Random(1937)                         # Eroeffnung der Golden Gate
        self.hill = [yh] * W
        for x in range(W):
            u = x / W
            left = yh - int(H * 0.16 * max(0.0, 1 - u / 0.35) * (0.8 + 0.2 * math.sin(x * 0.4)))
            right = yh - int(H * 0.07 * max(0.0, (u - 0.86) / 0.14))
            self.hill[x] = min(left, right)
        # Himmel
        self.sky = []
        for y in range(H):
            t = y / max(1, yh)
            c = mix(SKY_TOP, SKY_MID, t / 0.55) if t < 0.55 else mix(SKY_MID, SKY_LOW, (t - 0.55) / 0.45)
            self.sky.append([c] * W)
        self.palm_x = max(3, int(W * 0.07))
        self.clouds = [(rng.uniform(0, W), rng.randrange(2, max(3, int(H * 0.25))), rng.randint(4, 9)) for _ in range(4)]

    # ------------------------------------------------------------ Teile

    def wave_crest(self, f):
        """x-Lage der Wellenspitze waehrend des Ritts; sie bleibt rechts stehen, damit der
        Surfer im Standbild noch auf der Welle ist."""
        return -8 + (self.W * 0.74 + 8) * smooth((f - F_RIDE0) / (F_RIDE1 - F_RIDE0))

    def sprite(self, buf, rows, cols, x0, y0, scale=1):
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch in '. ':
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        x, y = x0 + c * scale + dx, y0 + r * scale + dy
                        if 0 <= x < self.W and 0 <= y < self.H:
                            buf[y][x] = cols[ch]

    def palm(self, buf, f):
        W, H, yh = self.W, self.H, self.yh
        px = self.palm_x
        top = int(H * 0.22)
        for y in range(top, yh + 2):
            k = (yh - y) / max(1, yh - top)
            x = px + round(math.sin(k * 1.6) * 2)          # leicht gebogener Stamm
            if 0 <= y < H:
                for xx in (x, x + 1):
                    if 0 <= xx < W:
                        buf[y][xx] = (90, 55, 40) if (y % 2) else (70, 42, 30)
        cx = px + round(math.sin(1.6) * 2)
        sway = math.sin(f * 0.25) * 0.15
        for a in (-2.6, -2.0, -1.2, -0.5, 0.2):
            for r in range(1, max(5, int(H * 0.12))):
                ang = a + sway + r * 0.03
                x = round(cx + math.cos(ang) * r * 1.4)
                y = round(top + math.sin(ang) * r * 0.7 + r * r * 0.025)
                if 0 <= x < W and 0 <= y < H:
                    buf[y][x] = (40, 130, 70) if r % 2 else (60, 160, 80)

    # ------------------------------------------------------------ Bild

    def frame(self, f):
        W, H, yh = self.W, self.H, self.yh
        sweep = H * smooth((f - F_SWEEP0) / (F_SWEEP1 - F_SWEEP0)) if f >= F_SWEEP0 else -1
        buf = [[(self.sky[y][x] if y < sweep else SCR) for x in range(W)] for y in range(H)]
        # Wolken
        for cx, cy, cw in self.clouds:
            x0 = int((cx + f * 0.15) % (W + cw)) - cw
            for dx in range(cw):
                for dy in range(2 if dx in (0, cw - 1) else 3):
                    x, y = x0 + dx, cy - dy + 1
                    if 0 <= x < W and 0 <= y < yh:
                        buf[y][x] = mix(buf[y][x], (255, 225, 220), 0.7)
        # Retro-Sonne mit Streifen
        sx, sy, sr = self.sun
        for y in range(max(0, int(sy - sr)), yh):
            band = (sy - y) / sr
            if band < 0.45 and int((sy - y) * 2) % 3 == 0:   # Streifen unten
                continue
            for x in range(max(0, int(sx - sr)), min(W, int(sx + sr) + 1)):
                if math.hypot(x - sx, (y - sy)) <= sr:
                    buf[y][x] = mix((255, 230, 120), (255, 110, 90), 1 - band)
        # Huegel
        for x in range(W):
            for y in range(self.hill[x], yh):
                buf[y][x] = (70, 40, 90) if x < W * 0.5 else (60, 50, 100)
        # Wasser mit Sonnenspiegelung
        for y in range(yh, H):
            depth = (y - yh) / max(1, H - yh)
            for x in range(W):
                c = mix((40, 70, 150), (20, 30, 90), depth)
                glint = abs(x - sx) < sr * (0.9 - 0.5 * depth) and (x + y * 3 + f) % 5 < 2
                buf[y][x] = mix(c, SUN, 0.75) if glint else c
        # Bruecke
        lights_on = f >= F_LIGHTS
        for x, cy in self.cable.items():
            if 0 <= cy < H:
                buf[cy][x] = ORANGE
            if x % 3 == 0:                                 # Haenger
                for y in range(cy + 1, self.deck):
                    buf[y][x] = mix(buf[y][x], ORANGE, 0.4)
        for x in range(int(W * 0.10), W):
            buf[self.deck][x] = ORANGE
            buf[self.deck + 1][x] = (130, 34, 30)
        for (x, y), _ in self.bridge.items():
            if 0 <= x < W and 0 <= y < H:
                buf[y][x] = ORANGE
        if lights_on:
            k = smooth((f - F_LIGHTS) / 4)
            for x in self.lights:
                if (x // 3 + f // 4) % 2 == 0 or f >= F_MEDAL:
                    buf[self.deck][x] = mix(buf[self.deck][x], (255, 250, 200), k)
            for tx in (self.t1, self.t2):
                buf[self.ttop - 1][tx] = (255, 60, 50) if (f // 5) % 2 == 0 else ORANGE
        self.palm(buf, f)
        # Welle und Surfer
        if f >= F_READY:
            sc = max(1, round(W / 45))
            if f < F_RIDE0:                                # paddelt hinaus
                x = int(W * 0.05 + (f - F_READY) * 0.6)
                self.sprite(buf, ['.AA.BB.AA', 'YYYRYYYYY'], SURF_COL, x, H - 2 - 2 * sc, sc)
            else:
                cx = self.wave_crest(f)
                peak = min(F_RIDE1, f) - F_RIDE0
                hgt = min(int((H - yh) * 0.55), 3 + peak)
                wl = 16 * sc
                for x in range(W):
                    d = x - cx
                    if -wl < d < 3 * sc:
                        h = hgt * math.exp(-((d + 2 * sc) / (6 * sc)) ** 2)
                        y0 = int(H - 1 - h)
                        for y in range(y0, H):
                            buf[y][x] = (245, 250, 255) if y <= y0 + sc - 1 else mix((90, 170, 220), (40, 90, 170), (y - y0) / max(1, h))
                # auf dem Kamm: das Brett liegt auf der Wellenspitze
                self.sprite(buf, SURFER, SURF_COL, int(cx) - 6 * sc, int(H - 1 - hgt) - (len(SURFER) - 1) * sc, sc)
        if f >= F_MEDAL:
            k = smooth((f - F_MEDAL) / 4)
            my = int(-len(MEDAL) + (int(H * 0.06) + len(MEDAL)) * k)
            self.sprite(buf, MEDAL, MEDAL_COL, int(W * 0.22), my, scale=max(1, W // 50))
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
                buf[y][x] = mix((255, 255, 255), SUN, x / W)
        return buf


if __name__ == '__main__':
    if '--png' in sys.argv:
        i = sys.argv.index('--png')
        n, path = int(sys.argv[i + 1]), sys.argv[i + 2]
        g = geometry(110, 34)
        W, H = g[10] - g[9] + 1, 2 * (g[12] - g[11] + 1)
        p = Panel(W, H)
        for f in range(n + 1):
            buf = p.frame(f)
        write_png(path, buf)
    else:
        sys.exit(nyc.main(NAME, Panel, 'CALIFORNIA SUMMER GAMES', ORANGE, SUN,
                          finale=f"WELCOME, {NAME}!  SURF'S UP IN SAN FRANCISCO.",
                          finale_border=(255, 140, 60), finale_at=F_MEDAL, border_at=F_READY, raster=raster) or 0)
