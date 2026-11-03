#!/usr/bin/env python3
"""Kopfleiste und Banner als eigenes Feld oben im Windows-Terminal-Tab (nur Windows-Fassung).

Auf macOS und Linux legt tmux Felder um Claude Code (frame.sh, boot.py --band und --banner).
Windows hat kein tmux; dort teilt LOAD den Tab mit `wt split-pane` in dieselben Felder: oben
dieses Feld, links, rechts und unten je ein schmales Randfeld, in der Mitte Claude Code. Oben
steht wie im tmux-Rahmen: drei Zeilen Kopfleiste (Logo, Himmel, zwei Krabben Hand in Hand), eine
Trennzeile in Rahmenfarbe, vier Zeilen Banner auf dem Bildschirmblau, wieder eine Trennzeile.

    head.py                 das Feld oben (C64_FRAME aus der Umgebung)
    head.py --fill <id>     ein Randfeld: nur Rahmenfarbe; Windows Terminal startet es selbst,
                            ohne die Umgebung von LOAD, darum die Kennung als Argument

Das Ende erkennt es an ~/.claude/retro-deck/<C64_FRAME>.pid: load.ps1 legt die Datei beim Start
von Claude Code an und loescht sie danach; der Mod erneuert daneben <C64_FRAME>.alive alle 15 s.
Fehlt die PID-Datei (nachdem sie da war) oder ist .alive laenger als 90 s alt, endet das Feld,
und LOAD kehrt oben zur Shell zurueck. /deck intro beruehrt party-<C64_FRAME> wie im tmux-Rahmen.
Den Tabtitel setzt es auf denselben wie unten ("C64 <Projekt> [pid]"), damit die Tafel den Tab
findet, gleich welches Feld gerade vorn ist.
"""
import os
import shutil
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402
from boot import (at, BOLD, BORDER_BG, BORDER_COLS, CLEAR, CRAB_W, CYCLE, FRAME_S, HIDE,  # noqa: E402
                  LB, LOGO_TEXT, PAIR_W, PARTY, RESET, SHOW, STAND_S, WALK, WHITE,
                  crab_rows, make_sky, mod_version, paint_pair, paint_sky,
                  party_file, party_stamp)

BAND_ROWS = 3
BANNER_TOP = BAND_ROWS + 2            # eine Trennzeile zwischen Kopfleiste und Banner
STALE_S = 90
# Colodore: Rahmenfarbe Hellblau auf ANSI 12, wie load.ps1 sie setzt. Ein Randfeld startet Windows
# Terminal mit seinem eigenen Farbschema; das Feld setzt sich die Farbe darum selbst.
LIGHT_BLUE = '70/6d/eb'
# Das Banner fest im Bildschirmblau: das Feld oben stellt seinen Grund auf Rahmenfarbe, damit auch
# der Innenabstand von Windows Terminal hellblau ist und keine dunkle Kante unter der Trennzeile bleibt.
SCREEN = '\033[48;2;46;44;155m'
EYE_BG = '\033[48;2;0;0;0m'


def paint_crab(rows, top, left, bg=boot.SCREEN_BG):
    """Wie boot.paint_crab, aber mit schwarzen Augen wie auf dem Mac. Dort zeichnet boot.py die
    Krabbe fuer Terminal.app mit ausgesparten Augen auf Krabbenfarbe; hier sind die Augen die Luecken
    in den Blockzeichen der Kopfzeile, die sonst den Grund durchscheinen lassen: Hellblau."""
    out = []
    for i, row in enumerate(rows):
        out.append(at(top + i, left))
        for text, cut in row:
            if cut:
                out.append(boot.BLACK + boot.LRED_BG + text)
                continue
            for j, ch in enumerate(text):     # Kopfzeile: Spalte 1 ist der Arm, ab 2 die Augenpartie
                out.append(boot.LRED + (EYE_BG if i == 0 and 2 <= j <= 7 and ch in '▛▟' else bg) + ch)
        out.append(RESET + bg)
    return ''.join(out)


boot.paint_crab = paint_crab                  # auch fuer paint_pair, die Krabben Hand in Hand


def frame_id():
    if '--fill' in sys.argv:
        i = sys.argv.index('--fill')
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return os.environ.get('C64_FRAME', '')


def frame_files():
    sock = frame_id()
    base = os.path.join(os.path.expanduser('~'), '.claude', 'retro-deck', sock)
    return base + '.pid', base + '.alive'


def banner_rows(cols, top, rows):
    """Das Banner ab Zeile `top`, hoechstens bis Zeile `rows`; die ersten zwei Zeilen mittig."""
    ver = mod_version()
    lines = ['proudly presented by Alf', f'**** CLAUDE CODE RETRO DECK {ver} ****'.replace('  ', ' '),
             '64K RAM SYSTEM  38911 BASIC BYTES FREE', 'READY.']
    margin = ' ' * BORDER_COLS
    inner = max(1, cols - 2 * BORDER_COLS)
    out = []
    for i, line in enumerate(lines):
        r = top + i
        if r > rows:
            break
        text = (line.center(inner) if i < 2 else (' ' + line).ljust(inner))[:inner]
        out.append(at(r, 1) + BORDER_BG + margin + SCREEN + (BOLD if i == 1 else '') + LB + text + RESET
                   + BORDER_BG + margin + RESET)
    return ''.join(out)


