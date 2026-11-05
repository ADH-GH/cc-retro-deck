# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Both plugins share one
version number.

## [0.12.1] — 2026-11-05

### Added
- `cc-retro-deck-windows` (Windows 10/11, Windows Terminal with cmd or PowerShell): footer, task
  deck with jumps between Windows Terminal tabs, `/deck setup` and `/deck uninstall`, and
  `LOAD "*",8,1` with the boot screen and a frame of Windows Terminal panes around Claude Code
  (crab header and banner on top, light blue edges). Windows Terminal cannot size panes, so the
  frame scales with the window and is exact again at the size it was built in.

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
