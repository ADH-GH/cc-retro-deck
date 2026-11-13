#!/usr/bin/env python3
"""Graph-Universum im Einschaltbildschirm: LOAD "YURI",8,1, die Fassung fuer Yuri von Ultipa
(Graphdatenbank).

Ablauf und Kopf wie nyc.py (links LOAD "YURI",8,1, SEARCHING FOR YURI ...), eigenes Bild: ein
Graph aus Knoten und Kanten dreht sich langsam im dunklen Raum, als C64-Bild auf
Bildschirmblau; die Abtastzeile laedt ihn in 24 Bit nach. Ladebalken in Ultipa-Orange, Dunkel
und Weiss. Bei READY. wird der Rahmen orange; bei RUN sucht eine Pfadabfrage den kuerzesten Weg
durch den Graphen und leuchtet ihn Knoten fuer Knoten orange aus, dann setzt sich rechts das
Ultipa-Zeichen zusammen. Kopf "ULTIPA GRAPH DATABASE", am Ende
"WELCOME, YURI!  MATCH (YURI)-[:BUILDS]->(GRAPHS)".

Das Zeichen sind die drei Pfade aus der Datei ultipa-logo.svg der Ultipa-Website
(www.ultipa.com/assets/ultipa-logo.svg), mit dem Rasterer aus berlin.py gezeichnet; das Dunkel
des Zeichens (#323346) wird auf dem dunklen Grund hell.

    ultipa.py               Animation, etwa 12 s und 3 s Stand; Rueckgabe 2, wenn das
                            Fenster zu klein ist (dann boot.py nehmen)
    ultipa.py --png N f     Bild N des Feldes als PNG, zur Kontrolle ohne Terminal
"""
import math
import os
import random
import sys
from collections import deque

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402
import nyc  # noqa: E402
from berlin import polygons, coverage  # noqa: E402
from boot import at, RESET, BOLD  # noqa: E402
from trek import (SCR, quantize, mix, add, smooth, geometry, write_png, bg, fg,  # noqa: E402
                  F_SWEEP0, F_SWEEP1, F_READY, F_RUN, F_END)

ORANGE = (237, 80, 52)        # #ED5034
ORANGE2 = (255, 140, 90)      # #FF8C5A
DARK = (10, 22, 40)           # #0A1628
LIGHT = (222, 226, 238)
NAME = 'YURI'
F_STEP = 2                                                # Bilder je Schritt auf dem Pfad
F_LOGO_AFTER = 3
QUERY = 'MATCH p = (a)-[*]-(b) RETURN p'
F_QUERY = F_RUN + (len(QUERY) + 2) // 3                     # Abfrage getippt, drei Zeichen je Bild
CONSOLE_BG = (14, 16, 26)


