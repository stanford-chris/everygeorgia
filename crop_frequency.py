#!/usr/bin/env python3
"""
crop_frequency.py -- step 5 of the everygeorgia plan: measure the sensitive
vocabulary at the CROP level rather than the page level.

Why this exists. The corpus measurement in README.md is page-level: one
pre-1931 front page in five carries slavery, lynching or Klan vocabulary and
nearly half mention "negro". Those figures decide nothing about a lane on their
own, because **the lanes are crops**. A nameplate is the top band of a page, and
a page that mentions lynching almost never mentions it in the masthead. The
README says outright that the crop-level measure "is still not possible and
waits on the rights join". The join finished on 22 August 2026. This is that
measure.

⚠️⚠️ CROP RATES AND PAGE RATES ARE COMPUTED BY THE SAME METHOD ON THE SAME
PAGES, and that is the only reason the comparison means anything. The README's
7.7% and 47.2% come from ONI's Solr index, which stems; this script matches OCR
word boxes with its own prefix rules. Comparing a crop rate measured here
against a page rate measured there would be comparing two methods and calling
the difference a finding. The page-level column below is this script's own, and
the README's figure is printed beside it only as a sanity check on the method.

⚠️ EVERY FIGURE IS AN UPPER BOUND ON SUBJECT. Search finds shape, never genre.
"slave" catches classical allusion and temperance rhetoric; "negro" spans
neutral news, church notices and the Black press writing about itself. A hit
here means the word is present, not that the crop is about it.

⚠️ TWO MEASURES, BECAUSE OCR CANNOT CARRY THE NAMEPLATE ONE ALONE. Display type
is the worst-recognised text on a page -- "THE ABBEVILLE CHRONICLE." OCRs as
't mraLE mK' -- so scoring a nameplate crop's OCR under-reports by construction.
The `--titles` pass therefore scores the 843 postable titles as EXACT strings
from the roster, which is the definitive answer for the title line itself. The
sampled OCR pass catches what the roster cannot see: mottos, ears, slogans, and
any headline that creeps into the band.

Usage:
    python3 crop_frequency.py --titles              # exact, offline, instant
    python3 crop_frequency.py --sample 120          # OCR pass over a sample
    python3 crop_frequency.py --calibrate --sample 60   # detector health only
    python3 crop_frequency.py --sample 40 --seed 7  # a different draw
"""
import csv
import glob
import json
import os
import random
import re
import sys
from collections import Counter

import ghn_api
import nameplate
from rights_join import identify

HERE = os.path.dirname(os.path.abspath(__file__))
RIGHTS_CACHE = os.path.join(HERE, "data", "rights")
RIGHTS_CSV = os.path.join(HERE, "data", "georgia_rights.csv")
CUTOFF = "1931-01-01"        # the project's own additional narrowing, never a
                             # substitute for the per-issue rights join
SEED = 20260826              # fixed, so a quoted figure can be reproduced

# ⚠️ Prefixes, not whole words: the point is to over-match. `lynch` takes
# lynched/lynching/lynchings, `slave` takes slaves and slavery. `klux` alone is
# the Klan marker because "ku" on its own is noise in OCR.
SUBJECT_PREFIXES = ("slave", "lynch", "klux")
NEGRO_PREFIXES = ("negro", "negre")     # negre*: a common OCR reading of negro
README_PAGE_RATES = {"subjects": 19.3, "negro": 47.2}   # front pages, pre-1931

WORD_RE = re.compile(r"[a-z]+")


def norm(text):
    """OCR token -> lowercase letters only. Returns '' for punctuation noise."""
    m = WORD_RE.findall((text or "").lower())
    return max(m, key=len) if m else ""


def score(words, prefixes):
    """Which of `prefixes` appear among these word boxes."""
    hits = Counter()
    for w in words:
        t = norm(w[4])
        if len(t) < 4:
            continue
        for p in prefixes:
            if t.startswith(p):
                hits[p] += 1
    return hits


def noc_issues():
    """Every distinct NoC-US issue in the cached DLG pages, pre-cutoff.

    ⚠️ Read through rights_join.identify(), never by re-parsing ids here.
    Roughly 15% of GHN records carry a batch-code id with no LCCN in it, and
    the rest carry a DLG `do:` URL rather than a GHN one -- a fresh regex
    written against a sample of either shape silently drops the other."""
    seen = set()
    files = sorted(glob.glob(os.path.join(RIGHTS_CACHE, "p*.json")))
    if not files:
        sys.exit("no cached DLG pages under data/rights/ -- run rights_join.py")
    for f in files:
        try:
            d = json.load(open(f))
        except (OSError, json.JSONDecodeError):
            continue
        for doc in d.get("response", {}).get("docs", []):
            hit = identify(doc)
            if hit and hit[1] < CUTOFF:
                seen.add(hit)
    return sorted(seen), len(files)


