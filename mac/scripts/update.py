#!/usr/bin/env python3
"""/deck update: Claude Code aktualisieren und alle Terminal-Tabs mit gleichem Stand neu starten.

  update.py plan  [--self SID] [--only-cwd DIR] [--all]   zeigt, was geschehen wuerde; aendert nichts
  update.py start [--self SID] [--only-cwd DIR] [--all] [--skip-update]
                                                            loest sich von Claude Code und fuehrt aus
  update.py resume                                          setzt einen abgebrochenen Lauf fort
  update.py run ...                                         (intern: der abgeloeste Lauf)

Neu gestartet wird jede interaktive Sitzung in Terminal.app, deren Version nicht die installierte
ist (nach `claude update`); mit --all jede. Sitzungen, die arbeiten, werden abgewartet. Neustart im
selben Tab: claude per SIGTERM beenden, warten bis die Shell frei ist, dann per AppleScript
`claude --resume <id>` (direkt) oder `LOAD "*",8,1 FAST --resume <id>` (Rahmen) in denselben Tab.
Die eigene Sitzung (--self) kommt zuletzt. Entscheidung: docs/decisions/0006-deck-update.md.
--only-cwd begrenzt auf Sitzungen in einem Ordner (Test mit Wegwerf-Tabs).
"""
import ctypes
import glob
import json
import os
import shlex
import signal
import subprocess
import sys
import time

HOME = os.path.expanduser('~')
REGISTRY = os.path.join(HOME, '.claude', 'sessions')
STATE_DIR = os.path.join(HOME, '.claude', 'retro-deck')
STATE = os.path.join(STATE_DIR, 'update-state.json')
LOG = os.path.join(STATE_DIR, 'update.log')
CLAUDE_LINK = os.path.join(HOME, '.local', 'bin', 'claude')

WAIT_BUSY_S = 2 * 60 * 60        # so lange warten laufende Sitzungen hoechstens
PASS_PAUSE_S = 10                # Pause zwischen zwei Durchgaengen ueber die wartenden
EXIT_WAIT_S = 20                 # bis claude nach SIGTERM weg ist
SHELL_WAIT_S = 30                # bis die Shell des Tabs wieder frei ist
STAY_S = 8                       # so lange muss die neue Sitzung danach noch leben
START_WAIT_S = 90                # bis sich die neue Sitzung im Register meldet

# Startargumente, die der Neustart uebernimmt; alles andere (Prompt, --resume, -c, -p ...) faellt weg.
KEEP_WITH_VALUE = {'--settings', '--model', '--permission-mode', '--plugin-dir', '--add-dir', '--agent',
                   '--mcp-config', '--fallback-model', '--setting-sources', '--allowedTools', '--disallowedTools'}
KEEP_FLAG = {'--dangerously-skip-permissions', '--verbose', '--ide', '--chrome', '--strict-mcp-config'}
LOAD_THEME = '{"theme":"dark-ansi"}'


def log(msg):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(LOG, 'a') as f:
        f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + msg + '\n')


def sh(args, timeout=10):
    try:
        r = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 1, '', str(e)


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def installed_version():
    try:
        return os.path.basename(os.path.realpath(CLAUDE_LINK))
    except OSError:
        return ''


def proc_argv(pid):
    """argv eines Prozesses exakt (sysctl KERN_PROCARGS2), ps verliert die Anfuehrungszeichen."""
    libc = ctypes.CDLL(None)
    mib = (ctypes.c_int * 3)(1, 49, pid)
    size = ctypes.c_size_t(0)
    if libc.sysctl(mib, 3, None, ctypes.byref(size), None, 0) != 0:
        return []
    buf = ctypes.create_string_buffer(size.value)
    if libc.sysctl(mib, 3, buf, ctypes.byref(size), None, 0) != 0:
        return []
    raw = buf.raw[:size.value]
    argc = int.from_bytes(raw[:4], sys.byteorder)
    rest = raw[4:]
    rest = rest[rest.index(b'\0'):]                      # Pfad des Programms
    parts = [p for p in rest.split(b'\0') if p]
    return [p.decode('utf-8', 'replace') for p in parts[:argc]]