MARK = [
    ('#323346', 'M415.77 229.58L306.41 292.71C305.27 308.17 297.03 321.64 284.94 329.9V456.28C276.16 452.89 266.74 451.12 257.05 451.12C247.36 451.12 237.94 452.89 229.16 456.28V329.9C217.07 321.64 208.83 308.16 207.69 292.71L98.29 229.54C100.37 227.85 102.38 226.05 104.3 224.12C116.1 212.32 123.62 197.38 126.08 181.18L235.58 244.4C242.07 241.26 249.36 239.51 257.05 239.51C264.74 239.51 272.04 241.27 278.54 244.4L387.94 181.23C390.41 197.41 397.93 212.33 409.71 224.12C411.65 226.06 413.67 227.88 415.77 229.58Z'),
    ('#ED5034', 'M492.41 367.93V210.22C505.51 201.31 514.12 186.29 514.12 169.26C514.12 141.92 491.96 119.76 464.62 119.76C456.9 119.76 449.59 121.53 443.08 124.68C427.61 132.17 416.63 147.48 415.27 165.47C415.18 166.72 415.13 167.98 415.13 169.26C415.13 170.54 415.18 171.79 415.27 173.04C416.43 188.42 424.62 201.84 436.64 210.09V367.97C424.59 376.21 416.36 389.65 415.19 405.05L305.64 468.28L284.95 480.22L278.55 483.92C272.05 480.78 264.76 479.02 257.06 479.02C249.36 479.02 242.07 480.78 235.57 483.92L229.17 480.23L208.47 468.28L98.8599 405.01C97.7099 389.61 89.51 376.18 77.48 367.93V210.31C89.6 202.02 97.8497 188.49 98.9497 172.98C99.0297 171.8 99.0796 170.62 99.0796 169.42C99.0796 168.11 99.0297 166.8 98.9297 165.52C97.5197 147.5 86.4697 132.2 70.9297 124.75C64.4697 121.66 57.2296 119.92 49.5796 119.92C22.2396 119.92 0.0795898 142.08 0.0795898 169.42C0.0795898 186.41 8.64994 201.41 21.6899 210.32V367.82C8.59994 376.73 0 391.74 0 408.77C0 436.11 22.16 458.27 49.5 458.27C57.21 458.27 64.52 456.5 71.02 453.36L180.57 516.59L207.68 532.24C209.58 557.84 230.95 578.03 257.04 578.03C283.13 578.03 304.5 557.85 306.4 532.25L323.87 522.17L333.51 516.6L442.96 453.42C449.48 456.58 456.79 458.35 464.52 458.35C491.86 458.35 514.02 436.19 514.02 408.85C514.02 391.85 505.45 376.85 492.39 367.94L492.41 367.93Z'),
    ('#323346', 'M416 109.04C413.82 110.8 411.72 112.68 409.71 114.68C398 126.4 390.5 141.22 387.99 157.28L278.53 94.1001C272.03 97.2401 264.74 98.9902 257.04 98.9902C249.34 98.9902 242.06 97.2401 235.57 94.1001L126.03 157.33C123.53 141.25 116.03 126.41 104.3 114.68C102.31 112.69 100.22 110.82 98.0601 109.07L207.68 45.79C209.58 20.19 230.95 0 257.04 0C283.13 0 304.51 20.18 306.4 45.79L416 109.04Z'),
]


def raster(cols, rows, f):
    """Ladebalken im Rahmen wie beim Schnelllader, in Ultipa-Orange, Dunkel und Weiss."""
    rng = random.Random(f * 7919)
    palette = (ORANGE, ORANGE, ORANGE2, (50, 51, 70), (250, 250, 250), (0, 0, 0))
    out = []
    for r in range(1, rows + 1):
        c = rng.choice(palette)
        if r <= boot.BORDER_ROWS or r > rows - boot.BORDER_ROWS:
            out.append(at(r, 1) + bg(c) + ' ' * cols)
        else:
            out.append(at(r, 1) + bg(c) + ' ' * boot.BORDER_COLS + at(r, cols - boot.BORDER_COLS + 1) + ' ' * boot.BORDER_COLS)
    return ''.join(out) + RESET


def line(x0, y0, x1, y1):
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


