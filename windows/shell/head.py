#!/usr/bin/env python3
"""Der Rahmen um Claude Code in Windows Terminal (nur Windows-Fassung).

Auf macOS und Linux legt tmux Felder um Claude Code (frame.sh, boot.py --band und --banner).
Windows hat kein tmux; dort teilt Windows Terminal den Tab in Felder, kann sie aber nicht
nachtraeglich auf eine Groesse setzen und verteilt sie bei Groessenaenderung anteilig. Darum
laeuft Claude Code in einem Feld, das bleibt, und alles darum sind Hilfsfelder, die sich bei jeder
Groessenaenderung schliessen und in der richtigen Groesse neu entstehen:

    head.py --frame <id>         im Hintergrund an der Konsole von Claude Code (C64-Run): legt die
                                 Felder an, beobachtet die Groesse, baut neu
    head.py --head <id>          oben: drei Zeilen Kopfleiste (Logo, Himmel, zwei Krabben Hand in
                                 Hand), Trennzeile, vier Zeilen Banner, Trennzeile
    head.py --fill <id> <rolle>  links, rechts (drei Spalten), unten (zwei Zeilen): Rahmenfarbe

Windows Terminal startet neue Felder ohne die Umgebung von LOAD, darum die Kennung als Argument.
Gemessen auf dem PC (scripts/frame-probe.ps1): ein neues Feld kommt immer rechts oder unten an,
schmal nur, wenn es einzeln mit Pause angelegt wird und das geteilte Feld keinen Innenabstand hat
(Profil "C64 Retro Deck Feld"), unten mindestens zwei Zeilen; swap-pane tauscht die Inhalte zweier
Felder, die Groessen bleiben am Platz, der Fokus wandert mit dem Inhalt. Kopf und linker Rand
entstehen darum gross rechts oder unten und werden an ihren Platz getauscht.

Das Ende erkennt jedes Teil an ~/.claude/retro-deck/<id>.pid: C64-Run legt die Datei beim Start
von Claude Code an und loescht sie danach; der Mod erneuert daneben <id>.alive alle 15 s. Fehlt
die PID-Datei (nachdem sie da war) oder ist .alive laenger als 90 s alt, enden alle. <id>.reframe
schickt die Hilfsfelder fuer einen Neuaufbau weg; jedes meldet sich mit <id>.<rolle>.up an und ab.
/deck intro beruehrt party-<id> wie im tmux-Rahmen. Den Tabtitel setzen alle auf "C64 <Projekt>
[pid]", damit die Tafel den Tab findet, gleich welches Feld gerade vorn ist.
"""
import os
import shutil
import signal
import subprocess
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
VERSION = '0.12.1-beta.14'                         # mit plugin.json hochzaehlen
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


FELD = '{6b3c64c6-4c0d-4f8e-9a64-0c64de5c0de2}'     # Profil "C64 Retro Deck Feld" im Fragment
HEAD_ROWS = 9
SIDE_COLS = 3.4                       # Anteile runden ab: so werden es drei Spalten, zwei Zeilen
BOTTOM_ROWS = 2.4


def arg(flag, n=1):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + n < len(sys.argv):
            return sys.argv[i + n]
    return ''


def frame_id():
    for flag in ('--frame', '--head', '--fill'):
        if arg(flag):
            return arg(flag)
    return os.environ.get('C64_FRAME', '')


def base_path(suffix):
    return os.path.join(os.path.expanduser('~'), '.claude', 'retro-deck', frame_id() + suffix)


def frame_files():
    return base_path('.pid'), base_path('.alive')


def mtime(path):
    try:
        return os.stat(path).st_mtime
    except OSError:
        return 0


