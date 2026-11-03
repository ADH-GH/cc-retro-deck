#!/usr/bin/env python3
"""Kopfleiste und Banner als eigenes Feld oben im Windows-Terminal-Tab (nur Windows-Fassung).

Auf macOS und Linux legt tmux Felder um Claude Code (frame.sh, boot.py --band und --banner).
Windows hat kein tmux; dort teilt LOAD den Tab mit `wt split-pane`: oben dieses Feld, darunter
Claude Code. Es zeichnet dasselbe wie die beiden tmux-Felder zusammen: drei Zeilen Kopfleiste
(Logo, Himmel, zwei Krabben Hand in Hand) und darunter das Banner, so viele Zeilen wie Platz ist.

    head.py      laeuft, bis die Sitzung unten endet

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
from boot import (at, BOLD, BORDER_BG, BORDER_COLS, CLEAR, CRAB_W, CYCLE, FRAME_S, HIDE,  # noqa: E402
                  LB, LOGO_TEXT, PAIR_W, PARTY, RESET, SCREEN_BG, SHOW, STAND_S, WALK, WHITE,
                  crab_rows, make_sky, mod_version, paint_crab, paint_pair, paint_sky,
                  party_file, party_stamp)

BAND_ROWS = 3
STALE_S = 90


def frame_files():
    sock = os.environ.get('C64_FRAME', '')
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
        out.append(at(r, 1) + BORDER_BG + margin + SCREEN_BG + (BOLD if i == 1 else '') + LB + text + RESET
                   + BORDER_BG + margin + RESET)
    return ''.join(out)


def main():
    write = sys.stdout.write
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    pid_path, alive_path = frame_files()
    logo_col = BORDER_COLS + 1
    text_col = logo_col + CRAB_W + 2
    dance_left = text_col + max(len(t) for t in LOGO_TEXT) + 3
    pfile = party_file()
    seen_party = party_stamp(pfile)
    seen_pid = False
    titled = False
    started = time.time()

    x, frame, direction = dance_left, 0, 1
    standing = 0
    party = False
    sky_span, stars, labels = -1, [], []
    last_size = None
    write(HIDE + CLEAR)
    try:
        while True:
            # Ende der Sitzung unten?
            if os.path.exists(pid_path):
                seen_pid = True
                if not titled:
                    try:
                        pid = open(pid_path).read().strip()
                        project = os.path.basename(os.getcwd().rstrip('\\/')) or 'claude'
                        parts = [p for p in os.getcwd().replace('\\', '/').split('/') if p]
                        project = next((p for p in parts if p[:3].isdigit() and p[3:4] == '-'), project)
                        write(f'\033]0;C64 {project} [{pid}]\007')
                        titled = True
                    except OSError:
                        pass
            elif seen_pid or time.time() - started > 120:
                break
            try:
                if time.time() - os.stat(alive_path).st_mtime > STALE_S:
                    break
            except OSError:
                pass

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
                out = CLEAR + out + banner_rows(cols, BAND_ROWS + 1, rows)
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
    main()
