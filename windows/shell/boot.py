#!/usr/bin/env python3
"""C64-Einschaltbildschirm in voller Terminalgroesse, mit tanzender Krabbe neben dem Logo.

Wird von `LOAD "*",8,1` (load.zsh) vor dem Start von Claude Code aufgerufen. Zeichnet
Rahmen und Bildschirm in den 16 ANSI-Farben, die das Terminal-Profil "C64" auf die
VIC-II-Palette legt: heller Rahmen (ANSI 12, hellblau), dunkler Bildschirm (Grundfarbe
des Profils), hellblaue Schrift, hellrote Krabbe. Ohne das Profil bleibt es ein blauer
Rahmen auf dem Grund des Terminals.

Die Krabbe ist dieselbe wie im Band des Mods (hooks/register.tsx, `crabSprite`): 9x3,
zwoelf Schrittbilder und vier Bilder Huepfer je Zyklus; auf Apple Terminal die Band-Form.

    boot.py            Animation, etwa fuenf Sekunden, dann Rueckkehr
    boot.py --band     die Kopfleiste oben im tmux-Rahmen (frame.sh): Logo, Sternenhimmel der
                       Werkzeuge und Firmen, zwei Krabben Hand in Hand tanzen hinueber, stehen
                       eine Minute, tanzen zurueck; `/deck intro` schickt sie sofort los
    boot.py --banner   das Einschalt-Banner darunter, vier Zeilen dunkelblau im Rahmen
    boot.py --test     ein paar Bilder ohne Wartezeit und ohne Bildschirmwechsel
"""
import signal
import os
import shutil
import sys
import time

FRAME_S = 0.09
CRAB_W = 9
CYCLE, WALK = 16, 12

# ANSI, so dass das Profil "C64" die Farbe bestimmt.
BORDER_BG = '\033[104m'
SCREEN_BG = '\033[49m'
LB, WHITE, LRED, YEL, LGREEN, CYAN = '\033[94m', '\033[97m', '\033[91m', '\033[93m', '\033[92m', '\033[96m'
BLACK = '\033[30m'
LRED_BG = '\033[101m'
BOLD, RESET = '\033[1m', '\033[0m'
HIDE, SHOW = '\033[?25l', '\033[?25h'
ALT_ON, ALT_OFF = '\033[?1049h', '\033[?1049l'
CLEAR = '\033[2J'

BORDER_ROWS, BORDER_COLS = 2, 4

LOGO_TEXT = ['CLAUDE CODE', 'retro deck']
BANNER = ['**** CLAUDE CODE 64 BASIC V2 ****', '64K RAM SYSTEM  38911 BASIC BYTES FREE']

# ADHs Werkzeuge als Sterne am Himmel; n8n zuerst, also dicht beim Logo.
TOOLS = ['n8n', 'Odoo', 'Supabase', 'FLEXbyte', 'Lovable', 'ElevenLabs', 'Flexcon IT', 'Starface', 'Ultipa']