class Panel:
    def __init__(self, W, H):
        self.W, self.H = W, H
        rng = random.Random(2016)
        # Graph: Knoten auf einer Kugel, Kanten zu den naechsten Nachbarn
        n = 34
        self.nodes = []
        for i in range(n):
            z = 1 - 2 * (i + 0.5) / n
            r = math.sqrt(1 - z * z)
            a = i * math.pi * (3 - math.sqrt(5)) + rng.uniform(-0.2, 0.2)
            self.nodes.append((r * math.cos(a), z, r * math.sin(a)))
        self.edges = set()
        for i, p in enumerate(self.nodes):
            near = sorted(range(n), key=lambda j: sum((p[k] - self.nodes[j][k]) ** 2 for k in range(3)))[1:4]
            for j in near:
                self.edges.add((min(i, j), max(i, j)))
        adj = {i: [] for i in range(n)}
        for a, b in self.edges:
            adj[a].append(b); adj[b].append(a)
        # kuerzester Weg zwischen den beiden Polen (Breitensuche)
        start, goal = 0, n - 1
        prev, q = {start: None}, deque([start])
        while q:
            u = q.popleft()
            for v in adj[u]:
                if v not in prev:
                    prev[v] = u; q.append(v)
        path, u = [], goal
        while u is not None:
            path.append(u); u = prev.get(u)
        self.path = path[::-1]
        self.path_edges = {(min(a, b), max(a, b)) for a, b in zip(self.path, self.path[1:])}
        self.f_path_end = F_QUERY + F_STEP * len(self.path)
        self.f_logo = self.f_path_end + F_LOGO_AFTER
        self.gcx, self.gcy, self.gr = W * 0.34, H * 0.42, min(W * 0.24, H * 0.52)
        self.cy0 = H - 4 - H % 2                          # Konsole: die letzten zwei Zeichenzeilen
        # Zeichen rechts: drei Pfade, harte Kanten, auf ganzen Zeichenzellen
        mh = (int(H * 0.56) // 2) * 2
        scale = mh / 579
        mw = int(514 * scale) + 2
        self.mx, self.my = int(W * 0.80 - mw / 2), (int(H * 0.42 - mh / 2) // 2) * 2
        self.mark = []
        for fill, d in MARK:
            cov = coverage(polygons(d), 0, 0, scale, mw, mh + 2)
            cells = []
            for r in range(0, len(cov), 2):
                pair = cov[r:r + 2]
                row = [sum(p[x] for p in pair) / len(pair) >= 0.4 for x in range(mw)]
                cells += [row, list(row)]
            self.mark.append((ORANGE if fill.upper() == '#ED5034' else LIGHT, cells[:len(cov)]))
        self.stars = [(rng.randrange(W), rng.randrange(H), rng.random()) for _ in range(max(10, W * H // 90))]

    def console(self, buf, f):
        """Grund der Konsole im Bild; die Schrift kommt als echter Text aus overlay()."""
        W, H, y = self.W, self.H, self.cy0
        for yy in range(y, H):
            for x in range(W):
                buf[yy][x] = CONSOLE_BG
        for x in range(W):
            buf[y][x] = (50, 51, 70)

    def overlay(self, f, top, left):
        """Konsolenzeile als Terminaltext: ULTIPA> Abfrage, danach das Ergebnis."""
        row = top + self.cy0 // 2 + 1
        base = at(row, left + 1) + bg(CONSOLE_BG) + BOLD
        out = base + fg(ORANGE) + 'ULTIPA> '
        room = self.W - 2 - len('ULTIPA> ')
        if f >= self.f_path_end:
            out += fg((120, 230, 140)) + f'{len(self.path) - 1} hops, path found'[:room]
        else:
            typed = QUERY[:max(0, (f - F_RUN + 1) * 3)] if f >= F_RUN else ''
            cur = '_' if (f // 4) % 2 == 0 else ' '
            out += fg(LIGHT) + (typed + cur)[:room]
        return out + RESET

    def project(self, f):
        a = f * 0.028
        ca, sa = math.cos(a), math.sin(a)
        out = []
        for x, y, z in self.nodes:
            xr, zr = x * ca + z * sa, -x * sa + z * ca
            yr = y * math.cos(0.35) - zr * math.sin(0.35)
            zr2 = y * math.sin(0.35) + zr * math.cos(0.35)
            k = 1 / (1.9 - zr2 * 0.6)
            out.append((round(self.gcx + xr * self.gr * 1.45 * k * 1.25), round(self.gcy - yr * self.gr * k * 1.25), zr2))
        return out

    def frame(self, f):
        W, H = self.W, self.H
        sweep = H * smooth((f - F_SWEEP0) / (F_SWEEP1 - F_SWEEP0)) if f >= F_SWEEP0 else -1
        buf = []
        for y in range(H):
            t = y / H
            buf.append([mix(DARK, (40, 24, 40), t) if y < sweep else SCR] * W)
        for sx, sy, tw in self.stars:
            a = 0.3 + 0.5 * (0.5 + 0.5 * math.sin(f * 0.3 + tw * 6.3))
            buf[sy][sx] = add(buf[sy][sx], (200, 210, 255), a * 0.5)
        pts = self.project(f)
        step = (f - F_QUERY) // F_STEP if f >= F_QUERY else -1  # wie weit die Abfrage ist
        reached = set(self.path[:max(0, step + 1)])
        busy = {i for i in range(len(pts)) if (i * 7 + f // 5) % 23 == 0}   # Abfragen im Hintergrund
        for a, b in sorted(self.edges, key=lambda e: pts[e[0]][2] + pts[e[1]][2]):
            on = (a, b) in self.path_edges and a in reached and b in reached
            depth = (pts[a][2] + pts[b][2]) / 2
            c = ORANGE if on else mix((60, 70, 110), (120, 140, 200), (depth + 1) / 2)
            for x, y in line(pts[a][0], pts[a][1], pts[b][0], pts[b][1]):
                if 0 <= x < W and 0 <= y < H:
                    buf[y][x] = c if on else mix(buf[y][x], c, 0.8)
        if 0 <= step < len(self.path) - 1:               # das Datenpaket auf der Kante
            a, b = self.path[step], self.path[step + 1]
            seg = line(pts[a][0], pts[a][1], pts[b][0], pts[b][1])
            t = ((f - F_QUERY) % F_STEP + 1) / F_STEP
            for d, k in ((0, 1.0), (-1, 0.6), (-2, 0.3)):
                j = int(t * (len(seg) - 1)) + d
                if 0 <= j < len(seg):
                    x, y = seg[j]
                    if 0 <= x < W and 0 <= y < H:
                        buf[y][x] = mix(buf[y][x], (255, 255, 255), k)
        for i in sorted(range(len(pts)), key=lambda i: pts[i][2]):
            x, y, z = pts[i]
            y = y // 2 * 2                                # Knoten auf ganzen Zeichenzellen
            hot = i in reached
            if hot:                                       # Glut um erreichte Knoten
                for dx in range(-2, 4):
                    for dy in range(-2, 4):
                        if 0 <= x + dx < W and 0 <= y + dy < H and abs(dx - 0.5) + abs(dy - 0.5) <= 3:
                            buf[y + dy][x + dx] = mix(buf[y + dy][x + dx], ORANGE, 0.35)
            if hot:
                c = ORANGE2 if step < len(self.path) and (f // 2) % 2 else ORANGE
            elif i in busy:
                c = (255, 255, 255)
            else:
                c = mix((110, 120, 165), LIGHT, (z + 1) / 2)
            size = 2 if z > -0.3 else 1
            for dx in range(size):
                for dy in range(2):
                    if 0 <= x + dx < W and 0 <= y + dy < H:
                        buf[y + dy][x + dx] = c
        if f >= self.f_logo:
            k = smooth((f - self.f_logo) / 6)
            for idx, (col, cells) in enumerate(self.mark):
                kk = smooth((f - self.f_logo - 2 * idx) / 4)
                for y, row in enumerate(cells):
                    for x, on in enumerate(row):
                        if on:
                            xx, yy = self.mx + x, self.my + y
                            if 0 <= xx < W and 0 <= yy < H:
                                buf[yy][xx] = mix(buf[yy][xx], col, min(k, kk))
        self.console(buf, f)
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
                buf[y][x] = mix((255, 255, 255), ORANGE, x / W)
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
        sys.exit(nyc.main(NAME, Panel, 'ULTIPA GRAPH DATABASE', ORANGE, ORANGE2,
                          finale=f'WELCOME, {NAME}!  MATCH ({NAME})-[:BUILDS]->(GRAPHS)',
                          finale_border=ORANGE, finale_at=F_RUN + 24, border_at=F_READY, raster=raster) or 0)