def session_over(pid_path, alive_path, state):
    """True, wenn die Sitzung unten endete; setzt beim ersten Mal den Tabtitel wie unten."""
    if os.path.exists(pid_path):
        state['seen'] = True
        if not state['titled']:
            try:
                pid = open(pid_path).read().strip()
                parts = [p for p in os.getcwd().replace('\\', '/').split('/') if p]
                project = next((p for p in parts if p[:3].isdigit() and p[3:4] == '-'), parts[-1] if parts else 'claude')
                sys.stdout.write(f'\033]0;C64 {project} [{pid}]\007')
                state['titled'] = True
            except OSError:
                pass
    elif state['seen'] or time.time() - state['started'] > 120:
        return True
    try:
        return time.time() - os.stat(alive_path).st_mtime > STALE_S
    except OSError:
        return False


def fill():
    """Ein Randfeld: ganz in Rahmenfarbe, bis die Sitzung endet."""
    write = sys.stdout.write
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    pid_path, alive_path = frame_files()
    state = {'seen': False, 'titled': False, 'started': time.time()}
    write(f'\033]4;12;rgb:{LIGHT_BLUE}\007\033]11;rgb:{LIGHT_BLUE}\007' + HIDE)
    last = None
    try:
        while not session_over(pid_path, alive_path, state):
            cols, rows = shutil.get_terminal_size((3, 1))
            if (cols, rows) != last:
                write(CLEAR + ''.join(at(r, 1) + BORDER_BG + ' ' * cols for r in range(1, rows + 1)) + RESET)
                sys.stdout.flush()
                last = (cols, rows)
            time.sleep(0.5)
    except (KeyboardInterrupt, SystemExit, BrokenPipeError):
        pass


def main():
    write = sys.stdout.write
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    pid_path, alive_path = frame_files()
    state = {'seen': False, 'titled': False, 'started': time.time()}
    logo_col = BORDER_COLS + 1
    text_col = logo_col + CRAB_W + 2
    dance_left = text_col + max(len(t) for t in LOGO_TEXT) + 3
    pfile = party_file()
    seen_party = party_stamp(pfile)

    x, frame, direction = dance_left, 0, 1
    standing = 0
    party = False
    sky_span, stars, labels = -1, [], []
    last_size = None
    write(f'\033]11;rgb:{LIGHT_BLUE}\007' + HIDE + CLEAR)
    try:
        while True:
            if session_over(pid_path, alive_path, state):
                break

            stamp = party_stamp(pfile)
            if stamp != seen_party:
                seen_party, party, frame = stamp, True, 0
                if standing:
                    standing = 0
                    direction = -direction
            cols, rows = shutil.get_terminal_size((80, 7))
            dance_right = max(dance_left, cols - BORDER_COLS - PAIR_W + 1)
            span = dance_right - dance_left + PAIR_W
            if span != sky_span:
                stars, labels = make_sky(span)
                sky_span = span
            x = max(dance_left, min(x, dance_right))
            out = ''.join(at(r, 1) + BORDER_BG + ' ' * cols + RESET for r in range(1, BAND_ROWS + 1))
            out += (paint_crab(crab_rows(False, 1, 0, logo=True), 1, logo_col, BORDER_BG)
                    + at(1, text_col) + WHITE + BOLD + BORDER_BG + LOGO_TEXT[0] + RESET
                    + at(2, text_col) + WHITE + BORDER_BG + LOGO_TEXT[1] + RESET)
            out += paint_sky(frame, 1, dance_left, span, stars, labels, bg=BORDER_BG, star=WHITE, dim=WHITE)
            if party:
                out += ''.join(at(1 + r, dance_left + c) + PARTY[(frame // 2 + i) % len(PARTY)] + BOLD + BORDER_BG
                               + '✦ ' + name + RESET for i, (r, c, name) in enumerate(labels))
            if standing:
                out += paint_pair(False, direction, 0, 1, x, BORDER_BG, standing=True)
                standing -= 1
                if standing == 0:
                    direction = -direction
                pause = 0.25
            else:
                out += paint_pair(False, direction, frame, 1, x, BORDER_BG)
                target = dance_right if direction == 1 else dance_left
                if frame % CYCLE < WALK and x != target:
                    x += direction
                if x == target and frame % CYCLE == CYCLE - 1:
                    standing = STAND_S * 4
                    party = False
                pause = FRAME_S
            if (cols, rows) != last_size:
                # Trennzeile, Banner, Trennzeile; was darunter an Zeilen uebrig ist, in Rahmenfarbe.
                rest = ''.join(at(r, 1) + BORDER_BG + ' ' * cols + RESET
                               for r in [BAND_ROWS + 1] + list(range(BANNER_TOP + 4, rows + 1)))
                out = CLEAR + out + rest + banner_rows(cols, BANNER_TOP, rows)
                last_size = (cols, rows)
            write(out)
            sys.stdout.flush()
            frame += 1
            time.sleep(pause)
    except (KeyboardInterrupt, SystemExit, BrokenPipeError):
        pass
    finally:
        try:
            write(RESET + CLEAR + at(1, 1) + SHOW)
            sys.stdout.flush()
        except Exception:
            pass


if __name__ == '__main__':
    fill() if '--fill' in sys.argv else main()
