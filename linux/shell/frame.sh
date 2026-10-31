#!/usr/bin/env bash
# C64-Rahmen unter Linux: tmux legt hellblaue Felder um Claude Code, oben tanzt die Krabbe.
#
# Anders als auf dem Mac (ein tmux-Server je Terminal.app-Tab) laufen hier alle Sitzungen in
# EINEM Server `-L c64`, jede als eigenes tmux-Fenster mit eigenem Rahmen. Die Fenster sind
# die Tabs: GNOME Terminal laesst sich von aussen nicht auf einen Tab umschalten, tmux schon —
# der Mod springt per `select-window` zwischen den Sitzungen.
#
#   frame.sh [CMD...]          neues Fenster mit Rahmen, CMD in der Mitte (Vorgabe: claude);
#                              startet den Server, falls er nicht laeuft, und haengt an
#   frame.sh --window CMD...   nur das Fenster anlegen, im Hintergrund (Mod: NEW, restore)
#   frame.sh --detach CMD...   Test: anlegen, nicht anhaengen, Pane-ID der Mitte ausgeben
#
# Aufbau je Fenster (Zeilen x Spalten):
#   ┌─ Krabbenleiste, 3 Zeilen: boot.py --band
#   ├─ Banner, 4 Zeilen: boot.py --banner
#   │ 3 Spalten + Linie │  Claude Code  │ Linie + 3 Spalten
#   └─ 1 Zeile + Linie
# Jedes Feld traegt seine Rolle in der Pane-Option @c64 (top, banner, bottom, left, right,
# main); fix.sh haelt daran die Masse fest, wenn das Fenster waechst oder schrumpft.
# Claude Code bekommt C64_FRAME=<Fenster-Kennung>, damit der Mod sein eigenes Intro laesst;
# `/deck intro` beruehrt ~/.claude/retro-deck/party-<Kennung>, und die Kopfleiste tanzt los.
#
# Bewusst ohne Bash-4-Eigenheiten, damit die Tests auch unter der Bash 3.2 von macOS laufen.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOCK="${C64_FRAME_SOCK:-c64}"         # Umgebungsvariable nur fuer Tests
T=(tmux -L "$SOCK" -f "$DIR/c64.tmux.conf")

mode=attach
case "${1:-}" in
  --window) mode=window; shift ;;
  --detach) mode=detach; shift ;;
esac
[ $# -gt 0 ] || set -- claude

q() { printf '%q' "$1"; }
cmd=""
for a in "$@"; do cmd="$cmd $(q "$a")"; done

ID="c64-$$-$RANDOM"
hold="sleep 2147483647"
# Die Mitte: endet das Programm, faellt das ganze Fenster weg, und mit dem letzten der Server.
# kill-window braucht das eigene Pane als Ziel; ohne -t trifft es das gerade vordere Fenster.
main="C64_FRAME=$ID$cmd; rm -f ~/.claude/retro-deck/party-$ID; tmux kill-window -t \"\$TMUX_PANE\""
band="C64_FRAME=$ID python3 $(q "$DIR/boot.py") --band || $hold"
banner="python3 $(q "$DIR/boot.py") --banner || $hold"
name="$(basename "$PWD")"

if "${T[@]}" has-session -t c64 2>/dev/null; then
  MAIN=$("${T[@]}" new-window -d -P -F '#{pane_id}' -t c64: -c "$PWD" -n "$name" "$main")
else
  cols=${COLUMNS:-$(tput cols 2>/dev/null || echo 120)}
  rows=${LINES:-$(tput lines 2>/dev/null || echo 40)}
  MAIN=$(TMUX= "${T[@]}" new-session -d -P -F '#{pane_id}' -s c64 -n "$name" -c "$PWD" \
    -x "$cols" -y "$rows" "$main")
fi

split() {   # split <role> <richtung> <groesse> [-b] <kommando>
  local role="$1" dir="$2" size="$3" before="" pane
  shift 3
  if [ "$1" = "-b" ]; then before="-b"; shift; fi
  if [ "$dir" = "-v" ]; then
    pane=$("${T[@]}" split-window -d -P -F '#{pane_id}' -t "$MAIN" -v $before -l "$size" "$1")
  else
    pane=$("${T[@]}" split-window -d -P -F '#{pane_id}' -t "$MAIN" -h $before -l "$size" "$1")
  fi
  "${T[@]}" set -p -t "$pane" @c64 "$role"
  if [ "$role" = banner ]; then
    "${T[@]}" select-pane -t "$pane" -P 'fg=default,bg=default'   # Banner auf Bildschirmblau
  else
    "${T[@]}" select-pane -t "$pane" -P 'fg=colour12,bg=colour12'
  fi
}

split top    -v 3 -b "$band"
split banner -v 4 -b "$banner"
split bottom -v 1    "$hold"
split left   -h 3 -b "$hold"
split right  -h 3    "$hold"
"${T[@]}" set -p -t "$MAIN" @c64 main
"${T[@]}" select-pane -t "$MAIN" -P 'fg=default,bg=default'
"${T[@]}" select-pane -t "$MAIN"

# Masse halten — fuer alle Fenster, denn ein verdecktes Fenster bekommt die neue Groesse erst,
# wenn es wieder vorn ist. Hooks und Tasten gelten serverweit; erneutes Setzen schadet nicht.
fix="run-shell -b \"bash $(q "$DIR/fix.sh") $(q "$SOCK")\""
"${T[@]}" set-hook -g client-resized "$fix"
# Terminal zu = Sitzungen zu, wie ohne Rahmen (dort beendet das SIGHUP claude). Sonst liefen
# alle Fenster im Server unsichtbar weiter. Mit zwei Terminals am Server endet er erst mit dem
# letzten. Erst beim Anhaengen setzen: vorher gesetzt beendet tmux die noch nie angehaengte
# Sitzung sofort (auf dem Mac mit tmux 3.8 geprueft) — und --window/--detach haengen nie an.
"${T[@]}" set-hook -g client-attached "$fix ; set -g destroy-unattached on"
"${T[@]}" set-hook -g session-window-changed "$fix"

# Maus nur fuer die Mitte: Klicks und Rad erreichen Claude Code, der Rahmen bleibt stumm.
is_main="#{==:#{@c64},main}"
for key in MouseDown1Pane MouseDrag1Pane MouseDragEnd1Pane DoubleClick1Pane TripleClick1Pane MouseDown3Pane; do
  "${T[@]}" bind -n "$key" if -F "$is_main" "send-keys -M" ""
done
"${T[@]}" bind -n WheelUpPane   if -F "$is_main" "if -F '#{mouse_any_flag}' 'send-keys -M' 'if -F \"#{pane_in_mode}\" \"send-keys -M\" \"copy-mode -e\"'" ""
"${T[@]}" bind -n WheelDownPane if -F "$is_main" "send-keys -M" ""

case "$mode" in
  detach) echo "$MAIN"; exit 0 ;;
  window) exit 0 ;;
esac

"${T[@]}" select-window -t "$MAIN"
# Schon in diesem Server (etwa LOAD aus einem Rahmenfenster): das Umschalten genuegt.
if [ -n "${TMUX:-}" ] && [ "$("${T[@]}" display -p '#{socket_path}' 2>/dev/null)" = "${TMUX%%,*}" ]; then
  exit 0
fi
TMUX= exec "${T[@]}" attach -t c64
