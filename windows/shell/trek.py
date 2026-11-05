#!/usr/bin/env python3
"""Star-Trek-Tribut im Einschaltbildschirm: von 16 Farben zu 16.777.216.

Ersetzt boot.py bei `LOAD "*",8,1`, solange der Tribut laeuft. Links tippt der C64 wie
gewohnt READY. / LOAD / SEARCHING / LOADING / READY. / RUN, rechts die Enterprise-D. Sie
ist ein kleines 3D-Modell (Ellipsoide und Kapseln), einmal per Strahl gerendert (0,1 bis
0,3 s) und erscheint erst als C64-Bild auf Bildschirmblau: VIC-II-Palette, Bayer-Raster,
doppelt breite Pixel wie im Multicolor-Modus. Bei LOADING flackern die Ladebalken im
Rahmen, und eine Abtastzeile laedt das Bild in 24 Bit nach (Nebel, Planet, Glanz). Bei
READY. fliegt sie davon, bei RUN geht sie auf Warp. "MAKE IT SO." steht von Anfang an
unter dem Banner. Keine Musik.

Alle Farben stehen fest als VIC-II-Werte in 24 Bit, auch was boot.py in Profil-ANSI
zeichnet (vic_fix) - das Bild sieht in jedem Terminal-Profil gleich aus.

    trek.py               Animation, etwa 12 s und 3 s Stand; Rueckgabe 2, wenn das
                          Fenster zu klein ist (dann boot.py nehmen)
    trek.py --png N f     Bild N des Feldes als PNG, zur Kontrolle ohne Terminal
"""
import math
import os
import random
import shutil
import struct
import sys
import time
import zlib

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402
from boot import at, RESET, BOLD, LB, SCREEN_BG, HIDE, SHOW, ALT_ON, ALT_OFF  # noqa: E402

# ---------------------------------------------------------------- Farben

VIC = [(0, 0, 0), (255, 255, 255), (129, 51, 56), (117, 206, 200), (142, 60, 151), (86, 172, 77),
       (46, 44, 155), (237, 241, 113), (142, 80, 41), (85, 56, 0), (196, 108, 113), (74, 74, 74),
       (123, 123, 123), (169, 255, 159), (112, 109, 235), (178, 178, 178)]

SCR, TXT, BRD = VIC[6], VIC[14], VIC[14]      # Bildschirm blau, Schrift und Rahmen hellblau

# Was boot.py in Profil-ANSI zeichnet, hier in festen VIC-Farben, damit jedes Profil passt.
ANSI_FIX = {'\033[49m': 'BG6', '\033[104m': 'BG14', '\033[101m': 'BG10', '\033[94m': 'FG14',
            '\033[91m': 'FG10', '\033[97m': 'FG1', '\033[30m': 'FG0'}


def vic_fix(text):
    for code, tag in ANSI_FIX.items():
        c = VIC[int(tag[2:])]
        text = text.replace(code, (bg if tag[0] == 'B' else fg)(c))
    return text


BAYER = [[0.0, 0.5], [0.75, 0.25]]
_qcache = {}


def quantize(c, x, y):
    d = (BAYER[y & 1][(x >> 1) & 1] - 0.4) * 56
    key = (c[0] >> 3, c[1] >> 3, c[2] >> 3, d)
    hit = _qcache.get(key)
    if hit is None:
        r, g, b = c[0] + d, c[1] + d, c[2] + d
        hit = min(VIC, key=lambda v: (v[0] - r) ** 2 * 0.3 + (v[1] - g) ** 2 * 0.59 + (v[2] - b) ** 2 * 0.11)
        _qcache[key] = hit
    return hit


def fg(c):
    return f'\033[38;2;{c[0]};{c[1]};{c[2]}m'


def bg(c):
    return f'\033[48;2;{c[0]};{c[1]};{c[2]}m'


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def add(a, b, k=1.0):
    return (min(255, int(a[0] + b[0] * k)), min(255, int(a[1] + b[1] * k)), min(255, int(a[2] + b[2] * k)))


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)

# ---------------------------------------------------------------- Modell


