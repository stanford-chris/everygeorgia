#!/bin/bash
# rights_join_tick.sh — one attempt at the DLG rights join. Fires on a timer from
# launchd; does nothing and exits 0 once the join has succeeded.
#
# ⚠️ Deliberately a SHORT job on a timer, not a long-lived watcher. launchd
# re-fires a StartInterval job after the machine wakes, so a timer survives sleep
# where a resident process does not.
#
# ⚠️ It probes before it works. DLG was returning 503 on 7 of 8 requests on
# 21 Aug 2026 and the join makes 1,088 of them; starting into that is thousands
# of retries against a service already shedding load. Only a clean 3/3 starts it.
# Cached pages under data/rights/ mean every partial attempt is progress.
set -uo pipefail
cd "$(dirname "$0")" || exit 1
LOG=data/await_dlg.log
OUT=data/georgia_rights.csv
UA="everygeorgia-roster/0.1 (scheduled; contact stanfordc+claude@mac.com)"
URL="https://dlg.usg.edu/records.json?per_page=1"
say(){ echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" >> "$LOG"; }

[ -f "$OUT" ] && exit 0            # done; nothing to do, and say nothing

ok=0
for _ in 1 2 3; do
  c=$(curl -sS --compressed -A "$UA" -L --max-time 40 -o /dev/null -w "%{http_code}" "$URL" || echo 000)
  [ "$c" = "200" ] && ok=$((ok+1))
  sleep 3
done

if [ "$ok" -lt 3 ]; then
  say "health $ok/3 — skipping"
  exit 0
fi

say "health 3/3 — running rights_join.py ($(ls data/rights 2>/dev/null | wc -l | tr -d ' ') pages already cached)"
python3 rights_join.py >> data/rights_join.log 2>&1
rc=$?
if [ -f "$OUT" ]; then
  say "join COMPLETED — $(wc -l < "$OUT" | tr -d ' ') rows"
else
  say "join exited $rc without a csv; $(ls data/rights 2>/dev/null | wc -l | tr -d ' ') pages cached, will retry"
fi
exit 0
