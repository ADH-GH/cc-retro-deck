#!/usr/bin/env python3
"""Berlin bei Nacht im Einschaltbildschirm: LOAD "JAN",8,1, die Fassung fuer Jan Oberhauser,
Gruender von n8n, im neuen n8n-Branding (vorgestellt am 14. Oktober 2026).

Ablauf und Kopf wie nyc.py (links LOAD "JAN",8,1, SEARCHING FOR JAN ...), eigenes Bild: Berlin
bei Nacht mit Fernsehturm und Spree, als C64-Bild auf Bildschirmblau; die Abtastzeile laedt den
Himmel in 24 Bit nach, von Core Black zu den dunklen n8n-Pinktoenen. Ladebalken in Accent Pink,
Schwarz und Weiss. Bei READY. steht ueber der Stadt das neue n8n-Symbol (drei verbundene Kreuze)
in dunklem Pink, der Rahmen wird Accent Pink; bei RUN leuchten die Kreuze nacheinander auf, ein
Puls laeuft durch das Band, dann erscheint der Schriftzug, die Kugel des Fernsehturms glitzert
und die Fenster gehen an. Kopf "FOUNDER OF n8n", am Ende "WELCOME, JAN!  WHERE THERE'S A WILL,
THERE'S ALREADY A WORKFLOW."

Symbol und Schriftzug sind die Pfade aus der offiziellen Datei n8n-logo-black-accent.svg
(guidelines.n8n.design/downloads/logo/lockup/), hier gerastert; Farben aus guidelines.n8n.design/colors.

    berlin.py               Animation, etwa 12 s und 3 s Stand; Rueckgabe 2, wenn das
                            Fenster zu klein ist (dann boot.py nehmen)
    berlin.py --png N f     Bild N des Feldes als PNG, zur Kontrolle ohne Terminal
"""
import math
import os
import random
import re
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

ACCENT = (255, 145, 172)      # #FF91AC
BLACK = (25, 25, 25)          # Core Black #191919
WHITE = (250, 250, 250)       # Core White #FAFAFA
PINK70, PINK80, PINK90 = (135, 0, 60), (90, 0, 38), (68, 0, 27)
PINK20 = (255, 208, 217)
NAME = 'JAN'
F_CROSS = [F_RUN + 4 * i for i in range(3)]               # Kreuz i leuchtet
F_WORD = F_CROSS[-1] + 4                                 # Schriftzug
F_WAVE0, F_WAVE1 = F_WORD + 4, F_END - 2

SYMBOL = 'M48 96C52.5 96 54 94.5 54 90V78C54 60 60 54 78 54H90C108 54 114 60 114 78V90C114 94.5 115.5 96 120 96C124.5 96 126 94.5 126 90V78C126 60 132 54 150 54H162C180 54 186 60 186 78V90C186 94.5 187.5 96 192 96C196.5 96 198 94.5 198 90V78C198 60 204 54 222 54H234C238.5 54 240 52.5 240 48C240 43.5 238.5 42 234 42H222C204 42 198 36 198 18V6C198 1.5 196.5 0 192 0C187.5 0 186 1.5 186 6V18C186 36 180 42 162 42H150C132 42 126 36 126 18V6C126 1.5 124.5 0 120 0C115.5 0 114 1.5 114 6V18C114 36 108 42 90 42H78C60 42 54 36 54 18V6C54 1.5 52.5 0 48 0C43.5 0 42 1.5 42 6V18C42 36 36 42 18 42H6C1.5 42 0 43.5 0 48C0 52.5 1.5 54 6 54H18C36 54 42 60 42 78V90C42 94.5 43.5 96 48 96Z'
WORDMARK = 'M396 85.5C411.75 85.5 422.25 77.1562 422.25 64.5938C422.25 55.7812 417.562 49.3125 409.312 46.125C416.156 43.125 420 37.5 420 30.0938C420 18.375 410.438 10.5 396 10.5C381.562 10.5 372 18.375 372 30.0938C372 37.5 375.844 43.125 382.688 46.125C374.438 49.3125 369.75 55.7812 369.75 64.5938C369.75 77.1562 380.25 85.5 396 85.5ZM312 84H324V60.2812C324 46.6875 329.531 42.1875 337.688 42.1875C344.719 42.1875 348 45.4688 348 55.2188V84H360V51C360 39 353.625 31.5 340.969 31.5C332.625 31.5 327 34.9688 323.625 40.875V33H312V84ZM396 75C387.656 75 382.5 70.5938 382.5 63.2812C382.5 55.9688 387.656 51.5625 396 51.5625C404.344 51.5625 409.5 55.9688 409.5 63.2812C409.5 70.5938 404.344 75 396 75ZM396 41.625C388.781 41.625 384 37.5 384 31.3125C384 25.125 388.781 21 396 21C403.219 21 408 25.125 408 31.3125C408 37.5 403.219 41.625 396 41.625ZM432 84H444V60.2812C444 46.6875 449.531 42.1875 457.688 42.1875C464.719 42.1875 468 45.4688 468 55.2188V84H480V51C480 39 473.625 31.5 460.969 31.5C452.625 31.5 447 34.9688 443.625 40.875V33H432V84Z'