def v_sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def v_add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def v_mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a):
    n = math.sqrt(dot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


HULL, GRILLE, BUSSARD, DEFLECTOR, WINDOW, IMPULSE = range(6)

# x Bug, y backbord, z oben. Masse frei nach der Galaxy-Klasse.
PRIMS = [
    ('ell', (0.62, 0.0, 0.30), (1.05, 1.28, 0.12), 'saucer'),
    ('ell', (0.42, 0.0, 0.40), (0.24, 0.19, 0.06), 'dome'),
    ('ell', (0.62, 0.0, 0.20), (0.62, 0.62, 0.07), 'belly'),
    ('ell', (-0.42, 0.0, 0.02), (0.42, 0.20, 0.27), 'neck'),
    ('ell', (-0.92, 0.0, -0.24), (1.02, 0.27, 0.24), 'eng'),
    ('ell', (0.07, 0.0, -0.28), (0.06, 0.17, 0.15), 'deflector'),
    ('cap', (-1.15, 0.20, -0.18), (-1.50, 0.88, 0.0), 0.05, 'pylon'),
    ('cap', (-1.15, -0.20, -0.18), (-1.50, -0.88, 0.0), 0.05, 'pylon'),
    ('cap', (-2.45, 0.88, 0.02), (-0.68, 0.88, 0.02), 0.085, 'nacelle'),
    ('cap', (-2.45, -0.88, 0.02), (-0.68, -0.88, 0.02), 0.085, 'nacelle'),
    ('ell', (-0.70, 0.88, 0.02), (0.11, 0.095, 0.095), 'bussard'),
    ('ell', (-0.70, -0.88, 0.02), (0.11, 0.095, 0.095), 'bussard'),
    ('ell', (-0.44, 0.34, 0.30), (0.04, 0.12, 0.035), 'impulse'),
    ('ell', (-0.44, -0.34, 0.30), (0.04, 0.12, 0.035), 'impulse'),
]

V_CAM = norm((0.62, -1.0, 0.62))         # zur Kamera: vorn, steuerbord, oben
D_RAY = v_mul(V_CAM, -1)
RIGHT = norm(cross(D_RAY, (0, 0, 1)))
if RIGHT[0] < 0:
    RIGHT = v_mul(RIGHT, -1)
UP = norm(cross(RIGHT, D_RAY))
if UP[2] < 0:
    UP = v_mul(UP, -1)
LIGHT = norm((0.5, -0.55, 0.8))
HALF = norm(v_add(LIGHT, V_CAM))


def hit_ell(ro, c, s):
    o = ((ro[0] - c[0]) / s[0], (ro[1] - c[1]) / s[1], (ro[2] - c[2]) / s[2])
    d = (D_RAY[0] / s[0], D_RAY[1] / s[1], D_RAY[2] / s[2])
    a, b, cc = dot(d, d), dot(o, d), dot(o, o) - 1
    h = b * b - a * cc
    if h < 0:
        return None
    return (-b - math.sqrt(h)) / a


def hit_cap(ro, pa, pb, r):
    rd = D_RAY
    ba, oa = v_sub(pb, pa), v_sub(ro, pa)
    baba, bard, baoa = dot(ba, ba), dot(ba, rd), dot(ba, oa)
    rdoa, oaoa = dot(rd, oa), dot(oa, oa)
    a = baba - bard * bard
    if a < 1e-9:
        return None
    b = baba * rdoa - baoa * bard
    c = baba * oaoa - baoa * baoa - r * r * baba
    h = b * b - a * c
    if h < 0:
        return None
    t = (-b - math.sqrt(h)) / a
    y = baoa + t * bard
    if 0 < y < baba:
        return t
    oc = oa if y <= 0 else v_sub(ro, pb)
    b, c = dot(rd, oc), dot(oc, oc) - r * r
    h = b * b - c
    return -b - math.sqrt(h) if h > 0 else None


def normal_of(p, prim):
    if prim[0] == 'ell':
        c, s = prim[1], prim[2]
        return norm(((p[0] - c[0]) / s[0] ** 2, (p[1] - c[1]) / s[1] ** 2, (p[2] - c[2]) / s[2] ** 2))
    pa, pb, r = prim[1], prim[2], prim[3]
    ba = v_sub(pb, pa)
    k = max(0.0, min(1.0, dot(v_sub(p, pa), ba) / dot(ba, ba)))
    return norm(v_sub(p, v_add(pa, v_mul(ba, k))))


def uv_bounds(prim):
    if prim[0] == 'ell':
        c, s = prim[1], prim[2]
        hu = math.sqrt(sum((s[i] * RIGHT[i]) ** 2 for i in range(3)))
        hv = math.sqrt(sum((s[i] * UP[i]) ** 2 for i in range(3)))
        return dot(c, RIGHT) - hu, dot(c, RIGHT) + hu, dot(c, UP) - hv, dot(c, UP) + hv
    pa, pb, r = prim[1], prim[2], prim[3]
    us, vs = (dot(pa, RIGHT), dot(pb, RIGHT)), (dot(pa, UP), dot(pb, UP))
    return min(us) - r, max(us) + r, min(vs) - r, max(vs) + r


HULL_RGB = (196, 204, 218)


def shade(p, n, prim):
    """(Material, Farbe) fuer einen Treffer; Farbe nur fuer den Rumpf fest."""
    kind = prim[-1]
    lam = max(0.0, dot(n, LIGHT))
    spec = max(0.0, dot(n, HALF)) ** 28
    rim = (1 - abs(dot(n, V_CAM))) ** 3
    if kind == 'bussard':
        return BUSSARD, lam
    if kind == 'deflector':
        return DEFLECTOR, lam
    if kind == 'impulse':
        return IMPULSE, lam
    if kind == 'nacelle' and n[2] > 0.3 and prim[1][0] + 0.15 < p[0] < prim[2][0] - 0.05:
        return GRILLE, lam
    if kind == 'saucer':
        q = ((p[0] - prim[1][0]) / prim[2][0], (p[1] - prim[1][1]) / prim[2][1], (p[2] - prim[1][2]) / prim[2][2])
        ang = math.atan2(q[1], q[0])
        if abs(q[2] - 0.15) < 0.16 and int((ang + math.pi) * 34) % 3 == 0:
            return WINDOW, lam
        if abs(q[2] + 0.25) < 0.12 and int((ang + math.pi) * 28) % 4 == 0:
            return WINDOW, lam
    if kind == 'eng' and abs(p[2] + 0.12) < 0.03 and int(p[0] * 18) % 3 == 0:
        return WINDOW, lam
    # Rumpf: Licht, Glanz, Plattenmuster (Aztec), blaues Gegenlicht vom Raum
    cell = (int(math.floor(p[0] * 9)) * 73856093 ^ int(math.floor(p[1] * 9)) * 19349663) & 1023
    var = 0.93 + (cell / 1023) * 0.12
    k = (0.16 + 0.84 * lam) * var
    col = add(add((HULL_RGB[0] * k, HULL_RGB[1] * k, HULL_RGB[2] * k), (255, 250, 235), spec * 0.55),
              (70, 120, 255), rim * 0.45)
    return HULL, col


def render_ship(max_w, max_h, ss=2):
    """Strahlt das Modell einmal ab. Rueckgabe: Breite, Hoehe in Pixeln und je Abtastpunkt
    (Material, Wert) oder None; ss x ss Abtastpunkte je Pixel."""
    b = [uv_bounds(p) for p in PRIMS]
    umin, umax = min(x[0] for x in b), max(x[1] for x in b)
    vmin, vmax = min(x[2] for x in b), max(x[3] for x in b)
    ppu = min(max_w / (umax - umin), max_h / (vmax - vmin))
    w, h = int((umax - umin) * ppu) + 1, int((vmax - vmin) * ppu) + 1
    sw, sh = w * ss, h * ss
    step = 1.0 / (ppu * ss)
    best = [1e9] * (sw * sh)
    who = [-1] * (sw * sh)
    for k, (prim, (u0, u1, v0, v1)) in enumerate(zip(PRIMS, b)):
        i0, i1 = max(0, int((u0 - umin) / step)), min(sw, int((u1 - umin) / step) + 2)
        j0, j1 = max(0, int((vmax - v1) / step)), min(sh, int((vmax - v0) / step) + 2)
        for j in range(j0, j1):
            v = vmax - (j + 0.5) * step
            for i in range(i0, i1):
                u = umin + (i + 0.5) * step
                ro = v_add(v_add(v_mul(RIGHT, u), v_mul(UP, v)), v_mul(V_CAM, 10))
                t = hit_ell(ro, prim[1], prim[2]) if prim[0] == 'ell' else hit_cap(ro, prim[1], prim[2], prim[3])
                idx = j * sw + i
                if t is not None and t < best[idx]:
                    best[idx], who[idx] = t, k
    samples = [None] * (sw * sh)
    for j in range(sh):
        v = vmax - (j + 0.5) * step
        for i in range(sw):
            idx = j * sw + i
            if who[idx] < 0:
                continue
            u = umin + (i + 0.5) * step
            ro = v_add(v_add(v_mul(RIGHT, u), v_mul(UP, v)), v_mul(V_CAM, 10))
            p = v_add(ro, v_mul(D_RAY, best[idx]))
            prim = PRIMS[who[idx]]
            samples[idx] = shade(p, normal_of(p, prim), prim)
    return w, h, ss, samples


def material_color(s, glow, pulse):
    mat, val = s
    if mat == HULL:
        return val
    if mat == GRILLE:
        k = glow * (0.65 + 0.35 * val)
        return (int(60 * k + 20), int(140 * k + 30), int(255 * k))
    if mat == BUSSARD:
        k = 0.7 + 0.3 * pulse
        return (255, int(70 + 90 * pulse * glow), int(30 + 40 * pulse * glow)) if k else (200, 40, 30)
    if mat == DEFLECTOR:
        return (255, int(150 + 60 * glow), int(50 + 40 * glow))
    if mat == IMPULSE:
        return (255, int(60 + 40 * pulse), 50)
    return (255, 236, 180)


def ship_image(ship, sx, sy, glow, pulse):
    """Bild in Zielgroesse: Liste von Zeilen mit (Farbe, Deckung)."""
    w, h, ss, samples = ship
    sw = w * ss
    tw, th = max(1, int(w * sx)), max(1, int(h * sy))
    out = []
    for y in range(th):
        j0 = int(y * ss / sy)
        j1 = max(j0 + 1, int((y + 1) * ss / sy))
        row = []
        for x in range(tw):
            i0 = int(x * ss / sx)
            i1 = max(i0 + 1, int((x + 1) * ss / sx))
            r = g = b = n = tot = 0
            for j in range(j0, min(j1, h * ss)):
                base = j * sw
                for i in range(i0, min(i1, sw)):
                    tot += 1
                    s = samples[base + i]
                    if s is not None:
                        c = material_color(s, glow, pulse)
                        r += c[0]; g += c[1]; b += c[2]; n += 1
            row.append(((r // n, g // n, b // n), n / tot) if n else (None, 0.0))
        out.append(row)
    return out

# ---------------------------------------------------------------- Raum


def make_space(W, H):
    """Nebel und Planet in 24 Bit, dazu die Planetenmaske."""
    sky, mask = [], []
    pcx, pcy, pr = W * 0.10, H * 1.55, H * 0.95
    L = norm((0.75, -0.55, 0.45))
    for y in range(H):
        row, mrow = [], []
        for x in range(W):
            u, v = x / W, y / H
            n1 = math.sin(u * 5.1 + math.sin(v * 3.3) * 1.7) * 0.5 + 0.5
            n2 = math.sin(v * 6.3 - u * 2.2 + math.cos(u * 4.0) * 1.3) * 0.5 + 0.5
            n3 = math.sin((u + v) * 9.0 + n1 * 2.0) * 0.5 + 0.5
            neb = mix((6, 4, 18), (70, 18, 92), n1 * n2 * 0.9)
            neb = mix(neb, (12, 74, 98), (1 - n1) * n3 * 0.55)
            neb = mix(neb, (130, 40, 110), (n2 * n3) ** 3 * 0.6)
            dx, dy = (x - pcx) / pr, (y - pcy) / pr
            d = math.hypot(dx, dy)
            inside = d < 1.0
            if inside:
                nz = math.sqrt(max(0.0, 1 - d * d))
                lam = max(0.0, dx * L[0] + dy * L[1] + nz * L[2])
                band = math.sin(dy * 14 + math.sin(dx * 6) * 1.5) * 0.5 + 0.5
                surf = mix((18, 60, 120), (40, 140, 170), band * 0.6)
                surf = mix(surf, (230, 236, 245), max(0.0, band - 0.78) * 3.5)
                col = mix((2, 4, 12), surf, 0.08 + 0.92 * lam)
                col = add(col, (90, 170, 255), (1 - nz) ** 4 * 0.9 * (0.3 + lam))
                row.append(col)
            else:
                glow = max(0.0, 1 - (d - 1.0) * pr / 2.6)
                row.append(add(neb, (70, 150, 255), glow * glow * 0.8))
            mrow.append(inside)
        sky.append(row)
        mask.append(mrow)
    return sky, mask

# ---------------------------------------------------------------- Ablauf

F_LOADING, F_SWEEP0, F_SWEEP1, F_READY, F_RUN, F_WARP1, F_FLASH1, F_END = 28, 30, 60, 62, 88, 94, 99, 128


def speed_at(f):
    if f < 64:
        return 0.35
    if f < F_RUN:
        return 0.35 + (f - 64) / (F_RUN - 64) * 0.6
    if f < F_RUN + 4:
        return 1.0
    if f < 102:
        return 9.0
    return max(0.4, 9.0 - (f - 102) * 0.8)


class Panel:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.ship = render_ship(int(W * 0.86), int(H * 0.82))
        self.sky, self.mask = make_space(W, H)
        # vor dem Laden: C64-Blau und der Planet, kein Nebel
        self.c64sky = [[self.sky[y][x] if self.mask[y][x] else SCR for x in range(W)] for y in range(H)]
        rng = random.Random(1701)
        self.rng = rng
        self.stars = [[rng.uniform(0, W), rng.randrange(H), rng.choice((0.5, 0.8, 1.0, 1.5))]
                      for _ in range(max(14, W * H // 55))]

    def frame(self, f):
        W, H = self.W, self.H
        sweep = H * smooth((f - F_SWEEP0) / (F_SWEEP1 - F_SWEEP0)) if f >= F_SWEEP0 else -1
        # Hintergrund: oberhalb der Abtastzeile 24 Bit, darunter C64-Schwarz mit Planet
        buf = [list(self.sky[y]) if y < sweep else list(self.c64sky[y]) for y in range(H)]
        # Sterne
        v = speed_at(f)
        for s in self.stars:
            s[0] -= v * s[2]
            if s[0] < 0:
                s[0] += W
                s[1] = self.rng.randrange(H)
            x, y = int(s[0]), s[1]
            tint = (255, 255, 255) if s[2] >= 1 else (170, 190, 255)
            length = max(1, int(v * s[2] * 1.4)) if v > 1.2 else 1
            for k in range(length):
                xx = x + k
                if xx >= W or self.mask[y][xx]:
                    break
                fade = 1.0 - k / (length + 1) * 0.85 if length > 1 else (0.55 + 0.45 * s[2] / 1.5)
                buf[y][xx] = add(buf[y][xx], tint, fade)
        # Schiff
        st = self.ship_state(f)
        if st:
            sx, sy, ox, oy, glow, pulse, trail = st
            img = ship_image(self.ship, sx, sy, glow, pulse)
            th = len(img)
            if trail:
                for row_off, col in ((0.42, (90, 160, 255)), (0.50, (150, 210, 255))):
                    yy = int(oy + th * row_off)
                    if 0 <= yy < H:
                        for xx in range(0, max(0, min(W, int(ox)))):
                            t = xx / max(1, ox)
                            buf[yy][xx] = add(buf[yy][xx], mix((20, 30, 120), col, t), trail * (0.3 + 0.7 * t))
            for y, row in enumerate(img):
                yy = int(oy) + y
                if not 0 <= yy < H:
                    continue
                for x, (c, a) in enumerate(row):
                    xx = int(ox) + x
                    if c is None or not 0 <= xx < W:
                        continue
                    buf[yy][xx] = mix(buf[yy][xx], c, a)
        # Warp-Blitz: Licht, das es auf dem C64 nie gab
        if F_WARP1 <= f < F_FLASH1 + 2:
            t = (f - F_WARP1) / (F_FLASH1 + 2 - F_WARP1)
            cx, cy = W - 4, int(H * 0.45)
            R, inten = 4 + t * W * 0.3, 1.6 * (1 - t) ** 1.3
            for y in range(H):
                for x in range(W):
                    d = math.hypot((x - cx) * 0.7, (y - cy) * 1.4)
                    k = max(0.0, 1 - d / R) ** 2 * inten
                    if abs(y - cy) <= 1:
                        k += (1 - abs(x - cx) / W) * inten * (0.9 if y == cy else 0.4)
                    if k > 0.01:
                        buf[y][x] = add(buf[y][x], (170, 210, 255), k * 1.4)
        # C64-Teil unterhalb der Abtastzeile: doppelt breite Pixel, VIC-Palette, Raster
        for y in range(H):
            if y < sweep:
                continue
            row = buf[y]
            for x in range(0, W, 2):
                q = quantize(row[x], x, y)
                row[x] = q
                if x + 1 < W:
                    row[x + 1] = q
        # die Abtastzeile selbst
        if 0 <= sweep < H:
            y = int(sweep)
            for x in range(W):
                buf[y][x] = mix((255, 255, 255), (120, 220, 255), x / W)
        return buf

    def ship_state(self, f):
        W, H = self.W, self.H
        w, h = self.ship[0], self.ship[1]
        cx, cy = (W - w) / 2, (H - h) / 2
        pulse = 0.5 + 0.5 * math.sin(f * 0.5)
        if f < F_READY:
            return 1.0, 1.0, cx - 2 + f / 24, cy, 0.45, pulse, 0
        if f < F_RUN:
            t = smooth((f - F_READY) / (F_RUN - F_READY))
            s = 1.0 - 0.55 * t
            return s, s, cx + w * (1 - s) * 0.65 + 1, cy + h * (1 - s) * 0.35, 0.45 + 0.55 * t, pulse, 0
        if f < F_WARP1:
            t = (f - F_RUN) / (F_WARP1 - F_RUN)
            s = 0.45
            x0, y0 = cx + w * 0.55 * 0.65 + 1, cy + h * 0.2
            if t < 0.67:
                k = 1 + 1.3 * (t / 0.67) ** 2
                return s * k, s * (1 - 0.15 * t), x0 - w * s * (k - 1) * 0.7, y0 + h * s * 0.05 * t, 1.0, 1.0, t / 0.67
            u = (t - 0.67) / 0.33
            return s * (2.3 + 4 * u), s * 0.8, x0 - w * s * 0.9 + u * u * W * 1.3, y0 + h * s * 0.05, 1.0, 1.0, 1.0
        return None


def paint_cells(buf, top, left):
    out = []
    for r in range(0, len(buf) - 1, 2):
        out.append(at(top + r // 2, left))
        last = None
        for a, b in zip(buf[r], buf[r + 1]):
            if (a, b) != last:
                out.append(f'\033[38;2;{a[0]};{a[1]};{a[2]};48;2;{b[0]};{b[1]};{b[2]}m')
                last = (a, b)
            out.append('▀')
    return ''.join(out) + RESET


def raster_border(cols, rows, f):
    """Ladebalken im Rahmen, wie beim Schnelllader."""
    rng = random.Random(f * 7919)
    out = []
    for r in range(1, rows + 1):
        c = VIC[rng.choice((1, 2, 3, 4, 5, 6, 7, 8, 10, 13, 14))] if rng.random() < 0.8 else SCR
        if r <= boot.BORDER_ROWS or r > rows - boot.BORDER_ROWS:
            out.append(at(r, 1) + bg(c) + ' ' * cols)
        else:
            out.append(at(r, 1) + bg(c) + ' ' * boot.BORDER_COLS + at(r, cols - boot.BORDER_COLS + 1) + ' ' * boot.BORDER_COLS)
    return ''.join(out) + RESET


def plain_border(cols, rows):
    out = []
    for r in range(1, rows + 1):
        if r <= boot.BORDER_ROWS or r > rows - boot.BORDER_ROWS:
            out.append(at(r, 1) + boot.BORDER_BG + ' ' * cols)
        else:
            out.append(at(r, 1) + boot.BORDER_BG + ' ' * boot.BORDER_COLS + at(r, cols - boot.BORDER_COLS + 1) + ' ' * boot.BORDER_COLS)
    return ''.join(out) + RESET


def gradient_text(row, col, text, a, b, k):
    out = [at(row, col) + bg(SCR) + BOLD]
    n = max(1, len(text) - 1)
    for i, ch in enumerate(text):
        c = mix(a, b, i / n)
        out.append(fg(mix(SCR, c, k)) + ch)
    return ''.join(out) + RESET


def geometry(cols, rows):
    sl, sr, st = boot.BORDER_COLS + 1, cols - boot.BORDER_COLS, boot.BORDER_ROWS + 1
    banner_top = st + 4
    text_w = 21
    pl, pr = sl + text_w, sr - 8
    pt, pb = banner_top + 4, rows - boot.BORDER_ROWS - 1
    cl, cr = pl, pr
    ct, cb = pt, pb - 1
    return sl, sr, st, banner_top, text_w, pl, pr, pt, pb, cl, cr, ct, cb


def main():
    cols, rows = shutil.get_terminal_size((100, 30))
    apple = os.environ.get('TERM_PROGRAM') == 'Apple_Terminal'
    sl, sr, st, banner_top, text_w, pl, pr, pt, pb, cl, cr, ct, cb = geometry(cols, rows)
    W, H = cr - cl + 1, 2 * (cb - ct + 1)
    if W < 40 or H < 14:
        return 2
    panel = Panel(W, H)

    lines, typed = [], ''

    def script(f):
        nonlocal typed
        if f == 0:
            lines.append('READY.')
        if 6 <= f < 18:
            typed = 'LOAD "*",8,1'[:f - 5]
        if f == 18:
            lines.extend([typed, '']); typed = ''
        if f == 22:
            lines.append('SEARCHING FOR *')
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
    f = 0
    try:
        while True:
            t0 = time.time()
            done = script(f)
            out = []
            if F_LOADING <= f < F_READY:
                out.append(raster_border(cols, rows, f))
            elif f == F_READY:
                out.append(plain_border(cols, rows))
            for i, line in enumerate(lines):
                out.append(at(pt + i, sl) + LB + SCREEN_BG + line.ljust(text_w - 1) + RESET)
            cursor = '█' if (f // 4) % 2 == 0 else ' '
            out.append(at(pt + len(lines), sl) + LB + SCREEN_BG + (typed + cursor).ljust(text_w - 1) + RESET)
            out.append(paint_cells(panel.frame(f), ct, cl))
            if f == 0:
                k = 1.0
                text = '"MAKE IT SO."'
                out.append(gradient_text(banner_top + 2, sl + text.center(sr - sl + 1).index(text), text, (255, 255, 255), (255, 200, 90), k))
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


def write_png(path, buf, scale=6):
    h, w = len(buf), len(buf[0])
    raw = bytearray()
    for y in range(h):
        line = bytearray([0])
        for x in range(w):
            line += bytes(buf[y][x]) * scale
        raw += bytes(line) * scale
    # Terminal-Pixel sind halbe Zellen, etwa quadratisch: gleiche Skala in beide Richtungen
    png = b'\x89PNG\r\n\x1a\n'
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', w * scale, h * scale, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b'')
    open(path, 'wb').write(png)


if __name__ == '__main__':
    if '--png' in sys.argv:
        i = sys.argv.index('--png')
        n, path = int(sys.argv[i + 1]), sys.argv[i + 2]
        cols, rows = 110, 34
        g = geometry(cols, rows)
        W, H = g[10] - g[9] + 1, 2 * (g[12] - g[11] + 1)
        t0 = time.time()
        p = Panel(W, H)
        print(f'render {time.time() - t0:.2f}s  {W}x{H}px  ship {p.ship[0]}x{p.ship[1]}')
        t1 = time.time()
        for f in range(n + 1):
            buf = p.frame(f)
        print(f'{(time.time() - t1) / (n + 1) * 1000:.0f} ms/Bild')
        write_png(path, buf)
    else:
        sys.exit(main() or 0)
