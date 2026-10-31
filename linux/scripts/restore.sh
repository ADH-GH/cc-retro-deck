#!/usr/bin/env bash
# Reopens the Claude Code sessions the deck last saw running, each with
# `claude --resume <sessionId>` in its working directory (Linux): a window in the
# C64 frame if it runs, else a GNOME Terminal tab (see open-session.sh). The
# --tabs/--windows flag of the Mac version is accepted and ignored.
# Sessions whose process is still alive are skipped, so running this from a
# surviving tab reopens only what was lost.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
  bash "$here/open-session.sh" "$cwd" --resume "$sid" >/dev/null </dev/null
  opened=$((opened+1))
  sleep 0.6
done <<<"$rows"

# GNU date has no `-r <epoch>`; python formats the snapshot time on every system.
echo "Reopened $opened session(s) from $(python3 -I -c 'import json,sys,time;print(time.strftime("%Y-%m-%d %H:%M",time.localtime(json.load(open(sys.argv[1]))["savedAt"]/1000)))' "$snapshot")."
