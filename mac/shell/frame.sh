#!/bin/zsh
# C64-Rahmen: tmux legt hellblaue Felder um Claude Code, oben tanzt die Krabbe.
#
#   frame.sh claude [args]     Rahmen aufbauen, claude in der Mitte, beim Ende von claude
#                              faellt der Rahmen wieder weg
#   frame.sh --detach CMD      nur aufbauen, nicht anhaengen; gibt den Socket-Namen aus (Test)
#
# Aufbau (Zeilen x Spalten des Tabs):
#   ┌─ Krabbenleiste, 3 Zeilen: boot.py --band, darunter 1 Trennzeile in Rahmenfarbe
#   ├─ Banner, 4 Zeilen: boot.py --banner (dunkelblau, proudly presented by Alf, RETRO DECK V0.x, 64K RAM, READY.)
#   │ 3 Spalten + Linie │  Claude Code, Grund des Profils (dunkelblau)  │ Linie + 3 Spalten
#   └─ 1 Zeile + Linie
# Alle Felder ausser der Mitte tragen bg=colour12; im Profil "C64" ist das VIC-Hellblau.
# Maus und Tasten gehen nur an das mittlere Feld. Claude Code bekommt TERM_PROGRAM des Tabs
# (Apple_Terminal), damit es seine Krabbe in der Form zeichnet, die Apples Schrift traegt,
# und C64_FRAME=<Socket>, damit der Mod sein eigenes Intro laesst: Krabbe und Banner stehen oben;
# `/deck intro` beruehrt ~/.claude/retro-deck/party-<Socket>, und die Kopfleiste tanzt los.

emulate -L zsh
setopt err_exit no_unset pipe_fail

DIR="${0:A:h}"
detach=0
if [[ "${1:-}" == --detach ]]; then detach=1; shift; fi
(( $# )) || set -- claude

SOCK="${C64_FRAME_SOCK:-c64-$$}"      # Umgebungsvariable nur fuer Tests
cols=${COLUMNS:-$(tput cols)}
rows=${LINES:-$(tput lines)}
T=(tmux -L "$SOCK" -f "$DIR/c64.tmux.conf")

# Die Mitte: Claude Code mit dem TERM_PROGRAM des Tabs; danach faellt der ganze Server.
typeset cmd="C64_FRAME=$SOCK TERM_PROGRAM=${(q)${TERM_PROGRAM:-}} ${(j: :)${(q)@}}; rm -f ~/.claude/retro-deck/party-$SOCK; tmux kill-server"
TMUX= "${T[@]}" new-session -d -s c64 -n claude -x "$cols" -y "$rows" "$cmd"
MAIN=$("${T[@]}" display -p -t c64:0 '#{pane_id}')

hold="sleep 2147483647"
band="C64_FRAME=$SOCK TERM_PROGRAM=${(q)${TERM_PROGRAM:-}} python3 ${(q)DIR}/boot.py --band || $hold"
banner="TERM_PROGRAM=${(q)${TERM_PROGRAM:-}} python3 ${(q)DIR}/boot.py --banner || $hold"
TOP=$("${T[@]}"   split-window -d -P -F '#{pane_id}' -t "$MAIN" -v -b -l 3 "$band")
BAN=$("${T[@]}"   split-window -d -P -F '#{pane_id}' -t "$MAIN" -v -b -l 4 "$banner")
BOT=$("${T[@]}"   split-window -d -P -F '#{pane_id}' -t "$MAIN" -v    -l 1 "$hold")
LEFT=$("${T[@]}"  split-window -d -P -F '#{pane_id}' -t "$MAIN" -h -b -l 3 "$hold")
RIGHT=$("${T[@]}" split-window -d -P -F '#{pane_id}' -t "$MAIN" -h    -l 3 "$hold")

for p in "$TOP" "$BOT" "$LEFT" "$RIGHT"; do
  "${T[@]}" select-pane -t "$p" -P 'fg=colour12,bg=colour12'
done
"${T[@]}" select-pane -t "$BAN" -P 'fg=default,bg=default'    # das Banner steht auf dem Bildschirmblau
"${T[@]}" select-pane -t "$MAIN" -P 'fg=default,bg=default'
"${T[@]}" select-pane -t "$MAIN"

# Groessen halten, wenn das Fenster waechst oder schrumpft.
fix="resize-pane -t $TOP -y 3 ; resize-pane -t $BAN -y 4 ; resize-pane -t $BOT -y 1 ; resize-pane -t $LEFT -x 3 ; resize-pane -t $RIGHT -x 3 ; select-pane -t $MAIN"
"${T[@]}" set-hook -g client-resized "$fix"
# Tab zu = Sitzung zu, wie ohne Rahmen (dort beendet das SIGHUP claude). Sonst liefe claude
# im verwaisten Server unsichtbar weiter, haelt Last und steht im Deck. Erst beim Anhaengen
# setzen: vorher gesetzt beendet tmux 3.8 die noch nie angehaengte Sitzung sofort.
"${T[@]}" set-hook -g client-attached "$fix ; set -g destroy-unattached on"

# Maus nur fuer die Mitte: Klicks und Rad erreichen Claude Code, der Rahmen bleibt stumm.
is_main="#{==:#{pane_id},$MAIN}"
for key in MouseDown1Pane MouseDrag1Pane MouseDragEnd1Pane DoubleClick1Pane TripleClick1Pane MouseDown3Pane; do
  "${T[@]}" bind -n "$key" if -F "$is_main" "send-keys -M" ""
done
"${T[@]}" bind -n WheelUpPane   if -F "$is_main" "if -F '#{mouse_any_flag}' 'send-keys -M' 'if -F \"#{pane_in_mode}\" \"send-keys -M\" \"copy-mode -e\"'" ""
"${T[@]}" bind -n WheelDownPane if -F "$is_main" "send-keys -M" ""

if (( detach )); then
  print "$SOCK"
  exit 0
fi
exec "${T[@]}" attach -t c64
