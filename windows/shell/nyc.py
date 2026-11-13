#!/usr/bin/env python3
"""New York im Einschaltbildschirm: LOAD "ERIC",8,1 (Eric, n8n Ambassador NYC), ebenso
LOAD "BERTRAND",8,1 - gleiches Bild, anderer Name.

Gleicher Ablauf wie trek.py, andere Diskette: links tippt der C64 LOAD "ERIC",8,1 und
SEARCHING FOR ERIC, rechts steht Manhattan bei Nacht als C64-Bild auf Bildschirmblau: Empire
State, Chrysler, One World Trade, links auf dem Wasser die Freiheitsstatue. Bei LOADING laedt
die Abtastzeile den Abendhimmel in 24 Bit nach. Bei READY. erscheint ueber der Stadt ein
Workflow aus vier Knoten in n8n-Farbe, bei RUN laeuft er durch, Knoten fuer Knoten gruen; ist
er fertig, geht die Spitze des Empire State in n8n-Farbe an, und die Fenster gehen von links
nach rechts an. Nur Text und Farbe von n8n, kein Logo.

    nyc.py [NAME]        Animation (NAME: ERIC, Vorgabe, oder BERTRAND), etwa 12 s und 3 s Stand; Rueckgabe 2, wenn das
                         Fenster zu klein ist (dann boot.py nehmen)
    nyc.py --png N f     Bild N des Feldes als PNG, zur Kontrolle ohne Terminal
"""
import math
import os
import random
import shutil
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402
from boot import at, RESET, BOLD, LB, SCREEN_BG, HIDE, SHOW, ALT_ON, ALT_OFF  # noqa: E402
from trek import (SCR, vic_fix, quantize, mix, add, smooth, paint_cells, raster_border,  # noqa: E402
                  plain_border, gradient_text, geometry, write_png, bg,
                  F_LOADING, F_SWEEP0, F_SWEEP1, F_READY, F_RUN, F_END)

N8N = (234, 75, 113)          # n8n-Farbe: Workflow, Spitze des Empire State, Schriftzug
DONE = (95, 210, 130)         # Knoten gelaufen
NAMES = ('ERIC', 'BERTRAND')
F_FLOW = [F_RUN, F_RUN + 4, F_RUN + 8, F_RUN + 12]     # Knoten i fertig
F_WAVE0, F_WAVE1 = F_FLOW[-1] + 1, F_FLOW[-1] + 20      # Fensterwelle

BODY, WIN, CROWN, TOP, LADY, TORCH = range(6)


def h32(x, y, k=0):
    return ((x * 73856093) ^ (y * 19349663) ^ (k * 83492791)) & 0xffff


