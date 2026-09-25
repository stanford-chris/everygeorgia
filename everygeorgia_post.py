#!/usr/bin/env python3
"""
everygeorgia_post.py -- post one nameplate clipping from Georgia Historic
Newspapers to Bluesky, as @georgianewspapers.bsky.social.

Permission: UGA Libraries, by email on 10 September 2026, to the request sent
21 August. One condition: credit the Digital Library of Georgia. Every post
does, in the citation
form from the GHN FAQ that the request promised, ending "Presented online by
the Digital Library of Georgia." The other promises in that email are kept
here too: NoC-US issues only (gates.py), an identifying User-Agent
(ghn_api.UA), a handful of cached calls a day from one machine on a schedule,
and the sensitive vocabulary screened on the WHOLE page before any part of it
is used.

⚠️ SELECTION, NOT SUPPLY. 836 titles hold 218,505 postable pre-1931 issues,
so the feed's character is entirely a matter of which are chosen. The order
is one issue per TITLE, titles in a fixed shuffled order, so every paper in
the roster posts once before any posts twice (a pass), and within a title the
date is drawn by a seeded shuffle so the same title shows a different year
each pass. Without the per-title rule the Atlanta Georgian's 14,185 issues
would be one post in fifteen. See reference_bot_variety_is_selection_not_supply.

⚠️ REVIEW IS NOT A REFUSAL, AND IT DOES NOT BLOCK THE RUN. A page whose body
carries slavery, lynching or Klan vocabulary comes back REVIEW from gates.py:
the crop is fine, the page it links to is not, and a person decides. That is
logged to data/review.jsonl for Chris and the run moves to the next date of
the same title, because for a nameplate a REVIEW costs only a change of date:
the masthead is the same picture next week. Nothing REVIEW is ever posted
by this script, and nothing REFUSED is ever posted by anyone.

⚠️ BOUNDED. At most TITLES_PER_RUN titles and TRIES_PER_TITLE dates each, so
a bad morning costs about 120 API calls and a normal one about 15. A title
that yields nothing in a pass is skipped for that pass, never for good.

⚠️ THE LAUNCH THREAD GATES THE DAILY POSTS. Before `--launch` has run, a
scheduled run prints one line and exits 0 (bothealthcheck and harden check 5
read non-zero exits as faults, and a job loaded ahead of its opening must not
raise them). After it, a missing thread is a fault: the account would open
with a masthead from Abbeville and no explanation of what any of it is.

⚠️ A dry run still APPENDS TO data/review.jsonl. It writes no post and no
state, but a REVIEW it meets is a page a person should see whether or not the
run was real, and a preview that discarded it would show a clean feed drawn
from a queue nobody was told about. Named here because this estate has one
documented case of a "writes nothing" flag that wrote something.

⚠️ Bare run posts live; --dry-run previews. That is this estate's convention
for scheduled bots (the reverse of nameplate_crop.py, which is a research
tool and fails closed). Unknown flags are rejected rather than ignored, so a
typo cannot turn a preview into a post.

Requires, once, on this Mac in a GUI session (Keychain reads fail over ssh):
    security add-generic-password -a "georgianewspapers.bsky.social" \\
        -s "everygeorgia-bluesky" -w

Usage:
    python3 everygeorgia_post.py                 # post one
    python3 everygeorgia_post.py --dry-run       # choose and print, post nothing
    python3 everygeorgia_post.py --count 2
    python3 everygeorgia_post.py --setup-profile # name, bio, avatar
    python3 everygeorgia_post.py --launch        # the six-post thread, pinned
    python3 everygeorgia_post.py --status
    python3 everygeorgia_post.py --approve LCCN:DATE   # a held review item may post
    python3 everygeorgia_post.py --reject LCCN:DATE    # recorded, never posts
"""
import argparse
import collections
import io
import json
import os
import re
import random
import subprocess
import sys
import time
from datetime import datetime, timezone

import clips
import ghn_api
import nameplate_crop as npc
import profile as prof
import transcribe
from crop_frequency import noc_issues

HERE = os.path.dirname(os.path.abspath(__file__))
# ⚠️ ~/Scripts by name, not this file's parent: this directory lives in
# ~/Projects and is reached from ~/Scripts through a symlink, so the parent
# of the real path is not ~/Scripts (the trap that broke everycarnegie's
# describer on 30 August 2026).
SCRIPTS = os.path.join(os.path.expanduser("~"), "Scripts")
DATA = os.path.join(HERE, "data")
STATE_FILE = os.path.join(DATA, "post_state.json")
REVIEW_FILE = os.path.join(DATA, "review.jsonl")
DECISIONS_FILE = os.path.join(DATA, "review_decisions.jsonl")
APPROVED_TRIES_PER_RUN = 2      # approved items re-cut per run, at most
# ⚠️ Held crops live in "review/" BESIDE whichever REVIEW_FILE is in use, never
# a path of their own: a separate constant let the test suite, which redirects
# REVIEW_FILE only, write 24 fake crops into the real data/review/ on 25 September.
REVIEW_MAIL_IMAGES = 12         # crops embedded in one review mail; the rest are listed
_DRY_RUN = False                # set by main(): a dry run's review lines say so, and mail nothing

HANDLE = prof.HANDLE
KEYCHAIN_SERVICE = "everygeorgia-bluesky"
TAGS = ("Georgia", "History")       # two, broad, as everylibrary's; a tag
                                    # facet is what puts a post in a feed
TRIES_PER_TITLE = 5
TITLES_PER_RUN = 8              # was 4: three runs in twelve came up empty on
                                    # 11 September, because failures correlate
                                    # within a title (an unreadable masthead
                                    # fails on every date) and many titles hold
                                    # one or two issues
SHUFFLE_SEED = 20260911             # the day the poster was built; fixed so
                                    # the order is reproducible
MAX_IMAGE_BYTES = 950_000           # under Bluesky's ~1 MB blob limit
ALT_MAX = 1900
# ⚠️ Was "Presented online by the Digital Library of Georgia." until 18:49 KST
# on 11 September 2026, his call on the fourth live post ("Change it ... to
# just 'The Digital Library of Georgia.'"). UGA's one condition (10 September)
# was to credit the Digital Library of Georgia, which this still does; the
# longer sentence was our wording, not theirs.
# ⚠️ And "Courtesy of the Digital Library of Georgia." since 19:05 KST the same
# evening, his wording ("Is this better ... Courtesy of the Digital"): the
# standard credit form, and it says what the relationship is.
CREDIT = "Courtesy of the Digital Library of Georgia."
LINK_TEXT = "Digital Library of Georgia"     # the words that carry the link to the page

CLIP = clips.clip                   # swapped by the tests; never call clips.clip
                                    # directly below this line

