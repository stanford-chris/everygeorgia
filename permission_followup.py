#!/usr/bin/env python3
"""
permission_followup.py -- the reminder that everygeorgia's permission request
to UGA has gone unanswered, and that a decision is owed.

Why this exists. HANDOFF.md says, of the email sent to dlgnwp@uga.edu and
gnp@uga.edu on 21 August 2026: "Silence is not permission; set a date to follow
up rather than letting it drift into a tacit yes." The second half was never
done. On 26 August 2026 a grep of the repo, the memory file and the observation
log found no follow-up date anywhere, no reminder and no job. The only thing
standing between the project and death by drift was somebody happening to ask.

⛔⛔ THIS SENDS NOTHING TO UGA AND MUST NEVER LEARN HOW. It mails Chris. The
decision to write to UGA a second time is his, it is editorial, and "do not
send a second email yet" was a deliberate call recorded on 21 August. A job
that re-contacted an institution unattended would override a human decision
while he slept. It prompts; it does not act.

⚠️ IT GOES QUIET THE DAY HE SAYS SO, and not before. `--resolved "<what
happened>"` writes data/permission_state.json and every later run exits 0 in
silence. There is no auto-detection of a reply: nothing here reads his mail,
and a reminder that guessed it had been answered would be the one failure this
cannot afford.

⚠️ IT REPEATS. A reminder that fires once and is missed is a reminder that
never happened. After the first date it nags every REPEAT_DAYS until resolved,
and the mail says how long the silence has run.

⚠️ `--snooze-until YYYY-MM-DD` is quiet, not resolved: it stays unresolved and
picks the normal nagging back up automatically once that date passes. Use it
when he already knows he's following up himself on a specific date and the
default 14-day cadence would nag before then. Unlike `--resolved` this never
needs a note saying what happened, because nothing has happened yet.

⚠️ launchd has no year field, so the plist's date fires ANNUALLY. That is
harmless here only because of the state file: once resolved, the run is a
no-op. Do not replace the state file with a one-shot job that deletes itself --
see [[reference_launchd_self_removing_job]].

Usage:
    python3 permission_followup.py --stdout        # print, mail nothing
    python3 permission_followup.py                 # mail if still unresolved
    python3 permission_followup.py --resolved "UGA said yes, with conditions"
    python3 permission_followup.py --snooze-until 2026-09-30
    python3 permission_followup.py --status
"""
import json
import os
import subprocess
import sys
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
STATE = os.path.join(HERE, "data", "permission_state.json")
SENT_ON = date(2026, 8, 21)          # the original email
NOT_BEFORE = date(2026, 9, 4)        # ⚠️ Two weeks after the email, and the
                                     # whole reason the job may run weekly. A
                                     # chase five days on is badgering; the
                                     # 21 August decision was "not yet", not
                                     # "never". Move this date, not the plist.
RECIPIENTS = "dlgnwp@uga.edu and gnp@uga.edu"
REPEAT_DAYS = 14
SUBJECT = "[claude] everygeorgia: UGA has not replied"


def load():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save(d):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, indent=2)
    os.replace(tmp, STATE)


def body(days, last):
    lines = [
        f"The everygeorgia permission request has been unanswered for {days} days.",
        "",
        f"  sent      {SENT_ON.isoformat()} to {RECIPIENTS}",
        f"  asked     permission to publish clippings from Georgia Historic",
        f"            Newspapers on a public Bluesky account",
        f"  status    nothing published, no account created. Correct, and it",
        f"            stays that way until they answer.",
    ]
    if last:
        lines.append(f"  reminded  last on {last}")
    lines += [
        "",
        "Nothing has been sent to UGA. This is a note to you, not a chase.",
        "The decision to write again is yours.",
        "",
        "The options, as they stood on 26 August 2026:",
        "",
        "  1. Send one follow-up. Ordinary correspondence, not badgering, and",
        "     late August is when a university library is least responsive.",
        "  2. Escalate to a named DLG staffer or phone the office. Read their",
        "     staff page first rather than guessing at a name.",
        "  3. Narrow the ask to the nameplate lane alone, which is a smaller",
        "     and easier yes than 'may I publish clippings'.",
        "  4. Decide the project waits indefinitely. The point is that it be",
        "     decided, rather than arrived at by drift.",
        "",
        "Worth putting in the follow-up if you send one: the rights join has",
        "since finished. 843 of 1,158 titles have a NoC-US issue and there are",
        "218,505 postable pre-1931 issues. The nameplate lane is built and",
        "measured, and none of the 843 postable titles carries slavery,",
        "lynching or Klan vocabulary in its own name.",
        "",
        "To stop this reminder:",
        "  python3 ~/Scripts/everygeorgia/permission_followup.py --resolved \"what happened\"",
        "",
        "Detail: ~/Scripts/everygeorgia/HANDOFF.md",
    ]
    return "\n".join(lines)


