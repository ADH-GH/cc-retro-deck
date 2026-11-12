# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Both plugins share one
version number.

## [0.12.6] — 2026-11-13

### Added
- All editions: guest disk `LOAD "ARNO",8,1` for Arno at Deutsche Telekom, in magenta. A city
  at night with a lattice radio tower, magenta loader stripes in the border, a satellite sprite
  crossing the sky and a demo scroller in a 5×7 pixel font ("HELLO ARNO * FROM 8 BIT TO AI *
  VISIONARY OF THE MAGENTA NET"). At READY. a four-layer AI network appears and the border
  turns magenta; at RUN the network lights up layer by layer and feeds the tower, which beams
  to the satellite and sends radio arcs, the windows turn magenta and the T with its squares
  lights up in the sky. Ends with "WELCOME, ARNO!  ERLEBEN, WAS VERBINDET."

Update: `claude plugin marketplace update cc-retro-deck`, then `claude plugin update
cc-retro-deck-<mac|linux|windows>@cc-retro-deck` and restart Claude Code.

## [0.12.5] — 2026-11-12

Includes 0.12.3 and 0.12.4, which were not released on their own.

### Added
- All editions: two guest disks. `LOAD "ERIC",8,1` and `LOAD "BERTRAND",8,1` show New York
  instead of the Enterprise: Manhattan at night in VIC-II colors (Empire State, Chrysler,
  One World Trade, the Statue of Liberty, reflections in the water), loading into 24-bit
  color. At READY. a four-node workflow appears above the skyline and greets you by name; at
  RUN it runs node by node, then the top of the Empire State lights up in n8n pink and the
  windows come on from left to right. Made for Eric, n8n Ambassador NYC, and Bertrand. Text and
  color only, no n8n logo.
- `cc-retro-deck-mac`: `/deck update`. Plain `/deck update` lists the Terminal tabs whose
  Claude Code is older than the installed one and changes nothing; `/deck update go` runs
  `claude update`, then restarts each of those tabs in the same tab with `--resume` (inside
  the `LOAD` frame again with the frame), waits for busy sessions, and restarts its own tab
  last, which then shows the result. `/deck update resume` continues an interrupted run. Text
  typed but not sent in a tab is lost. Log: `~/.claude/retro-deck/update.log`.

### Fixed
- An empty session list no longer overwrites the snapshot `/deck restore` falls back on.

Update: `claude plugin marketplace update cc-retro-deck`, then `claude plugin update
cc-retro-deck-<mac|linux|windows>@cc-retro-deck` and restart Claude Code; a set-up shell picks
up the new files on that start, `LOAD` uses them in the next new tab.

## [0.12.2] — 2026-11-07

### Changed
- `cc-retro-deck-mac`: inside the `LOAD` frame the crab header animates only in the Terminal tab
  in front. Tabs in the background show a still picture and check once a second, so many open
  frames no longer keep Terminal redrawing (one test machine: 28 frames, Terminal at 48 % CPU).
  `cc-retro-deck-linux` and `cc-retro-deck-windows` carry the same number without changes.

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