def ps_field(pid, field):
    _, out, _ = sh(['ps', '-o', f'{field}=', '-p', str(pid)])
    return out.strip()


def frame_socket(pid):
    """tmux-Socket des Rahmens (frame.sh), wenn claude darin laeuft: Vorfahren nach `tmux -L c64-…`."""
    p = pid
    for _ in range(6):
        p = int(ps_field(p, 'ppid') or 0)
        if p <= 1:
            return ''
        argv = proc_argv(p)
        if len(argv) >= 3 and os.path.basename(argv[0]) == 'tmux' and argv[1] == '-L' and argv[2].startswith('c64-'):
            return argv[2]
    return ''


def tmux_bin():
    for b in ('/opt/homebrew/bin/tmux', '/usr/local/bin/tmux', 'tmux'):
        if b == 'tmux' or os.path.exists(b):
            return b
    return 'tmux'


def outer_tty(entry_tty, sock):
    if not sock:
        return entry_tty
    _, out, _ = sh([tmux_bin(), '-L', sock, 'list-clients', '-F', '#{client_tty}'])
    return out.splitlines()[0] if out else ''


def kept_args(argv, in_frame):
    out, skipped, i = [], [], 1
    while i < len(argv):
        a = argv[i]
        key = a.split('=', 1)[0]
        if key in KEEP_WITH_VALUE:
            val = a.split('=', 1)[1] if '=' in a else (argv[i + 1] if i + 1 < len(argv) else '')
            i += 1 if '=' in a else 2
            if in_frame and key == '--settings' and val == LOAD_THEME:
                continue                                   # LOAD setzt das Theme selbst
            out += [key, val]
            continue
        if a in KEEP_FLAG:
            out.append(a)
        else:
            skipped.append(a)
        i += 1
    return out, skipped


# --- Terminal.app -------------------------------------------------------------------------------

TAB_SCRIPT = '''
on run argv
  set wanted to item 1 of argv
  set what to item 2 of argv
  tell application "Terminal"
    repeat with w in windows
      repeat with t in tabs of w
        if tty of t is wanted then
          if what is "busy" then return (busy of t) as string
          if what is "profile" then return name of current settings of t
          if what is "run" then
            do script (item 3 of argv) in t
            return "ok"
          end if
        end if
      end repeat
    end repeat
  end tell
  return "missing"
end run
'''


def tab(tty, what, cmd=''):
    _, out, _ = sh(['osascript', '-e', TAB_SCRIPT, '--', tty, what, cmd], timeout=15)
    return out


def terminal_ttys():
    _, out, _ = sh(['osascript', '-e', 'tell application "Terminal" to get tty of tabs of windows'], timeout=15)
    return {t.strip() for t in out.replace('{', ',').replace('}', ',').split(',') if t.strip().startswith('/dev/')}


# --- Inventur -----------------------------------------------------------------------------------

def registry():
    out = []
    for f in glob.glob(os.path.join(REGISTRY, '*.json')):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if isinstance(d, dict) and isinstance(d.get('pid'), int) and alive(d['pid']):
            out.append(d)
    return out


def inventory(opts):
    have = installed_version()
    tabs = terminal_ttys()
    rows = []
    for d in registry():
        if d.get('kind') != 'interactive' or d.get('entrypoint') != 'cli':
            continue
        if opts.get('only_cwd') and os.path.realpath(d.get('cwd', '')) != os.path.realpath(opts['only_cwd']):
            continue
        pid = d['pid']
        tty = ps_field(pid, 'tty')
        tty = '/dev/' + tty if tty and not tty.startswith('/dev/') and tty != '??' else ''
        sock = frame_socket(pid)
        otty = outer_tty(tty, sock)
        if otty not in tabs:
            continue                                       # nicht in Terminal.app (VS Code, iTerm, ohne Tab)
        argv = proc_argv(pid)
        args, skipped = kept_args(argv, bool(sock))
        rows.append({
            'sessionId': d.get('sessionId', ''), 'pid': pid, 'cwd': d.get('cwd', HOME),
            'version': d.get('version', ''), 'status': d.get('status', ''), 'tty': otty,
            'frame': bool(sock), 'args': args, 'skipped': skipped,
            'name': d.get('name', ''), 'self': d.get('sessionId') == opts.get('self'),
        })
    rows.sort(key=lambda r: (r['self'], r['tty']))
    if not opts.get('all'):
        rows = [r for r in rows if r['version'] != have]
    return have, rows


