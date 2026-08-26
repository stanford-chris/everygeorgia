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
    python3 crop_frequency.py --lane headline --sample 120 --by-decade
    python3 crop_frequency.py --lane block --sample 120 --by-decade --slave-ads
"""
import csv
import glob
import json
import os
import random
import re
import sys
from collections import Counter

import gates
import ghn_api
import lanes
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

# ⚠️ The slave-sale scan is deliberately NARROW and exact. It asks whether a
# person-term and a sale-term sit in the SAME crop-sized block, which is the
# shape of a slave-sale notice: a few lines of body type in a classified
# column. It is not a subject classifier and will catch a runaway notice, a
# hiring advertisement and an estate sale alongside the thing it is looking
# for. That is the right direction to err for a gate.
PERSON_PREFIXES = ("negro", "negre", "slave", "wench", "mulatto")
SALE_PREFIXES = ("sale", "sold", "sell", "auction", "vendue", "hire",
                 "runaway", "reward")

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


LANES = ("nameplate", "headline", "ad", "block")


def crops_for(lane, words, cw, ch):
    """Candidate crops for a lane, in OCR space. Never raises."""
    if lane == "nameplate":
        b = nameplate.nameplate_box(words, cw, ch)
        return [b] if b else []
    if lane == "headline":
        nb = nameplate.nameplate_box(words, cw, ch)
        return lanes.headline_boxes(words, cw, ch, nb[3] if nb else 0)
    if lane == "ad":
        return lanes.display_ad_boxes(words, cw, ch)
    if lane == "block":
        return lanes.text_blocks(words, cw, ch)
    raise ValueError(f"unknown lane: {lane}")


def slave_ad_blocks(words, cw, ch):
    """Blocks where a person-term and a sale-term co-occur. Exact, not a model."""
    hits = []
    for b in lanes.text_blocks(words, cw, ch):
        inside = nameplate.words_in(words, b)
        if score(inside, PERSON_PREFIXES) and score(inside, SALE_PREFIXES):
            hits.append(b)
    return hits


def gate_pass(n, seed, lane):
    """What the gates actually cost: the outcome distribution over a sample,
    and which titles are sent to REVIEW most.

    ⚠️ REVIEW IS REPORTED SEPARATELY FROM REFUSE AND MUST STAY THAT WAY. They
    mean different things, and folding them together would hide exactly the
    effect this report exists to make visible."""
    issues, _ = noc_issues()
    rng = random.Random(seed)
    draw = rng.sample(issues, min(n, len(issues)))
    ros = gates.roster()
    counts = Counter()
    review_titles = Counter()
    seen_titles = Counter()
    era_lost = Counter()
    for i, (lccn, date, ed) in enumerate(draw, 1):
        title = (ros.get(lccn) or {}).get("title", lccn)
        seen_titles[title] += 1
        # the era and rights gates need no page at all, so check them first and
        # skip the fetch when they already decide it
        pre = gates.check(lane, lccn, date, have_geometry=True)
        if pre.outcome == gates.REFUSE:
            counts["REFUSE"] += 1
            if any("era gate" in r for r in pre.reasons):
                era_lost[date[:3] + "0s"] += 1
            continue
        try:
            page = ghn_api.front_page(lccn, date, ed)
            c = page.coords()
        except (ghn_api.FetchError, ValueError):
            counts["NOT CHECKED"] += 1
            continue
        words = c["words"]
        boxes = crops_for(lane, words, c["width"], c["height"])
        page_hits = set(score(words, SUBJECT_PREFIXES)) | set(score(words, NEGRO_PREFIXES))
        if not boxes:
            counts["REFUSE"] += 1
            continue
        best = None
        for box in boxes:
            inside = nameplate.words_in(words, box)
            ch = set(score(inside, SUBJECT_PREFIXES)) | set(score(inside, NEGRO_PREFIXES))
            v = gates.check(lane, lccn, date, crop_hits=ch, page_hits=page_hits)
            if best is None or (best.outcome, v.outcome) == (gates.REVIEW, gates.PASS) \
               or (best.outcome == gates.REFUSE and v.outcome != gates.REFUSE):
                best = v
        counts[best.outcome] += 1
        if best.outcome == gates.REVIEW:
            review_titles[title] += 1
        if i % 25 == 0:
            print(f"  [{i}/{len(draw)}] ...", file=sys.stderr)

    tot = sum(counts.values())
    print()
    print(f"gate impact, lane {lane}, {tot} issues, seed {seed}")
    print(f"  {gates.describe_policies()}")
    print()
    for k in ("PASS", "REVIEW", "REFUSE", "NOT CHECKED"):
        if counts[k]:
            print(f"  {k:<12} {counts[k]:4d}  {counts[k]/tot*100:5.1f}%")
    if era_lost:
        print("\n  refused by the era gate, by decade:")
        for d in sorted(era_lost):
            print(f"    {d}  {era_lost[d]}")
    if review_titles:
        print("\n  ⚠️ titles most often sent to REVIEW (a person decides; this is")
        print("     NOT a rejection, and it is printed so the effect is visible")
        print("     rather than silent):")
        for t, c_ in review_titles.most_common(8):
            print(f"    {c_:3d} of {seen_titles[t]:3d}  {t}")
    print("\n⚠️ A PASS share is not a supply figure. There are 218,505 postable")
    print("   pre-1931 issues, so even a low share leaves five figures of material.")
    return counts


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


def sample_pass(n, seed, calibrate=False, lane="nameplate", by_decade=False,
                slave_scan=False, since=None, until=None):
    issues, npages = noc_issues()
    if since or until:
        issues = [i for i in issues
                  if (not since or i[1] >= since) and (not until or i[1] < until)]
        print(f"date filter {since or '...'} to {until or '...'}: "
              f"{len(issues):,} issues", file=sys.stderr)
    print(f"NoC-US pre-{CUTOFF[:4]} issues available: {len(issues):,} "
          f"(from {npages} cached DLG pages)", file=sys.stderr)
    rng = random.Random(seed)
    draw = rng.sample(issues, min(n, len(issues)))

    st = Counter()
    dec = {}                      # decade -> Counter
    band_fracs = []
    examples = []
    for i, (lccn, date, ed) in enumerate(draw, 1):
        d = date[:3] + "0s"
        dd = dec.setdefault(d, Counter())
        try:
            page = ghn_api.front_page(lccn, date, ed)
            c = page.coords()
        except (ghn_api.FetchError, ValueError) as e:
            st["unreadable"] += 1
            print(f"  [{i}/{len(draw)}] {lccn} {date}: NOT CHECKED -- {e}",
                  file=sys.stderr)
            continue
        words = c["words"]
        if not words:
            st["no_ocr"] += 1
            continue
        st["scored_page"] += 1
        dd["pages"] += 1

        page_hit = False
        page_flagged = bool(score(words, SUBJECT_PREFIXES))
        if page_flagged:
            st["page_subjects"] += 1; dd["page_subjects"] += 1
        if score(words, NEGRO_PREFIXES):
            st["page_negro"] += 1; dd["page_negro"] += 1

        boxes = crops_for(lane, words, c["width"], c["height"])
        if not boxes:
            st["no_crop"] += 1
            continue
        st["pages_with_crop"] += 1
        dd["pages_with_crop"] += 1
        for box in boxes:
            st["crops"] += 1; dd["crops"] += 1
            band_fracs.append(box[3] / c["height"])
            inside = nameplate.words_in(words, box)
            cs, cn = score(inside, SUBJECT_PREFIXES), score(inside, NEGRO_PREFIXES)
            if cs:
                st["crop_subjects"] += 1; dd["crop_subjects"] += 1
            if cn:
                st["crop_negro"] += 1; dd["crop_negro"] += 1
            if page_flagged:
                st["crops_on_flagged"] += 1
                if cs or cn:
                    st["crop_any_on_flagged"] += 1
            if cs or cn:
                # ⚠️ Counted once per CROP, not summed from the two columns: a
                # crop carrying both terms is one bad crop, and adding the
                # columns printed "200.0%" before this was fixed.
                st["crop_any"] += 1; dd["crop_any"] += 1; page_hit = True
            if (cs or cn) and len(examples) < 12:
                examples.append((lccn, date, dict(cs), dict(cn)))
        if page_hit:
            st["pages_hit"] += 1; dd["pages_hit"] += 1

        if slave_scan:
            sb = slave_ad_blocks(words, c["width"], c["height"])
            if sb:
                st["slave_pages"] += 1; dd["slave_pages"] += 1
                st["slave_blocks"] += len(sb); dd["slave_blocks"] += len(sb)

        if i % 20 == 0:
            print(f"  [{i}/{len(draw)}] ...", file=sys.stderr)

    print()
    print(f"lane: {lane}    sample: {len(draw)} issues, seed {seed}")
    print(f"  front pages read              {st['scored_page']}")
    print(f"  NOT CHECKED (fetch failed)    {st['unreadable']}")
    print(f"  pages yielding a crop         {st['pages_with_crop']}")
    print(f"  pages yielding none           {st['no_crop']}")
    print(f"  crops produced                {st['crops']}")
    if band_fracs:
        band_fracs.sort()
        print(f"  crop height, median           "
              f"{band_fracs[len(band_fracs)//2]*100:.1f}% of page "
              f"(min {band_fracs[0]*100:.1f}%, max {band_fracs[-1]*100:.1f}%)")
    if calibrate:
        return st

    p_, cr = st["scored_page"], st["crops"]
    if not p_ or not cr:
        print("\n  no crop produced: nothing to report, and this is NOT a "
              "finding of safety.")
        return st
    print()
    print("  measure                       page      this lane's crops   pages w/ a hit")
    for key, label in (("subjects", "slavery/lynching/Klan"), ("negro", "negro")):
        print(f"  {label:<28} {st[f'page_{key}']/p_*100:5.1f}%    "
              f"{st[f'crop_{key}']/cr*100:5.1f}%")
    print(f"  {'either, per crop':<28} {'':>5}     {st['crop_any']/cr*100:5.1f}%")
    print(f"  {'either, per page':<28} {'':>5}     {'':>5}       "
          f"{st['pages_hit']/p_*100:5.1f}%")
    if st["crops_on_flagged"]:
        print()
        print("  ⚠️ On the pages whose BODY TEXT already carries slavery/lynching/Klan")
        print("     vocabulary, this lane's crops carry it "
              f"{st['crop_any_on_flagged']/st['crops_on_flagged']*100:.1f}% of the time")
        print(f"     ({st['crop_any_on_flagged']} of {st['crops_on_flagged']} crops). "
              "A LOW number here is not safety: it means")
        print("     the crop is blind to what the page is about, so the lane cannot")
        print("     screen itself on the crop alone.")
    if slave_scan:
        print()
        print(f"  slave-sale shape (person-term + sale-term in one block):")
        print(f"    pages carrying at least one   {st['slave_pages']} of {p_} "
              f"({st['slave_pages']/p_*100:.1f}%)")
        print(f"    blocks                        {st['slave_blocks']}")

    if by_decade:
        print()
        print("  by decade (pages / crops / % of crops carrying either term)")
        for d in sorted(dec):
            v = dec[d]
            if not v["crops"]:
                print(f"    {d}  pages {v['pages']:3d}  crops {v['crops']:4d}   -")
                continue
            rate = v["crop_any"] / v["crops"] * 100
            extra = (f"   slave-shape pages {v['slave_pages']}"
                     if slave_scan and v["slave_pages"] else "")
            print(f"    {d}  pages {v['pages']:3d}  crops {v['crops']:4d}   "
                  f"{rate:5.1f}%{extra}")

    if examples:
        print("\n  crop-level hits, for reading by eye:")
        for lccn, date, cs, cn in examples:
            print(f"    {lccn} {date}  {cs or ''} {cn or ''}")
    print("\n⚠️ Upper bounds on subject, and depressed by OCR quality. A lane "
          "geometry\n   that has not been designed yet is an assumption, not a "
          "specification.")
    return st


def main():
    args = sys.argv[1:]
    n, seed = 120, SEED
    since = until = None
    gate_report = False
    lane = "nameplate"
    by_decade = slave_scan = False
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
        elif a == "--lane" and i + 1 < len(args):
            i += 1; lane = args[i]
        elif a.startswith("--lane="):
            lane = a.split("=", 1)[1]
        elif a == "--by-decade":
            by_decade = True
        elif a == "--slave-ads":
            slave_scan = True
        elif a == "--gates":
            gate_report = True
        elif a == "--since" and i + 1 < len(args):
            i += 1; since = args[i]
        elif a.startswith("--since="):
            since = a.split("=", 1)[1]
        elif a == "--until" and i + 1 < len(args):
            i += 1; until = args[i]
        elif a.startswith("--until="):
            until = a.split("=", 1)[1]
        else:
            sys.exit(f"unknown argument: {a}")
        i += 1
    if titles:
        title_pass()
        if not calibrate and "--sample" not in " ".join(args):
            return
        print()
    if lane not in LANES:
        sys.exit(f"unknown lane: {lane} (one of {', '.join(LANES)})")
    if gate_report:
        gate_pass(n, seed, lane)
        return
    sample_pass(n, seed, calibrate, lane, by_decade, slave_scan, since, until)


if __name__ == "__main__":
    main()