# ⚠️ The lanes, in the order the feed cycles through them, one per run. A
# lane that yields nothing hands its slot to the next, so a slot is lost only
# when all of them come up empty. nameplate and headline draw from the title order (front
# pages); ad and market draw from search hits on genre phrases, since their
# material is on inner pages and the OCR of a display ad cannot say what it
# is (see clips.py).
# ✅ "article" since 25 September 2026, his call ("Release the article lane
# into the rotation"), held from 11 September until clips.py could tell an ad
# from an article (both picks that evening were grocers' ads). The test is
# clips.story_shape(): a dateline or wire credit, never merely no ad words;
# with the headline and column fixes of the same day, 14 of 16 passing crops
# in two 60-page samples were a single story, headline and first paragraph.
# ✅ "cartoon" since 12 September 2026, his instruction ("Build the cartoon
# lane, strips included"): a drawing on any page of a daily, found by the hole
# it leaves in the OCR and sorted by the model (pictures.py). Title order,
# dailies only, the first lane whose alt is a description.
# ✅ "classified" since 20 September 2026, his ask on seeing the WANTS column
# beside the Brunswick News strip ("Build it, and bring me the crops to look
# at first", then, on the crops, "Release the lane into the rotation"): a run
# of want-ad items (LOST, FOR SALE, FOR RENT) from search on
# clips.CLASSIFIED_PHRASES, closed by clips.classified_block(). Between market
# and cartoon, so the two OCR-only search lanes sit together.
# HELD_LANES is the mechanism a lane waits in before it joins: `--lane <x>`
# runs it, the rotation never reaches it. Empty now.
LANES = ("nameplate", "headline", "article", "ad", "market", "classified", "cartoon")
HELD_LANES = ()
LANE_LABEL = {"nameplate": "Nameplate", "headline": "Headline", "article": "Article",
              "ad": "Advertisement", "market": "Market report", "cartoon": "Cartoon",
              "classified": "Classified advertisements"}
SEARCH_LANES = ("ad", "market", "classified")
SEARCH_TRIES = {"ad": 8, "market": 16,  # candidates a search lane looks at per
               "classified": 8,        # run: the market lane passes one in fifteen
               "cartoon-search": 4}   # and handed off twelve times in twelve at 8;
                                    # a cartoon-search candidate costs up to two
                                    # model calls, so four
RECENT_TITLE_WINDOW = 30            # a search lane skips a title posted in its
                                    # last N posts, for variety
# ⚠️ The cartoon lane draws TWO ways, since 12 September 2026 ("Build the
# credit-line search seed"): first from search hits on the syndicate credit
# lines a strip carries (clips.CARTOON_PHRASES), then, if none passes, from
# the title order like the headline lane. The title order alone gave one
# cartoon in 33 issues; the credit lines are where the strips are. The search
# half keeps its own tried map under CARTOON_SEARCH and posts under "cartoon".
CARTOON_SEARCH = "cartoon-search"
CARTOON_RECENT_WINDOW = 3           # ⚠️ Not RECENT_TITLE_WINDOW: the credit
                                    # lines are overwhelmingly one title's (the
                                    # Atlanta Georgian, a Hearst paper), and the
                                    # ad lane's 30-post rule would bar it after
                                    # its first cartoon. Three lets the Georgian
                                    # post one cartoon in four; measured share
                                    # of hits in HANDOFF.md

# ⚠️⚠️ TITLE FAMILIES. A handful of continuously-published papers are split
# by Chronicling America across several LCCNs, one per title change, and
# title_order/eligible() otherwise count each LCCN as an independent title
# with its own turn -- which is exactly the shape of two incidents already
# hit here: Griffin occupying 3 of headline/cartoon's ~19/13 "dailies" slots
# (HANDOFF.md, 14 September; a reader noticed it posting three times in
# three days) and "the first dozen posts carried the Cordele Dispatch three
# times in three lanes" (the lane-offset fix, same file). The 14 September
# fix stopped the shared order COLLAPSING to a narrow lane's subset; it did
# not stop a split paper getting more than its share of that subset's turns,
# which HANDOFF.md names outright as "a structural bias... [that] would
# recur for any other town whose paper Chronicling America split the same
# way." This is that recurrence, confirmed 19 September 2026: Griffin still
# holds 3 of headline's 19 slots and 2 of cartoon's 13 (unchanged by the
# collapse fix), plus a shuffle coincidence put all three within the first
# ten of the full 843-title order, so the nameplate lane hit all three in
# its opening two weeks (3 of its first 12 posts).
#
# Each family here was verified by reading its members' ACTUAL held issue
# dates (not the roster's declared, sometimes open-ended year range) and
# confirming they are gapless and non-overlapping -- a real handoff from one
# masthead to the next, not two papers that happened to share a city:
#   Griffin daily news        1881-89 -> 1889-1924 -> 1924-present, no gap
#   Cordele dispatch          1916-1920-06-01 -> 1920-06-02-1926-04-07 ->
#                             1926-04-08-1927, no gap (day-to-day handoffs)
#   Augusta herald            1909-1914-03-03 -> 1914-03-18-1924, 15-day gap
#   Macon telegraph & messenger  1871-1873-08-30 -> 1873-10-09-1882, 40-day gap
# ⛔ NOT auto-derived from "same city": Savannah alone has 12 daily titles
# in one city, and they are genuinely distinct, competing papers running in
# parallel (Savannah Morning News, Savannah Daily Republican, Savannah
# Georgian...), not one renamed. Left OUT for the same reason, pending a
# closer read: Columbus's Daily Sun -> Sun and Columbus Daily Enquirer ->
# Daily Times -> Columbus Daily Times chain is gapless too, but "Sun" to
# "Times" is a bigger discontinuity than any family merged here, and
# Columbus Enquirer-Sun picks up four years after Columbus Daily Times ends;
# Atlanta Georgian and News -> Atlanta Georgian has a 14-month gap; Macon
# News arrives the year after Telegraph and Messenger folded under an
# unrelated name. A human should read those before merging them.
#
# The merge is scoped to TURN-TAKING ONLY (title_order/eligible/choose): it
# never touches issues_by_title(), dailies() or eligible()'s own per-LCCN
# density and era-floor math, so a family's real per-member issue lists,
# and which real LCCN a given date is fetched from, are untouched. The
# canonical id for a family is always its first (oldest) member, so it is
# stable regardless of dict ordering.
TITLE_FAMILIES = (
    ("sn89053182", "sn89053183", "sn83009936"),   # Griffin daily news
    ("sn89053138", "2022239691", "2022239700"),   # Cordele dispatch
    ("sn89053973", "sn89053972"),                 # Augusta herald
    ("sn85034225", "sn85038493"),                 # Macon telegraph and messenger
)
FAMILY_OF = {member: fam[0] for fam in TITLE_FAMILIES for member in fam}


def family(lccn):
    """The canonical id for lccn's title family (its oldest member), or
    lccn itself when it belongs to no known family."""
    return FAMILY_OF.get(lccn, lccn)


# --------------------------------------------------------------- credentials