def polygons(d):
    """SVG-Pfad (nur M, C, H, V, Z, absolut) als Liste geschlossener Polygone."""
    toks = re.findall(r'[MCHVZ]|-?\d*\.?\d+', d)
    polys, cur, x, y, cmd, i = [], [], 0.0, 0.0, None, 0
    while i < len(toks):
        t = toks[i]
        if t in 'MCHVZ':
            cmd = t; i += 1
            if cmd == 'Z':
                if cur:
                    polys.append(cur)
                cur = []
            continue
        if cmd == 'M':
            x, y = float(toks[i]), float(toks[i + 1]); i += 2
            cur = [(x, y)]
        elif cmd == 'H':
            x = float(toks[i]); i += 1; cur.append((x, y))
        elif cmd == 'V':
            y = float(toks[i]); i += 1; cur.append((x, y))
        elif cmd == 'C':
            x1, y1, x2, y2, x3, y3 = (float(v) for v in toks[i:i + 6]); i += 6
            for k in range(1, 9):
                t_ = k / 8
                a = (1 - t_) ** 3; b = 3 * (1 - t_) ** 2 * t_; c = 3 * (1 - t_) * t_ ** 2; e = t_ ** 3
                cur.append((a * x + b * x1 + c * x2 + e * x3, a * y + b * y1 + c * y2 + e * y3))
            x, y = x3, y3
    if cur:
        polys.append(cur)
    return polys