def project(cwd):
    return os.path.basename(cwd.rstrip('/')) or cwd


def plan_text(have, rows, note=''):
    if not rows:
        return f'Nothing to restart: every Claude Code tab already runs {have}.' + note
    vers = sorted({r['version'] for r in rows})
    busy = [r for r in rows if r['status'] != 'idle']
    lines = [f'{len(rows)} tab(s) restart on {have} (now {", ".join(vers)}):']
    for r in rows:
        mark = ' busy, waits' if r['status'] != 'idle' else ''
        lines.append(f'  {r["tty"].replace("/dev/", ""):8} {project(r["cwd"])[:28]:28} {r["version"]:9} '
                     f'{"LOAD" if r["frame"] else "claude"}{mark}{"  (this tab, last)" if r["self"] else ""}')
    if busy:
        lines.append(f'{len(busy)} still working: they restart when their turn has ended.')
    lines.append('Unsent text in an input field is lost. Type /deck update go to start.')
    return '\n'.join(lines) + note


# --- Neustart -----------------------------------------------------------------------------------

def save(state):
    tmp = STATE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE)


def status_of(pid):
    f = os.path.join(REGISTRY, f'{pid}.json')
    try:
        return json.load(open(f)).get('status', '')
    except Exception:
        return '' if alive(pid) else 'gone'


def has_transcript(r):
    """Eine Sitzung ohne Nachricht hat keinen Verlauf; --resume meldet dann "No conversation found"."""
    folder = ''.join(c if c.isalnum() else '-' for c in r['cwd'])
    return os.path.exists(os.path.join(HOME, '.claude', 'projects', folder, r['sessionId'] + '.jsonl'))


def restart_cmd(r):
    args = ' '.join(shlex.quote(a) for a in r['args'])
    resume = f"--resume {shlex.quote(r['sessionId'])}" if has_transcript(r) else ''
    if r['frame']:
        extra = ' RAHMEN' if r.get('profile') == 'C64 Rahmen' else ''
        load = f"LOAD '*,8,1' FAST{extra} {args} {resume}"
        return f'cd {shlex.quote(r["cwd"])} && {" ".join(load.split())}'
    return ' '.join(f'cd {shlex.quote(r["cwd"])} && claude {args} {resume}'.split())


def wait(cond, seconds, step=0.5):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(step)
    return cond()


def find_new(r, since, have):
    for d in registry():
        if d.get('pid') == r['pid'] or d.get('startedAt', 0) < since - 2000:
            continue
        if d.get('sessionId') == r['sessionId'] or (os.path.realpath(d.get('cwd', '')) == os.path.realpath(r['cwd'])
                                                   and ps_field(d['pid'], 'tty') and outer_tty('/dev/' + ps_field(d['pid'], 'tty'), frame_socket(d['pid'])) == r['tty']):
            return d
    return None


def restart(r, have):
    r['profile'] = tab(r['tty'], 'profile')
    if r['profile'] == 'missing':
        return 'tab not found'
    cmd = restart_cmd(r)
    log(f'{r["tty"]} {r["sessionId"]} {project(r["cwd"])}: SIGTERM {r["pid"]}, then: {cmd}')
    try:
        os.kill(r['pid'], signal.SIGTERM)
    except OSError:
        pass
    if not wait(lambda: not alive(r['pid']), EXIT_WAIT_S):
        return f'claude {r["pid"]} did not end after SIGTERM'
    if not wait(lambda: tab(r['tty'], 'busy') == 'false', SHELL_WAIT_S):
        state = tab(r['tty'], 'busy')
        if state == 'missing':
            return 'tab closed when claude ended'
        return 'shell of the tab stays busy'
    since = int(time.time() * 1000)
    if tab(r['tty'], 'run', cmd) != 'ok':
        return 'could not type into the tab'
    found = [None]
    if not wait(lambda: found.__setitem__(0, find_new(r, since, have)) or found[0] is not None, START_WAIT_S, 1):
        return 'no new session registered'
    d = found[0]
    r['newPid'], r['newSessionId'], r['newVersion'] = d.get('pid'), d.get('sessionId'), d.get('version')
    time.sleep(STAY_S)
    if not alive(d['pid']):
        return 'new session ended right after start'
    if d.get('version') != have:
        return f'restarted, but on {d.get("version")}'
    return ''


