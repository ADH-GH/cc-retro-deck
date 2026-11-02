# cc-retro-deck-windows (beta)

A Claude Code mod in Commodore 64 colors for **Windows Terminal with PowerShell**. It is the
Windows edition of the Retro Deck; macOS and Linux have their own plugins in the same
marketplace.

What it draws:

- **A header above the prompt**: the Claude Code crab as logo, a star sky, two crabs walking hand
  in hand across it, and the C64 boot banner ("proudly presented by Alf", RETRO DECK, READY.).
  On macOS and Linux a tmux frame holds this header; Windows has no tmux, so the mod draws it
  itself. Turn it off with the `header` option.
- **The footer**: project, zoom (+)(-), model, context meter, cost, turns, the rate-limit windows
  your plan reports, and the session state (BUSY, ASK, DONE, IDLE).
- **The deck** (`/deck`): every Claude Code session on this machine, by tab number and state.
  Click a row or type its number to jump to that Windows Terminal tab.

## Install

```
claude plugin marketplace add ADH-GH/cc-retro-deck#windows-beta
claude plugin install cc-retro-deck-windows@cc-retro-deck
```

Then, in a Claude session: `/deck setup` shows what it would change, `/deck setup apply` does it:
the shell scripts go to `~\.claude\retro-deck\shell\`, `LOAD.cmd` and `SYS.cmd` go to
`~\.local\bin` (where Claude Code's installer puts `claude.exe`, so they are on the PATH), a marked
block goes into your PowerShell profiles, and Windows Terminal gets a profile "C64 Retro Deck"
as a fragment (your `settings.json` is not touched).

Open a new tab, **cmd or PowerShell**, and type `LOAD "*",8,1`, or open the profile
"C64 Retro Deck". The tab turns C64 blue, shows the boot screen (Python needed:
`winget install Python.Python.3.12`) and starts Claude Code. `SYS 64738` resets the tab's colors.

In cmd, and in a Windows PowerShell whose execution policy is "Restricted" (the Windows default),
`LOAD` is `LOAD.cmd`: it runs the C64 part in a PowerShell that may run just that one script, and
when Claude Code ends you are back where you started. Nothing changes the policy unless you ask:
`/deck setup apply policy` sets `RemoteSigned` for your user, after which the PowerShell profile
defines `LOAD` itself.

## How the jump finds a tab

`LOAD` writes the PID of its PowerShell into the tab title, `C64 042-demo [1234]`, and starts
Claude Code with `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` so the title stays. The deck finds that
tab by UI Automation and selects it. A session started with plain `claude` has no such title, so
the deck lists it but cannot jump there.

## Check and remove

- `/deck doctor` prints what the mod sees: Windows Terminal, PowerShell, Python, the profiles,
  the tab titles. Send the text along with any bug report.
- `/deck uninstall` and `/deck uninstall apply` take back everything outside the plugin, then
  `claude plugin uninstall cc-retro-deck-windows@cc-retro-deck`.

Other commands: `/deck theme c64|amiga|cga`, `/deck intro`, `/deck zoom +|-`, `/deck restore`
(reopens closed sessions as new tabs with `--resume`), `/pure` (C64 BASIC as deck commands),
`/emul` (a C64 BASIC V2 in a pane).
