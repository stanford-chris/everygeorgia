#!/usr/bin/env python3
"""
crop_closure_check.py -- read-only sweep of every lane's own crop: did the
lane's own closing walk stop with room to spare, or right at the edge of
what it could safely justify?

Why this exists. The Cooke's clothing ad, posted 14 September 2026, closed
cleanly by every existing check (rights, vocabulary, ad_markers,
legibility) and still shipped truncated at both ends: nothing here had
ever asked whether the WALK's OWN stopping decision was a confident one,
only whether the words it kept were clean. clips.closure_margins() (15
September 2026) answers that by running block_around ITSELF with its own
instrumentation on, so the reason reported is always block_around's real
one, never a reconstruction.

⚠️ The ad and market lanes came first, and market was DELIBERATELY held
back at first: closure_margins originally tried to reconstruct the stop
reason from the finished box's own y-range, and on a dense market table
that reconstruction picked the wrong row as "included" (the box's own
padding overlapped the next EXCLUDED row) and reported a phantom near
miss with a zero gap. Fixed by having block_around record its OWN reason
at the exact moment it stops, rather than guessing from the outside --
see closure_margins' own docstring in clips.py. Both lanes' searched
phrases are read from data/post_state.json's own `tried[lane]` map,
which is also what supplies `seed` for market's PARA_GAP grace-period
check.

⚠️ The other four lanes were added 15 September 2026, each with its OWN
closing mechanism -- none reusable via closure_margins as it stands --
instrumented the SAME way, live at the moment of its own stop, never
reconstructed: headline_closure_margins/article_closure_margins in
clips.py (items.box_with_deck's down-walk, and the article paragraph's
own tight-line loop), pictures.cartoon_closure_margins (frame()'s
caption-line walk), and nameplate_crop.nameplate_closure_margins
(ink_bottom()'s own "already clear" short-circuit -- the one place in
that lane a wrong call is never re-examined by anything downstream).
Neither headline nor article needs a search phrase at all: both pick
their item deterministically from the page, so `tried[lane]` is only
ever consulted for "ad" and "market". See LANES below for which kind
each lane is and CONFIDENT_REASONS for which of each lane's own reasons
are structural stops rather than near misses.

ADVISORY ONLY. This gates nothing and posts nothing, changes nothing and
deletes nothing: it reports a post that might be worth a second look, and
the decision -- delete and repost, or leave it -- stays with a person, per
feedback_delete_and_repost_bad_bot_post in auto-memory.

Identity comes from data/post_state.json, not the public feed: `posted`
names lccn/date/edition/seq/lane for every real post, and `tried[lane]`
maps "lccn:date:seq" to the search phrase used, which is what lets the
exact same crop be re-derived. A post whose phrase or page can no longer
be re-derived is reported NOT CHECKED, never as a pass -- the dangerous
state (a real near miss) and the healthy one must not look the same on a
source this script could not read.

Scheduled weekly (Friday 10:00, com.chrisstanford.everygeorgiacropclosure,
~/Library/LaunchAgents, no mirror in ~/Scripts -- see the general estate's
own warning on why a job bootstrapped anywhere else does not survive a
reboot). Silent on a clean run, same as every other audit in this estate:
mails only when something is flagged, or when the check could not run at
all for the whole window (the "dangerous state and the healthy one must
not look the same" rule applied to the check's own health, not just a
crop's). Reuses ~/Scripts/estate_mail.py and ~/Scripts/observe.py rather
than a second copy of either, the same way permission_followup.py does in
this same repo.

Usage:
    python3 crop_closure_check.py                 # last 7 days, mails if warranted
    python3 crop_closure_check.py --days 14
    python3 crop_closure_check.py --margin 0.20    # the flagging floor
    python3 crop_closure_check.py --stdout         # print only, mail nothing
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import clips
import ghn_api
import nameplate_crop as npc
import pictures
import rules

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "data", "post_state.json")
SCRIPTS = os.path.join(os.path.expanduser("~"), "Scripts")

# Per-lane re-derivation. "search" (ad, market) re-finds the block around a
# recorded search phrase via clips.closure_margins/block_around; the other
# four pick their own item deterministically from the page and need no
# phrase at all -- see check_post() below for how each "kind" is dispatched.
LANES = {
    "ad": {"kind": "search", "allow_display": True, "max_frac": None},
    "market": {"kind": "search", "allow_display": False, "max_frac": "MARKET_MAX_FRAC"},
    "headline": {"kind": "headline"},
    "article": {"kind": "article"},
    "cartoon": {"kind": "cartoon"},
    "nameplate": {"kind": "nameplate"},
}
LANES["market"]["max_frac"] = clips.MARKET_MAX_FRAC

# A ratio under this is a near miss worth a look. The Cooke's ad, fixed,
# reads 0.41-0.60 on real content; comfortably above this floor.
MARGIN_FLOOR = 0.15

# Reasons any lane's closure diagnostics can report that are CONFIDENT,
# structural stops -- never flagged regardless of ratio (most have none).
# Only "gap", "paragraph-gap", "caption-count-cap" and "clear" carry a
# ratio worth comparing to MARGIN_FLOOR; everything else here is a fixed
# rule, a different item, a tier, a reach bound or a cap this script has
# no business second-guessing. See each producing function's own
# docstring (clips.block_around, items.box_with_deck, clips._article_span,
# pictures._caption_edge, nameplate_crop.ink_bottom) for what each reason
# means in its own lane.
CONFIDENT_REASONS = {
    "rule", "display-boundary", "row-count-cap", "cap",       # ad / market
    "different-item", "boundary", "tier", "height-cap", "iteration-cap",   # headline
    "indent",                                                  # article
    "reach",                                                   # cartoon
    "walked",                                                  # nameplate
}


def load_state(path=STATE_FILE):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def recent_posts(state, days, lanes=tuple(LANES), now=None):
    """Posted entries in `lanes` from the last `days` days, per their own
    `at` timestamp. `now` is injectable for tests."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    out = []
    for p in state.get("posted", []):
        if p.get("lane") not in lanes:
            continue
        try:
            at = datetime.fromisoformat(p["at"])
        except (KeyError, ValueError, TypeError):
            continue
        if at >= cutoff:
            out.append(p)
    return out


