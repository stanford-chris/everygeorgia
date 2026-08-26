#!/usr/bin/env python3
"""
nameplate_crop.py -- produce one nameplate clipping: the image, the caption and
the alt text, from a Georgia Historic Newspapers issue.

⛔⛔ THIS SCRIPT CANNOT POST AND MUST NEVER LEARN HOW. Nothing here imports
atproto, holds a credential or knows an account exists -- because none does.
everygeorgia has an unanswered permission request with the Digital Library of
Georgia (emailed 21 August 2026) and DLG's terms require written permission
from the holding institution to publish. Silence is not permission. This writes
files to disk and prints; that is the whole of it.

⚠️ It also defaults to writing NOTHING. `--out` is required to save an image.
That is the reverse of the scheduled bots in this estate, which post live on a
bare run -- and it is deliberate. See [[reference_seoul_index_dry_run_flag]]:
`seoul_index_post.py --help` published a real card on 20 July 2026 because the
flag question was only ever "is --dry-run present". A one-shot research tool for
an unlaunched account should fail closed.

⚠️ NO MODEL WRITES ANY OF THIS. The crop is chosen by arithmetic in
nameplate.py, and the caption and alt text are assembled from the title, city
and date the archive already holds exactly. That is the answer this lane
contributes to open question 2: the nameplate lane has nothing to disclose,
because nothing about it is generated.

Gates, in order, all of them in gates.py except the two about the image:

  1. geometry   nameplate.py finds a confident band, or refuses the page
  2. rights,    gates.check(): NoC-US recorded, before the 1931 cutoff, and
     era, crop  after this lane's era floor; and no sensitive term inside the
                band. That last is the belt: on 26 August 2026 a looser
                detector cropped "SHERIFF OF CARROLL FIRES ON THE MOB" out of
                the Macon Telegraph and called it a nameplate.
  3. page       ⚠️ the sensitive vocabulary anywhere on the page returns
                REVIEW, not a refusal. The crop cannot see the page it came
                from: measured, a headline crop carries what its page carries
                only 16.3% of the time. REVIEW keeps a person in it without
                erasing the titles that use this vocabulary most.
  4. shape      a nameplate is a wide, shallow strip. A crop that comes back
                nearly square means the band was wrong whatever the maths said.
  5. arrival    the bytes are a real JPEG of the size asked for. A curl 200 is
                not arrival.

⚠️ `clip()` returns a verdict and does NOT raise on REVIEW. A caller that
treats "not PASS" as "error" throws away the distinction this is built on.

Usage:
    python3 nameplate_crop.py sn89053135 1898-01-06            # report only
    python3 nameplate_crop.py sn89053135 1898-01-06 --out x.jpg
    python3 nameplate_crop.py --random --seed 5 --out /tmp/np.jpg
"""
import csv
import io
import os
import random
import sys

import gates
import ghn_api
import nameplate
from crop_frequency import (NEGRO_PREFIXES, SUBJECT_PREFIXES, noc_issues,
                            norm, score)

HERE = os.path.dirname(os.path.abspath(__file__))
RIGHTS_CSV = os.path.join(HERE, "data", "georgia_rights.csv")
CROP_WIDTH = 1600
MIN_ASPECT = 2.5          # gate 3: width/height of a nameplate strip
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


class Refused(Exception):
    """This issue is not usable. Say why, and skip it."""


def roster():
    with open(RIGHTS_CSV) as f:
        return {r["lccn"]: r for r in csv.DictReader(f)}


def uk_date(iso):
    """1898-01-06 -> 6 January 1898. UK order, no ordinal suffix."""
    y, m, d = iso.split("-")
    return f"{int(d)} {MONTHS[int(m) - 1]} {y}"


def describe(meta, date, page):
    """Caption and alt text, assembled from archive metadata only.

    ⚠️ House style: work titles take quotation marks, not italics, and the
    newspaper's own name is the work here. Dates are UK order."""
    title = (meta.get("title") or "").strip().rstrip(".")
    city = (meta.get("city") or "").strip()
    county = (meta.get("county") or "").strip()
    where = f"{city}, Georgia" if city else "Georgia"
    caption = (f"“{title},” {where}, {uk_date(date)}.")
    alt = (f"The nameplate of “{title},” a newspaper published in {where}"
           + (f" ({county} County)" if county else "")
           + f", as printed on {uk_date(date)}. "
           f"Scanned from microfilm; the page is worn and the ink uneven.")
    return caption, alt, f"{page.url}  (Georgia Historic Newspapers, Digital Library of Georgia)"


def check_words(words, box):
    """Gate 2. Raises Refused naming the term that stopped it."""
    inside = nameplate.words_in(words, box)
    for prefixes, label in ((SUBJECT_PREFIXES, "slavery/lynching/Klan"),
                            (NEGRO_PREFIXES, "negro")):
        hits = score(inside, prefixes)
        if hits:
            raise Refused(f"vocabulary gate: {label} {dict(hits)} inside the band")
    return inside


