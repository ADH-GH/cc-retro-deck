#!/usr/bin/env python3
"""Telekom in Magenta im Einschaltbildschirm: LOAD "ARNO",8,1, die Fassung fuer Arno von der
Deutschen Telekom, Visionaer und Fan der 8-Bit-Zeit.

Ablauf und Kopf wie nyc.py (links LOAD "ARNO",8,1, SEARCHING FOR ARNO ...), eigenes Bild:
eine Stadt bei Nacht mit Funkturm, als C64-Bild auf Bildschirmblau; die Abtastzeile laedt den
Himmel in 24 Bit nach, von dunklem Magenta bis Magenta am Horizont. Die Ladebalken im Rahmen
flackern in Magenta, Weiss und Schwarz. Von Anfang an laeuft unten ein Demo-Scroller wie in
einem Cracktro, oben zieht ein Satellit als Sprite ueber den Himmel. Bei READY. erscheint neben
dem Turm ein KI-Netz in vier Schichten, der Rahmen wird magenta; bei RUN leuchtet das Netz
Schicht fuer Schicht auf und speist den Turm. Dann funkt der Turm zum Satelliten, sendet
Funkboegen, die Fenster gehen in Magenta an, und am Himmel leuchtet das T mit seinen Quadraten.
Kopf "DEUTSCHE TELEKOM", am Ende "WELCOME, ARNO!  ERLEBEN, WAS VERBINDET." Telekom-Bezug von
ADH gewollt.

    magenta.py               Animation, etwa 12 s und 3 s Stand; Rueckgabe 2, wenn das
                             Fenster zu klein ist (dann boot.py nehmen)
    magenta.py --png N f     Bild N des Feldes als PNG, zur Kontrolle ohne Terminal
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
from nyc import h32  # noqa: E402
from trek import (SCR, quantize, mix, add, smooth, geometry, write_png, bg,  # noqa: E402
                  F_SWEEP0, F_SWEEP1, F_READY, F_RUN, F_END)

MAGENTA = (226, 0, 116)
PINK = (255, 150, 205)
NAME = 'ARNO'
SCROLL = 'HELLO ARNO * FROM 8 BIT TO AI * VISIONARY OF THE MAGENTA NET * HELLO ARNO'
SCROLL_END = 'HELLO ARNO'                                  # steht im Standbild in der Mitte
LAYERS = (3, 4, 3, 1)                                     # KI-Netz, Schicht fuer Schicht
F_LAYER = [F_RUN + 3 * i for i in range(len(LAYERS))]     # Schicht i leuchtet
F_FEED = F_LAYER[-1] + 3                                  # Ausgang hat den Turm erreicht
F_BEAM0, F_BEAM1 = F_FEED, F_FEED + 6                     # Strahl zum Satelliten
F_WAVE0 = F_BEAM1
F_WAVE1 = F_END - 2

# 5x7-Pixelschrift fuer den Scroller
FONT = {
    'A': ['.###.', '#...#', '#...#', '#####', '#...#', '#...#', '#...#'],
    'B': ['####.', '#...#', '#...#', '####.', '#...#', '#...#', '####.'],
    'C': ['.###.', '#...#', '#....', '#....', '#....', '#...#', '.###.'],
    'D': ['####.', '#...#', '#...#', '#...#', '#...#', '#...#', '####.'],
    'E': ['#####', '#....', '#....', '####.', '#....', '#....', '#####'],
    'F': ['#####', '#....', '#....', '####.', '#....', '#....', '#....'],
    'G': ['.###.', '#...#', '#....', '#.###', '#...#', '#...#', '.###.'],
    'H': ['#...#', '#...#', '#...#', '#####', '#...#', '#...#', '#...#'],
    'I': ['.###.', '..#..', '..#..', '..#..', '..#..', '..#..', '.###.'],
    'J': ['..###', '...#.', '...#.', '...#.', '...#.', '#..#.', '.##..'],
    'K': ['#...#', '#..#.', '#.#..', '##...', '#.#..', '#..#.', '#...#'],
    'L': ['#....', '#....', '#....', '#....', '#....', '#....', '#####'],
    'M': ['#...#', '##.##', '#.#.#', '#.#.#', '#...#', '#...#', '#...#'],
    'N': ['#...#', '##..#', '#.#.#', '#..##', '#...#', '#...#', '#...#'],
    'O': ['.###.', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.'],
    'P': ['####.', '#...#', '#...#', '####.', '#....', '#....', '#....'],
    'Q': ['.###.', '#...#', '#...#', '#...#', '#.#.#', '#..#.', '.##.#'],
    'R': ['####.', '#...#', '#...#', '####.', '#.#..', '#..#.', '#...#'],
    'S': ['.####', '#....', '#....', '.###.', '....#', '....#', '####.'],
    'T': ['#####', '..#..', '..#..', '..#..', '..#..', '..#..', '..#..'],
    'U': ['#...#', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.'],
    'V': ['#...#', '#...#', '#...#', '#...#', '#...#', '.#.#.', '..#..'],
    'W': ['#...#', '#...#', '#...#', '#.#.#', '#.#.#', '##.##', '#...#'],
    'X': ['#...#', '#...#', '.#.#.', '..#..', '.#.#.', '#...#', '#...#'],
    'Y': ['#...#', '#...#', '.#.#.', '..#..', '..#..', '..#..', '..#..'],
    'Z': ['#####', '....#', '...#.', '..#..', '.#...', '#....', '#####'],
    '0': ['.###.', '#...#', '#..##', '#.#.#', '##..#', '#...#', '.###.'],
    '1': ['..#..', '.##..', '..#..', '..#..', '..#..', '..#..', '.###.'],
    '2': ['.###.', '#...#', '....#', '...#.', '..#..', '.#...', '#####'],
    '3': ['####.', '....#', '....#', '.###.', '....#', '....#', '####.'],
    '4': ['...#.', '..##.', '.#.#.', '#..#.', '#####', '...#.', '...#.'],
    '5': ['#####', '#....', '####.', '....#', '....#', '#...#', '.###.'],
    '6': ['.###.', '#....', '#....', '####.', '#...#', '#...#', '.###.'],
    '7': ['#####', '....#', '...#.', '..#..', '.#...', '.#...', '.#...'],
    '8': ['.###.', '#...#', '#...#', '.###.', '#...#', '#...#', '.###.'],
    '9': ['.###.', '#...#', '#...#', '.####', '....#', '....#', '.###.'],
    '*': ['.....', '#.#.#', '.###.', '#####', '.###.', '#.#.#', '.....'],
    '!': ['..#..', '..#..', '..#..', '..#..', '..#..', '.....', '..#..'],
    '.': ['.....', '.....', '.....', '.....', '.....', '.....', '..#..'],
    ',': ['.....', '.....', '.....', '.....', '.....', '..#..', '.#...'],
    '-': ['.....', '.....', '.....', '#####', '.....', '.....', '.....'],
    "'": ['..#..', '..#..', '.....', '.....', '.....', '.....', '.....'],
    ' ': ['.....'] * 7,
}

# Satellit als Sprite: P Solarflaeche, S Rumpf, - Strebe, D Schuessel, L Licht
SAT = ['......D......',
       'PPP...S...PPP',
       'PPP--SLS--PPP',
       'PPP...S...PPP']
SAT_COL = {'P': (60, 80, 190), 'S': (210, 210, 225), '-': (160, 160, 175), 'D': (235, 235, 245)}


def line(x0, y0, x1, y1):
    """Pixel einer Strecke (Bresenham), vom ersten zum letzten Punkt."""
    pts, dx, dy = [], abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        pts.append((x0, y0))
        if (x0, y0) == (x1, y1):
            return pts
        e2 = 2 * err
        if e2 >= dy:
            err += dy; x0 += sx
        if e2 <= dx:
            err += dx; y0 += sy


def raster(cols, rows, f):
    """Ladebalken im Rahmen wie beim Schnelllader, in Magenta, Weiss und Schwarz."""
    rng = random.Random(f * 7919)
    palette = (MAGENTA, MAGENTA, PINK, (255, 255, 255), (0, 0, 0), (120, 0, 62))
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
        yh = self.yh = int(H * 0.74)                      # darunter laeuft der Scroller
        rng = random.Random(1995)                         # Gruendungsjahr der Telekom AG
        top = [yh] * W
        x = 0
        while x < W:
            w = rng.randint(max(2, W // 24), max(3, W // 11))
            h = int(yh * rng.uniform(0.08, 0.30))
            for i in range(x, min(W, x + w)):
                top[i] = yh - h
            x += w + (1 if rng.random() < 0.35 else 0)
        self.top = top
        # Funkturm: Gitter aus zwei Beinen, die sich nach oben naehern, mit Kreuzstreben
        self.tcx = int(W * 0.76)
        self.ttop = max(2, int(H * 0.16))
        base_hw, top_hw = max(3, round(W / 24)), 1
        self.tower = {}
        span = yh - self.ttop
        cab_y = self.cab_y = self.ttop + int(span * 0.18)
        for y in range(self.ttop, yh):
            k = (y - self.ttop) / span
            hw = round(top_hw + (base_hw - top_hw) * k ** 1.3)
            if y < cab_y - 1:
                self.tower[(self.tcx, y)] = 'mast'
                continue
            for xx in (self.tcx - hw, self.tcx + hw):
                self.tower[(xx, y)] = 'leg'
            if (y - cab_y) % 3 == 0:
                for xx in range(self.tcx - hw, self.tcx + hw + 1):
                    self.tower[(xx, y)] = 'brace'
            else:
                t = ((y - cab_y) % 3) / 3
                for xx in (round(self.tcx - hw + 2 * hw * t), round(self.tcx + hw - 2 * hw * t)):
                    self.tower.setdefault((xx, y), 'brace')
        for dy in range(2):
            for xx in range(self.tcx - 3, self.tcx + 4):
                self.tower[(xx, cab_y + dy)] = 'cab'
        self.lights = [(self.tcx, self.ttop - 1)] + [(self.tcx + s * round(top_hw + (base_hw - top_hw) * k ** 1.3),
                                                      self.ttop + int(span * k)) for k in (0.45, 0.75) for s in (-1, 1)]
        self.ant = (self.tcx, self.ttop)
        # KI-Netz: Schichten zwischen dem T (links oben) und dem Turm
        x0, x1 = W * 0.38, W * 0.64
        y0, y1 = H * 0.22, H * 0.52
        self.net = []
        for li, n in enumerate(LAYERS):
            lx = round(x0 + (x1 - x0) * li / (len(LAYERS) - 1))
            self.net.append([(lx, round(y0 + (y1 - y0) * (j + 0.5) / n)) for j in range(n)])
        self.links = [(li, line(a[0], a[1], b[0], b[1])) for li in range(len(LAYERS) - 1)
                      for a in self.net[li] for b in self.net[li + 1]]
        out = self.net[-1][0]
        self.feed = line(out[0], out[1], self.tcx - 3, cab_y)
        # Himmel
        self.sky = []
        for y in range(H):
            t = y / max(1, yh)
            c = mix((18, 0, 32), (96, 0, 66), t / 0.5) if t < 0.5 else mix((96, 0, 66), MAGENTA, (t - 0.5) / 0.5)
            self.sky.append([c] * W)
        self.stars = [(rng.randrange(W), rng.randrange(max(1, int(yh * 0.6))), rng.random()) for _ in range(max(10, W * H // 90))]
        self.lit = {}
        for x in range(W):
            for y in range(top[x] + 1, yh - 1):
                if x % 2 == 0 and y % 2 == 1:
                    r = h32(x, y) / 0xffff
                    self.lit[(x, y)] = 0 if r < 0.45 else (1 if r < 0.85 else 2)
        self.sat_scale = max(1, W // 90)

    # ------------------------------------------------------------ Teile

    def satellite(self, f):
        """Linke obere Ecke des Sprites: zieht ueber den ganzen Lauf von links nach rechts."""
        sw = len(SAT[0]) * self.sat_scale
        x = round(-sw + (self.W * 0.92) * f / F_END)
        return x, max(1, int(self.H * 0.04))

    def draw_sat(self, buf, f):
        sx, sy = self.satellite(f)
        s = self.sat_scale
        for r, row in enumerate(SAT):
            for c, ch in enumerate(row):
                if ch == '.':
                    continue
                col = (255, 40, 150) if ch == 'L' and (f // 3) % 2 == 0 else SAT_COL.get(ch, (255, 255, 255))
                for dy in range(s):
                    for dx in range(s):
                        x, y = sx + c * s + dx, sy + r * s + dy
                        if 0 <= x < self.W and 0 <= y < self.H:
                            buf[y][x] = col

    def draw_net(self, buf, f):
        if f < F_READY:
            return
        k = smooth((f - F_READY) / 6)
        for li, pts in self.links:
            on = f >= F_LAYER[li + 1]
            going = F_LAYER[li] <= f < F_LAYER[li + 1]
            for i, (x, y) in enumerate(pts):
                c = (255, 40, 150) if on else (110, 0, 70)
                if going:
                    t = (f - F_LAYER[li] + 1) / (F_LAYER[li + 1] - F_LAYER[li])
                    if i <= t * len(pts):
                        c = (255, 40, 150)
                buf[y][x] = mix(buf[y][x], c, k * (0.9 if on else 0.75))
        if f >= F_LAYER[-1]:
            t = min(1.0, (f - F_LAYER[-1] + 1) / (F_FEED - F_LAYER[-1]))
            for x, y in self.feed[:max(1, int(t * len(self.feed)))]:
                if (x, y) not in self.tower:
                    buf[y][x] = (255, 60, 160)
        for li, layer in enumerate(self.net):
            on = f >= F_LAYER[li]
            for x, y in layer:
                for dx in (0, 1):
                    for dy in (0, 1):
                        if 0 <= x + dx < self.W and 0 <= y + dy < self.H:
                            c = (255, 255, 255) if on and (dx, dy) == (0, 0) else (PINK if on else (150, 60, 150))
                            buf[y + dy][x + dx] = mix(buf[y + dy][x + dx], c, k)

    def logo(self, buf, k):
        """Das T mit seinen Quadraten (eins links, zwei rechts, auf der Grundlinie), oben links.
        Alles auf geraden Pixelzeilen: eine Zeichenzelle ist ganz T oder gar nicht, sonst zeichnet
        Apples Terminal an halben Zellen feine Kanten."""
        W, H = self.W, self.H
        lh = max(8, int(H * 0.30)) // 2 * 2
        t = max(2, round(lh / 4) // 2 * 2)
        bw = max(3 * t, round(lh * 0.8))
        bw += (bw - t) % 2
        gap = t
        x0 = max(1, int(W * 0.05)) + t + gap
        y0 = max(4, int(H * 0.16)) // 2 * 2
        cells = [(x, y) for y in range(y0, y0 + t) for x in range(x0, x0 + bw)]
        sx = x0 + (bw - t) // 2
        cells += [(x, y) for y in range(y0 + t, y0 + lh) for x in range(sx, sx + t)]
        base = y0 + lh - t
        for qx in (sx - gap - t, sx + t + gap, sx + 2 * (t + gap)):
            cells += [(x, y) for y in range(base, base + t) for x in range(qx, qx + t)]
        for x, y in cells:
            if 0 <= x < W and 0 <= y < H:
                buf[y][x] = mix(buf[y][x], MAGENTA, k)

    def scroller(self, buf, f):
        """Lauftext im Sinus-Schwung unten, wie in einem C64-Cracktro. Jeder Buchstabe schwingt
        als Ganzes (spaltenweise zerfallen sie bei dieser Aufloesung); die Geschwindigkeit ist so
        gewaehlt, dass im Standbild SCROLL_END mittig steht."""
        W, H, yh = self.W, self.H, self.yh
        band = H - yh
        amp = max(0.0, (band - 8) / 2)
        base = (yh + (band - 7) // 2) // 2 * 2            # auf ganzen Zeichenzellen, wie das T
        last = (len(SCROLL) - len(SCROLL_END)) * 6
        speed = (W - (W - len(SCROLL_END) * 6) / 2 + last) / F_END
        off = W - f * speed
        for i, ch in enumerate(SCROLL):
            cx = round(off + i * 6)
            if cx < -6 or cx >= W:
                continue
            glyph = FONT.get(ch, FONT[' '])
            dy = round(math.sin(cx * 0.12 + f * 0.3) * amp * min(1.0, (F_END - f) / 12) / 2) * 2
            for c in range(5):
                x = cx + c
                if not 0 <= x < W:
                    continue
                for r in range(7):
                    if glyph[r][c] == '#':
                        y = base + r + dy
                        if yh <= y < H:
                            buf[y][x] = mix((255, 255, 255), MAGENTA, (r // 2) / 3)   # je Zelle eine Farbe

    # ------------------------------------------------------------ Bild

    def frame(self, f):
        W, H, yh = self.W, self.H, self.yh
        sweep = H * smooth((f - F_SWEEP0) / (F_SWEEP1 - F_SWEEP0)) if f >= F_SWEEP0 else -1
        wave = W * smooth((f - F_WAVE0) / (F_WAVE1 - F_WAVE0)) if f >= F_WAVE0 else -1
        buf = [[(self.sky[y][x] if y < sweep else SCR) for x in range(W)] for y in range(H)]
        for sx, sy, tw in self.stars:
            a = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(f * 0.35 + tw * 6.3))
            buf[sy][sx] = add(buf[sy][sx], (255, 200, 235), a * 0.75)
        # Funkboegen links und rechts der Antenne; sie klingen bis zum Standbild aus.
        if f >= F_WAVE0:
            ax, ay = self.ant
            step = max(4.0, W * 0.06)
            calm = 1 - smooth((f - F_WAVE0) / (F_END - F_WAVE0))
            for ring in range(3):
                r = ((f - F_WAVE0) * 0.9 + ring * step) % (3 * step) + 2
                fade = (1 - r / (3 * step + 2)) ** 0.5 * calm
                if fade <= 0.02:
                    continue
                for y in range(max(0, int(ay - r)), min(yh, int(ay + r) + 1)):
                    for x in range(max(0, int(ax - r) - 1), min(W, int(ax + r) + 2)):
                        dx, dy = x - ax, y - ay
                        if abs(math.hypot(dx, dy) - r) < 0.6 and abs(dy) < abs(dx) * 0.9:
                            buf[y][x] = mix(buf[y][x], PINK if ring == 0 else MAGENTA, fade)
        self.draw_net(buf, f)
        # Stadt
        for x in range(W):
            for y in range(self.top[x], yh):
                st = self.lit.get((x, y))
                if st is None:
                    buf[y][x] = (40, 8, 40)
                    continue
                on = st == 1 or (st == 2 and x < wave)
                if not on:
                    buf[y][x] = (62, 14, 56)
                elif h32(x, y, 2) % 3 == 0 or (x < wave and h32(x, y, 2) % 3 == 1):
                    buf[y][x] = MAGENTA
                else:
                    buf[y][x] = ((255, 220, 150), (255, 240, 220), PINK)[h32(x, y, 1) % 3]
        # Turm, von unten magenta angestrahlt
        for (x, y), part in self.tower.items():
            if 0 <= x < W and 0 <= y < H:
                c = (205, 205, 220) if part in ('mast', 'cab') else (150, 150, 172)
                buf[y][x] = mix(c, MAGENTA, 0.15 + 0.45 * (y - self.ttop) / max(1, yh - self.ttop))
        if f >= F_FEED:
            glow = 1.0 if f >= F_WAVE0 else 0.5 + 0.5 * math.sin(f * 0.8)
            buf[self.ant[1]][self.ant[0]] = mix((255, 255, 255), MAGENTA, glow)
        for i, (x, y) in enumerate(self.lights):
            if 0 <= x < W and 0 <= y < H and (f // 6 + i) % 2 == 0:
                buf[y][x] = (255, 40, 40)
        # Satellit und Strahl vom Turm hinauf
        self.draw_sat(buf, f)
        if F_BEAM0 <= f < F_BEAM1 + 3:
            sx, sy = self.satellite(f)
            tx, ty = sx + len(SAT[0]) * self.sat_scale // 2, sy + len(SAT) * self.sat_scale
            pts = line(self.ant[0], self.ant[1] - 1, tx, ty)
            t = min(1.0, (f - F_BEAM0 + 1) / 3)
            for x, y in pts[:max(1, int(t * len(pts)))]:
                if 0 <= x < W and 0 <= y < H:
                    buf[y][x] = (255, 255, 255) if (f - F_BEAM0) % 2 == 0 else PINK
        if f >= F_WAVE0 + 4:
            self.logo(buf, smooth((f - F_WAVE0 - 4) / 6))
        # Boden mit dem Scroller
        for y in range(yh, H):
            fall = 1 - (y - yh) / max(1, H - yh)
            for x in range(W):
                buf[y][x] = mix((24, 0, 26), (120, 0, 62), 0.6 * fall)
        for x in range(W):
            buf[yh][x] = MAGENTA
        self.scroller(buf, f)
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
                buf[y][x] = mix((255, 255, 255), PINK, x / W)
        return buf


if __name__ == '__main__':
    if '--png' in sys.argv:
        i = sys.argv.index('--png')
        n, path = int(sys.argv[i + 1]), sys.argv[i + 2]
        g = geometry(110, 34)
        W, H = g[10] - g[9] + 1, 2 * (g[12] - g[11] + 1)
        p = Panel(W, H)
        t1 = time.time()
        for f in range(n + 1):
            buf = p.frame(f)
        print(f'{W}x{H}px  {(time.time() - t1) / (n + 1) * 1000:.0f} ms/Bild')
        write_png(path, buf)
    else:
        sys.exit(nyc.main(NAME, Panel, 'DEUTSCHE TELEKOM', MAGENTA, PINK,
                          finale=f'WELCOME, {NAME}!  ERLEBEN, WAS VERBINDET.', finale_border=MAGENTA,
                          finale_at=F_WAVE0 + 4, border_at=F_READY, raster=raster) or 0)
