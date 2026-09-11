#!/bin/bash
# everygeorgia_launch.sh — the one-off opening of Georgia in Print, 11 September 2026.
#
# Posts the six-post pinned thread (everygeorgia_post.py --launch), kickstarts
# the daily job once so the first clipping (the Dawson Journal of 14 June 1867)
# follows the thread within a minute, then removes its own launchd job so it
# can never fire again.
#
# ⚠️ Timing. 20:00 Asia/Seoul on Friday 11 September, which is 7:00 a.m. that
# Friday in Georgia: his instruction at 18:16 KST the same day, "move the first
# post up to 7a ET today. I wanna get this going." It had been 08:40 KST on
# Saturday the 12th ("post it tomorrow morning, so I can catch it if something
# goes wrong"), with the daily 09:10 slot posting the first clipping; the
# kickstart below replaces that half-hour gap, since the next daily slot after
# 20:00 is 23:10. The 23:10 and 09:10 slots then carry on as scheduled.
#
# ⚠️ It does NOT self-remove if the thread fails. A half-posted thread has to be
# repaired by hand, and leaving the job in place is the only signal that
# something needs looking at. The poster refuses a second --launch once the
# thread is recorded in data/post_state.json, so a job left in place cannot
# double-post; it can only fire again on 12 September 2027, which is what the
# `rm` below prevents on the success path.
#
#     bash everygeorgia_launch.sh --dry-run    # prints the thread, posts nothing,
#                                              # removes nothing

export PATH="/Library/Frameworks/Python.framework/Versions/3.13/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
PY="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
HERE="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.chrisstanford.everygeorgia-launch"
DRY=""
[ "${1:-}" = "--dry-run" ] && DRY="--dry-run"

say() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)  $*"; }
notify() { osascript -e "display notification \"$1\" with title \"Georgia in Print\"" 2>/dev/null; }

say "=== opening Georgia in Print ${DRY:+(dry run)} ==="
"$PY" "$HERE/everygeorgia_post.py" --launch $DRY
launch_rc=$?

if [ $launch_rc -ne 0 ]; then
  say "!! the thread failed (exit $launch_rc). Leaving this job in place deliberately."
  notify "Launch FAILED. See ~/Library/Logs/everygeorgia-launch.log"
  exit $launch_rc
fi
if [ -n "$DRY" ]; then
  say "=== dry run: nothing posted, job left in place ==="
  exit 0
fi

say "--- removing this one-off job"
# ⚠️ THE ORDER IS LOAD-BEARING: `launchctl bootout` terminates this job's own
# processes, so the script dies ON that line. Delete the plist and say
# everything worth saying FIRST; the bootout goes last and is allowed to kill
# us. StartCalendarInterval has no year field, so a surviving plist means
# `Month 9, Day 12` fires every 12 September. See reference_launchd_self_removing_job.
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
rm -f "$PLIST"
if [ -e "$PLIST" ]; then
  say "!! $PLIST is STILL THERE. Remove it by hand or this fires again on 12 Sep 2027."
  notify "Posted, but the one-off job did not remove itself. See the log."
else
  say "    plist deleted; the job cannot reload at login"
  notify "Posted and pinned. Kickstarting the daily job for the first clipping."
fi

# The first clipping, now rather than at the next daily slot. `kickstart` runs
# the daily job exactly as launchd would (its own log, its own Keychain read,
# verified under launchd on 11 September). The poster's gate reads the state
# file --launch just wrote, so this is the first run that can post.
say "--- kickstarting the daily job for the first clipping"
launchctl kickstart "gui/$(id -u)/com.chrisstanford.everygeorgia" \
  && say "    kickstarted; see ~/Library/Logs/everygeorgia.log" \
  || say "!! kickstart failed; the 23:10 slot will post the first clipping instead"
say "=== done. The daily slots (23:10 and 09:10 KST) carry on from here. ==="

# Last, deliberately: this terminates the script, so nothing may follow it.
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