class Helper:
    """Meldet ein Hilfsfeld an und ab; weg() wird wahr, wenn der Rahmen neu gebaut wird."""

    def __init__(self, role):
        self.up = base_path(f'.{role}.up')
        self.started = time.time()
        log(f'{role} up {console_size()}')
        try:
            open(self.up, 'w').close()
        except OSError:
            pass

    def gone(self):
        return mtime(base_path('.reframe')) > self.started

    def close(self):
        try:
            os.remove(self.up)
        except OSError:
            pass


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
    """Ein Randfeld: ganz in Rahmenfarbe, bis die Sitzung endet oder der Rahmen neu gebaut wird."""
    write = sys.stdout.write
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    pid_path, alive_path = frame_files()
    state = {'seen': False, 'titled': False, 'started': time.time()}
    helper = Helper(arg('--fill', 2) or 'fill')
    write(f'\033]4;12;rgb:{LIGHT_BLUE}\007\033]11;rgb:{LIGHT_BLUE}\007' + HIDE)
    last = None
    try:
        while not session_over(pid_path, alive_path, state) and not helper.gone():
            cols, rows = shutil.get_terminal_size((3, 1))
            if (cols, rows) != last:
                write(CLEAR + ''.join(at(r, 1) + BORDER_BG + ' ' * cols for r in range(1, rows + 1)) + RESET)
                sys.stdout.flush()
                last = (cols, rows)
            time.sleep(0.3)
    except (KeyboardInterrupt, SystemExit, BrokenPipeError):
        pass
    finally:
        helper.close()


def main():
    write = sys.stdout.write
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    pid_path, alive_path = frame_files()
    state = {'seen': False, 'titled': False, 'started': time.time()}
    logo_col = BORDER_COLS + 1
    text_col = logo_col + CRAB_W + 2
    dance_left = text_col + max(len(t) for t in LOGO_TEXT) + 3
    pfile = os.path.join(os.path.dirname(base_path('')), 'party-' + frame_id()) if frame_id() else party_file()
    seen_party = party_stamp(pfile)
    helper = Helper('head')

    x, frame, direction = dance_left, 0, 1
    standing = 0
    party = False
    sky_span, stars, labels = -1, [], []
    last_size = None
    write(f'\033]11;rgb:{LIGHT_BLUE}\007' + HIDE + CLEAR)
    try:
        while True:
            if session_over(pid_path, alive_path, state) or helper.gone():
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
        helper.close()
        try:
            write(RESET + CLEAR + at(1, 1) + SHOW)
            sys.stdout.flush()
        except Exception:
            pass


def log(msg):
    """~/.claude/retro-deck/<id>.log: was der Rahmen tat; zum Einsenden, wenn er ausbleibt."""
    try:
        with open(base_path('.log'), 'a', encoding='utf-8') as f:
            f.write(f'{time.strftime("%H:%M:%S")} {msg}\n')
    except OSError:
        pass


def wt(*args):
    try:
        r = subprocess.run(['wt.exe', '-w', '0', *args], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=15)
        log(f'wt {" ".join(a for a in args[:6])} -> {r.returncode}')
    except (OSError, subprocess.SubprocessError) as e:
        log(f'wt {args[0]} failed: {e}')


def conout_size():
    """Fensterflaeche der Konsole ueber CONOUT$: gilt auch, wenn Start-Process die Standardkanaele
    nicht als Konsole weitergab (os.get_terminal_size kennt unter Windows nur fd 0 bis 2)."""
    if os.name != 'nt':
        return (0, 0)
    try:
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.CreateFileW.restype = wintypes.HANDLE
        h = k.CreateFileW('CONOUT$', 0xC0000000, 3, None, 3, 0, None)
        if not h or h == wintypes.HANDLE(-1).value:
            return (0, 0)

        class Info(ctypes.Structure):
            _fields_ = [('size', wintypes._COORD), ('cursor', wintypes._COORD), ('attr', wintypes.WORD),
                        ('win', wintypes.SMALL_RECT), ('max', wintypes._COORD)]
        info = Info()
        ok = k.GetConsoleScreenBufferInfo(h, ctypes.byref(info))
        k.CloseHandle(h)
        if not ok:
            return (0, 0)
        return (info.win.Right - info.win.Left + 1, info.win.Bottom - info.win.Top + 1)
    except Exception:
        return (0, 0)


def console_size():
    """Groesse des Feldes von Claude Code: --frame laeuft an dessen Konsole."""
    for fd in (1, 2, 0):
        try:
            size = tuple(os.get_terminal_size(fd))
            if size[0] > 0:
                return size
        except (OSError, ValueError):
            continue
    return conout_size()


def share(x):
    return f'{min(0.995, max(0.005, x)):.3f}'


def wait_up(role, timeout=2.5):
    """True, sobald das Hilfsfeld sich angemeldet hat (sonst lehnte Windows Terminal die Teilung ab)."""
    end = time.time() + timeout
    while time.time() < end:
        if os.path.exists(base_path(f'.{role}.up')):
            return True
        time.sleep(0.1)
    log(f'{role} did not come up')
    return False


