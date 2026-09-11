#!/bin/bash
# everygeorgia_second_post.sh — one-off: the second clipping on launch day,
# 11 September 2026, at 20:20 KST (7:20 a.m. Eastern), two hours after the
# thread. His instruction at 18:20 KST: "follow up with a second post in a
# couple hours." The next daily slot was 23:10, so this kickstarts the daily
# job once, then removes its own launchd job. Same shape as
# everygeorgia_launch.sh: delete the plist and say everything first, bootout
# last, because bootout kills this script (reference_launchd_self_removing_job).
LABEL="com.chrisstanford.everygeorgia-second"
say() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)  $*"; }
say "=== second clipping: kickstarting the daily job ==="
launchctl kickstart "gui/$(id -u)/com.chrisstanford.everygeorgia" \
  && say "    kickstarted; see ~/Library/Logs/everygeorgia.log" \
  || say "!! kickstart failed; the 23:10 slot posts next"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
rm -f "$PLIST"
[ -e "$PLIST" ] && say "!! $PLIST is STILL THERE; remove it by hand or this fires every 11 September" \
                || say "    plist deleted"
say "=== done ==="
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