def keychain_password(account, service):
    r = subprocess.run(
        ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
        capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        sys.exit(f"No Bluesky app password in the keychain for {account}.\n"
                 f'  security add-generic-password -a "{account}" '
                 f'-s "{service}" -w')
    return r.stdout.strip()


def login_client(retries=4):
    """Log in, retrying transient network failures at fire time. Only the
    login retries: a failed send cannot distinguish a post that never landed
    from one that landed with the response lost, and retrying the second
    case double-posts."""
    from atproto import Client, exceptions
    password = keychain_password(HANDLE, KEYCHAIN_SERVICE)
    last = None
    for attempt in range(retries):
        try:
            client = Client()
            client.login(HANDLE, password)
            return client
        except exceptions.NetworkError as exc:
            last = f"{type(exc).__name__}: {exc}"
            print(f"Login attempt {attempt + 1}/{retries} failed ({last})")
            if attempt + 1 < retries:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Could not log in after {retries} attempts: {last}")


# --------------------------------------------------------------------- state


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)
    else:
        state = {"order": [], "pass": 1, "posted": [], "tried": {}}
    # tried is per lane since the lanes arrived; an older file's flat map
    # was the nameplate lane's
    tried = state.get("tried", {})
    if tried and not all(isinstance(v, dict) for v in tried.values()):
        state["tried"] = {"nameplate": tried}
    state.setdefault("tried", {})
    for lane in LANES + (CARTOON_SEARCH,):
        state["tried"].setdefault(lane, {})
    return state


def lane_tried(state, lane):
    return state.setdefault("tried", {}).setdefault(lane, {})


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, STATE_FILE)


def issues_by_title():
    """{lccn: [(date, ed), ...]} for every postable pre-1931 NoC-US issue,
    read through the rights join's own identifier logic."""
    issues, _ = noc_issues()
    roster = npc.roster()
    by = collections.defaultdict(list)
    for lccn, date, ed in issues:
        # ⚠️ DLG's pages carry a few titles the roster does not (sn01884514
        # on 11 September 2026); a title the gates will refuse is not a
        # candidate, and every try on one is a wasted fetch.
        if roster.get(lccn, {}).get("postable") == "yes":
            by[lccn].append((date, ed))
    return dict(by)


DAILY_PER_YEAR = 150            # a title with at least this many issues per
                                # year of its run is a daily. Weeklies hold
                                # about 52. ⚠️ The headline lane draws from
                                # dailies ONLY: a weekly's front page is
                                # advertisements under a masthead, and on a
                                # sample of them the "headline" came back as
                                # "COUNTY DIRECTORY", an office address and a
                                # brand name, 11 September 2026.


def dailies(issues):
    out = {}
    for lccn, iss in issues.items():
        years = sorted({d[:4] for d, _ in iss})
        span = int(years[-1]) - int(years[0]) + 1
        if len(iss) / float(span) >= DAILY_PER_YEAR:
            out[lccn] = iss
    return out


def eligible(issues, lane):
    """The issues a lane may draw from: those on or after its era floor,
    titles with none dropped. ⚠️ Without this a title whose every issue
    predates the floor still costs TRIES_PER_TITLE fetch-free skips a run,
    and in the cartoon lane's first dry run (12 September 2026) four of
    eight titles went that way, 1828 to 1878, before a page was looked at."""
    import gates
    floor = gates.earliest(lane)
    if not floor:
        return issues
    out = {}
    for lccn, iss in issues.items():
        keep = [(d, e) for d, e in iss if d >= floor]
        if keep:
            out[lccn] = keep
    return out


def title_order(state, titles):
    """Fixed shuffled order over the titles, appended never reshuffled, so a
    title that appears later (a re-run rights join) joins the tail and the
    sequence already published is undisturbed. Same shape as everycarnegie.

    ⚠️⚠️ `titles` MUST be the account's full postable-title universe, never a
    lane's own narrower eligible set. The first line below drops anything in
    the existing order not present in `titles` -- meant for a title the
    rights join genuinely lost, but a lane-restricted set (headline/article's
    19 dailies, cartoon's 13, against 843 overall) makes it drop everything
    else too, and PERSISTS that collapse to `state["order"]` the moment that
    lane's post wins the run. Found 14 September 2026, three days after
    HANDOFF.md logged it as an open, unfixed finding: the Griffin Daily News
    (three LCCNs for one continuously-published paper, one of Chronicling
    America's title-change splits) occupies 3 of headline/article's 19
    eligible slots, and a headline-lane post collapsed the persisted order
    from 843 to 19 the same evening a reader noticed Griffin posting twice in
    two days. `next_titles()` now threads a separate `full_titles` argument
    through for exactly this reason -- call this only with that.

    ⚠️ The order holds FAMILY ids (see TITLE_FAMILIES/family()), not raw
    LCCNs, so a split paper occupies one slot regardless of how many LCCNs
    it is catalogued under. `titles` may still be a dict/iterable of real
    LCCNs; membership below is tested through family(), and the loop over
    the existing order also dedupes through family() and drops a second
    member if one is somehow already present -- self-healing an order saved
    before this merge existed, the same way the 14 September fix self-healed
    a collapsed one."""
    universe = {family(t) for t in titles}
    order, seen = [], set()
    for t in state.get("order", []):
        f = family(t)
        if f in universe and f not in seen:
            order.append(f)
            seen.add(f)
    fresh = sorted(f for f in universe if f not in seen)
    if fresh:
        random.Random(SHUFFLE_SEED + len(order)).shuffle(fresh)
        order += fresh
    state["order"] = order
    return order


def dates_for(lccn, issues, pass_no, lane="nameplate"):
    """This title's issues in the order this pass tries them: seeded by the
    title, the pass and the lane, so a pass shows each title on a different
    date and two lanes do not land on the same issue of it."""
    rng = random.Random(f"{lccn}:{pass_no}:{lane}")
    out = list(issues)
    rng.shuffle(out)
    return out


def posted_this_pass(state, lccn, lane="nameplate"):
    """⚠️ Compared through family(): once any member of a title family has
    posted in this lane this pass, the family's turn is taken, whichever of
    its LCCNs actually got picked."""
    f = family(lccn)
    return any(family(p["lccn"]) == f and p.get("pass") == state["pass"]
               and p.get("lane", "nameplate") == lane
               for p in state.get("posted", []))


