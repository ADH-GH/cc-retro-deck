#!/usr/bin/env bash
# Reopens the Claude Code sessions the deck last saw running, each with
# `claude --resume <sessionId>` in its working directory, one Terminal.app
# window (default) or tab (--tabs, needs Accessibility for System Events) each.
# Sessions whose process is still alive are skipped, so running this from a
# surviving tab reopens only what was lost.
set -euo pipefail

mode="${1:---windows}"
snapshot="${HOME}/.claude/retro-deck/last-deck.json"
registry="${HOME}/.claude/sessions"

[[ -f "$snapshot" ]] || { echo "No snapshot at $snapshot yet. Run a session with the retro-deck mod first."; exit 1; }
command -v python3 >/dev/null || { echo "python3 missing"; exit 1; }

# sessionId<TAB>cwd per line, tty order.
rows=$(python3 -I -c '
import json,sys
d=json.load(open(sys.argv[1]))
for s in d.get("sessions",[]):
    print(s["sessionId"]+"\t"+s["cwd"])
' "$snapshot")

# Alive sessionIds from the registry.
alive=$(python3 -I -c '
import json,os,sys,glob
out=[]
for f in glob.glob(os.path.join(sys.argv[1],"*.json")):
    try:
        d=json.load(open(f))
        os.kill(int(d["pid"]),0)
        out.append(d["sessionId"])
    except Exception:
        pass
print("\n".join(out))
' "$registry")

opened=0
while IFS=$'\t' read -r sid cwd; do
  [[ -z "$sid" ]] && continue
  if grep -qx "$sid" <<<"$alive"; then continue; fi
  [[ -d "$cwd" ]] || cwd="$HOME"
  cmd="cd $(printf '%q' "$cwd") && claude --resume $sid"
  if [[ "$mode" == "--tabs" ]]; then
    osascript - "$cmd" <<'APPLESCRIPT'
on run argv
  tell application "Terminal" to activate
  tell application "System Events" to keystroke "t" using command down
  delay 0.4
  tell application "Terminal" to do script (item 1 of argv) in front window
end run
APPLESCRIPT
  else
    osascript -e 'on run argv' -e 'tell application "Terminal" to do script (item 1 of argv)' -e 'end run' -- "$cmd" >/dev/null
  fi
  opened=$((opened+1))
  sleep 0.6
done <<<"$rows"

echo "Reopened $opened session(s) from $(date -r "$(python3 -I -c 'import json,sys;print(int(json.load(open(sys.argv[1]))["savedAt"]/1000))' "$snapshot")" '+%Y-%m-%d %H:%M')."
