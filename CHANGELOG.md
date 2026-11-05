# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Both plugins share one
version number.

## [0.12.1-beta.17] — 2026-11-05 — Windows

### Behoben
- Aus Windows PowerShell 5.1 blieb das PowerShell-Feld ueber dem Rahmen stehen. Der Profilblock steht
  nur im Profil von PowerShell 7, in 5.1 ist `LOAD` darum `LOAD.cmd`, ein Kindprozess, der seine Shell
  nicht beenden kann. `load.ps1` erkennt jetzt eine PowerShell ueber `LOAD.cmd` und legt Esc,
  `exit 0` und Enter in den Eingabepuffer der gemeinsamen Konsole (`WriteConsoleInputW`). Die
  PowerShell liest das nach `LOAD.cmd`, endet mit 0, und Windows Terminal schliesst ihr Feld. Aus
  cmd aendert sich nichts.

### Bekannt
- Die Linien zwischen den Feldern bleiben: Windows Terminal zeichnet je 3 px unfokussierten Rand
  (fest `#2E2E2E` bzw. `#E8E8E8` im hellen Design) und 3 px in der Windows-Akzentfarbe am Feld mit
  dem Fokus. Dafuer gibt es keine Einstellung, auch nicht in 1.25.

## [0.12.1-beta.16] — 2026-11-04 — Windows

### Geaendert
- Kein Neuaufbau des Rahmens mehr bei Groessenaenderung. Gemessen mit einem portablen Windows
  Terminal 1.24.12741 im eigenen Prozess: Schliesst ein Feld, dessen Inhalt per `swap-pane`
  getauscht wurde (Kopfleiste, linker Rand), stuerzt Windows Terminal bei der naechsten
  Groessenaenderung ab (`TerminalApp.dll`, `0xc0000005`) und reisst alle Fenster mit, auch
  fremde Tabs. Ohne Claude Code und ohne Ausgabe der Hilfsfelder ebenso. Zuruecktauschen vor dem
  Schliessen hilft nicht verlaesslich; nur die ungetauschten Felder neu bauen laesst Geisterfelder
  stehen und verliert den Fokus. Die Felder bleiben jetzt stehen, Windows Terminal verteilt sie
  anteilig: im kleineren Fenster werden Kopf und Raender schmaler, wieder maximiert stimmt der
  Rahmen genau. Sieben Groessenwechsel hintereinander ohne Absturz.
- `head.py --frame` beendet sich nach dem Aufbau; das Ende der Sitzung erkennen die Hilfsfelder
  selbst. `<id>.reframe` entfaellt.

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