class City:
    """Skyline als Materialkarte: je Pixel (Material, Wert) oder None (Himmel)."""

    def __init__(self, W, H):
        self.W, self.H = W, H
        yh = self.yh = int(H * 0.84)                      # Horizont: darunter das Wasser
        u = W / 80
        top, who = [yh] * W, [-1] * W
        tone = {}
        rng = random.Random(1625)                         # Nieuw Amsterdam
        n, x = 0, int(W * 0.11)
        while x < W:
            w = rng.randint(max(2, W // 28), max(3, W // 13))
            h = int(yh * rng.uniform(0.12, 0.42))
            for i in range(x, min(W, x + w)):
                top[i], who[i] = yh - h, n
            tone[n] = rng.uniform(0.75, 1.15)
            n += 1
            x += w + (1 if rng.random() < 0.3 else 0)
        self.towers = {}

        def tower(name, cx, levels):
            nonlocal n
            for hw, hf in levels:
                hw = max(0, round(hw))
                t = yh - int(yh * hf)
                for i in range(cx - hw, cx + hw + 1):
                    if 0 <= i < W:
                        top[i] = min(top[i], t) if who[i] == n else t
                        who[i] = n
            tone[n] = 1.0
            self.towers[name] = (n, cx)
            n += 1

        # Breiteste Stufe zuerst; jede weitere setzt nur die Mitte hoeher.
        tower('esb', int(W * 0.30), [(5 * u, 0.42), (4 * u, 0.52), (3 * u, 0.60), (1.5 * u, 0.66),
                                      (0.5 * u, 0.70), (0, 0.77)])
        tower('chrysler', int(W * 0.50), [(3.5 * u, 0.50), (3 * u, 0.53), (2.5 * u, 0.56), (2 * u, 0.59),
                                          (1.5 * u, 0.62), (1 * u, 0.65), (0.5 * u, 0.67), (0, 0.74)])
        tower('wtc', int(W * 0.72), [(4.5 * u - 2.5 * u * j / 12, 0.70 * (j + 1) / 12) for j in range(12)]
              + [(0, 0.80)])
        self.top, self.who, self.tone = top, who, tone
        # Freiheitsstatue auf ihrer Insel, links vor der Stadt
        lx = max(2, int(W * 0.05))
        self.lady = {}
        for hw, hf in ((1.5 * u, 0.10), (0.7 * u, 0.22), (0.4 * u, 0.25)):
            hw = max(0, round(hw))
            for i in range(lx - hw, lx + hw + 1):
                self.lady[i] = min(self.lady.get(i, yh), yh - int(yh * hf))
        arm = lx + max(1, round(0.7 * u))
        self.lady[arm] = min(self.lady.get(arm, yh), yh - int(yh * 0.30))
        self.torch = (arm, yh - int(yh * 0.30) - 1)
        self.lit = {}                                     # Fenster: an ab Bild 0 oder erst mit der Welle
        for x in range(W):
            for y in range(top[x] + 2, yh - 1):
                if x % 2 == 1 and y % 2 == 0:
                    r = h32(x, y) / 0xffff
                    self.lit[(x, y)] = 0 if r < 0.42 else (1 if r < 0.88 else 2)

    def at(self, x, y, f, wave):
        """Material und Farbe fuer (x, y), oder None fuer Himmel."""
        yh = self.yh
        if y >= yh:
            return None
        if (x, y) == self.torch:
            k = 0.75 + 0.25 * math.sin(f * 0.9)
            return (int(255 * k), int(200 * k), 70)
        if x in self.lady and y >= self.lady[x]:
            shade = 0.85 + 0.15 * ((x + y) % 2)
            return (int(78 * shade), int(160 * shade), int(140 * shade))
        if y < self.top[x]:
            return None
        n = self.who[x]
        tone = self.tone.get(n, 1.0)
        tid = {v[0]: k for k, v in self.towers.items()}.get(n)
        hf = (yh - y) / yh
        if tid == 'chrysler' and hf > 0.50:
            # Krone aus Stahl mit dreieckigen Fenstern
            lit = (y % 2 == 0) and abs(x - self.towers['chrysler'][1]) % 2 == 0
            return (255, 236, 190) if lit else (176, 184, 200)
        if tid == 'esb' and hf > 0.60:
            base = (230, 230, 240)
            return mix(base, N8N, smooth((f - F_WAVE0) / 4)) if f >= F_WAVE0 else base
        state = self.lit.get((x, y))
        if state is not None:
            on = state == 1 or (state == 2 and x < wave)
            if on:
                warm = h32(x, y, 1) % 3
                return ((255, 214, 120), (255, 236, 170), (200, 225, 255))[warm]
            return (34, 38, 62)
        glow = 1 - hf / 0.5                                # Stadtlicht von unten
        return (int((22 + 26 * max(0.0, glow)) * tone), int((24 + 18 * max(0.0, glow)) * tone),
                int((44 + 20 * max(0.0, glow)) * tone))


class Panel:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.city = City(W, H)
        yh = self.city.yh
        mx, my, mr = W * 0.90, H * 0.22, max(2.0, H * 0.05)
        self.sky, self.moon = [], set()
        for y in range(H):
            row = []
            for x in range(W):
                t = y / max(1, yh)
                c = mix((8, 10, 34), (44, 26, 86), t / 0.6) if t < 0.6 else mix((44, 26, 86), (236, 112, 82), (t - 0.6) / 0.4)
                d = math.hypot(x - mx, (y - my))
                if d < mr:
                    c = (240, 236, 220)
                    self.moon.add((x, y))
                else:
                    c = add(c, (120, 120, 150), max(0.0, 1 - (d - mr) / (mr * 2.5)) ** 2 * 0.6)
                row.append(c)
            self.sky.append(row)
        rng = random.Random(10001)                        # ZIP von Manhattan
        self.stars = [(rng.randrange(W), rng.randrange(max(1, int(yh * 0.55))), rng.random()) for _ in range(max(10, W * H // 90))]
        # Workflow: vier Knoten ueber der Stadt
        nw, nh = max(6, round(W / 11)), max(4, round(H / 9))
        y0 = max(1, int(H * 0.05))
        xs = [int(W * k) for k in (0.08, 0.27, 0.46, 0.65)]
        self.nodes = [(x, y0, nw, nh) for x in xs]

    def flow(self, buf, f):
        if f < F_READY:
            return
        for i, (x, y, w, h) in enumerate(self.nodes):
            k = smooth((f - F_READY - 3 * i) / 3)
            if k <= 0:
                continue
            ring = DONE if f >= F_FLOW[i] else N8N
            for yy in range(y, y + h):
                for xx in range(x, x + w):
                    if 0 <= xx < self.W and 0 <= yy < self.H:
                        edge = yy in (y, y + h - 1) or xx in (x, x + w - 1)
                        corner = (yy in (y, y + h - 1)) and (xx in (x, x + w - 1))
                        if corner:
                            continue
                        buf[yy][xx] = mix(buf[yy][xx], ring if edge else (46, 46, 64), k)
            if i + 1 < len(self.nodes):
                nx = self.nodes[i + 1][0]
                cy = y + h // 2
                k2 = smooth((f - F_READY - 3 * i - 2) / 3)
                if k2 <= 0:
                    continue
                for xx in range(x + w, nx):
                    buf[cy][xx] = mix(buf[cy][xx], (150, 150, 175), k2)
                if F_FLOW[i] <= f < F_FLOW[i + 1]:               # das Datenpaket unterwegs
                    t = (f - F_FLOW[i] + 1) / (F_FLOW[i + 1] - F_FLOW[i])
                    px = int(x + w + (nx - x - w) * t) - 1
                    for d, a in ((0, 1.0), (-1, 0.5)):
                        if x + w <= px + d < nx:
                            buf[cy][px + d] = mix(buf[cy][px + d], (255, 255, 255), a)

    def frame(self, f):
        W, H, city = self.W, self.H, self.city
        yh = city.yh
        sweep = H * smooth((f - F_SWEEP0) / (F_SWEEP1 - F_SWEEP0)) if f >= F_SWEEP0 else -1
        wave = W * smooth((f - F_WAVE0) / (F_WAVE1 - F_WAVE0)) if f >= F_WAVE0 else -1
        buf = []
        for y in range(H):
            row = []
            for x in range(W):
                if y < yh:
                    c = city.at(x, y, f, wave)
                    if c is None:
                        c = self.sky[y][x] if (y < sweep or (x, y) in self.moon) else SCR
                    row.append(c)
                else:
                    row.append(None)
            buf.append(row)
        for sx, sy, tw in self.stars:
            if buf[sy][sx] == self.sky[sy][sx] or buf[sy][sx] == SCR:
                if (sx, sy) not in self.moon:
                    a = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(f * 0.35 + tw * 6.3))
                    buf[sy][sx] = add(buf[sy][sx], (255, 255, 255), a * 0.8)
        self.flow(buf, f)
        # Wasser: Spiegelbild mit Wellen, dunkler nach unten
        for y in range(yh, H):
            depth = (y - yh + 1) / max(1, H - yh)
            src = max(0, 2 * yh - y - 1)
            for x in range(W):
                off = int(round(math.sin(y * 1.9 + f * 0.45 + x * 0.15) * 1.2))
                c = buf[src][min(W - 1, max(0, x + off))]
                water = (6, 14, 40) if y < sweep else (20, 26, 120)
                buf[y][x] = mix(c, water, 0.45 + 0.4 * depth)
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
                buf[y][x] = mix((255, 255, 255), (120, 220, 255), x / W)
        return buf


def wrap(line, width):
    """Wie der C64: was ueber die Spalte geht, laeuft in der naechsten Zeile weiter."""
    return [line[i:i + width] for i in range(0, len(line), width)] or ['']


def color_border(cols, rows, c):
    """Der Rahmen in einer festen Farbe statt der des Profils."""
    out = []
    for r in range(1, rows + 1):
        if r <= boot.BORDER_ROWS or r > rows - boot.BORDER_ROWS:
            out.append(at(r, 1) + bg(c) + ' ' * cols)
        else:
            out.append(at(r, 1) + bg(c) + ' ' * boot.BORDER_COLS + at(r, cols - boot.BORDER_COLS + 1) + ' ' * boot.BORDER_COLS)
    return ''.join(out) + RESET


def main(name, panel_cls=None, motto='n8n AMBASSADOR NYC', accent=N8N, accent2=(255, 176, 96),
         finale=None, finale_border=None, finale_at=F_WAVE0, border_at=None, raster=None):
    """Der Ablauf links (LOAD, SEARCHING, ...) und der Kopf; das Bild rechts liefert panel_cls.
    magenta.py nimmt denselben Ablauf mit eigenem Bild. finale: Zeile, die ab finale_at die
    Begruessung ersetzt; finale_border: Rahmenfarbe ab border_at (Vorgabe finale_at);
    raster(cols, rows, f): eigene Ladebalken statt der bunten."""
    raster = raster or raster_border
    border_at = finale_at if border_at is None else border_at
    panel_cls = panel_cls or Panel
    cols, rows = shutil.get_terminal_size((100, 30))
    apple = os.environ.get('TERM_PROGRAM') == 'Apple_Terminal'
    sl, sr, st, banner_top, text_w, pl, pr, pt, pb, cl, cr, ct, cb = geometry(cols, rows)
    W, H = cr - cl + 1, 2 * (cb - ct + 1)
    if W < 40 or H < 14:
        return 2
    panel = panel_cls(W, H)
    lines, typed = [], ''
    cmd = f'LOAD "{name}",8,1'

    def script(f):
        nonlocal typed
        if f == 0:
            lines.append('READY.')
        if 6 <= f < 18:                                   # in 12 Bildern getippt, wie lang der Name auch ist
            typed = cmd[:math.ceil((f - 5) * len(cmd) / 12)]
        if f == 18:
            lines.extend(wrap(cmd, text_w - 1) + ['']); typed = ''
        if f == 22:
            lines.extend(wrap(f'SEARCHING FOR {name}', text_w - 1))
        if f == F_LOADING:
            lines.append('LOADING')
        if f == F_READY:
            lines.append('READY.')
        if F_RUN - 4 <= f < F_RUN - 1:
            typed = 'RUN'[:f - F_RUN + 5]
        if f == F_RUN - 1:
            lines.append(typed); typed = ''
        return f >= F_END

    write = lambda text: sys.stdout.write(vic_fix(text))
    write(ALT_ON + HIDE + boot.frame_border(cols, rows))
    write(boot.paint_crab(boot.crab_rows(apple, 1, 0, logo=True), st, sl + 1))
    write(at(st, sl + 1 + boot.CRAB_W + 2) + boot.WHITE + BOLD + SCREEN_BG + 'CLAUDE CODE' + RESET)
    write(at(st + 1, sl + 1 + boot.CRAB_W + 2) + LB + SCREEN_BG + 'retro deck' + RESET)
    for i, line in enumerate(boot.BANNER):
        write(at(banner_top + i, sl) + LB + SCREEN_BG + line.center(sr - sl + 1) + RESET)
    width = sr - sl + 1
    f = 0
    try:
        while True:
            t0 = time.time()
            done = script(f)
            out = []
            if F_LOADING <= f < F_READY:
                out.append(raster(cols, rows, f))
            elif f == F_READY:
                out.append(plain_border(cols, rows))
            for i, line in enumerate(lines):
                out.append(at(pt + i, sl) + LB + SCREEN_BG + line.ljust(text_w - 1) + RESET)
            cursor = '█' if (f // 4) % 2 == 0 else ' '
            out.append(at(pt + len(lines), sl) + LB + SCREEN_BG + (typed + cursor).ljust(text_w - 1) + RESET)
            out.append(paint_cells(panel.frame(f), ct, cl))
            if hasattr(panel, 'overlay'):                 # echte Schrift ueber dem Bild
                out.append(panel.overlay(f, ct, cl))
            if f == 0:
                text = motto
                out.append(gradient_text(banner_top + 2, sl + text.center(width).index(text), text, accent, accent2, 1.0))
            if F_READY <= f < F_READY + 6:
                text = f'WELCOME, {name}!'
                out.append(gradient_text(banner_top + 3, sl + text.center(width).index(text), text, (255, 255, 255), (255, 214, 120),
                                         smooth((f - F_READY) / 5)))
            if finale_border and f == border_at:
                out.append(color_border(cols, rows, finale_border))
            if finale and finale_at <= f < finale_at + 6:
                out.append(at(banner_top + 3, sl) + SCREEN_BG + ' ' * width + RESET)
                out.append(gradient_text(banner_top + 3, sl + finale.center(width).index(finale), finale, accent2, accent,
                                         smooth((f - finale_at) / 5)))
            write(''.join(out))
            sys.stdout.flush()
            if done:
                break
            f += 1
            time.sleep(max(0.0, boot.FRAME_S - (time.time() - t0)))
        time.sleep(3)
    except KeyboardInterrupt:
        pass
    finally:
        write(SHOW + ALT_OFF)
        sys.stdout.flush()


if __name__ == '__main__':
    if '--png' in sys.argv:
        i = sys.argv.index('--png')
        n, path = int(sys.argv[i + 1]), sys.argv[i + 2]
        cols, rows = 110, 34
        g = geometry(cols, rows)
        W, H = g[10] - g[9] + 1, 2 * (g[12] - g[11] + 1)
        t0 = time.time()
        p = Panel(W, H)
        print(f'render {time.time() - t0:.2f}s  {W}x{H}px')
        t1 = time.time()
        for f in range(n + 1):
            buf = p.frame(f)
        print(f'{(time.time() - t1) / (n + 1) * 1000:.0f} ms/Bild')
        write_png(path, buf)
    else:
        arg = sys.argv[1].upper() if len(sys.argv) > 1 else NAMES[0]
        sys.exit(main(arg if arg in NAMES else NAMES[0]) or 0)
