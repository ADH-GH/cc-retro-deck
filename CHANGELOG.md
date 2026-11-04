# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Both plugins share one
version number.

## [0.12.1-beta.15] — 2026-11-04 — Windows

### Behoben
- Der Rahmen blieb aus, weil `head.py --frame` nie lief: `C64-Python` lieferte `py.exe|-3`,
  `Start-Process` setzte jedes Argument in Anfuehrungszeichen, und der Launcher erkennt `"-3"`
  dann nicht als Schalter. Python brach mit `Unknown option: -3` ab, noch vor dem ersten
  Protokolleintrag. `C64-Python` liefert jetzt den echten Interpreter (`sys.executable`), und
  Anfuehrungszeichen gibt es nur noch bei Leerzeichen.
- `C64-Python`: `Select-Object -First 1` im Fluss brach den Prozess ab und verfaelschte
  `$LASTEXITCODE`; der Platzhalter `python3.exe` aus dem Store warf dann einen Fehler.
- Aus cmd blieb das LOAD-Feld offen mit „Prozess mit Code 64 beendet“: Windows Terminal schliesst
  ein Feld nur bei Rueckgabe 0. `LOAD.cmd` endet jetzt mit `exit 0`.

## [0.12.1] — 2026-11-03

### Fixed
- After a minute without input the footer turned to a red `ASK idle_prompt`: Claude Code's
  notice that it waits for your next prompt is no question. It now stays DONE or IDLE.

## [0.12.0] — 2026-10-31

First public release.

### Added
- `cc-retro-deck-mac` (macOS, Terminal.app) and `cc-retro-deck-linux` (Linux, GNOME Terminal).
- Two ways to start: `claude` (standard, with C64 footer and task deck) or `LOAD "*",8,1`
  (Retro Deck: C64 profile, boot screen, tmux frame with crab header and banner).
- `/deck setup` and `/deck uninstall`: set up and remove everything outside the plugin
  (shell line, Terminal profiles, runtime data), each showing its changes before `apply`.
- Star Trek tribute: on `LOAD "*",8,1` the boot screen shows an Enterprise-D drawn in VIC-II
  colors, loading into 24-bit color and going to warp. Unofficial fan art (see NOTICE).
- Sessions started by `LOAD` use the theme `dark-ansi` for that session only; a plain `claude`
  keeps your own theme.
- The footer shows only the limit windows your plan reports (`5h`, `7d`, `$`).