def phrase_for(state, post):
    key = f"{post['lccn']}:{post['date']}:{post['seq']}"
    return state.get("tried", {}).get(post.get("lane"), {}).get(key)


def flag_from_margins(margins, floor=MARGIN_FLOOR):
    """The findings a set of closure_margins() report on its own -- pure,
    no network, so this is the part covered by injected fixtures rather
    than mocked HTTP. A CONFIDENT_REASONS stop is never flagged; `None`
    (nothing outside that edge) is never flagged; a "gap" or
    "paragraph-gap" reading below `floor` is."""
    findings = []
    for side, info in (margins or {}).items():
        if info is None or info["reason"] in CONFIDENT_REASONS:
            continue
        ratio = info["ratio"]
        if ratio is None or ratio < floor:
            findings.append({"side": side, "reason": info["reason"],
                            "ratio": ratio, "text": info["text"]})
    return findings


def check_post(post, phrase, floor=MARGIN_FLOOR, log=print):
    """Re-derive the crop and its closure margins for one posted item, in
    whatever lane it is. Returns a findings list (possibly empty, meaning
    clean), or None if the page/phrase could not be re-derived at all, the
    lane's own closing walk itself refused the crop, or the lane isn't one
    this script covers (NOT CHECKED either way)."""
    lane_params = LANES.get(post.get("lane"))
    if lane_params is None:
        return None
    kind = lane_params["kind"]

    if kind == "nameplate":
        # ⚠️ The one lane that fetches its own page: nameplate_closure_
        # margins() re-derives the band from lccn/date/edition directly
        # (it needs a real image fetch that the other lanes' OCR-only
        # re-derivation never does), so there is no shared `pages` lookup
        # to do first the way the other five lanes share below.
        try:
            margins = npc.nameplate_closure_margins(post["lccn"], post["date"],
                                                     post.get("edition", 1))
        except (ghn_api.FetchError, ValueError) as e:
            log(f"  {post['lccn']} {post['date']}: could not refetch ({e})")
            return None
        if margins is None:
            return None
        return flag_from_margins(margins, floor)

    try:
        pages = ghn_api.issue_pages(post["lccn"], post["date"], post.get("edition", 1))
    except (ghn_api.FetchError, ValueError) as e:
        log(f"  {post['lccn']} {post['date']}: could not refetch ({e})")
        return None
    seq = post.get("seq", 1)
    if seq < 1 or seq > len(pages):
        return None
    page = pages[seq - 1]
    c = page.coords()

    if kind == "search":
        hit = clips.find_phrase(c["words"], phrase)
        if not hit:
            return None
        pi = rules.PageInk(page)
        margins = clips.closure_margins(pi, c, hit, lane_params["allow_display"],
                                        max_frac=lane_params["max_frac"],
                                        split_wide_headings=True)
    elif kind == "headline":
        margins = clips.headline_closure_margins(c, page)
    elif kind == "article":
        margins = clips.article_closure_margins(c, page)
    elif kind == "cartoon":
        pi = rules.PageInk(page)
        margins = pictures.cartoon_closure_margins(pi, c, page)
    else:                                            # pragma: no cover
        return None

    if margins is None:
        return None      # the lane's own closing walk refused this crop
    return flag_from_margins(margins, floor)