def next_titles(state, issues, lane="nameplate", full_titles=None):
    """Titles still owed a post this pass, in order. Rolls the pass over when
    every title has either posted or been exhausted. The pass counter is
    shared; each title-order lane keeps its own tried map.

    ⚠️ `full_titles` is the account's full postable-title universe, and must
    be the SAME object/set across every lane's call in one run -- `issues`
    alone is a lane's own narrower eligible set for headline/article/cartoon
    (19/19/13 of 843 titles). Defaults to `issues` only so a caller with
    nothing broader to offer (a test, say) still gets the old single-set
    behaviour; every real caller in `pick()` passes `sources["nameplate"]`,
    which is always the unfiltered set. See `title_order()`'s own warning.

    ⚠️ Returns FAMILY ids, not raw LCCNs -- Cordele's or Griffin's three
    LCCNs occupy one slot here even though `issues` still holds each of
    them separately (see TITLE_FAMILIES). `choose()` resolves a family id
    back to whichever of its real members is actually being tried."""
    master = title_order(state, full_titles if full_titles is not None else issues)
    # ⚠️ Each lane starts the shared MASTER order at its own point, or the
    # lanes march through the same titles together: the first dozen posts
    # carried the Cordele Dispatch three times in three lanes. The offset is
    # computed against the master's own length, which is now stable across
    # every lane, rather than against a lane's own narrower eligible count.
    if master:
        off = (LANES.index(lane) * len(master)) // len(LANES)
        master = master[off:] + master[:off]
    present = {family(l) for l in issues}
    order = [f for f in master if f in present]
    for _ in range(2):
        tried = lane_tried(state, lane)
        owed = []
        for f in order:
            if posted_this_pass(state, f, lane):
                continue
            members = [m for m in issues if family(m) == f]
            n_issues = sum(len(issues[m]) for m in members)
            n_tried = len(tried.get(f, []))
            if n_tried >= min(TRIES_PER_TITLE, n_issues):
                continue                    # exhausted this pass
            owed.append(f)
        if owed:
            return owed
        state["pass"] = state.get("pass", 1) + 1
        state["tried"][lane] = {}
        print(f"Every title has been through in the {lane} lane; starting pass {state['pass']}.")
    return []


# ---------------------------------------------------------------- the post


def page_url(r):
    return r["url"]


def town_tag(city):
    """The roster's city as one hashtag word, or None: "Fort Valley" ->
    "FortValley", "Atlanta" -> "Atlanta"."""
    parts = re.findall(r"[A-Za-z]+", city or "")
    if not parts:
        return None
    return "".join(w[:1].upper() + w[1:] for w in parts)


def compose(r):
    """The post as segments: ("text", s), ("link", s, url), ("tag", s, tag).
    Built without atproto so it can be tested anywhere; to_builder() turns it
    into a TextBuilder at post time.

    The form is the GHN FAQ's citation, as promised to UGA on 21 August 2026:
      "[article title]", [newspaper title], [issue date], p.[page number],
      [url]. Presented online by the Digital Library of Georgia.
    with a bracketed description in the title slot, since a nameplate has no
    article title. ⚠️ Cut to the title, the date and the credit on the first
    post, his instructions (11 September 2026: "The Dawson Journal, June 14,
    1867. {link} is sufficient", then "move the link to 'Presented online'
    rather than printing it in full"): no city, no page number and no URL in
    the text; the page link is a facet on "Presented online". The city and
    page live on in the alt text and in the link itself. Dates are
    U.S. order, his instruction, for this account alone. Their reply said the
    form is ours to choose; the credit sentence is the one thing they asked
    for, and it stays."""
    meta = r["meta"]
    title = npc.display_title(meta.get("title"))
    url = r["url"]
    # ⚠️ No bracketed lane label on any post, his calls on launch evening
    # (11 September 2026: "We don't need [nameplate] here", then on the first
    # headline "Delete the [x] at the start of the posts going forward"). The
    # picture says what it is; the alt names the lane in words.
    label = ""
    # ⚠️ No quotation marks round the title, his instruction on the first post
    # (11 September 2026: "The Dawson Journal, no quotes around it"), over the
    # house rule that a title of a work is quoted: in a one-line citation the
    # name IS the line. This account only; the alt text keeps its quotes.
    head = f"{label}{title}, {npc.post_date(r['date'])}. "
    # ⚠️ The link to the page rides on the library's name inside the credit,
    # his instruction on the first post (11 September 2026: "move the link to
    # 'Presented online' rather than printing it in full", then the credit
    # itself was reworded twice). LINK_TEXT is asserted to occur exactly once
    # in CREDIT so the two cannot drift apart.
    assert CREDIT.count(LINK_TEXT) == 1
    before, after = CREDIT.split(LINK_TEXT)
    segs = [("text", head + before), ("link", LINK_TEXT, url), ("text", after + "\n\n")]
    # ⚠️ A third tag for the town, his call (11 September 2026, "can we add a
    # tag to the town?"): the roster's own city, folded to one word
    # (#FortValley). No feed carries a town tag; it is for search. Absent
    # when the roster has no city.
    tags = [("tag", f"#{t}", t) for t in TAGS]
    town = town_tag(meta.get("city"))
    if town:
        tags.append(("tag", f"#{town}", town))
    for i, t in enumerate(tags):
        if i:
            segs.append(("text", " "))
        segs.append(t)
    return segs


def text_of(segs):
    return "".join(s[1] for s in segs)


def to_builder(segs):
    from atproto import client_utils
    tb = client_utils.TextBuilder()
    for s in segs:
        if s[0] == "text":
            tb.text(s[1])
        elif s[0] == "link":
            tb.link(s[1], s[2])
        elif s[0] == "tag":
            tb.tag(s[1], s[2])
        elif s[0] == "mention":
            tb.mention(s[1], s[2])
        else:
            raise ValueError(f"unknown segment {s[0]!r}")
    return tb


def alt_text(r):
    """The nameplate lane's alt is built in nameplate_crop.describe(). Every
    other lane's alt carries the clip's own words, which is post 4's
    promise, and names the model when a model read them: transcribe.PREFIX
    leads, for the reason image_alt.py gives (alt travels without the bio)."""
    lane = r.get("lane", "nameplate")
    if lane == "cartoon":
        # built in pictures.compose_alt(): the description labelled as the
        # model's, the printed words labelled as transcribed
        alt = r["alt"]
        if len(alt) > ALT_MAX:
            alt = alt[:ALT_MAX - 1].rstrip() + "…"
        return alt
    if lane == "nameplate":
        alt = r["alt"]
        if r.get("context") and r.get("words"):
            alt = (alt.rstrip(".") + f", with the top of the page beneath it. "
                   f"{transcribe.PREFIX}, the band beneath reads: “{r['words']}”")
        if len(alt) > ALT_MAX:
            alt = alt[:ALT_MAX - 2].rstrip() + "…”"
        return alt
    if not r.get("words"):
        return r["alt"][:ALT_MAX]
    meta = r["meta"]
    title = npc.display_title(meta.get("title"))
    city = (meta.get("city") or "").strip()
    where = f"{city}, Georgia" if city else "Georgia"
    seq = r["url"].rstrip("/").rsplit("-", 1)[-1]
    what = {"headline": "headline", "article": "article", "ad": "advertisement",
            "market": "market report", "classified": "classified advertisements"}[lane]
    lead = f"{transcribe.PREFIX} {what}" if r.get("generated") else what.capitalize()
    alt = (f"{lead} from “{title},” {where}, {npc.post_date(r['date'])}, page {seq}, "
           f"reading: “{r['words']}”")
    if len(alt) > ALT_MAX:
        alt = alt[:ALT_MAX - 2].rstrip() + "…”"
    return alt