def title_pass():
    """Exact scoring of the postable titles. No network, no OCR, no sampling."""
    rows = [r for r in csv.DictReader(open(RIGHTS_CSV)) if r["postable"] == "yes"]
    if not rows:
        sys.exit("no postable titles in the rights csv")
    subj, neg = [], []
    for r in rows:
        toks = [norm(t) for t in re.split(r"\s+", r["title"])]
        if any(t.startswith(SUBJECT_PREFIXES) for t in toks if len(t) >= 4):
            subj.append(r["title"])
        if any(t.startswith(NEGRO_PREFIXES) for t in toks if len(t) >= 4):
            neg.append(r["title"])
    print(f"postable titles scored: {len(rows)}")
    print(f"  titles carrying slavery/lynching/Klan vocabulary: {len(subj)}")
    for t in subj:
        print(f"    - {t}")
    print(f"  titles carrying 'negro': {len(neg)}")
    for t in neg:
        print(f"    - {t}")
    print("\n⚠️ This is the title LINE only. It says nothing about a motto, an\n"
          "   ear or a slogan set beside the title, which the sampled OCR pass\n"
          "   below is what covers.")
    return len(rows), len(subj), len(neg)


def sample_pass(n, seed, calibrate=False):
    issues, npages = noc_issues()
    print(f"NoC-US pre-{CUTOFF[:4]} issues available: {len(issues):,} "
          f"(from {npages} cached DLG pages)", file=sys.stderr)
    rng = random.Random(seed)
    draw = rng.sample(issues, min(n, len(issues)))

    stats = Counter()
    band_fracs = []
    crop_examples = []
    for i, (lccn, date, ed) in enumerate(draw, 1):
        try:
            page = ghn_api.front_page(lccn, date, ed)
            c = page.coords()
        except (ghn_api.FetchError, ValueError) as e:
            stats["unreadable"] += 1
            print(f"  [{i}/{len(draw)}] {lccn} {date}: NOT CHECKED -- {e}",
                  file=sys.stderr)
            continue
        words = c["words"]
        if not words:
            stats["no_ocr"] += 1
            continue
        stats["scored_page"] += 1

        box = nameplate.nameplate_box(words, c["width"], c["height"])
        if box is None:
            stats["no_nameplate"] += 1
        else:
            stats["scored_crop"] += 1
            band_fracs.append(box[3] / c["height"])
            crop_words = nameplate.words_in(words, box)
            cs = score(crop_words, SUBJECT_PREFIXES)
            cn = score(crop_words, NEGRO_PREFIXES)
            if cs:
                stats["crop_subjects"] += 1
                crop_examples.append((lccn, date, "subjects", dict(cs)))
            if cn:
                stats["crop_negro"] += 1
                crop_examples.append((lccn, date, "negro", dict(cn)))

        if score(words, SUBJECT_PREFIXES):
            stats["page_subjects"] += 1
        if score(words, NEGRO_PREFIXES):
            stats["page_negro"] += 1
        if i % 10 == 0:
            print(f"  [{i}/{len(draw)}] ...", file=sys.stderr)

    print()
    print(f"sample: {len(draw)} issues, seed {seed}")
    print(f"  front pages read              {stats['scored_page']}")
    print(f"  NOT CHECKED (fetch failed)    {stats['unreadable']}")
    print(f"  no OCR at all                 {stats['no_ocr']}")
    print(f"  nameplate detected            {stats['scored_crop']}")
    print(f"  detector refused              {stats['no_nameplate']}")
    if band_fracs:
        band_fracs.sort()
        mid = band_fracs[len(band_fracs) // 2]
        print(f"  band height, median           {mid*100:.1f}% of page "
              f"(min {band_fracs[0]*100:.1f}%, max {band_fracs[-1]*100:.1f}%)")
    if calibrate:
        return stats

    p, c = stats["scored_page"], stats["scored_crop"]
    if not p or not c:
        sys.exit("nothing scored -- refusing to report a rate")
    print()
    print("  measure                       page      nameplate crop")
    for key, label in (("subjects", "slavery/lynching/Klan"), ("negro", "negro")):
        pr = stats[f"page_{key}"] / p * 100
        cr = stats[f"crop_{key}"] / c * 100
        print(f"  {label:<28} {pr:5.1f}%    {cr:5.1f}%"
              f"      (README page-level: {README_PAGE_RATES[key]}%)")
    if crop_examples:
        print("\n  every crop-level hit, for reading by eye:")
        for lccn, date, kind, hits in crop_examples:
            print(f"    {lccn} {date}  {kind}: {hits}")
    else:
        print("\n  no crop-level hit in this sample.")
    print("\n⚠️ Upper bounds on subject, and the crop column is additionally\n"
          "   depressed by display-type OCR. Read --titles beside it.")
    return stats


def main():
    args = sys.argv[1:]
    n, seed = 120, SEED
    titles = calibrate = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--titles":
            titles = True
        elif a == "--calibrate":
            calibrate = True
        elif a == "--sample" and i + 1 < len(args):
            i += 1; n = int(args[i])
        elif a.startswith("--sample="):
            n = int(a.split("=", 1)[1])
        elif a == "--seed" and i + 1 < len(args):
            i += 1; seed = int(args[i])
        elif a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])
        else:
            sys.exit(f"unknown argument: {a}")
        i += 1
    if titles:
        title_pass()
        if not calibrate and "--sample" not in " ".join(args):
            return
        print()
    sample_pass(n, seed, calibrate)


if __name__ == "__main__":
    main()
