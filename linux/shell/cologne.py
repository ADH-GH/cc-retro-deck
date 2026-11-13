#!/usr/bin/env python3
"""Koeln im Einschaltbildschirm: LOAD "ROB",8,1, die Fassung fuer Rob in Koeln.

Ablauf und Kopf wie nyc.py (links LOAD "ROB",8,1, SEARCHING FOR ROB ...), eigenes Bild: Koeln
zur blauen Stunde, der Dom mit seinen zwei Tuermen, die Hohenzollernbruecke mit drei Boegen,
dahinter der Colonius, darunter der Rhein mit Spiegelbild; als C64-Bild auf Bildschirmblau, die
Abtastzeile laedt den Himmel in 24 Bit nach. Ladebalken in Rot und Weiss. Bei READY. faehrt ein
Zug ueber die Bruecke und der Rahmen wird rot; bei RUN steigt das Flutlicht am Dom von unten
nach oben, die Liebesschloesser am Gelaender glitzern, und am Ende steigt Feuerwerk ueber dem
Rhein wie bei den Koelner Lichtern. Kopf "GREETINGS FROM COLOGNE", am Ende
"WELCOME, ROB!  KOELLE ALAAF!" (mit Oe).

    cologne.py               Animation, etwa 12 s und 3 s Stand; Rueckgabe 2, wenn das
                             Fenster zu klein ist (dann boot.py nehmen)
    cologne.py --png N f     Bild N des Feldes als PNG, zur Kontrolle ohne Terminal
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
from trek import (SCR, quantize, mix, add, smooth, geometry, write_png, bg,  # noqa: E402
                  F_SWEEP0, F_SWEEP1, F_READY, F_RUN, F_END)

RED, WHITE = (200, 16, 46), (250, 250, 250)
STONE, GOLD = (58, 58, 72), (232, 190, 120)
STEEL = (110, 120, 140)
NAME = 'ROB'
F_FLOOD0, F_FLOOD1 = F_RUN, F_RUN + 14                    # Flutlicht steigt am Dom hinauf
F_BURSTS = [F_RUN + 12, F_RUN + 19, F_RUN + 26, F_END - 9]  # Feuerwerk
FW_COLS = [(255, 70, 70), (255, 210, 90), (120, 230, 140), (255, 196, 80)]


def raster(cols, rows, f):
    """Ladebalken im Rahmen wie beim Schnelllader, in Rot und Weiss."""
    rng = random.Random(f * 7919)
    palette = (RED, RED, WHITE, (120, 0, 20), (0, 0, 0))
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
        yh = self.yh = int(H * 0.70)                      # Rheinufer
        rng = random.Random(1248)                         # Grundsteinlegung des Doms
        # Altstadt: niedrige Haeuser mit Giebeln
        self.top = [yh] * W
        x = 0
        while x < W:
            w = rng.randint(max(2, W // 26), max(3, W // 14))
            h = int(yh * rng.uniform(0.05, 0.14))
            for i in range(x, min(W, x + w)):
                self.top[i] = yh - h - (1 if i - x == w // 2 else 0)
            x += w
        # Dom: zwei Tuerme mit Helm, Kreuzblumen, Langhaus mit Dach
        self.dom = {}
        top = max(2, int(H * 0.10))
        tw = max(3, round(W / 22))                        # Turmbreite
        gap = max(2, round(W / 30))
        x0 = int(W * 0.18)
        self.dom_x = (x0, x0 + 2 * tw + gap + int(W * 0.16))
        spire0 = top + int((yh - top) * 0.42)             # Helmansatz
        for t in range(2):
            tx = x0 + t * (tw + gap)
            for y in range(spire0, yh):
                for x in range(tx, tx + tw):
                    self.dom[(x, y)] = 'stone'
            for y in range(top, spire0):                  # Helm: spitz zulaufend
                k = (y - top) / max(1, spire0 - top)
                hw = (tw - 1) / 2 * k
                cx = tx + (tw - 1) / 2
                for x in range(round(cx - hw), round(cx + hw) + 1):
                    self.dom[(x, y)] = 'stone'
            for px in (tx, tx + tw - 1):                  # Fialen am Helmansatz
                for y in range(spire0 - max(2, tw // 2), spire0):
                    self.dom[(px, y)] = 'stone'
            for y in range(spire0 + 2, yh - 1, 3):        # Fenster
                self.dom[(tx + tw // 2, y)] = 'window'
                self.dom[(tx + tw // 2, y + 1)] = 'window'
        nave0 = x0 + 2 * tw + gap
        nave_top = yh - int((yh - top) * 0.34)
        for x in range(x0 + tw, self.dom_x[1]):
            for y in range(nave_top, yh):
                self.dom.setdefault((x, y), 'stone')
            ridge = nave_top - max(1, int((yh - top) * 0.06))
            for y in range(ridge, nave_top):
                if x >= nave0:
                    self.dom.setdefault((x, y), 'roof')
        for x in range(nave0 + 1, self.dom_x[1] - 1, 3):  # Strebebogen und Fenster am Langhaus
            self.dom[(x, nave_top - 1)] = 'stone'
            for y in range(nave_top + 2, yh - 1):
                self.dom[(x, y)] = 'window'
        self.dom_top = top
        # Colonius im Hintergrund
        self.col_x, self.col_top = int(W * 0.93), int(H * 0.20)
        # Hohenzollernbruecke: drei Boegen ueber den Rhein, Fahrbahn knapp ueber dem Wasser
        self.deck = yh + 1
        self.b0, self.b1 = int(W * 0.46), W + 2
        span = (self.b1 - self.b0) / 3
        self.arch = {}
        for x in range(self.b0, min(W, self.b1)):
            i = int((x - self.b0) // span)
            u = ((x - self.b0) - i * span) / span * 2 - 1
            self.arch[x] = self.deck - 1 - int((H * 0.18) * (1 - u * u))
        self.locks = [x for x in range(self.b0, W) if h32(x, 7) % 2 == 0]
        # Himmel: blaue Stunde
        self.sky = []
        for y in range(H):
            t = y / max(1, yh)
            c = mix((14, 18, 60), (60, 50, 130), t / 0.6) if t < 0.6 else mix((60, 50, 130), (240, 130, 90), (t - 0.6) / 0.4)
            self.sky.append([c] * W)
        self.stars = [(rng.randrange(W), rng.randrange(max(1, int(yh * 0.4))), rng.random()) for _ in range(max(8, W * H // 140))]
        self.burst_at = [(W * 0.55, H * 0.22), (W * 0.80, H * 0.16), (W * 0.66, H * 0.30), (W * 0.74, H * 0.22)]
        self.sparks = [[(rng.uniform(0, 2 * math.pi), rng.uniform(0.3, 1.0), rng.random() < 0.2)
                        for _ in range(max(40, W // 2))] for _ in F_BURSTS]

    def train(self, f):
        """Linke Kante des Zuges auf der Bruecke, oder None."""
        if f < F_READY:
            return None
        return self.W + 2 - (f - F_READY) * 2.0

    def frame(self, f):
        W, H, yh = self.W, self.H, self.yh
        sweep = H * smooth((f - F_SWEEP0) / (F_SWEEP1 - F_SWEEP0)) if f >= F_SWEEP0 else -1
        buf = [[(self.sky[y][x] if y < sweep else SCR) for x in range(W)] for y in range(yh + 2)]
        for sx, sy, tw in self.stars:
            a = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(f * 0.35 + tw * 6.3))
            buf[sy][sx] = add(buf[sy][sx], WHITE, a * 0.6)
        # Feuerwerk ueber dem Rhein: Funken mit eigener Richtung, Schweif und Schwerkraft
        for i, t0 in enumerate(F_BURSTS):
            if f < t0:
                continue
            age = f - t0
            cx, cy = self.burst_at[i]
            if age < 3:                                   # aufsteigende Rakete
                y = int(yh - (yh - cy) * (age + 1) / 3)
                if 0 <= y < yh:
                    buf[y][int(cx)] = (255, 240, 200)
                continue
            t = age - 2
            last = i == len(F_BURSTS) - 1                 # die letzte steht im Standbild noch
            fade = 1.0 if last else max(0.0, 1 - t / 16)
            col = FW_COLS[i % len(FW_COLS)]
            reach = H * 0.17
            for k, (ang, sp, spark) in enumerate(self.sparks[i]):
                for back, a in ((0, 1.0), (1, 0.5), (2, 0.25)):
                    dd = reach * sp * (1 - math.exp(-max(0, t - back) / 3))
                    x = round(cx + math.cos(ang) * dd * 1.3)
                    y = round(cy + math.sin(ang) * dd + 0.012 * max(0, t - back) ** 2 * H / 10)
                    if 0 <= x < W and 0 <= y < yh:
                        c = WHITE if spark and back == 0 and sp > 0.7 and (f + k) % 3 == 0 else col
                        buf[y][x] = mix(buf[y][x], c, fade * a)
        # Colonius
        for y in range(self.col_top, yh):
            buf[y][self.col_x] = (90, 95, 120)
        for x in range(self.col_x - 2, self.col_x + 3):
            for y in (self.col_top + 3, self.col_top + 4):
                if 0 <= x < W:
                    buf[y][x] = (110, 115, 140)
        if (f // 6) % 2 == 0:
            buf[self.col_top - 1][self.col_x] = (255, 50, 50)
        # Altstadt
        for x in range(W):
            for y in range(self.top[x], yh):
                lit = (x + y) % 3 == 0 and h32(x, y) % 3 != 0 and y > self.top[x]
                buf[y][x] = (255, 214, 140) if lit else (34, 32, 48)
        # Dom mit steigendem Flutlicht
        flood = yh - (yh - self.dom_top + 2) * smooth((f - F_FLOOD0) / (F_FLOOD1 - F_FLOOD0)) if f >= F_FLOOD0 else yh + 1
        for (x, y), part in self.dom.items():
            if not (0 <= x < W and 0 <= y < yh):
                continue
            lit = y >= flood
            if part == 'window':
                buf[y][x] = (255, 244, 210) if lit else ((255, 200, 110) if h32(x, y) % 2 else (40, 40, 60))
            elif part == 'roof':
                buf[y][x] = mix((44, 50, 64), (150, 140, 120), 0.8) if lit else (44, 50, 64)
            else:
                shade = 0.78 + 0.22 * ((x + y // 2) % 2)     # Steinstruktur bleibt sichtbar
                c = (205, 155, 92) if lit else STONE
                buf[y][x] = (int(c[0] * shade), int(c[1] * shade), int(c[2] * shade))
        # Ufer, dann der Rhein mit Spiegelbild
        for x in range(W):
            buf[yh][x] = (30, 28, 40)
            buf[yh + 1][x] = (30, 28, 40)
        for y in range(yh + 2, H):
            depth = (y - yh) / max(1, H - yh)
            src = max(0, 2 * yh - y)
            row = []
            for x in range(W):
                off = int(round(math.sin(y * 1.7 + f * 0.45 + x * 0.17) * 1.3))
                c = buf[src][min(W - 1, max(0, x + off))]
                row.append(mix(c, (10, 16, 50) if y < sweep else (20, 26, 120), 0.45 + 0.4 * depth))
            buf.append(row)
        # Bruecke ueber dem Wasser: Boegen, Haenger, Fahrbahn, Liebesschloesser
        for x, ay in self.arch.items():
            if not 0 <= x < W:
                continue
            for y in (ay, ay + 1):                        # Bogen zwei Pixel stark
                if 0 <= y < H:
                    buf[y][x] = STEEL
            if x % 2 == 0:
                for y in range(ay + 1, self.deck):
                    buf[y][x] = mix(buf[y][x], STEEL, 0.55)
            for y in (self.deck, self.deck + 1):
                buf[y][x] = (70, 78, 96)
        for x in self.locks:
            buf[self.deck - 1][x] = mix((70, 78, 96), FW_COLS[h32(x, 3) % 3], 0.8 if f >= F_FLOOD0 and (x + f) % 4 == 0 else 0.35)
        tx = self.train(f)
        if tx is not None:
            n = max(14, W // 5)
            for i in range(n):
                x = int(tx) + i
                if self.b0 <= x < W:
                    buf[self.deck - 2][x] = (230, 230, 236) if i % 4 else (255, 220, 120)
                    buf[self.deck - 3][x] = (200, 30, 40) if i < 2 else (230, 230, 236)
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
                buf[y][x] = mix(WHITE, RED, x / W)
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
        sys.exit(nyc.main(NAME, Panel, 'GREETINGS FROM COLOGNE', RED, WHITE,
                          finale=f'WELCOME, {NAME}!  KÖLLE ALAAF!',
                          finale_border=RED, finale_at=F_BURSTS[0], border_at=F_READY, raster=raster) or 0)