def fit_image(data, max_bytes=MAX_IMAGE_BYTES):
    """A 1600px nameplate strip is a 100-300 KB JPEG; this is the guard for
    the day one is not."""
    if len(data) <= max_bytes:
        return data
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    for scale in (0.8, 0.6, 0.45):
        buf = io.BytesIO()
        im.resize((int(im.width * scale), int(im.height * scale))).save(
            buf, format="JPEG", quality=86, optimize=True)
        if buf.tell() <= max_bytes:
            return buf.getvalue()
    return buf.getvalue()


def aspect_ratio(data):
    from PIL import Image
    from atproto import models
    with Image.open(io.BytesIO(data)) as im:
        return models.AppBskyEmbedDefs.AspectRatio(width=im.width, height=im.height)


# ----------------------------------------------------------------- choosing


def log_review(r, state):
    """Append one line a person can act on. The run does not wait for them.

    ✅ Since 25 September 2026, his ask ("email me with new review items, with
    the crop images"): the crop itself is saved under data/review/ and named in
    the line, and a dry run's lines carry "dry": true, so review_mail() can
    mail a live run's items and never a preview's."""
    image = None
    base = os.path.dirname(REVIEW_FILE)
    if r.get("bytes"):
        os.makedirs(os.path.join(base, "review"), exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        name = f"{stamp}_{r.get('lane') or 'item'}_{r['lccn']}_{r['date']}_p{r.get('seq', 1)}.jpg"
        try:
            with open(os.path.join(base, "review", name), "wb") as f:
                f.write(fit_image(r["bytes"]))
            image = os.path.join("review", name)
        except Exception as e:                      # noqa: BLE001 - the line matters more
            print(f"  (review crop not saved: {e})")
    line = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lccn": r["lccn"], "date": r["date"], "edition": r["edition"],
        "url": r["url"], "caption": r["caption"], "lane": r.get("lane"),
        "image_box": r.get("image_box"), "words": r.get("words"),
        "page_hits": r["page_hits"], "reasons": r["verdict"].reasons,
        "pass": state.get("pass"), "image": image, "dry": _DRY_RUN,
    }
    os.makedirs(DATA, exist_ok=True)
    with open(REVIEW_FILE, "a") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def review_size():
    try:
        return os.path.getsize(REVIEW_FILE)
    except OSError:
        return 0


def review_mail(offset, send=None):
    """Mail the review lines a LIVE run appended after byte `offset`, with
    their crops embedded, through ~/Scripts/estate_mail.py. Best-effort: a
    failure is printed and never changes the run's outcome. Returns the
    number of items mailed."""
    import html as _html
    import tempfile
    try:
        with open(REVIEW_FILE, "rb") as f:
            f.seek(offset)
            raw = f.read().decode("utf-8", "replace")
    except OSError:
        return 0
    items = []
    for ln in raw.splitlines():
        try:
            it = json.loads(ln)
        except ValueError:
            continue
        if not it.get("dry"):
            items.append(it)
    if not items:
        return 0
    roster = npc.roster()
    text, parts, images = [], [], []
    for i, it in enumerate(items, 1):
        title = (roster.get(it["lccn"]) or {}).get("title") or it["lccn"]
        head = f"{i}. {LANE_LABEL.get(it.get('lane'), it.get('lane') or 'Item')}: {title}, {it['date']}"
        why = "; ".join(it.get("reasons") or [])
        words = (it.get("words") or "").strip()
        text += [head, f"   Why held: {why}", f"   Page: {it['url']}"] + \
            ([f"   Reads: {words[:600]}"] if words else []) + [""]
        img = os.path.join(os.path.dirname(REVIEW_FILE), it["image"]) if it.get("image") else None
        pic = ""
        if img and os.path.exists(img) and len(images) < REVIEW_MAIL_IMAGES:
            images.append(img)
            pic = (f'<p><img src="cid:{_html.escape(os.path.basename(img))}" '
                   f'style="max-width:100%;border:1px solid #999"></p>')
        elif img:
            pic = "<p><i>(crop not embedded: see the page)</i></p>"
        parts.append(
            f'<h3>{_html.escape(head)}</h3>{pic}'
            f'<p><b>Why held:</b> {_html.escape(why)}<br>'
            f'<a href="{_html.escape(it["url"])}">The page on the Digital Library of Georgia</a></p>'
            + (f'<p><b>Reads:</b> {_html.escape(words[:600])}</p>' if words else ""))
    n = len(items)
    subject = f"[georgia in print] review: {n} new"
    body = "\n".join([f"{n} clipping{'s' if n != 1 else ''} held for review, never posted.", ""] + text)
    page = ("<html><body style=\"font-family:-apple-system,Helvetica,sans-serif\">"
            f"<p>{n} clipping{'s' if n != 1 else ''} held for review, never posted.</p>"
            + "<hr>".join(parts) + "</body></html>")
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
        fh.write(page)
        html_path = fh.name
    cmd = [sys.executable, os.path.join(SCRIPTS, "estate_mail.py"), subject, "--html", html_path]
    for img in images:
        cmd += ["--image", img]
    try:
        r = (send or subprocess.run)(cmd, input=body, text=True, capture_output=True, timeout=120)
        if r.returncode != 0:
            print(f"  (review mail not sent: {(r.stderr or '').strip()})")
            return 0
        print(f"Review mail sent: {n} item(s), {len(images)} crop(s).")
        return n
    except Exception as e:                          # noqa: BLE001 - best-effort
        print(f"  (review mail not sent: {e})")
        return 0
    finally:
        os.unlink(html_path)



# ------------------------------------------------------- review decisions

# ✅ Since 26 September 2026, his call on the first review mail ("all but
# no. 4 can be added to the pool to post. reject no. 4"). A REVIEW item is
# never posted by the ordinary path; a person's APPROVAL is what lets one
# through. Decisions are appended to data/review_decisions.jsonl (the last
# decision for an item wins) and review.jsonl is never rewritten.
# ⚠️ An approved item is RE-CUT, not posted from the saved JPEG, because the
# alt needs the clip's fields. Two guards keep the post the thing he saw:
# the re-cut must land on the SAME image_box, and its words are replaced by
# the words he read in the mail (the band is a model transcription and can
# come back differently). A REFUSE on the re-cut (rights, era, geometry) is
# never overridden: approval covers the vocabulary hold and nothing else.

def _item_key(lccn, date, lane):
    return f"{lccn}:{date}:{lane or 'nameplate'}"