def make_sky(span, seed=64):
    """Feste Sternpositionen (3 Zeilen) und je ein beschrifteter Stern pro Werkzeug."""
    import random
    rng = random.Random(seed)
    stars = [(rng.randrange(3), rng.randrange(max(1, span)), rng.randrange(3)) for _ in range(max(6, span // 4))]
    labels = []
    for i, tool in enumerate(TOOLS):
        col = int(span * (i + 0.3) / len(TOOLS))
        if col + len(tool) + 2 <= span:
            labels.append((i % 3, col, tool))
    # das n8n-Sternbild: drei Sterne um die erste Marke
    if labels:
        r, c, _ = labels[0]
        stars += [((r + 1) % 3, c + 1, 1), ((r + 2) % 3, c + 4, 2), (r, c + 6 + len('n8n'), 0)]
    return stars, labels


def paint_sky(frame, top, left, span, stars, labels, bg=SCREEN_BG, star=LB, dim=LB):
    out = [at(top + r, left) + bg + ' ' * span for r in range(3)]
    for r, c, k in stars:
        if c >= span:
            continue
        glyph = '·✦*'[(k + frame // 6) % 3] if (frame // 5 + k) % 4 else ' '
        out.append(at(top + r, left + c) + star + bg + glyph)
    for r, c, name in labels:
        bright = (frame // 7 + r) % 3 == 0
        out.append(at(top + r, left + c) + (YEL if bright else dim) + bg + ('✦ ' if bright else '· ') + name)
    return ''.join(out) + RESET


def at(row, col):
    return f'\033[{row};{col}H'


def crab_rows(apple, direction, frame, logo=False):
    """Drei Zeilen aus Segmenten (text, cut); cut = Bildschirmfarbe auf Krabbenfarbe."""
    if logo:                                      # stehend, Augen offen, beide Fuesse
        if apple:
            return [[('▗', False), (' ▗   ▖ ', True), ('▖', False)],
                    [(' ', False), ('       ', True), (' ', False)],
                    [(' ▘▘   ▝▝ ', False)]]
        return [[(' ▐▛███▛█ ', False)], [('▝▜██████▀', False)], [(' ▝▝   ▝▝ ', False)]]
    phase = frame % CYCLE
    walking = phase < WALK
    step_left = (phase // 2) % 2 == 0
    up = phase % 2 == 0
    feet = (' ▘▘      ' if step_left else '      ▝▝ ') if walking else ' ▘▘   ▝▝ '
    if apple:
        eyes = (' ▝   ▝ ' if direction == 1 else ' ▘   ▘ ') if walking else (' ▂   ▂ ' if up else ' ▗   ▂ ')
        return [[('▗', False), (eyes, True), ('▖', False)],
                [(' ', False), ('       ', True), (' ', False)],
                [(feet, False)]]
    eyes = ('█▟███▟' if direction == 1 else '▟███▟█') if walking else '▛███▛█'
    arms_up = not walking and up
    return [[(f'▗▟{eyes}▄' if arms_up else f' ▐{eyes} ', False)],
            [(' ▜██████▘' if arms_up else '▝▜██████▀', False)],
            [(feet, False)]]


def paint_crab(rows, top, left, bg=SCREEN_BG):
    out = []
    for i, row in enumerate(rows):
        out.append(at(top + i, left))
        for text, cut in row:
            out.append((BLACK + LRED_BG if cut else LRED + bg) + text)
        out.append(RESET + bg)
    return ''.join(out)


def frame_border(cols, rows):
    out = [CLEAR]
    blank = ' ' * cols
    for r in range(1, rows + 1):
        if r <= BORDER_ROWS or r > rows - BORDER_ROWS:
            out.append(at(r, 1) + BORDER_BG + blank + RESET)
        else:
            out.append(at(r, 1) + BORDER_BG + ' ' * BORDER_COLS + SCREEN_BG + ' ' * (cols - 2 * BORDER_COLS)
                       + BORDER_BG + ' ' * BORDER_COLS + RESET)
    return ''.join(out)


def run(test=False):
    cols, rows = shutil.get_terminal_size((100, 30))
    if test:
        cols, rows = 100, 30
    apple = os.environ.get('TERM_PROGRAM') == 'Apple_Terminal'
    screen_left = BORDER_COLS + 1
    screen_right = cols - BORDER_COLS            # letzte Spalte des Bildschirms
    screen_top = BORDER_ROWS + 1
    width = screen_right - screen_left + 1

    # Logo links oben: statische Krabbe plus Wortmarke; die tanzende Krabbe rechts daneben.
    logo_col = screen_left + 1
    text_col = logo_col + CRAB_W + 2
    dance_left = text_col + max(len(t) for t in LOGO_TEXT) + 3
    dance_right = max(dance_left, screen_right - CRAB_W)
    span = dance_right - dance_left + CRAB_W
    stars, labels = make_sky(span)
    banner_top = screen_top + 4

    lines = []                   # was unter dem Banner steht, Zeile fuer Zeile
    typed = ''                   # die Zeile, die gerade "getippt" wird

    def paint_text_area():
        out = []
        for i, line in enumerate(BANNER):
            out.append(at(banner_top + i, screen_left) + LB + SCREEN_BG + line.center(width) + RESET)
        for i, line in enumerate(lines):
            out.append(at(banner_top + 3 + i, screen_left) + LB + SCREEN_BG + line.ljust(width) + RESET)
        return ''.join(out)

    # Drehbuch: (ab Bild, Aktion)
    def script(frame):
        nonlocal typed
        if frame == 0:
            lines.append('READY.')
        if 8 <= frame < 8 + len('LOAD "*",8,1'):
            typed = 'LOAD "*",8,1'[:frame - 7]
        if frame == 8 + len('LOAD "*",8,1'):
            lines.extend([typed, '']); typed = ''
        if frame == 26:
            lines.append('SEARCHING FOR *')
        if frame == 32:
            lines.append('LOADING')
        if frame == 44:
            lines.append('READY.')
        if 48 <= frame < 51:
            typed = 'RUN'[:frame - 47]
        if frame == 51:
            lines.append(typed); typed = ''
        return frame >= 56

    write = sys.stdout.write
    if not test:
        write(ALT_ON + HIDE)
    write(frame_border(cols, rows))
    static = crab_rows(apple, 1, 0, logo=True)   # das stehende Logo
    write(paint_crab(static, screen_top, logo_col))
    write(at(screen_top, text_col) + WHITE + BOLD + SCREEN_BG + LOGO_TEXT[0] + RESET)
    write(at(screen_top + 1, text_col) + LB + SCREEN_BG + LOGO_TEXT[1] + RESET)

    x, direction, frame = dance_left, 1, 0
    last = 0
    try:
        while True:
            done = script(frame)
            dancer = crab_rows(apple, direction, frame)
            write(paint_sky(frame, screen_top, dance_left, span, stars, labels))
            write(paint_crab(dancer, screen_top, x))
            write(paint_text_area())
            cursor = '█' if (frame // 4) % 2 == 0 else ' '
            write(at(banner_top + 3 + len(lines), screen_left) + LB + SCREEN_BG + (typed + cursor).ljust(width) + RESET)
            sys.stdout.flush()
            if done:
                break
            if frame % CYCLE < WALK:
                x += direction
                if x >= dance_right:
                    x, direction = dance_right, -1
                if x <= dance_left:
                    x, direction = dance_left, 1
            frame += 1
            if test and frame > 12:
                break
            if not test:
                time.sleep(FRAME_S)
    except KeyboardInterrupt:
        pass
    finally:
        if not test:
            write(SHOW + ALT_OFF)
        sys.stdout.flush()


STAND_S = 60


def mod_version():
    """V<major>.<minor> aus plugin.json, damit das Banner der Leiste nie veraltet. Die Kopie unter
    ~/.claude/retro-deck/shell/ (von /deck setup) traegt die Version in .version daneben."""
    import json
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        v = open(os.path.join(here, '.version')).read().strip()
    except Exception:
        try:
            v = json.load(open(os.path.join(here, '..', '.claude-plugin', 'plugin.json')))['version']
        except Exception:
            return ''
    return 'V' + '.'.join(v.split('.')[:2]) if v else ''


HAND_GAP = 3                          # Spalten zwischen den Krabben, dort halten sie sich
PAIR_W = 2 * CRAB_W + HAND_GAP
# Arm, Haende, Arm: die Verdickung in der Mitte sind die beiden gefassten Haende.
HANDS = '━' * ((HAND_GAP + 1) // 2) + '●' + '━' * ((HAND_GAP + 1) // 2)
PARTY = [YEL, LGREEN, CYAN, WHITE, LRED]


def paint_pair(apple, direction, frame, top, left, bg, standing=False):
    """Zwei Krabben Hand in Hand: die rechte setzt den Schritt versetzt, in der mittleren
    Zeile verbindet ein hellroter Arm die beiden, in der Mitte die gefassten Haende."""
    if standing:
        a = b = crab_rows(apple, direction, 0, logo=True)
    else:
        a, b = crab_rows(apple, direction, frame), crab_rows(apple, direction, frame + 2)
    return (paint_crab(a, top, left, bg) + paint_crab(b, top, left + CRAB_W + HAND_GAP, bg)
            + at(top + 1, left + CRAB_W - 1) + LRED + bg + HANDS + RESET)


def party_file():
    sock = os.environ.get('C64_FRAME', '')
    if not sock or sock == '1':
        return None
    return os.path.join(os.path.expanduser('~'), '.claude', 'retro-deck', f'party-{sock}')


def party_stamp(path):
    try:
        return os.stat(path).st_mtime if path else 0
    except OSError:
        return 0


def band():
    """Die Kopfleiste im tmux-Rahmen, drei Zeilen hellblau wie das Intro des Mods: links das
    Logo (stehende Krabbe, Wortmarke), daneben der Sternenhimmel aus ADHs Werkzeugen und
    Firmen, und zwei Krabben Hand in Hand, die hinueberlaufen, eine Minute stehen und
    zurueckkommen. Die Sterne funkeln auch im Stand; dafuer zeichnet die Leiste dann viermal
    je Sekunde. Beruehrt `/deck intro` die Party-Datei, laufen die Krabben sofort los, und
    die Namen am Himmel blinken bunt, bis sie drueben sind.
    """
    apple = os.environ.get('TERM_PROGRAM') == 'Apple_Terminal'
    write = sys.stdout.write
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    logo_col = BORDER_COLS + 1
    text_col = logo_col + CRAB_W + 2
    dance_left = text_col + max(len(t) for t in LOGO_TEXT) + 3
    pfile = party_file()
    seen = party_stamp(pfile)

    def size():
        return shutil.get_terminal_size((80, 3))

    def logo():
        return (paint_crab(crab_rows(apple, 1, 0, logo=True), 1, logo_col, BORDER_BG)
                + at(1, text_col) + WHITE + BOLD + BORDER_BG + LOGO_TEXT[0] + RESET
                + at(2, text_col) + WHITE + BORDER_BG + LOGO_TEXT[1] + RESET)

    def party_labels(frame, labels):
        return ''.join(at(1 + r, dance_left + c) + PARTY[(frame // 2 + i) % len(PARTY)] + BOLD + BORDER_BG
                       + '✦ ' + name + RESET for i, (r, c, name) in enumerate(labels))

    x, frame, direction = dance_left, 0, 1
    standing = 0                      # Takte, die die Krabben noch stehen
    party = False
    sky_span, stars, labels = -1, [], []
    write(HIDE)
    try:
        while True:
            stamp = party_stamp(pfile)
            if stamp != seen:
                seen, party, frame = stamp, True, 0
                if standing:
                    standing = 0
                    direction = -direction
            cols, rows = size()
            dance_right = max(dance_left, cols - BORDER_COLS - PAIR_W + 1)
            span = dance_right - dance_left + PAIR_W
            if span != sky_span:
                stars, labels = make_sky(span)
                sky_span = span
            x = max(dance_left, min(x, dance_right))
            out = ''.join(at(r, 1) + BORDER_BG + ' ' * cols + RESET for r in (1, 2, 3)) + logo()
            out += paint_sky(frame, 1, dance_left, span, stars, labels, bg=BORDER_BG, star=WHITE, dim=WHITE)
            if party:
                out += party_labels(frame, labels)
            if standing:
                out += paint_pair(apple, direction, 0, 1, x, BORDER_BG, standing=True)
                standing -= 1
                if standing == 0:
                    direction = -direction
                pause = 0.25
            else:
                out += paint_pair(apple, direction, frame, 1, x, BORDER_BG)
                target = dance_right if direction == 1 else dance_left
                if frame % CYCLE < WALK and x != target:
                    x += direction
                if x == target and frame % CYCLE == CYCLE - 1:
                    standing = STAND_S * 4
                    party = False
                pause = FRAME_S
            write(out)
            sys.stdout.flush()
            frame += 1
            time.sleep(pause)
    except (KeyboardInterrupt, SystemExit, BrokenPipeError):
        pass
    finally:
        try:
            write(SHOW)
            sys.stdout.flush()
        except Exception:
            pass


def banner():
    """Das Einschalt-Banner als Feld im tmux-Rahmen: vier Zeilen auf dem Grund des Profils
    (dunkelblau), links und rechts Rahmenfarbe, hellblaue Schrift wie im Mod. Ueber dem Titel
    die Widmung, beide mittig.
    Neu gezeichnet, wenn sich die Breite aendert; sonst schlaeft es."""
    write = sys.stdout.write
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    ver = mod_version()
    lines = ['proudly presented by Alf', f'**** CLAUDE CODE RETRO DECK {ver} ****'.replace('  ', ' '),
             '64K RAM SYSTEM  38911 BASIC BYTES FREE', 'READY.']
    centered = 2                              # die ersten zwei Zeilen stehen mittig

    def paint(cols):
        margin = ' ' * BORDER_COLS            # so breit wie der Rand neben dem Bildschirm
        inner = max(1, cols - 2 * BORDER_COLS)
        out = [CLEAR]
        for i, line in enumerate(lines):
            text = (line.center(inner) if i < centered else (' ' + line).ljust(inner))[:inner]
            out.append(at(i + 1, 1) + BORDER_BG + margin + SCREEN_BG + (BOLD if i == 1 else '') + LB + text + RESET
                       + BORDER_BG + margin + RESET)
        return ''.join(out)

    write(HIDE)
    last = None
    try:
        while True:
            cols = shutil.get_terminal_size((80, 4)).columns
            if cols != last:
                write(paint(cols))
                sys.stdout.flush()
                last = cols
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit, BrokenPipeError):
        pass
    finally:
        try:
            write(SHOW)
            sys.stdout.flush()
        except Exception:
            pass


if __name__ == '__main__':
    if '--band' in sys.argv:
        band()
    elif '--banner' in sys.argv:
        banner()
    else:
        run(test='--test' in sys.argv)
