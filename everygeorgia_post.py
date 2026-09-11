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
"""
import argparse
import collections
import io
import json
import os
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
CREDIT = "Presented online by the Digital Library of Georgia."

CLIP = clips.clip                   # swapped by the tests; never call clips.clip
                                    # directly below this line

# ⚠️ The four lanes, in the order the feed cycles through them, one per run:
# with two runs a day each lane posts every other day. A lane that yields
# nothing hands its slot to the next, so a slot is lost only when all four
# come up empty. nameplate and headline draw from the title order (front
# pages); ad and market draw from search hits on genre phrases, since their
# material is on inner pages and the OCR of a display ad cannot say what it
# is (see clips.py).
LANES = ("nameplate", "headline", "article", "ad", "market")
LANE_LABEL = {"nameplate": "Nameplate", "headline": "Headline", "article": "Article",
              "ad": "Advertisement", "market": "Market report"}
SEARCH_LANES = ("ad", "market")
SEARCH_TRIES = {"ad": 8, "market": 16}   # candidates a search lane looks at per
                                    # run: the market lane passes one in fifteen
                                    # and handed off twelve times in twelve at 8
RECENT_TITLE_WINDOW = 30            # a search lane skips a title posted in its
                                    # last N posts, for variety


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
    for lane in LANES:
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


def title_order(state, titles):
    """Fixed shuffled order over the titles, appended never reshuffled, so a
    title that appears later (a re-run rights join) joins the tail and the
    sequence already published is undisturbed. Same shape as everycarnegie."""
    order = [t for t in state.get("order", []) if t in titles]
    known = set(order)
    fresh = sorted(t for t in titles if t not in known)
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
    return any(p["lccn"] == lccn and p.get("pass") == state["pass"]
               and p.get("lane", "nameplate") == lane
               for p in state.get("posted", []))


def next_titles(state, issues, lane="nameplate"):
    """Titles still owed a post this pass, in order. Rolls the pass over when
    every title has either posted or been exhausted. The pass counter is
    shared; each title-order lane keeps its own tried map."""
    order = title_order(state, issues)
    # ⚠️ Each lane starts the shared order at its own point, or the lanes
    # march through the same titles together: the first dozen posts carried
    # the Cordele Dispatch three times in three lanes. The offset is the
    # lane's place in LANES, so it is fixed and needs no state.
    if order:
        off = (LANES.index(lane) * len(order)) // len(LANES)
        order = order[off:] + order[:off]
    for _ in range(2):
        tried = lane_tried(state, lane)
        owed = []
        for lccn in order:
            if posted_this_pass(state, lccn, lane):
                continue
            n_tried = len(tried.get(lccn, []))
            if n_tried >= min(TRIES_PER_TITLE, len(issues[lccn])):
                continue                    # exhausted this pass
            owed.append(lccn)
        if owed:
            return owed
        state["pass"] = state.get("pass", 1) + 1
        state["tried"][lane] = {}
        print(f"Every title has been through in the {lane} lane; starting pass {state['pass']}.")
    return []


# ---------------------------------------------------------------- the post


def page_url(r):
    return r["url"]


def compose(r):
    """The post as segments: ("text", s), ("link", s, url), ("tag", s, tag).
    Built without atproto so it can be tested anywhere; to_builder() turns it
    into a TextBuilder at post time.

    The form is the GHN FAQ's citation, as promised to UGA on 21 August 2026:
      "[article title]", [newspaper title], [issue date], p.[page number],
      [url]. Presented online by the Digital Library of Georgia.
    with a bracketed description in the title slot, since a nameplate has no
    article title, and the image sequence number as the page, as the FAQ's own
    example does. The city is added after the title (post 5 of the pinned
    thread does the same) because half the roster's titles do not name their
    town. Dates are U.S. order, his instruction, for this account alone. Their reply said the form is ours
    to choose; the credit sentence is the one thing they asked for."""
    meta = r["meta"]
    title = npc.display_title(meta.get("title"))
    city = (meta.get("city") or "").strip()
    seq = r["url"].rstrip("/").rsplit("-", 1)[-1]
    url = r["url"]
    where = f" {city}," if city else ""
    label = LANE_LABEL[r.get("lane", "nameplate")]
    head = f"[{label}], “{title},”{where} {npc.post_date(r['date'])}, p. {seq}, "
    tail = f". {CREDIT}\n\n"
    visible = url.replace("https://", "").rstrip("/")
    tags = [("tag", f"#{t}", t) for t in TAGS]
    tag_len = sum(len(t[1]) for t in tags) + len(tags) - 1
    if len(head) + len(visible) + len(tail) + tag_len > 300:
        visible = "gahistoricnewspapers.galileo.usg.edu/lccn/…"
    segs = [("text", head), ("link", visible, url), ("text", tail)]
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
            "market": "market report"}[lane]
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
    """Append one line a person can act on. The run does not wait for them."""
    line = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lccn": r["lccn"], "date": r["date"], "edition": r["edition"],
        "url": r["url"], "caption": r["caption"], "lane": r.get("lane"),
        "image_box": r.get("image_box"), "words": r.get("words"),
        "page_hits": r["page_hits"], "reasons": r["verdict"].reasons,
        "pass": state.get("pass"),
    }
    os.makedirs(DATA, exist_ok=True)
    with open(REVIEW_FILE, "a") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def choose(state, issues, log=print, lane="nameplate"):
    """Walk the owed titles and their dates until one clip PASSES. Returns
    (lccn, result) or (None, None). Every date looked at is recorded in
    state['tried'][lane] whether it passed or not, so a dry run that is then
    followed by a live run does not re-fetch, and a REVIEW is not re-offered
    next run."""
    tried = lane_tried(state, lane)
    for lccn in next_titles(state, issues, lane)[:TITLES_PER_RUN]:
        seen = set(tried.get(lccn, []))
        used = {(q["lccn"], q["date"]) for q in state.get("posted", []) if q.get("pass") == state["pass"]}
        for date, ed in dates_for(lccn, issues[lccn], state["pass"], lane):
            if date in seen or (lccn, date) in used:
                continue
            if len(seen) >= TRIES_PER_TITLE:
                break
            seen.add(date)
            tried[lccn] = sorted(seen)
            try:
                r = CLIP(lane, lccn, date, ed)
            except (npc.Refused, ghn_api.FetchError, ValueError) as e:
                log(f"  skip {lane} {lccn} {date}: {e}")
                continue
            if r["postable"]:
                return lccn, r
            log_review(r, state)
            log(f"  review {lane} {lccn} {date}: {'; '.join(r['verdict'].reasons)}")
        log(f"  {lane} {lccn}: nothing passed in {len(seen)} tries; next title")
    return None, None


def recent_titles(state, lane, n=RECENT_TITLE_WINDOW):
    """Titles this lane posted among its last `n` posts."""
    mine = [p["lccn"] for p in state.get("posted", []) if p.get("lane") == lane]
    return set(mine[-n:])


def choose_search(state, cands, lane, log=print):
    """A search lane: candidates are (lccn, date, ed, seq, phrase) from
    clips.search_candidates, walked in a seeded order that the pass number
    reshuffles, skipping what this lane has tried and the titles it posted
    recently. Bounded at SEARCH_TRIES a run."""
    tried = lane_tried(state, lane)
    order = list(cands)
    random.Random(f"{lane}:{state.get('pass', 1)}:{SHUFFLE_SEED}").shuffle(order)
    recent = recent_titles(state, lane)
    looked = 0
    for lccn, date, ed, seq, phrase in order:
        key = f"{lccn}:{date}:{seq}"
        if key in tried:
            continue
        if lccn in recent:
            continue
        if looked >= SEARCH_TRIES.get(lane, 8):
            break
        looked += 1
        tried[key] = phrase
        try:
            r = CLIP(lane, lccn, date, ed, seq, phrase)
        except (npc.Refused, ghn_api.FetchError, ValueError) as e:
            log(f"  skip {lane} {lccn} {date} p{seq}: {e}")
            continue
        if r["postable"]:
            return lccn, r
        log_review(r, state)
        log(f"  review {lane} {lccn} {date} p{seq}: {'; '.join(r['verdict'].reasons)}")
    return None, None


def next_lane(state):
    """The lane this run starts with: the rotation position of the next
    post, counting every post so far."""
    # ⚠️ Dry posts count too. Saved state never holds one (a dry run writes
    # no state), and counting them is what makes `--dry-run --count 4`
    # preview the rotation instead of four of the same lane, which is what
    # the first dry run produced.
    n = len(state.get("posted", []))
    return LANES[n % len(LANES)]


def pick(state, sources, lane, log=print):
    if lane in SEARCH_LANES:
        return choose_search(state, sources[lane], lane, log=log)
    return choose(state, sources[lane], log=log, lane=lane)


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
    ap.add_argument("--lane", choices=LANES, help="this lane only, instead of the rotation")
    ap.add_argument("--setup-profile", action="store_true", help="write name, bio and avatar")
    ap.add_argument("--launch", action="store_true", help="post the pinned thread (once)")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

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
    sources = {"nameplate": issues, "headline": dailies(issues), "article": dailies(issues),
               "ad": clips.ad_candidates(rights), "market": clips.market_candidates(rights)}
    client = None
    for n in range(args.count):
        start = LANES.index(args.lane) if args.lane else LANES.index(next_lane(state))
        lccn = r = None
        for k in range(len(LANES)):
            lane = LANES[(start + k) % len(LANES)]
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
              f"{', extended to the ink edge' if r.get('extended') else ''}; "
              f"crop {r['size'][0]}x{r['size'][1]}")
        if len(text) > 300:
            sys.exit(f"post is {len(text)} characters")
        if args.dry_run:
            state.setdefault("posted", []).append(
                {"lccn": lccn, "date": r["date"], "pass": state["pass"], "lane": r["lane"], "dry": True})
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
