# Claude Code Retro Deck

**English** · [Deutsch](README.de.md)

A Commodore 64 look for Claude Code: C64 colors in the prompt footer, a deck of every running
session, and `LOAD "*",8,1` with a boot screen and two dancing crabs holding hands.

*Unofficial community mod. Not affiliated with or endorsed by Anthropic. "Claude" and the
Claude Code crab belong to Anthropic. Product names in the header belong to their owners;
no affiliation or endorsement implied.*

## Pick your edition

| System | Plugin | Terminal |
|---|---|---|
| macOS | `cc-retro-deck-mac` | Terminal.app |
| Linux (tested target: Mint 22) | `cc-retro-deck-linux` | GNOME Terminal |
| Windows | coming later | |

Install exactly one: the edition for your system. Claude Code has no way to pick it for you.

## Two ways to start

| | You type | You get |
|---|---|---|
| **Standard** | `claude` | Claude Code as usual, plus the C64 footer and the task deck (`/deck`) |
| **Retro Deck** | `LOAD "*",8,1` | C64 terminal colors, the boot screen, then Claude Code inside a C64 frame with the crab header and the banner |

Standard works right after installing the plugin. Retro Deck needs the one-time setup (step 3).

## Install

**Requirements.** Standard needs only Claude Code 2.1.312 or later. Retro Deck also needs
`tmux` and `python3`:

| | check | macOS | Linux (Mint/Ubuntu) |
|---|---|---|---|
| tmux | `tmux -V` | `brew install tmux` (Homebrew: [brew.sh](https://brew.sh)) | `sudo apt install tmux` |
| python3 | `python3 --version` | `xcode-select --install` (Command Line Tools) | preinstalled; else `sudo apt install python3` |

`/deck setup` checks both and names the install command if one is missing; it installs
nothing itself. Without tmux, `LOAD` starts Claude Code without the frame; without python3 it
shows three lines instead of the boot screen.

**1. Add the marketplace** (in a shell, or as `/plugin …` inside Claude Code):

```bash
claude plugin marketplace add ADH-GH/cc-retro-deck
```

**2. Install your edition:**

```bash
claude plugin install cc-retro-deck-mac@cc-retro-deck      # macOS
claude plugin install cc-retro-deck-linux@cc-retro-deck    # Linux
```

Claude Code may note that the plugin's options are not set yet: they are optional, the
defaults apply (change them later under `/plugin`). Start `claude`. You now have **Standard**.

**3. For Retro Deck: run the setup** inside Claude Code:

```
/deck setup          shows what it will change, changes nothing
/deck setup apply    does it
```

What `apply` does:

- copies the shell scripts to `~/.claude/retro-deck/shell/` (kept current on every start)
- adds one marked block to `~/.zshrc` (macOS) or `~/.bashrc` (Linux), between
  `# >>> cc-retro-deck >>>` and `# <<< cc-retro-deck <<<`; it defines `LOAD` and `RUN`
- macOS only: imports the Terminal profiles "C64" and "C64 Rahmen"
- tells you if `tmux` is missing

Open a new terminal tab and type `LOAD "*",8,1`.

Sessions started by `LOAD` draw Claude Code itself in C64 colors too (theme `dark-ansi`, for
that session only). A plain `claude` keeps your own theme.

## Use

| Command | Does |
|---|---|
| `/deck` | open the task deck; type a tab number and Enter, or click a row, to jump there |
| `/deck intro` | send the crabs dancing |
| `/deck zoom +` / `-` | font of this tab one point bigger / smaller (macOS; also the `(+)` `(-)` in the footer) |
| `/deck restore` | reopen sessions a closed terminal took with it |
| `/deck theme c64\|amiga\|cga` | palette for this session |
| `/pure HELP` | C64 BASIC commands read as deck actions |
| `/emul` | a Commodore 64 in a pane |

Settings (theme, auto-switch, deck at start, intro): `/plugin` → the plugin → configure.

## Turn it off

**Just once:** type `claude` instead of `LOAD "*",8,1` — no frame, no C64 colors.

**Disable, keep installed:**

```bash
claude plugin disable cc-retro-deck-mac@cc-retro-deck      # Linux: cc-retro-deck-linux@cc-retro-deck
```

From the next session on, Claude Code looks as shipped. Back with `claude plugin enable …`.
`LOAD` still exists in your shell until you uninstall.

## Uninstall

**1. Remove what the setup added** — inside Claude Code, while the plugin is still installed:

```
/deck uninstall          shows what it will remove, removes nothing
/deck uninstall apply    does it
```

It ends running Retro Deck frames (after a warning; your conversations stay available via
`claude --resume`), removes the marked block from your shell file, deletes the Terminal
profiles (macOS) and `~/.claude/retro-deck/`.

**2. Remove the plugin and the marketplace:**

```bash
claude plugin uninstall cc-retro-deck-mac@cc-retro-deck    # Linux: cc-retro-deck-linux@cc-retro-deck
claude plugin marketplace remove cc-retro-deck
```

Check: `claude plugin list` no longer lists it, a new tab shows your usual prompt, `LOAD` is
unknown.

### By hand, if the plugin is already gone

```bash
# end running frames (macOS: one tmux server per tab; Linux: one shared server)
for s in "${TMUX_TMPDIR:-/tmp}/tmux-$(id -u)"/c64-*; do tmux -S "$s" kill-server; done   # macOS
tmux -L c64 kill-server                                                                   # Linux
rm -rf ~/.claude/retro-deck
rm -rf ~/.claude/plugins/cache/cc-retro-deck     # Claude Code's own copy, if still there
```

Then delete the block between `# >>> cc-retro-deck >>>` and `# <<< cc-retro-deck <<<` from
`~/.zshrc` or `~/.bashrc`. On macOS remove the profiles "C64" and "C64 Rahmen" in
Terminal → Settings → Profiles (set another profile as default first).

## Branding

The crab header and the banner ("proudly presented by Alf") are the signature of this mod's
builders and are not configurable. The code is MIT licensed: fork it freely, but if you change
the header or the banner, please give your version a name of its own.

## Star Trek tribute

The boot screen after `LOAD "*",8,1` is a tribute to Sir Patrick Stewart. It is **unofficial
fan art**: the ship is drawn from scratch in code, no Star Trek images or music are included.
Star Trek and related names, ships and quotes are trademarks and copyrights of CBS Studios
Inc. / Paramount; this tribute is not affiliated with or endorsed by them. The MIT license
covers this project's code only and grants no rights in third-party marks or designs. See
[NOTICE](NOTICE).

## License

[MIT](LICENSE) · [NOTICE](NOTICE)