def observe(days):
    """One line in the shared log, so the Sunday estate-review sees it recur.

    Best-effort: a failure here must not change this script's exit status."""
    try:
        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "observe.py"), "add",
             "--source", "everygeorgia-followup", "--kind", "finding",
             "--key", "everygeorgia-uga-silence", "--quiet",
             f"UGA permission request unanswered for {days} days; "
             f"nothing published, decision owed"],
            check=False, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


def main():
    args = sys.argv[1:]
    stdout = "--stdout" in args
    status = "--status" in args
    resolved = None
    snooze_until = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--resolved" and i + 1 < len(args):
            i += 1; resolved = args[i]
        elif a.startswith("--resolved="):
            resolved = a.split("=", 1)[1]
        elif a == "--snooze-until" and i + 1 < len(args):
            i += 1; snooze_until = args[i]
        elif a.startswith("--snooze-until="):
            snooze_until = a.split("=", 1)[1]
        elif a not in ("--stdout", "--status"):
            sys.exit(f"unknown argument: {a}")
        i += 1

    st = load()
    if resolved is not None:
        if not resolved.strip():
            sys.exit("--resolved needs a note saying what happened")
        st["resolved_on"] = date.today().isoformat()
        st["resolution"] = resolved.strip()
        save(st)
        print(f"recorded: {st['resolved_on']} -- {resolved.strip()}")
        print("this reminder is now silent.")
        return 0

    if snooze_until is not None:
        try:
            datetime.strptime(snooze_until, "%Y-%m-%d")
        except ValueError:
            sys.exit("--snooze-until needs a YYYY-MM-DD date")
        st["snoozed_until"] = snooze_until
        save(st)
        print(f"snoozed: quiet until {snooze_until}, still unresolved")
        return 0

    days = (date.today() - SENT_ON).days
    if st.get("resolved_on"):
        if status:
            print(f"resolved {st['resolved_on']}: {st.get('resolution','')}")
        return 0

    snoozed_until = st.get("snoozed_until")
    snoozed_date = None
    if snoozed_until:
        try:
            snoozed_date = datetime.strptime(snoozed_until, "%Y-%m-%d").date()
        except ValueError:
            snoozed_date = None  # unparseable snooze is not a snooze

    if status:
        snooze_note = (f"; snoozed until {snoozed_until}"
                        if snoozed_date and date.today() < snoozed_date else "")
        print(f"unresolved, {days} days since {SENT_ON.isoformat()}; "
              f"first reminder due {NOT_BEFORE.isoformat()}; "
              f"last reminded {st.get('last_reminded','never')}{snooze_note}")
        return 0

    if not stdout and snoozed_date and date.today() < snoozed_date:
        return 0                          # snoozed; stay silent until the date

    if not stdout and date.today() < NOT_BEFORE:
        return 0                          # too soon to nag; stay silent

    last = st.get("last_reminded")
    if not stdout and last:
        try:
            if (date.today() - datetime.strptime(last, "%Y-%m-%d").date()).days < REPEAT_DAYS:
                return 0                      # nagged recently enough
        except ValueError:
            pass

    text = body(days, last)
    if stdout:
        print(SUBJECT)
        print()
        print(text)
        return 0

    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "estate_mail.py"),
                        SUBJECT], input=text.encode(), capture_output=True)
    if r.returncode != 0:
        print(f"mail failed: {r.stderr.decode().strip()}", file=sys.stderr)
        # ⚠️ Do NOT record a reminder that never arrived, or the repeat clock
        # starts on a mail nobody got.
        return 1
    st["last_reminded"] = date.today().isoformat()
    save(st)
    observe(days)
    print(f"reminded ({days} days unanswered)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