def run(state):
    have = state['installed']
    pending = lambda: [r for r in state['rows'] if r.get('result') is None]
    started = time.time()
    while pending():
        others = [r for r in pending() if not r['self']]
        batch = others or pending()                       # die eigene Sitzung erst, wenn alle anderen durch sind
        progressed = False
        for r in batch:
            st = status_of(r['pid'])
            if st == 'gone':
                r['result'] = 'skipped: session ended meanwhile'
            elif st != 'idle':
                continue
            else:
                err = restart(r, have)
                r['result'] = 'ok' if not err else 'failed: ' + err
            log(f'{r["tty"]} {project(r["cwd"])}: {r["result"]}')
            progressed = True
            save(state)
        if not pending():
            break
        if time.time() - started > WAIT_BUSY_S:
            for r in pending():
                r['result'] = 'skipped: still working after 2 h'
            break
        if not progressed:
            time.sleep(PASS_PAUSE_S)
    state['finishedAt'] = int(time.time() * 1000)
    ok = sum(1 for r in state['rows'] if r['result'] == 'ok')
    state['summary'] = f'{ok}/{len(state["rows"])} tab(s) restarted on {have}'
    save(state)
    log(state['summary'])


def detach(argv):
    if os.fork() > 0:
        return
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    devnull = os.open(os.devnull, os.O_RDWR)
    for fd in (0, 1, 2):
        os.dup2(devnull, fd)
    os.execv(sys.executable, [sys.executable, '-I', os.path.abspath(__file__), 'run'] + argv)


def parse(argv):
    opts = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--self':
            opts['self'] = argv[i + 1]; i += 2; continue
        if a == '--only-cwd':
            opts['only_cwd'] = argv[i + 1]; i += 2; continue
        if a == '--all':
            opts['all'] = True
        elif a == '--skip-update':
            opts['skip_update'] = True
        i += 1
    return opts


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    verb, argv = sys.argv[1], sys.argv[2:]
    opts = parse(argv)
    if verb == 'plan':
        have, rows = inventory(opts)
        print(plan_text(have, rows, '\n(claude update runs first; the list is taken again after it.)'))
        return 0
    if verb == 'start':
        try:
            prev = json.load(open(STATE))
            if prev.get('finishedAt') is None and alive(prev.get('runnerPid', 0)):
                print(f'An update is already running (log: {LOG}).')
                return 1
        except Exception:
            pass
        detach(argv)
        print(f'Update started. Tabs restart one by one, this one last. Log: {LOG}')
        return 0
    if verb == 'resume':
        try:
            state = json.load(open(STATE))
        except Exception:
            print('No update to resume.')
            return 1
        if state.get('finishedAt'):
            for r in state['rows']:
                if r.get('result', '').startswith(('failed', 'skipped')):
                    r['result'] = None
                    r['pid'] = r.get('newPid') or r['pid']
            state['finishedAt'] = None
        save(state)
        detach(['--resume-state'])
        print(f'Update resumed. Log: {LOG}')
        return 0
    if verb == 'run':
        if '--resume-state' in argv:
            state = json.load(open(STATE))
            state['runnerPid'] = os.getpid()
            save(state)
            run(state)
            return 0
        before = installed_version()
        log(f'--- update, installed {before}')
        state = {'startedAt': int(time.time() * 1000), 'runnerPid': os.getpid(), 'before': before,
                 'installed': before, 'rows': [], 'finishedAt': None, 'self': opts.get('self', '')}
        save(state)
        if not opts.get('skip_update'):
            code, out, err = sh(['claude', 'update'], timeout=600)
            log(f'claude update -> {code}: {(out or err).splitlines()[-1] if (out or err) else ""}')
        state['installed'] = installed_version()
        have, rows = inventory(opts)
        state['installed'], state['rows'] = have, rows
        log(f'installed {have}; {len(rows)} tab(s) to restart')
        save(state)
        run(state)
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main())