def decide(spec, decision, log=print):
    """Record `decision` ("approve"/"reject") for the newest LIVE review line
    matching spec "LCCN:DATE[:LANE]". Returns the decision line, or None."""
    parts = spec.split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"{spec!r}: expected LCCN:DATE or LCCN:DATE:LANE")
    lccn, date = parts[0], parts[1]
    lane = parts[2] if len(parts) == 3 else None
    match = None
    try:
        with open(REVIEW_FILE) as f:
            for ln in f:
                try:
                    it = json.loads(ln)
                except ValueError:
                    continue
                if it.get("dry") is not False:
                    continue             # a preview's line, or one from before 25 Sep
                if it["lccn"] == lccn and it["date"] == date and (lane is None or it.get("lane") == lane):
                    match = it
    except OSError:
        pass
    if match is None:
        log(f"  {spec}: no live review line matches; nothing recorded")
        return None
    line = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "decision": decision, "lccn": lccn, "date": date,
            "edition": match.get("edition", 1), "lane": match.get("lane") or "nameplate",
            "seq": int(match["url"].rstrip("/").rsplit("-", 1)[-1]) if match.get("url") else 1,
            "image_box": match.get("image_box"), "words": match.get("words"),
            "review_at": match.get("at")}
    os.makedirs(DATA, exist_ok=True)
    with open(DECISIONS_FILE, "a") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    log(f"  {decision.rstrip('e')}ed: {lccn} {date} ({line['lane']})")
    return line


def approved_pending(state, lane):
    """Approved items for `lane` not yet posted and not given up on, in the
    order they were approved."""
    latest = {}
    try:
        with open(DECISIONS_FILE) as f:
            for ln in f:
                try:
                    d = json.loads(ln)
                except ValueError:
                    continue
                k = _item_key(d["lccn"], d["date"], d.get("lane"))
                latest.pop(k, None)          # re-decided: moves to the back
                latest[k] = d
    except OSError:
        return []
    # a dry run's own picks count too, so `--dry-run --count 3` previews three
    done = {_item_key(p["lccn"], p["date"], p.get("lane")) for p in state.get("posted", [])}
    failed = set(state.get("approved_failed", {}))
    return [d for k, d in latest.items()
            if d["decision"] == "approve" and (d.get("lane") or "nameplate") == lane
            and k not in done and k not in failed]


def choose_approved(state, lane, log=print):
    """An approved item for this lane's turn, or (None, None). Skips one from
    the same title family as this lane's last post, so a queue holding four
    Savannah Morning News nameplates does not post them back to back; the
    turn then goes to the ordinary selection and the item waits."""
    mine = [p for p in state.get("posted", []) if p.get("lane") == lane]
    last = family(mine[-1]["lccn"]) if mine else None
    tries = 0
    for d in approved_pending(state, lane):
        if family(d["lccn"]) == last:
            continue
        if tries >= APPROVED_TRIES_PER_RUN:
            break
        tries += 1
        k = _item_key(d["lccn"], d["date"], lane)
        try:
            r = CLIP(lane, d["lccn"], d["date"], d.get("edition", 1), d.get("seq", 1))
        except (npc.Refused, ghn_api.FetchError, ValueError) as e:
            log(f"  approved {lane} {d['lccn']} {d['date']}: re-cut failed, {e}")
            continue                       # transient: tried again next run
        why = None
        if r["verdict"].outcome == "REFUSE":      # gates.REFUSE
            why = f"refused on the re-cut: {'; '.join(r['verdict'].reasons)}"
        elif d.get("image_box") and list(r.get("image_box") or []) != list(d["image_box"]):
            why = f"re-cut landed on {r.get('image_box')}, not the approved {d['image_box']}"
        if why:
            state.setdefault("approved_failed", {})[k] = why
            log(f"  approved {lane} {d['lccn']} {d['date']}: dropped, {why}")
            continue
        if d.get("words"):
            r["words"] = d["words"]
        r["approved"] = True
        log(f"  approved {lane} {d['lccn']} {d['date']}: posting the item he approved")
        return d["lccn"], r
    return None, None


def choose(state, issues, log=print, lane="nameplate", full_titles=None):
    """Walk the owed titles and their dates until one clip PASSES. Returns
    (lccn, result) or (None, None) -- the REAL lccn a passing clip was
    fetched from, exactly as before this merge existed; the family id
    `next_titles()` hands back is resolved to a real member below and never
    leaks into the return value, `state["posted"]`, or the caller. Every
    date looked at is recorded in state['tried'][lane] whether it passed or
    not, so a dry run that is then followed by a live run does not
    re-fetch, and a REVIEW is not re-offered next run. `full_titles` passes
    straight through to `next_titles()`.

    ⚠️ A family's dates are drawn from ALL its members present in `issues`
    combined into one pool (dates never overlap between real members --
    verified by hand for every family in TITLE_FAMILIES), tagged with
    whichever real lccn actually holds that date, so `CLIP()` and the
    result's own `meta`/citation are always for the LCCN that truly
    published it. `seen`/`tried` key on the family id and hold plain dates,
    which is safe for the same no-overlap reason."""
    tried = lane_tried(state, lane)
    for f in next_titles(state, issues, lane, full_titles=full_titles)[:TITLES_PER_RUN]:
        members = sorted(m for m in issues if family(m) == f)
        combined = [(d, e, m) for m in members for d, e in issues[m]]
        seen = set(tried.get(f, []))
        used = {(family(q["lccn"]), q["date"]) for q in state.get("posted", []) if q.get("pass") == state["pass"]}
        for date, ed, lccn in dates_for(f, combined, state["pass"], lane):
            if date in seen or (f, date) in used:
                continue
            if len(seen) >= TRIES_PER_TITLE:
                break
            seen.add(date)
            tried[f] = sorted(seen)
            try:
                r = CLIP(lane, lccn, date, ed)
            except (npc.Refused, ghn_api.FetchError, ValueError) as e:
                log(f"  skip {lane} {lccn} {date}: {e}")
                continue
            if r["postable"]:
                return lccn, r
            log_review(r, state)
            log(f"  review {lane} {lccn} {date}: {'; '.join(r['verdict'].reasons)}")
        log(f"  {lane} {f}: nothing passed in {len(seen)} tries; next title")
    return None, None


def recent_titles(state, lane, n=RECENT_TITLE_WINDOW):
    """Title families this lane posted among its last `n` posts. Through
    family() so a search lane (ad/market/cartoon-search) treats two LCCNs
    of the same split paper as the one title it is to a reader."""
    mine = [family(p["lccn"]) for p in state.get("posted", []) if p.get("lane") == lane]
    return set(mine[-n:])