def build():
    """Legt die Hilfsfelder um das Feld von Claude Code an, das dabei den Fokus behaelt."""
    cols, rows = console_size()
    log(f'build {cols}x{rows}')
    if cols < 20 or rows < HEAD_ROWS + 6:
        log('too small or no console size: no frame')
        return
    me = [sys.executable, os.path.abspath(__file__)]
    here = ['-p', FELD, '-d', os.getcwd()]
    fid = frame_id()
    # Kopf: gross unten neu, dann nach oben getauscht; der Fokus wandert mit, zurueck nach unten.
    wt('split-pane', '-H', '-s', share((rows - HEAD_ROWS) / rows), *here, *me, '--head', fid)
    if wait_up('head'):
        time.sleep(0.4)
        wt('swap-pane', 'up')
        time.sleep(0.4)
        wt('move-focus', 'down')
        time.sleep(0.6)
    rows_below = rows - HEAD_ROWS
    # Linker Rand: ebenso gross rechts neu, nach links getauscht.
    wt('split-pane', '-V', '-s', share((cols - 3) / cols), *here, *me, '--fill', fid, 'left')
    if wait_up('left'):
        time.sleep(0.4)
        wt('swap-pane', 'left')
        time.sleep(0.4)
        wt('move-focus', 'right')
        time.sleep(0.6)
    # Rechter Rand und unterer Rand: schmal neu, einzeln, mit Pause.
    wt('split-pane', '-V', '-s', share(SIDE_COLS / (cols - 3)), *here, *me, '--fill', fid, 'right')
    if wait_up('right'):
        time.sleep(0.4)
        wt('move-focus', 'left')
        time.sleep(0.6)
    wt('split-pane', '-H', '-s', share(BOTTOM_ROWS / rows_below), *here, *me, '--fill', fid, 'bottom')
    if wait_up('bottom'):
        time.sleep(0.4)
        wt('move-focus', 'up')


def frame():
    """Baut den Rahmen, sobald das Feld von LOAD weg ist, und nach jeder Groessenaenderung neu."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)     # Strg+C gilt Claude Code, nicht diesem Helfer
    pid_path, alive_path = frame_files()
    state = {'seen': False, 'titled': True, 'started': time.time()}
    roles = ('head', 'left', 'right', 'bottom')
    log(f'frame {VERSION} python {sys.version.split()[0]} wt {shutil.which("wt.exe") or "-"} '
        f'cwd {os.getcwd()} fds {[os.isatty(fd) for fd in (0, 1, 2)]} size {console_size()}')
    # LOAD schliesst sein Feld 1,2 s nach dem Teilen; danach waechst dieses auf den ganzen Tab.
    time.sleep(1.2)
    size, stable = console_size(), time.time()
    while time.time() - stable < 0.8 and time.time() - state['started'] < 6:
        time.sleep(0.2)
        if console_size() != size:
            size, stable = console_size(), time.time()
    build()
    time.sleep(1.0)
    size = console_size()
    while not session_over(pid_path, alive_path, state):
        time.sleep(0.5)
        now = console_size()
        if now == size:
            continue
        if now[0] == 0:                               # keine Konsole mehr: Tab zu, nichts mehr teilen
            log('console gone')
            break
        log(f'resize {size} -> {now}')
        # Erst wenn die Groesse 1,5 s steht: Hilfsfelder weg, warten bis alle zu sind, neu bauen.
        stable = time.time()
        while time.time() - stable < 1.5:
            time.sleep(0.3)
            if console_size() != now:
                now, stable = console_size(), time.time()
        try:
            with open(base_path('.reframe'), 'w') as f:
                f.write(str(time.time()))
        except OSError:
            continue
        end = time.time() + 5
        while time.time() < end and any(os.path.exists(base_path(f'.{r}.up')) for r in roles):
            time.sleep(0.2)
        time.sleep(0.8)
        if session_over(pid_path, alive_path, state):
            break
        build()
        time.sleep(1.0)
        size = console_size()
    try:
        os.remove(base_path('.reframe'))
    except OSError:
        pass


if __name__ == '__main__':
    if '--frame' in sys.argv:
        frame()
    elif '--fill' in sys.argv:
        fill()
    else:
        main()
