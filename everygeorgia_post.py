#!/usr/bin/env python3
"""
everygeorgia_post.py -- post one nameplate clipping from Georgia Historic
Newspapers to Bluesky, as @georgianewspapers.bsky.social.

Permission: Donnie Summerlin, Digital Projects Archivist, UGA Libraries, by
email on 10 September 2026, to the request sent 21 August. One condition:
"credit the Digital Library of Georgia". Every post does, in the citation
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
a bad morning costs about 60 API calls and a normal one about 10. A title
that yields nothing in a pass is skipped for that pass, never for good.

⚠️ THE LAUNCH THREAD GATES THE DAILY POSTS. Before `--launch` has run, a
scheduled run prints one line and exits 0 (bothealthcheck and harden check 5
read non-zero exits as faults, and a job loaded ahead of its opening must not
raise them). After it, a missing thread is a fault: the account would open
with a masthead from Abbeville and no explanation of what any of it is.

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

import ghn_api
import nameplate_crop as npc
import profile as prof
from crop_frequency import noc_issues

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
STATE_FILE = os.path.join(DATA, "post_state.json")
REVIEW_FILE = os.path.join(DATA, "review.jsonl")

HANDLE = prof.HANDLE
KEYCHAIN_SERVICE = "everygeorgia-bluesky"
TAGS = ("Georgia", "History")       # two, broad, as everylibrary's; a tag
                                    # facet is what puts a post in a feed
TRIES_PER_TITLE = 5
TITLES_PER_RUN = 4
SHUFFLE_SEED = 20260911             # the day the poster was built; fixed so
                                    # the order is reproducible
MAX_IMAGE_BYTES = 950_000           # under Bluesky's ~1 MB blob limit
ALT_MAX = 1900
CREDIT = "Presented online by the Digital Library of Georgia."

CLIP = npc.clip                     # swapped by the tests; never call npc.clip
                                    # directly below this line


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
            return json.load(f)
    return {"order": [], "pass": 1, "posted": [], "tried": {}}


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, STATE_FILE)


def issues_by_title():
    """{lccn: [(date, ed), ...]} for every postable pre-1931 NoC-US issue,
    read through the rights join's own identifier logic."""
    issues, _ = noc_issues()
    by = collections.defaultdict(list)
    for lccn, date, ed in issues:
        by[lccn].append((date, ed))
    return dict(by)


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


def dates_for(lccn, issues, pass_no):
    """This title's issues in the order this pass tries them: seeded by the
    title and the pass, so a pass shows each title on a different date."""
    rng = random.Random(f"{lccn}:{pass_no}")
    out = list(issues)
    rng.shuffle(out)
    return out


def posted_this_pass(state, lccn):
    return any(p["lccn"] == lccn and p.get("pass") == state["pass"]
               for p in state.get("posted", []))


def next_titles(state, issues):
    """Titles still owed a post this pass, in order. Rolls the pass over when
    every title has either posted or been exhausted."""
    order = title_order(state, issues)
    for _ in range(2):
        tried = state.setdefault("tried", {})
        owed = []
        for lccn in order:
            if posted_this_pass(state, lccn):
                continue
            n_tried = len(tried.get(lccn, []))
            if n_tried >= min(TRIES_PER_TITLE, len(issues[lccn])):
                continue                    # exhausted this pass
            owed.append(lccn)
        if owed:
            return owed
        state["pass"] = state.get("pass", 1) + 1
        state["tried"] = {}
        print(f"Every title has been through; starting pass {state['pass']}.")
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
    town. Dates are UK order, house style. Their reply said the form is ours
    to choose; the credit sentence is the one thing they asked for."""
    meta = r["meta"]
    title = npc.display_title(meta.get("title"))
    city = (meta.get("city") or "").strip()
    seq = r["url"].rstrip("/").rsplit("-", 1)[-1]
    url = r["url"]
    where = f" {city}," if city else ""
    head = f"[Nameplate], “{title},”{where} {npc.uk_date(r['date'])}, p. {seq}, "
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
    return r["alt"][:ALT_MAX]


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
        "url": r["url"], "caption": r["caption"],
        "page_hits": r["page_hits"], "reasons": r["verdict"].reasons,
        "pass": state.get("pass"),
    }
    os.makedirs(DATA, exist_ok=True)
    with open(REVIEW_FILE, "a") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def choose(state, issues, log=print):
    """Walk the owed titles and their dates until one clip PASSES. Returns
    (lccn, result) or (None, None). Every date looked at is recorded in
    state['tried'] whether it passed or not, so a dry run that is then
    followed by a live run does not re-fetch, and a REVIEW is not re-offered
    next run."""
    tried = state.setdefault("tried", {})
    for lccn in next_titles(state, issues)[:TITLES_PER_RUN]:
        seen = set(tried.get(lccn, []))
        for date, ed in dates_for(lccn, issues[lccn], state["pass"]):
            if date in seen:
                continue
            if len(seen) >= TRIES_PER_TITLE:
                break
            seen.add(date)
            tried[lccn] = sorted(seen)
            try:
                r = CLIP(lccn, date, ed)
            except (npc.Refused, ghn_api.FetchError, ValueError) as e:
                log(f"  skip {lccn} {date}: {e}")
                continue
            if r["postable"]:
                return lccn, r
            log_review(r, state)
            log(f"  review {lccn} {date}: {'; '.join(r['verdict'].reasons)}")
        log(f"  {lccn}: nothing passed in {len(seen)} tries; next title")
    return None, None


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
    client = None
    for n in range(args.count):
        lccn, r = choose(state, issues)
        if r is None:
            print("Nothing passed the gates this run.")
            break
        segs = compose(r)
        text = text_of(segs)
        alt = alt_text(r)
        print("-" * 60)
        print(text)
        print(f"[{len(text)} chars]  [alt] {alt}")
        print(f"[band] {r['band_fraction']*100:.1f}% of page"
              f"{', extended to the ink edge' if r.get('extended') else ''}; "
              f"crop {r['size'][0]}x{r['size'][1]}")
        if len(text) > 300:
            sys.exit(f"post is {len(text)} characters")
        if args.dry_run:
            state.setdefault("posted", []).append(
                {"lccn": lccn, "date": r["date"], "pass": state["pass"], "dry": True})
            continue

        image = fit_image(r["bytes"])
        if client is None:
            client = login_client()
        res = client.send_images(text=to_builder(segs), images=[image],
                                 image_alts=[alt], image_aspect_ratios=[aspect_ratio(image)],
                                 langs=["en"])
        state.setdefault("posted", []).append({
            "lccn": lccn, "date": r["date"], "edition": r["edition"],
            "pass": state["pass"], "uri": res.uri,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        save_state(state)
        print(f"Posted {res.uri}")
        if n + 1 < args.count:
            time.sleep(2)

    if args.dry_run:
        print("\nDry run: nothing posted, no state written.")


if __name__ == "__main__":
    # Gated on __name__: this file is imported by its test suite, and patching
    # subprocess.run at import time would leak into every test in the process.
    sys.path.insert(0, SCRIPTS)
    import api_call_log
    api_call_log.install("everygeorgia_post.py")
    main()
