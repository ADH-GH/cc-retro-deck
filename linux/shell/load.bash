# LOAD "*",8,1  —  startet Claude Code, wie ein C64 ein Programm von Diskette laedt (Linux, bash).
#
# Eingebunden ueber /deck setup: es kopiert diese Dateien nach ~/.claude/retro-deck/shell/ und
# traegt in ~/.bashrc einen markierten Block ein, der sie laedt. /deck uninstall nimmt beides zurueck.
#
#   LOAD "*",8,1            Tab in C64-Farben, Einschaltbildschirm: der Star-Trek-Tribut (trek.py),
#                           bei zu kleinem Fenster die tanzende Krabbe (boot.py),
#                           dann claude im C64-Rahmen (frame.sh: tmux, hellblaue Felder, Krabbe oben)
#   LOAD "*",8,1 --resume   alles nach dem C64-Teil geht an claude weiter
#   LOAD "*",8,1 RAHMEN     hellblauer Grund statt dunkelblauem Bildschirm
#   LOAD "*",8,1 FAST       ohne Einschaltbildschirm, nur die drei Zeilen
#   LOAD "*",8,1 FLACH      ohne tmux-Rahmen, claude direkt im Tab
#   RUN                     nur claude, ohne alles
#   SYS 64738               Reset: Farben und Prompt des Tabs wie vorher
#
# Laeuft der Rahmen schon (etwa in einem anderen Tab), wird die neue Sitzung ein weiteres
# Fenster darin, und dieser Tab haengt sich an denselben Rahmen.
#
# Statt eines Terminal-Profils wie auf dem Mac setzt LOAD die Farben per Steuersequenz
# (OSC 4/10/11/12) nur in diesem Tab; GNOME Terminal und die meisten Linux-Terminals
# verstehen das. Schliessen des Tabs oder SYS 64738 setzt sie zurueck.

C64_RETRO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colodore-Palette, ANSI 0-15 belegt wie in den Mac-Profilen (make-profiles.py).
# ANSI 8 traegt die Grundfarbe: Claude Code malt damit Flaechen, und grau passt nicht ins Bild.
_c64_colors() {   # _c64_colors screen|rahmen
  local black=000000 white=FFFFFF red=813338 cyan=75CEC8 purple=8E3C97 green=56AC4D
  local blue=2E2C9B yellow=EDF171 lightRed=C46C71 lightGreen=A9FF9F lightBlue=706DEB lightGrey=B2B2B2
  local bg fg cursor
  if [ "$1" = rahmen ]; then bg=$lightBlue fg=$white cursor=$white
  else bg=$blue fg=$lightBlue cursor=$lightBlue; fi
  local pal=($black $red $green $yellow $lightBlue $purple $cyan $lightGrey
             $bg $lightRed $lightGreen $yellow $lightBlue $purple $cyan $white)
  local i out="" c
  for i in "${!pal[@]}"; do
    c=${pal[$i]}
    out+="\e]4;$i;rgb:${c:0:2}/${c:2:2}/${c:4:2}\a"
  done
  for i in 10:$fg 11:$bg 12:$cursor; do
    c=${i#*:}
    out+="\e]${i%%:*};rgb:${c:0:2}/${c:2:2}/${c:4:2}\a"
  done
  printf '%b' "$out"
}

# Das C64-Theme gilt nur fuer Sitzungen aus LOAD: Claude Code zeichnet mit dark-ansi in den
# 16 Profilfarben (VIC-II), ein schlichtes `claude` in einem anderen Tab bleibt beim globalen
# Theme. --settings legt die Einstellung nur fuer diese eine Sitzung darueber.
C64_THEME='{"theme":"dark-ansi"}'

LOAD() {
  local look=screen fast=0 flat=0 a
  local -a args=()
  for a in "$@"; do
    case "$a" in
      '*,8,1'|'*,8'|'*') ;;                # der C64-Teil, verschluckt
      RAHMEN|rahmen) look=rahmen ;;
      FAST|fast) fast=1 ;;
      FLACH|flach|FLAT|flat) flat=1 ;;
      *) args+=("$a") ;;
    esac
  done
  [ -t 1 ] && _c64_colors "$look"
  if (( fast )) || [ ! -t 1 ] || ! command -v python3 >/dev/null; then
    printf '\nSEARCHING FOR *\n'; sleep 0.4
    printf 'LOADING\n'; sleep 0.4
    printf 'READY.\n'; sleep 0.3
  else
    python3 "$C64_RETRO_DIR/trek.py" || python3 "$C64_RETRO_DIR/boot.py"
  fi
  # Die Shell danach im C64-Ton: READY. als Prompt (ANSI 12 = Hellblau), Eingabe darunter.
  [ -n "${_C64_PS1+x}" ] || _C64_PS1="$PS1"
  PS1='\n\[\e[94m\]READY.\[\e[0m\]\n'
  # Rahmen nur ausserhalb von tmux oder im eigenen Rahmen-Server, nie verschachtelt.
  if (( ! flat )) && [ -t 1 ] && command -v tmux >/dev/null \
     && { [ -z "${TMUX:-}" ] || [[ "$TMUX" == */c64,* ]]; }; then
    bash "$C64_RETRO_DIR/frame.sh" claude --settings "$C64_THEME" "${args[@]}"
  else
    claude --settings "$C64_THEME" "${args[@]}"
  fi
}

# RUN allein startet ebenfalls — fuer alle, die nach LOAD aus Gewohnheit RUN tippen.
RUN() { claude "$@"; }

# SYS 64738 ist der Reset-Vektor des C64: Farben des Tabs und Prompt zurueck.
SYS() {
  if [ "${1:-}" != 64738 ]; then echo "?SYNTAX  ERROR"; return 1; fi
  printf '\e]104\a\e]110\a\e]111\a\e]112\a'
  if [ -n "${_C64_PS1+x}" ]; then PS1="$_C64_PS1"; unset _C64_PS1; fi
  clear
}