def coverage(polys, ox, oy, scale, w, h, ss=4):
    """Deckung je Pixel (0..1) einer gerade-ungerade gefuellten Form; Zeilenabtastung mit ss x ss."""
    edges = [(p[k], p[(k + 1) % len(p)]) for p in polys for k in range(len(p))]
    cov = [[0.0] * w for _ in range(h)]
    for sy in range(h * ss):
        yy = (sy + 0.5) / ss / scale - oy
        xs = []
        for (x0, y0), (x1, y1) in edges:
            if (y0 <= yy < y1) or (y1 <= yy < y0):
                xs.append(x0 + (yy - y0) * (x1 - x0) / (y1 - y0))
        xs.sort()
        row = cov[sy // ss]
        for a, b in zip(xs[0::2], xs[1::2]):
            pa, pb = (a + ox) * scale * ss, (b + ox) * scale * ss
            for sx in range(max(0, math.ceil(pa - 0.5)), min(w * ss, math.ceil(pb - 0.5))):
                row[sx // ss] += 1 / (ss * ss)
    return cov


def raster(cols, rows, f):
    """Ladebalken im Rahmen wie beim Schnelllader, in den n8n-Farben."""
    rng = random.Random(f * 7919)
    palette = (ACCENT, ACCENT, PINK20, WHITE, BLACK, PINK70)
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
        yh = self.yh = int(H * 0.82)                      # darunter die Spree
        rng = random.Random(2019)
        top = [yh] * W
        x = 0
        while x < W:
            w = rng.randint(max(2, W // 22), max(3, W // 10))
            h = int(yh * rng.uniform(0.06, 0.22))
            for i in range(x, min(W, x + w)):
                top[i] = yh - h
            x += w + (1 if rng.random() < 0.3 else 0)
        self.top = top
        # Fernsehturm: Schaft, Kugel, Antenne mit rot-weissen Ringen
        self.tcx = int(W * 0.87)
        tt = max(2, int(H * 0.10))                       # Spitze
        self.sphere = (self.tcx, tt + int((yh - tt) * 0.30), max(3.0, H * 0.075))
        self.tower = {}
        for y in range(tt, yh):
            k = (y - tt) / (yh - tt)
            if y < self.sphere[1] - self.sphere[2]:
                self.tower[(self.tcx, y)] = 'red' if (y - tt) % 3 == 0 else 'ant'
            else:
                hw = 0 if k < 0.6 else 1
                for xx in range(self.tcx - hw, self.tcx + hw + 1):
                    self.tower[(xx, y)] = 'shaft'
        sx, sy, sr = self.sphere
        for y in range(int(sy - sr) - 1, int(sy + sr) + 2):
            for x in range(int(sx - sr) - 1, int(sx + sr) + 2):
                if math.hypot(x - sx, (y - sy)) <= sr + 0.3:
                    self.tower[(x, y)] = 'ball'
        self.top_light = (self.tcx, tt)
        # Logo: Symbol und Schriftzug (480 x 96), ueber der Stadt links
        lw = int(W * 0.76)
        scale = lw / 480
        lh = (int(96 * scale) + 3) // 2 * 2
        self.lx, self.ly = max(1, int(W * 0.04)), max(2, int(H * 0.14)) // 2 * 2
        # Harte Kanten und ganze Zeichenzellen: je zwei Pixelzeilen entscheiden gemeinsam. Sonst
        # zeichnet Apples Terminal an halb gedeckten Zellen Streifen; und es ist 8-Bit-Look.
        def crisp(cov):
            out = []
            for r in range(0, len(cov), 2):
                pair = cov[r:r + 2]
                row = [1.0 if sum(p[x] for p in pair) / 2 >= 0.4 else 0.0 for x in range(len(cov[0]))]
                out += [row, list(row)]
            return out[:len(cov)]
        # Die Mitte des Querbalkens (y = 48) auf die Mitte einer Zelle legen, sonst werden die
        # Kreuze oben und unten ungleich.
        oy = (2 * int(48 * scale / 2) + 1) / scale - 48
        lh += 2
        self.sym = crisp(coverage(polygons(SYMBOL), 0, oy, scale, lw + 1, lh))
        self.word = crisp(coverage(polygons(WORDMARK), 0, oy, scale, lw + 1, lh))
        self.lw, self.lh, self.scale = lw + 1, lh, scale
        # Himmel
        self.sky = []
        for y in range(H):
            t = y / max(1, yh)
            c = mix(BLACK, PINK90, t / 0.6) if t < 0.6 else mix(PINK90, PINK70, (t - 0.6) / 0.4)
            self.sky.append([c] * W)
        self.stars = [(rng.randrange(W), rng.randrange(max(1, int(yh * 0.55))), rng.random()) for _ in range(max(10, W * H // 100))]
        self.lit = {}
        for x in range(W):
            for y in range(top[x] + 1, yh - 1):
                if x % 2 == 1 and y % 2 == 0:
                    r = h32(x, y) / 0xffff
                    self.lit[(x, y)] = 0 if r < 0.45 else (1 if r < 0.85 else 2)

    def draw_logo(self, buf, f):
        if f < F_READY:
            return
        k = smooth((f - F_READY) / 5)
        for y in range(self.lh):
            yy = self.ly + y
            if not 0 <= yy < self.H:
                continue
            for x in range(self.lw):
                xx = self.lx + x
                if not 0 <= xx < self.W:
                    continue
                a = self.sym[y][x]
                if a > 0:
                    u = x / self.scale                    # Lage im Symbol (0..240)
                    i = min(2, int(u // 80))              # welches Kreuz
                    c = PINK70
                    if f >= F_CROSS[i]:
                        c = mix(PINK70, ACCENT, smooth((f - F_CROSS[i]) / 3))
                    if F_CROSS[0] <= f < F_WORD:          # der Puls durch das Band
                        p = (f - F_CROSS[0]) / (F_WORD - F_CROSS[0]) * 240
                        if abs(u - p) < 14:
                            c = mix(c, WHITE, 1 - abs(u - p) / 14)
                    buf[yy][xx] = mix(buf[yy][xx], c, a * k)
                w = self.word[y][x]
                if w > 0 and f >= F_WORD:
                    buf[yy][xx] = mix(buf[yy][xx], WHITE, w * smooth((f - F_WORD) / 4))

    def frame(self, f):
        W, H, yh = self.W, self.H, self.yh
        sweep = H * smooth((f - F_SWEEP0) / (F_SWEEP1 - F_SWEEP0)) if f >= F_SWEEP0 else -1
        wave = W * smooth((f - F_WAVE0) / (F_WAVE1 - F_WAVE0)) if f >= F_WAVE0 else -1
        buf = [[(self.sky[y][x] if y < sweep else SCR) for x in range(W)] for y in range(yh)]
        for sx, sy, tw in self.stars:
            a = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(f * 0.35 + tw * 6.3))
            buf[sy][sx] = add(buf[sy][sx], WHITE, a * 0.7)
        self.draw_logo(buf, f)
        # Stadt
        for x in range(W):
            for y in range(self.top[x], yh):
                st = self.lit.get((x, y))
                if st is None:
                    buf[y][x] = (36, 36, 40)
                    continue
                on = st == 1 or (st == 2 and x < wave)
                if not on:
                    buf[y][x] = (53, 53, 58)
                elif h32(x, y, 2) % 3 == 0 or (x < wave and h32(x, y, 2) % 3 == 1):
                    buf[y][x] = ACCENT
                else:
                    buf[y][x] = ((255, 226, 170), WHITE, PINK20)[h32(x, y, 1) % 3]
        # Fernsehturm
        sx, sy, sr = self.sphere
        for (x, y), part in self.tower.items():
            if not (0 <= x < W and 0 <= y < yh):
                continue
            if part == 'ball':
                shade = 0.55 + 0.45 * max(0.0, ((sx - x) + (sy - y)) / (2 * sr))
                c = mix((70, 70, 78), (225, 225, 232), shade)
                if f >= F_WAVE0 and h32(x, y, f // 2) % 5 == 0:   # die Kugel glitzert
                    c = ACCENT
                buf[y][x] = c
            elif part == 'red':
                buf[y][x] = (220, 40, 40)
            else:
                buf[y][x] = (170, 170, 178) if part == 'ant' else (200, 200, 208)
        if (f // 6) % 2 == 0:
            x, y = self.top_light
            buf[y][x] = (255, 50, 50)
        # Spree: Spiegelbild mit Wellen
        for y in range(yh, H):
            depth = (y - yh + 1) / max(1, H - yh)
            src = max(0, 2 * yh - y - 1)
            row = []
            for x in range(W):
                off = int(round(math.sin(y * 1.9 + f * 0.45 + x * 0.15) * 1.2))
                c = buf[src][min(W - 1, max(0, x + off))]
                row.append(mix(c, BLACK if y < sweep else (20, 26, 120), 0.45 + 0.4 * depth))
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
                buf[y][x] = mix(WHITE, ACCENT, x / W)
        return buf


if __name__ == '__main__':
    if '--png' in sys.argv:
        i = sys.argv.index('--png')
        n, path = int(sys.argv[i + 1]), sys.argv[i + 2]
        g = geometry(110, 34)
        W, H = g[10] - g[9] + 1, 2 * (g[12] - g[11] + 1)
        t0 = time.time()
        p = Panel(W, H)
        print(f'{W}x{H}px  Aufbau {time.time() - t0:.2f}s')
        for f in range(n + 1):
            buf = p.frame(f)
        write_png(path, buf)
    else:
        sys.exit(nyc.main(NAME, Panel, 'FOUNDER OF n8n', ACCENT, PINK20,
                          finale=f"WELCOME, {NAME}!  WHERE THERE'S A WILL, THERE'S ALREADY A WORKFLOW.",
                          finale_border=ACCENT, finale_at=F_WAVE0 + 2, border_at=F_READY, raster=raster) or 0)