def post_url(post):
    rkey = post.get("uri", "").rsplit("/", 1)[-1]
    return f"https://bsky.app/profile/georgianewspapers.bsky.social/post/{rkey}"


def send_mail(subject, body):
    """Best-effort, matching permission_followup.py in this same repo: a
    failed send must not be silent (it prints to stderr, caught in the
    log), but it also must not crash the run -- a mail that could not go
    out is not a reason to also lose the exit code the caller relies on."""
    try:
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "estate_mail.py"), subject],
                           input=body.encode(), capture_output=True, timeout=60)
        if r.returncode != 0:
            print(f"mail failed: {r.stderr.decode().strip()}", file=sys.stderr)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"mail failed: {e}", file=sys.stderr)


def log_observe(text):
    """One line in the shared log, so the Sunday estate-review sees a
    recurring pattern. Best-effort, same as permission_followup.py's own
    observe() -- a failure here must not change this script's exit status."""
    try:
        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "observe.py"), "add",
             "--source", "crop-closure-check", "--kind", "finding",
             "--key", "everygeorgia-crop-closure", "--quiet", text],
            check=False, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--margin", type=float, default=MARGIN_FLOOR)
    ap.add_argument("--stdout", action="store_true", help="print only, mail nothing")
    args, unknown = ap.parse_known_args()
    if unknown:
        sys.exit(f"unrecognised argument(s): {' '.join(unknown)}")

    lines = []

    def log(msg=""):
        lines.append(msg)

    state = load_state()
    if state is None:
        log(f"crop closure check: NOT CHECKED -- {STATE_FILE} not found")
        report = "\n".join(lines)
        print(report)
        if not args.stdout:
            send_mail("[claude] everygeorgia: crop closure check could not run", report)
            log_observe(f"post_state.json not found at {STATE_FILE}")
        return 0

    posts = recent_posts(state, args.days)
    log(f"crop closure check: {len(posts)} post(s) (all six lanes) in the last {args.days} day(s)")

    flagged = not_checked = 0
    for post in posts:
        lane_params = LANES.get(post.get("lane"), {})
        label = f"{post.get('lane')} {post['lccn']} {post['date']} p{post.get('seq')}"
        # ⚠️ Only the "search" lanes (ad, market) need a phrase on record --
        # headline, article, cartoon and nameplate all pick their own item
        # deterministically from the page, so a missing phrase there is not
        # a reason to skip them.
        phrase = None
        if lane_params.get("kind") == "search":
            phrase = phrase_for(state, post)
            if not phrase:
                not_checked += 1
                log(f"  {label}: NOT CHECKED (no phrase on record)")
                continue
        findings = check_post(post, phrase, args.margin, log=log)
        if findings is None:
            not_checked += 1
            log(f"  {label}: NOT CHECKED (could not re-derive the crop)")
            continue
        if findings:
            flagged += 1
            suffix = f" ({phrase!r})" if phrase else ""
            log(f"  QUESTIONABLE {label}{suffix} {post_url(post)}")
            for f in findings:
                ratio = "n/a" if f["ratio"] is None else f"{f['ratio']:.2f}"
                log(f"    {f['side']}: {f['reason']} (ratio {ratio}) -- excluded: {f['text']!r}")

    if not flagged and not not_checked:
        log("  clean")
    log(f"\n{flagged} questionable, {not_checked} not checked, of {len(posts)} post(s)")

    report = "\n".join(lines)
    print(report)

    if args.stdout:
        return 1 if flagged else 0

    # ⚠️ A fully-unreadable window mails too, not just a flagged crop: a
    # week where nothing could be re-derived must not look like a clean
    # week to whoever reads the mailbox, same reasoning as every other
    # NOT-CHECKED-is-not-a-pass rule in this estate.
    if flagged:
        n = flagged
        subject = f"[claude] everygeorgia: {n} questionable crop{'s' if n != 1 else ''}"
        send_mail(subject, report)
        log_observe(f"{flagged} questionable crop(s) of {len(posts)} checked "
                   f"in the last {args.days} days")
    elif posts and not_checked == len(posts):
        send_mail("[claude] everygeorgia: crop closure check could not check any posts", report)
        log_observe(f"could not re-derive any of {len(posts)} post(s) "
                   f"in the last {args.days} days")

    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