def choose_search(state, cands, lane, log=print, clip_lane=None, recent_lane=None, window=None):
    """A search lane: candidates are (lccn, date, ed, seq, phrase) from
    clips.search_candidates, walked in a seeded order that the pass number
    reshuffles, skipping what this lane has tried and the titles it posted
    recently. Bounded at SEARCH_TRIES a run. `clip_lane` is the lane the
    clip is cut and posted as when it differs from the tried-map key (the
    cartoon lane's search half)."""
    tried = lane_tried(state, lane)
    clip_lane = clip_lane or lane
    order = list(cands)
    random.Random(f"{lane}:{state.get('pass', 1)}:{SHUFFLE_SEED}").shuffle(order)
    recent = recent_titles(state, recent_lane or lane, window or RECENT_TITLE_WINDOW)
    looked = 0
    for lccn, date, ed, seq, phrase in order:
        key = f"{lccn}:{date}:{seq}"
        if key in tried:
            continue
        if family(lccn) in recent:
            continue
        if looked >= SEARCH_TRIES.get(lane, 8):
            break
        looked += 1
        tried[key] = phrase
        try:
            r = CLIP(clip_lane, lccn, date, ed, seq, phrase)
        except (npc.Refused, ghn_api.FetchError, ValueError) as e:
            log(f"  skip {lane} {lccn} {date} p{seq}: {e}")
            continue
        if r["postable"]:
            return lccn, r
        log_review(r, state)
        log(f"  review {lane} {lccn} {date} p{seq}: {'; '.join(r['verdict'].reasons)}")
    return None, None


def next_lane(state):
    """The lane this run starts with: the one after the lane that last
    POSTED, not the next position in a count of posts."""
    # ⚠️ Since 25 September 2026, his call. Counting posts (`LANES[n % 6]`)
    # gave the lane after a run of empty lanes a DOUBLE turn: market (1 post
    # in 39) and classified handed their slot to cartoon, and the next run,
    # counting on from market, landed on classified, failed again and handed
    # cartoon a second post. Cartoons were 8 of the last 24 posts, twice
    # their share. Reading the last lane that actually posted means an empty
    # lane is skipped once, and the rotation goes on from what went out.
    # ⚠️ Dry posts still count (they carry a lane), which is what makes
    # `--dry-run --count 4` preview the rotation instead of four of the same
    # lane. A last post from a lane not in LANES (a held lane run by hand
    # with `--lane`) falls back to the post count.
    posted = state.get("posted", [])
    if posted and posted[-1].get("lane") in LANES:
        return LANES[(LANES.index(posted[-1]["lane"]) + 1) % len(LANES)]
    return LANES[len(posted) % len(LANES)]


def pick(state, sources, lane, log=print):
    # ⚠️ sources["nameplate"] is always the FULL postable-title universe
    # (main() builds it that way), so it doubles as `full_titles` for every
    # narrower lane -- see title_order()'s and next_titles()'s warnings.
    # `.get()`, not `[]`: a caller testing one lane in isolation may build a
    # `sources` dict with no "nameplate" key at all, and `choose()`/
    # `next_titles()` already fall back to the lane's own set when
    # `full_titles` is None.
    lccn, r = choose_approved(state, lane, log=log)
    if r is not None:
        return lccn, r
    if lane in SEARCH_LANES:
        return choose_search(state, sources[lane], lane, log=log)
    if lane == "cartoon":
        lccn, r = choose_search(state, sources[CARTOON_SEARCH], CARTOON_SEARCH, log=log,
                                clip_lane="cartoon", recent_lane="cartoon",
                                window=CARTOON_RECENT_WINDOW)
        if r is not None:
            return lccn, r
        log("  cartoon: nothing from the credit-line search; the title order")
    return choose(state, sources[lane], log=log, lane=lane, full_titles=sources.get("nameplate"))


# ------------------------------------------------------------------ profile


def setup_profile(client, dry_run=False):
    """Display name, bio and avatar, from profile.py. Keeps whatever is
    pinned. Safe to re-run: it writes the same record again."""
    from atproto import models
    name, bio = prof.DISPLAY_NAME, prof.bio()
    print(f"display name  {name}\nbio [{len(bio)}/256]\n{bio}\navatar        {prof.AVATAR}")
    if len(bio) > 256:
        sys.exit("bio is over 256 characters")
    if dry_run:
        print("\nDry run: profile untouched.")
        return
    with open(prof.AVATAR, "rb") as f:
        avatar = client.upload_blob(f.read()).blob
    try:
        existing = client.app.bsky.actor.profile.get(client.me.did, "self")
        record, swap = existing.value, existing.cid
    except Exception:                                   # noqa: BLE001 - no record yet
        record, swap = models.AppBskyActorProfile.Record(), None
    record.display_name = name
    record.description = bio
    record.avatar = avatar
    client.com.atproto.repo.put_record(models.ComAtprotoRepoPutRecord.Data(
        repo=client.me.did, collection="app.bsky.actor.profile", rkey="self",
        record=record, swap_record=swap))
    print("Profile written.")


def thread_segments(post, dids):
    """A thread post's text as segments, with its links and mentions placed
    where the text carries them. Every visible string must occur exactly
    once, or the facet would land on the wrong occurrence."""
    text = post["text"]
    marks = []
    for visible, url in post["links"]:
        i = text.find(visible)
        if i < 0 or text.find(visible, i + 1) >= 0:
            raise ValueError(f"link text not unique in post: {visible!r}")
        marks.append((i, i + len(visible), ("link", visible, url)))
    for handle in post["mentions"]:
        visible = "@" + handle
        i = text.find(visible)
        if i < 0 or text.find(visible, i + 1) >= 0:
            raise ValueError(f"mention not unique in post: {visible!r}")
        marks.append((i, i + len(visible), ("mention", visible, dids[handle])))
    marks.sort()
    segs, pos = [], 0
    for start, end, seg in marks:
        if start < pos:
            raise ValueError("overlapping facets")
        if start > pos:
            segs.append(("text", text[pos:start]))
        segs.append(seg)
        pos = end
    if pos < len(text):
        segs.append(("text", text[pos:]))
    return segs


def post_launch(client, state, dry_run=False):
    """The six-post thread. Post 1 is pinned; each reply carries root AND
    parent. Recorded in the state the moment the root exists: a thread that
    fails halfway is repaired by hand, never restarted from the top, because
    a second opening thread cannot be taken back."""
    from atproto import models
    posts = prof.thread()
    over = [i for i, p in enumerate(posts, 1) if len(p["text"]) > 300]
    if over:
        sys.exit(f"Posts over the 300-character limit: {over}")
    handles = sorted({h for p in posts for h in p["mentions"]})
    dids = {}
    if not dry_run:
        for h in handles:
            dids[h] = client.resolve_handle(h).did
    else:
        dids = {h: "did:plc:dryrun" for h in handles}
    for i, p in enumerate(posts, 1):
        segs = thread_segments(p, dids)
        print("-" * 60)
        print(f"{i}/{len(posts)}  [{len(p['text'])} chars]")
        print(text_of(segs))
        for s in segs:
            if s[0] != "text":
                print(f"   [{s[0]}] {s[1]!r} -> {s[2]}")
    print("-" * 60)
    if dry_run:
        print("\nDry run: nothing posted.")
        return
    if state.get("launch_thread_posted"):
        sys.exit("The launch thread has already been posted. Refusing to post it twice.")

    root = parent = None
    for i, p in enumerate(posts, 1):
        tb = to_builder(thread_segments(p, dids))
        reply = None
        if parent is not None:
            reply = models.AppBskyFeedPost.ReplyRef(root=root, parent=parent)
        res = client.send_post(text=tb, langs=["en"], reply_to=reply)
        ref = models.ComAtprotoRepoStrongRef.Main(uri=res.uri, cid=res.cid)
        if root is None:
            root = ref
            state["launch_thread_posted"] = True
            state["launch_thread_root"] = res.uri
            save_state(state)
        parent = ref
        print(f"posted {i}/{len(posts)}  {res.uri.rsplit('/', 1)[-1]}")
        time.sleep(2)

    existing = client.app.bsky.actor.profile.get(client.me.did, "self")
    record = existing.value
    record.pinned_post = root
    client.com.atproto.repo.put_record(models.ComAtprotoRepoPutRecord.Data(
        repo=client.me.did, collection="app.bsky.actor.profile", rkey="self",
        record=record, swap_record=existing.cid))
    print(f"\nThread posted and post 1 pinned. Root: {root.uri}")