def check_image(data, want_width):
    """Gate 4 and gate 3. Returns (width, height)."""
    try:
        from PIL import Image
    except ImportError:                      # pragma: no cover
        raise Refused("Pillow not installed; cannot verify the crop -- "
                      "NOT CHECKED, refusing rather than trusting the bytes")
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception as e:                   # noqa: BLE001
        raise Refused(f"not a readable image ({e})") from e
    if im.width != want_width:
        raise Refused(f"server returned width {im.width}, asked for {want_width}")
    if im.height <= 0 or im.width / im.height < MIN_ASPECT:
        raise Refused(f"shape gate: {im.width}x{im.height} is not a nameplate strip")
    return im.width, im.height


def clip(lccn, date, ed=1, width=CROP_WIDTH, lane="nameplate"):
    """The whole pipeline for one issue.

    Returns a dict carrying `verdict`. Raises Refused only when there is
    nothing to show at all: no rights, wrong era, no geometry, or a crop that
    itself carries the vocabulary. A REVIEW verdict comes back as a normal
    result with `postable` False, because a person is meant to look at it."""
    page = None
    box = None
    inside = []
    words = []
    meta = roster().get(lccn)

    if meta is not None and meta.get("postable") == "yes" and date < "1931-01-01":
        page = ghn_api.front_page(lccn, date, ed)
        c = page.coords()
        words = c["words"]
        box = nameplate.nameplate_box(words, c["width"], c["height"])
        inside = nameplate.words_in(words, box) if box else []

    crop_hits = set()
    page_hits = set()
    for prefixes in (SUBJECT_PREFIXES, NEGRO_PREFIXES):
        crop_hits |= set(score(inside, prefixes))
        page_hits |= set(score(words, prefixes))

    verdict = gates.check(lane, lccn, date, crop_hits=crop_hits,
                          page_hits=page_hits, have_geometry=box is not None)
    if verdict.outcome == gates.REFUSE:
        raise Refused("; ".join(verdict.reasons))

    image_box = page.to_image(box)
    data = page.fetch_crop(image_box, width)
    w, h = check_image(data, width)
    caption, alt, credit = describe(meta, date, page)
    return {
        "lccn": lccn, "date": date, "edition": ed, "lane": lane,
        "verdict": verdict, "postable": verdict.postable,
        "band_fraction": box[3] / page.coords()["height"],
        "image_box": image_box, "size": (w, h),
        "words_in_band": [t[4] for t in inside],
        "page_hits": sorted(page_hits),
        "caption": caption, "alt": alt, "credit": credit,
        "bytes": data,
    }


def main():
    args = sys.argv[1:]
    out = None
    seed = None
    pick_random = False
    pos = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--random":
            pick_random = True
        elif a == "--out" and i + 1 < len(args):
            i += 1; out = args[i]
        elif a.startswith("--out="):
            out = a.split("=", 1)[1]
        elif a == "--seed" and i + 1 < len(args):
            i += 1; seed = int(args[i])
        elif a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])
        elif a.startswith("-"):
            sys.exit(f"unknown argument: {a}")
        else:
            pos.append(a)
        i += 1

    if pick_random:
        issues, _ = noc_issues()
        rng = random.Random(seed)
        for _ in range(40):                 # bounded: never loop for ever
            lccn, date, ed = rng.choice(issues)
            try:
                r = clip(lccn, date, ed)
                break
            except (Refused, ghn_api.FetchError, ValueError) as e:
                print(f"  skip {lccn} {date}: {e}", file=sys.stderr)
        else:
            sys.exit("40 draws, none passed the gates")
    else:
        if len(pos) < 2:
            sys.exit(__doc__.strip().split("Usage:")[1])
        try:
            r = clip(pos[0], pos[1], int(pos[2]) if len(pos) > 2 else 1)
        except (Refused, ghn_api.FetchError, ValueError) as e:
            sys.exit(f"refused: {e}")

    print(f"{r['lccn']} {r['date']} ed-{r['edition']}   [{r['verdict'].outcome}]")
    for why in r["verdict"].reasons:
        print(f"  gate       {why}")
    print(f"  band       {r['band_fraction']*100:.1f}% of page, "
          f"image box {r['image_box']}, crop {r['size'][0]}x{r['size'][1]}")
    print(f"  in band    {' '.join(r['words_in_band'][:18]) or '(no readable text)'}")
    print(f"  caption    {r['caption']}")
    print(f"  alt        {r['alt']}")
    print(f"  credit     {r['credit']}")
    if out and not r["postable"]:
        print("  ⚠️ NOT auto-postable: writing the file anyway so a person can "
              "look at it,\n     which is what REVIEW means.")
    if out:
        with open(out, "wb") as f:
            f.write(r["bytes"])
        print(f"  wrote      {out}")
    else:
        print("  (no --out given, so nothing was written)")


if __name__ == "__main__":
    main()
