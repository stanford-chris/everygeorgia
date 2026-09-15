#!/usr/bin/env python3
"""
crop_closure_check.py -- read-only sweep of the ad lane's own crops: did
clips.block_around's row-walk stop with room to spare, or right at the edge
of what it could safely justify?

Why this exists. The Cooke's clothing ad, posted 14 September 2026, closed
cleanly by every existing check (rights, vocabulary, ad_markers,
legibility) and still shipped truncated at both ends: nothing here had
ever asked whether the WALK's OWN stopping decision was a confident one,
only whether the words it kept were clean. clips.closure_margins() (15
September 2026) answers that for a single crop, already-returned box; this
re-derives and checks every recent ad post against it.

⚠️ AD LANE ONLY, and that is not laziness. closure_margins() only models
the walk's allow_display=True checks (a printed rule, the 2.2*med gap
ceiling, the display-heading allowance); market's own
PARA_GAP/MARKET_ROWS paragraph-break guard only ever fires when
allow_display is False, and is not modelled. Feeding a market post
through this would produce numbers that do not mean what they look like.
Extend to market only once that guard is modelled too -- see
closure_margins' own docstring in clips.py.

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

Usage:
    python3 crop_closure_check.py                 # last 7 days
    python3 crop_closure_check.py --days 14
    python3 crop_closure_check.py --margin 0.20    # the flagging floor
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import clips
import ghn_api
import rules

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "data", "post_state.json")

# A ratio under this (or negative, or the should-have-been-included flag,
# which reads as 0.0) is a near miss worth a look. The Cooke's ad, fixed,
# reads 0.41-0.60 on real content; comfortably above this floor.
MARGIN_FLOOR = 0.15


def load_state(path=STATE_FILE):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def recent_ad_posts(state, days, now=None):
    """Posted ad-lane entries from the last `days` days, per their own
    `at` timestamp. `now` is injectable for tests."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    out = []
    for p in state.get("posted", []):
        if p.get("lane") != "ad":
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
    return state.get("tried", {}).get("ad", {}).get(key)


def flag_from_margins(margins, floor=MARGIN_FLOOR):
    """The findings a set of closure_margins() report on its own -- pure,
    no network, so this is the part covered by injected fixtures rather
    than mocked HTTP. "rule" and "display-excluded-by-cap" are never
    flagged (both are confident, structural stops); `None` (nothing
    outside that edge) is never flagged; a "gap" or
    "should-have-been-included" reading below `floor` is."""
    CONFIDENT = {"rule", "display-excluded-by-cap"}
    findings = []
    for side, info in (margins or {}).items():
        if info is None or info["reason"] in CONFIDENT:
            continue
        ratio = info["ratio"]
        if ratio is None or ratio < floor:
            findings.append({"side": side, "reason": info["reason"],
                            "ratio": ratio, "text": info["text"]})
    return findings


def check_post(post, phrase, floor=MARGIN_FLOOR, log=print):
    """Re-derive the crop and its closure margins for one posted ad.
    Returns a findings list (possibly empty, meaning clean), or None if
    the page/phrase could not be re-derived at all (NOT CHECKED)."""
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
    hit = clips.find_phrase(c["words"], phrase)
    if not hit:
        return None
    pi = rules.PageInk(page)
    box = clips.block_around(pi, c, hit, allow_display=True, split_wide_headings=True)
    if not box:
        return None
    margins = clips.closure_margins(pi, c, box, allow_display=True)
    return flag_from_margins(margins, floor)


def post_url(post):
    rkey = post.get("uri", "").rsplit("/", 1)[-1]
    return f"https://bsky.app/profile/georgianewspapers.bsky.social/post/{rkey}"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--margin", type=float, default=MARGIN_FLOOR)
    args, unknown = ap.parse_known_args()
    if unknown:
        sys.exit(f"unrecognised argument(s): {' '.join(unknown)}")

    state = load_state()
    if state is None:
        print(f"crop closure check: NOT CHECKED -- {STATE_FILE} not found")
        return 0

    posts = recent_ad_posts(state, args.days)
    print(f"crop closure check: {len(posts)} ad post(s) in the last {args.days} day(s)")

    flagged = not_checked = 0
    for post in posts:
        phrase = phrase_for(state, post)
        label = f"{post['lccn']} {post['date']} p{post.get('seq')}"
        if not phrase:
            not_checked += 1
            print(f"  {label}: NOT CHECKED (no phrase on record)")
            continue
        findings = check_post(post, phrase, args.margin)
        if findings is None:
            not_checked += 1
            print(f"  {label}: NOT CHECKED (could not re-derive the crop)")
            continue
        if findings:
            flagged += 1
            print(f"  QUESTIONABLE {label} ({phrase!r}) {post_url(post)}")
            for f in findings:
                ratio = "n/a" if f["ratio"] is None else f"{f['ratio']:.2f}"
                print(f"    {f['side']}: {f['reason']} (ratio {ratio}) -- excluded: {f['text']!r}")

    if not flagged and not not_checked:
        print("  clean")
    print(f"\n{flagged} questionable, {not_checked} not checked, of {len(posts)} ad post(s)")
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
