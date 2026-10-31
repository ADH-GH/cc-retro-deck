#!/usr/bin/env bash
# Haelt die Rahmenfelder aller C64-Fenster auf festen Massen. frame.sh ruft das als tmux-Hook
# (client-resized, client-attached, session-window-changed); die Rolle jedes Feldes steht in
# der Pane-Option @c64.
#
#   fix.sh [SOCKET]     Vorgabe c64
sock="${1:-c64}"
tmux -L "$sock" list-panes -a -F '#{pane_id} #{@c64}' 2>/dev/null | while read -r pane role; do
  case "$role" in
    top)        tmux -L "$sock" resize-pane -t "$pane" -y 3 ;;
    banner)     tmux -L "$sock" resize-pane -t "$pane" -y 4 ;;
    bottom)     tmux -L "$sock" resize-pane -t "$pane" -y 1 ;;
    left|right) tmux -L "$sock" resize-pane -t "$pane" -x 3 ;;
  esac
done
