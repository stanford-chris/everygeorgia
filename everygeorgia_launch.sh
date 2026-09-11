#!/bin/bash
# everygeorgia_launch.sh — the one-off opening of Georgia in Print, 12 September 2026.
#
# Posts the six-post pinned thread (everygeorgia_post.py --launch), then removes
# its own launchd job so it can never fire again. The daily job posts the first
# clipping, the Dawson Journal of 14 June 1867, at 09:10 the same morning.
#
# ⚠️ Timing. 08:40 Asia/Seoul on Saturday 12 September, his instruction of the
# evening before: "post it tomorrow morning, so I can catch it if something goes
# wrong." Thirty minutes ahead of the 09:10 daily slot, so the thread is up
# before the first clipping and there is a run to watch. 7:40 p.m. Friday in
# Georgia.
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
  notify "Posted and pinned. The daily job posts the Dawson Journal at 09:10."
fi
say "=== done. The daily job posts the first clipping at 09:10. ==="

# Last, deliberately: this terminates the script, so nothing may follow it.
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
