# LOAD "*",8,1  —  startet Claude Code, wie ein C64 ein Programm von Diskette laedt.
#
# Eingebunden ueber /deck setup: es kopiert diese Dateien nach ~/.claude/retro-deck/shell/ und
# traegt in ~/.zshrc einen markierten Block ein, der sie laedt. /deck uninstall nimmt beides zurueck.
#
#   LOAD "*",8,1            Tab auf das Terminal-Profil "C64", Einschaltbildschirm in voller
#                           Groesse: der Star-Trek-Tribut (trek.py), bei zu kleinem Fenster
#                           die tanzende Krabbe (boot.py); dann claude im
#                           C64-Rahmen (frame.sh: tmux, hellblaue Felder, Krabbe oben)
#   LOAD "*",8,1 --resume   alles nach dem C64-Teil geht an claude weiter
#   LOAD "*",8,1 RAHMEN     nimmt das Profil "C64 Rahmen" (hellblauer Grund) statt "C64"
#   LOAD "*",8,1 FAST       ohne Einschaltbildschirm, nur die drei Zeilen
#   LOAD "*",8,1 FLACH      ohne tmux-Rahmen, claude direkt im Tab
#   LOAD "ERIC",8,1         wie "*", aber mit New York statt der Enterprise (nyc.py): die
#                           Fassung fuer Eric, n8n Ambassador NYC; LOAD "BERTRAND",8,1 ebenso
#   LOAD "ARNO",8,1         Telekom in Magenta (magenta.py), fuer Arno von der Telekom
#   RUN                     nur claude, ohne alles
#
# Der Rahmen braucht tmux (brew install tmux); fehlt es oder laeuft die Shell schon in tmux,
# startet claude direkt.
#
# Nach LOAD meldet sich die Shell mit READY. statt mit dem gewohnten Prompt (bis zum
# naechsten Oeffnen des Tabs). Die Profile "C64" und "C64 Rahmen" importiert /deck setup.

typeset -g C64_RETRO_DIR="${${(%):-%x}:A:h}"

# Das C64-Theme gilt nur fuer Sitzungen aus LOAD: Claude Code zeichnet mit dark-ansi in den
# 16 Profilfarben (VIC-II), ein schlichtes `claude` in einem anderen Tab bleibt beim globalen
# Theme. --settings legt die Einstellung nur fuer diese eine Sitzung darueber.
C64_THEME='{"theme":"dark-ansi"}'

LOAD() {
  local profile="C64" fast=0 flat=0 disk='*' a
  local -a args
  for a in "$@"; do
    case "${(U)a}" in
      ERIC|ERIC,8|ERIC,8,1|BERTRAND|BERTRAND,8|BERTRAND,8,1|ARNO|ARNO,8|ARNO,8,1) disk=${(U)a%%,*}; continue ;;
    esac
    case "$a" in
      '*,8,1'|'*,8'|'*') ;;                # der C64-Teil, verschluckt
      RAHMEN|rahmen) profile="C64 Rahmen" ;;
      FAST|fast) fast=1 ;;
      FLACH|flach|FLAT|flat) flat=1 ;;
      *) args+=("$a") ;;
    esac
  done
  if [[ "$TERM_PROGRAM" == Apple_Terminal && -n "$TTY" ]]; then
    osascript - "$TTY" "$profile" >/dev/null 2>&1 <<'APPLESCRIPT'
on run argv
  set wanted to item 1 of argv
  set prof to item 2 of argv
  tell application "Terminal"
    repeat with w in windows
      repeat with t in tabs of w
        if tty of t is wanted then
          -- Ein Profilwechsel setzt die Fenstergroesse des Profils; das Fenster soll bleiben.
          set b to bounds of w
          set current settings of t to settings set prof
          set bounds of w to b
        end if
      end repeat
    end repeat
  end tell
end run
APPLESCRIPT
  fi
  if (( fast )) || [[ ! -t 1 ]] || ! command -v python3 >/dev/null; then
    print ""
    print "SEARCHING FOR $disk"
    sleep 0.4
    print "LOADING"
    sleep 0.4
    print "READY."
    sleep 0.3
  else
    if [[ $disk == '*' ]]; then
      python3 "$C64_RETRO_DIR/trek.py" || python3 "$C64_RETRO_DIR/boot.py"
    else
      local intro=nyc.py
      [[ $disk == ARNO ]] && intro=magenta.py
      python3 "$C64_RETRO_DIR/$intro" "$disk" || python3 "$C64_RETRO_DIR/boot.py"
    fi
  fi
  # Die Shell danach im C64-Ton: READY. als Prompt, Eingabe darunter.
  PROMPT=$'\n%F{12}READY.%f\n'
  RPROMPT=''
  if (( ! flat )) && [[ -z "${TMUX:-}" && -t 1 ]] && command -v tmux >/dev/null; then
    "$C64_RETRO_DIR/frame.sh" claude --settings "$C64_THEME" "${args[@]}"
  else
    claude --settings "$C64_THEME" "${args[@]}"
  fi
}

# RUN allein startet ebenfalls — fuer alle, die nach LOAD aus Gewohnheit RUN tippen.
RUN() { claude "$@" }