# ---------------------------------------------------------------------- main


def status(state, issues):
    posted = state.get("posted", [])
    print(f"titles with postable pre-1931 issues: {len(issues)}")
    print(f"pass {state.get('pass', 1)}; posted {len(posted)} in all, "
          f"{sum(1 for p in posted if p.get('pass') == state.get('pass', 1))} this pass")
    print(f"launch thread posted: {bool(state.get('launch_thread_posted'))}")
    if posted:
        p = posted[-1]
        print(f"last: {p['lccn']} {p['date']} at {p['at']}  {p['uri']}")
    n_review = 0
    if os.path.exists(REVIEW_FILE):
        with open(REVIEW_FILE) as f:
            n_review = sum(1 for _ in f)
    print(f"review queue: {n_review} line(s) in {os.path.relpath(REVIEW_FILE, HERE)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print, post nothing, write no state")
    ap.add_argument("--count", type=int, default=1, help="how many to post (default 1)")
    ap.add_argument("--save", metavar="DIR",
                    help="dry run only: write each crop and its post text and alt to DIR")
    ap.add_argument("--lane", choices=LANES + HELD_LANES,
                    help="this lane only, instead of the rotation (a held lane runs only this way)")
    ap.add_argument("--setup-profile", action="store_true", help="write name, bio and avatar")
    ap.add_argument("--launch", action="store_true", help="post the pinned thread (once)")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--approve", metavar="LCCN:DATE[:LANE]", action="append", default=[],
                    help="let a held review item post in its lane's next turns")
    ap.add_argument("--reject", metavar="LCCN:DATE[:LANE]", action="append", default=[],
                    help="record that a held review item is never to post")
    args = ap.parse_args()

    if args.approve or args.reject:
        for spec in args.approve:
            decide(spec, "approve")
        for spec in args.reject:
            decide(spec, "reject")
        return

    state = load_state()
    if args.status:
        status(state, issues_by_title())
        return
    if args.setup_profile:
        setup_profile(None if args.dry_run else login_client(), dry_run=args.dry_run)
        return
    if args.launch:
        post_launch(None if args.dry_run else login_client(), state, dry_run=args.dry_run)
        return

    if not args.dry_run and not state.get("launch_thread_posted"):
        print("Not launched yet: the pinned thread has not been posted. Nothing posted.")
        return

    issues = issues_by_title()
    rights = npc.roster()
    sources = {"nameplate": issues, "headline": eligible(dailies(issues), "headline"),
               "article": eligible(dailies(issues), "article"),
               "ad": clips.ad_candidates(rights), "market": clips.market_candidates(rights),
               "classified": clips.classified_candidates(rights),
               "cartoon": eligible(dailies(issues), "cartoon"),
               CARTOON_SEARCH: clips.cartoon_candidates(rights)}
    global _DRY_RUN
    _DRY_RUN = bool(args.dry_run)
    review_from = review_size()
    try:
        _run(args, state, sources)
    finally:
        # A live run mails what it queued, even when it stopped early.
        if not args.dry_run:
            review_mail(review_from)


def _run(args, state, sources):
    client = None
    for n in range(args.count):
        if args.lane:
            order = (args.lane,)                 # one lane, held or not
        else:
            start = LANES.index(next_lane(state))
            order = LANES[start:] + LANES[:start]
        lccn = r = None
        for lane in order:
            print(f"[{lane}]")
            lccn, r = pick(state, sources, lane)
            if r is not None or args.lane:
                break
        if r is None:
            print("Nothing passed the gates this run, in any lane.")
            break
        segs = compose(r)
        text = text_of(segs)
        alt = alt_text(r)
        print("-" * 60)
        print(text)
        print(f"[{len(text)} chars]  [alt] {alt}")
        print(f"[{r['lane']}] {r['band_fraction']*100:.1f}% of page"
              f"{', extended to the ink edge' if r.get('extended') else ''}"
              f"{', the printed border' if r.get('boxed') else ''}; "
              f"crop {r['size'][0]}x{r['size'][1]}")
        if len(text) > 300:
            sys.exit(f"post is {len(text)} characters")
        if args.dry_run:
            state.setdefault("posted", []).append(
                {"lccn": lccn, "date": r["date"], "pass": state["pass"], "lane": r["lane"], "dry": True})
            if args.save:
                os.makedirs(args.save, exist_ok=True)
                stem = os.path.join(args.save, f"{n + 1:02d}_{r['lane']}_{lccn}_{r['date']}")
                with open(stem + ".jpg", "wb") as f:
                    f.write(fit_image(r["bytes"]))
                with open(stem + ".txt", "w") as f:
                    f.write(text + "\n\n[alt] " + alt + "\n")
            continue

        image = fit_image(r["bytes"])
        if client is None:
            client = login_client()
        res = client.send_images(text=to_builder(segs), images=[image],
                                 image_alts=[alt], image_aspect_ratios=[aspect_ratio(image)],
                                 langs=["en"])
        state.setdefault("posted", []).append({
            "lccn": lccn, "date": r["date"], "edition": r["edition"],
            "lane": r["lane"], "seq": r.get("seq", 1),
            "pass": state["pass"], "uri": res.uri,
            **({"approved": True} if r.get("approved") else {}),
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        save_state(state)
        print(f"Posted {res.uri}")
        if n + 1 < args.count:
            time.sleep(2)

    if args.dry_run:
        print("\nDry run: nothing posted, no state written"
              + (f"; REVIEW lines were appended to {os.path.relpath(REVIEW_FILE, HERE)}."
                 if os.path.exists(REVIEW_FILE) else "."))


if __name__ == "__main__":
    # Gated on __name__: this file is imported by its test suite, and patching
    # subprocess.run at import time would leak into every test in the process.
    sys.path.insert(0, SCRIPTS)
    import api_call_log
    api_call_log.install("everygeorgia_post.py")
    main()
