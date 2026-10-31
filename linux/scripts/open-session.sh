#!/usr/bin/env bash
# Opens a Claude Code session next to the running ones (Linux). Used by `/pure NEW` and
# restore.sh.
#
#   open-session.sh DIR [claude args...]
#
# With the C64 frame running (tmux server `-L c64`), the session becomes a new window in it,
# framed like the others. Otherwise a new GNOME Terminal tab, otherwise a new window of the
# Debian/Mint default terminal.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dir="${1:-$HOME}"
shift || true
[ -d "$dir" ] || dir="$HOME"

if tmux -L "${C64_FRAME_SOCK:-c64}" has-session -t c64 2>/dev/null; then
  cd "$dir"
  exec bash "$here/../shell/frame.sh" --window claude "$@"
elif command -v gnome-terminal >/dev/null; then
  exec gnome-terminal --tab --working-directory="$dir" -- claude "$@"
elif command -v x-terminal-emulator >/dev/null; then
  cd "$dir"
  exec x-terminal-emulator -e claude "$@"
fi
echo "No terminal found: neither the C64 frame, gnome-terminal nor x-terminal-emulator." >&2
exit 1
