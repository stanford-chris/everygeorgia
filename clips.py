#!/usr/bin/env python3
"""
clips.py -- one clipping from any lane: the image, the citation pieces and
the alt text, through the same gates.

    clip("nameplate", lccn, date, ed)             -> nameplate_crop.clip()
    clip("headline",  lccn, date, ed)             the topmost display item
                                                   below the nameplate, with
                                                   its deck; words by model
    clip("ad",        lccn, date, ed)             the largest rule-closed item
                                                   whose own words sell
                                                   something; words by OCR,
                                                   by model when the OCR is
                                                   too poor to quote
    clip("market",    lccn, date, ed, seq, phrase) the column cell holding a
                                                   searched-for phrase; words
                                                   by OCR

Every lane returns the same dict nameplate_crop.clip() does, plus `lane`,
`words` (the text a reader is promised), `generated` (True when a model
wrote `words`, so the alt carries transcribe.PREFIX) and `seq`. Every lane
raises nameplate_crop.Refused when there is nothing to show, and returns a
REVIEW verdict as a result with `postable` False, exactly as the nameplate
lane does: a caller that treats "not PASS" as "error" throws away the
distinction gates.py is built on.

⚠️ THREE VOCABULARY PASSES, NOT TWO. gates.py reads the OCR of the crop and
of the page. For display type the OCR is the text it cannot read, so the
words a model transcribes are scored a third time and refuse the crop if
they carry the prefixes. That pass is what the nameplate lane's ink-edge gate
exists to stand in for, and here it is direct.

⚠️ Legibility is a gate, not a preference. An alt promising "the actual
words" and delivering 'jgF EXPRESS AND f' is worse than no post. OCR words
are quoted only when LEGIBLE of the tokens look like words; below that the
advertisement lane asks the model, and the market lane refuses (a price
table the OCR cannot read is not one a model reads better).
"""
import re

import gates
import ghn_api
import items
import nameplate
import nameplate_crop as npc
import rules
import transcribe
from crop_frequency import NEGRO_PREFIXES, SUBJECT_PREFIXES, norm, score

CROP_WIDTH = 1200
LEGIBLE = 0.80           # share of OCR tokens that look like words (0.72 let
                         # "seven dsvs the longest nine In or" through)
MIN_TOKENS = 6
AD_MARKERS = 3           # distinct advertising markers an item needs
MIN_AD_FRAC = 0.02       # an advertisement smaller than this of the page
                         # area is a classified line, not a display ad
MAX_ALT_WORDS = 1500

# ⚠️ Shape, never genre, as everywhere here: these are the words an
# advertisement is made of, and three distinct ones in one rule-closed item
# of display type is an advertisement on every page looked at on
# 11 September 2026, while no headline with its deck reached two.
AD_WORDS = ("sale", "sold", "sell", "sells", "selling", "buy", "price", "prices",
            "cheap", "cheapest", "druggist", "druggists", "dealer", "dealers",
            "guaranteed", "cure", "cures", "cured", "remedy", "manufactured",
            "manufacturers", "wholesale", "retail", "goods", "groceries", "wanted",
            "apply", "agent", "agents", "bros", "warranted", "trial", "bottle",
            "bottles", "store", "stock", "bargain", "bargains", "millinery",
            "clothing", "hardware", "furniture", "pills", "liver", "tonic",
            "offerings", "merchant", "merchants", "advertisement", "advertisements",
            "customers", "trade", "shoes", "hats", "dry", "orders", "terms")
# ⚠️ One of these alone makes a headline or an article an advertisement:
# "GROVER GRAHAM DYSPEPSIA REMEDY" and "A MERRY CHRISTMAS WITHOUT A BOX OF
# Huyler's CANDIES" both reached the feed preview on 11 September 2026 with
# fewer than the general markers a story could carry innocently.
STRONG_AD = ("remedy", "remedies", "cure", "cures", "druggist", "druggists", "pills",
             "tonic", "dyspepsia", "candies", "candy", "cigars", "tobacco", "whiskey",
             "whiskies", "sarsaparilla", "bargain", "bargains", "millinery", "castoria",
             "liniment", "bitters", "ointment", "cordial", "dealers", "wholesale")
PRICE_RE = re.compile(r"\$\d|\b\d+[\s-]?c(?:ts|ents?)?\b|¢")   # "25-cent", "cents", "cts"
MARKET_PHRASES = ("cotton market", "market report", "prices current",
                  "produce market", "local market", "wholesale prices")
# ⚠️ Genre-specific, as reference_ghn_lane_findings requires: "sarsaparilla"
# appears only in an advertisement (93,910 pages). Each phrase below was
# chosen for having no other life in a newspaper.
AD_PHRASES = ("sarsaparilla", "for sale by all druggists", "dry goods and notions",
              "sewing machines", "guaranteed to cure", "castoria", "liver pills",
              "wholesale and retail dealers", "buggies and wagons", "pianos and organs",
              "clothing and hats", "boots and shoes", "millinery goods")
MAX_BLOCK_FRAC = 0.25
MAX_BLOCK_W = 0.45       # a block wider than this of the page is not one item
MARKET_MAX_FRAC = 0.15   # a market column deeper than this is unreadable as a post
MIN_BLOCK_ROWS = 4
PARA_GAP = 1.3           # a row gap this many body heights is a paragraph break
MARKET_ROWS = 10         # ...and failing one, this many rows under the heading:
                         # the Marietta Journal sets its paragraphs with no
                         # extra lead at all
HEADLINE_MAX_FRAC = 0.16 # a headline item deeper than this has taken a second
                         # headline or a story with it
MIN_BLOCK_FRAC = 0.015


def wordlike(tok):
    t = tok.strip(".,;:!?()[]\"'“”‘’-")
    return len(t) >= 2 and sum(ch.isalpha() for ch in t) >= 0.8 * len(t)


def legibility(words):
    toks = [w[4] for w in words if w[4].strip()]
    if len(toks) < MIN_TOKENS:
        return 0.0, len(toks)
    return sum(1 for t in toks if wordlike(t)) / float(len(toks)), len(toks)


def reading_order(words):
    """Words in reading order: rows by top, then left to right."""
    rows = nameplate.rows_of(sorted(words, key=lambda w: (w[1], w[0])), row_tol=0.5)
    out = []
    for r in rows:
        out.extend(sorted(r, key=lambda w: w[0]))
    return out


def ocr_text(words):
    t = " ".join(w[4] for w in reading_order(words))
    return " ".join(t.split())


TOKEN_RE = re.compile(r"[a-z]+")
BAND_ALT_CHARS = 300


def cut_band(words, limit=BAND_ALT_CHARS):
    """The band's words for the alt: whole if they fit, else cut at the last
    item boundary (transcribe.join_items puts a period between items) or,
    failing one in the first half, at a word, and closed with an ellipsis.
    The period before the ellipsis is dropped so it reads "…WITH WILSON…"
    and not "WILSON.…"."""
    if len(words) <= limit:
        return words
    head = words[:limit]
    at = head.rfind(". ")
    if at < limit // 2:
        at = head.rfind(" ")
    if at <= 0:
        at = limit
    return head[:at].rstrip().rstrip(".") + "…"


def tokens(text):
    """⚠️ Not crop_frequency.norm(), which returns ONE token (the longest
    alphabetic run of a single OCR word). Fed a whole transcription it
    returned one word, and the first version of both passes below scored
    that one word: every advertisement had no advertising words and a
    transcription carrying "negro" reached REVIEW instead of REFUSE."""
    return TOKEN_RE.findall((text or "").lower())


def ad_markers(text):
    hits = {t for t in set(tokens(text)) if t in AD_WORDS}
    if PRICE_RE.search(text or ""):
        hits.add("$")
    return hits


def vocabulary_hits(text):
    fake = [(0, 0, 0, 0, t) for t in tokens(text)]
    return set(score(fake, SUBJECT_PREFIXES)) | set(score(fake, NEGRO_PREFIXES))


TABULAR = 0.12           # share of tokens carrying a figure in a market
                         # column. ⚠️ Not a clean table: the Savannah
                         # Morning News's commercial column of 6 February
                         # 1873 runs "Bacon.—clear rib sides 10 cts,
                         # shoulders 7 cts" as prose, and its figures OCR
                         # with a letter or two attached ("16@17c").


def tabular(words):
    toks = [w[4].strip() for w in words if w[4].strip()]
    if not toks:
        return 0.0
    figs = [t for t in toks if any(ch.isdigit() for ch in t) and sum(ch.isalpha() for ch in t) <= 2]
    return len(figs) / float(len(toks))


def _curl(s):
    return s.replace("'", "’").replace('"', "”")


def _loosen(box, coords, wfrac, hfrac):
    """A box with a margin of the page's own proportions on each side,
    clamped to the page. His request, 11 September 2026, on the Dublin
    article: "zoom out a little bit... it doesn't have to be quite so
    tight, and can include surrounding text, as long as the hed/article
    is the focus." The margin is a fraction of the PAGE, not of the box,
    so a one-line headline and a six-line one get the same air."""
    cw, ch = coords["width"], coords["height"]
    mx, my = int(cw * wfrac), int(ch * hfrac)
    x0 = max(0, box[0] - mx); y0 = max(0, box[1] - my)
    x1 = min(cw, box[0] + box[2] + mx); y1 = min(ch, box[1] + box[3] + my)
    return (x0, y0, x1 - x0, y1 - y0)


LOOSE_W = 0.035          # margin either side of a headline or article, of
LOOSE_H = 0.018          # the page's width, and above and below, of its height


def _fetch(page, box_ocr, width=CROP_WIDTH):
    image_box = page.to_image(box_ocr)
    w = min(width, image_box[2])
    data = page.fetch_crop(image_box, w)
    npc._open_image(data)
    return image_box, data


def _verdict(lane, lccn, date, crop_words, page_words, have):
    crop_hits, page_hits = set(), set()
    for prefixes in (SUBJECT_PREFIXES, NEGRO_PREFIXES):
        crop_hits |= set(score(crop_words, prefixes))
        page_hits |= set(score(page_words, prefixes))
    v = gates.check(lane, lccn, date, crop_hits=crop_hits, page_hits=page_hits,
                    have_geometry=have)
    if v.outcome == gates.REFUSE:
        raise npc.Refused("; ".join(v.reasons))
    return v, sorted(page_hits)


def _review(verdict, reason):
    """The verdict downgraded to REVIEW with `reason` added: a hit in the
    words a MODEL read out of the crop (the band under a nameplate, a
    transcribed headline, article or advertisement), which gates.check()
    never saw because the OCR could not read them. REVIEW is queued for a
    person and never posted, exactly as the page gate's is. Until
    11 September 2026 these raised Refused; his call: "I'd like to look at
    them."
    """
    return gates.Verdict(gates.REVIEW, list(verdict.reasons)
                         + [f"{reason}; a person decides, this is not a rejection"])


def _result(lane, page, meta, date, ed, box, image_box, data, verdict,
            page_hits, words, generated, extra=None):
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(data))
    r = {
        "lccn": page.lccn, "date": date, "edition": ed, "seq": page.seq, "lane": lane,
        "verdict": verdict, "postable": verdict.postable,
        "band_fraction": box[3] / float(page.coords()["height"]),
        "extended": False, "meta": meta, "url": page.url,
        "image_box": image_box, "size": (im.width, im.height),
        "words_in_band": [], "page_hits": page_hits,
        "words": words, "generated": generated,
        "caption": "", "alt": "", "credit": f"{page.url}  (Georgia Historic Newspapers, Digital Library of Georgia)",
        "bytes": data,
    }
    r.update(extra or {})
    return r


def _meta(lccn, date, lane=None):
    meta = npc.roster().get(lccn)
    if meta is None or meta.get("postable") != "yes":
        raise npc.Refused(f"{lccn} has no NoC-US issue recorded")
    if gates.CUTOFF and date >= gates.CUTOFF:
        raise npc.Refused(f"{date} is on or after the cutoff")
    floor = gates.earliest(lane) if lane else None
    if floor and date < floor:
        raise npc.Refused(f"era gate: {lane} starts at {floor}")
    return meta


NAMEPLATE_CONTEXT = 0.50  # of the page's height below the masthead band: the
                          # fold. Was 0.14 ("the lead headlines, not the fold",
                          # his request of 11 September 2026), then 0.32 that
                          # evening ("Can we make the clip deeper?"), then 0.50
                          # an hour later ("Want to go as deep as possible",
                          # settled on the fold as the deepest setting that
                          # costs no resolution). Measured on the Dawson
                          # Journal (1867) and the Cordele Dispatch (1925):
                          # 58 percent of the page, 1600 wide, under 700 KB.
                          # At 0.70 the 1867 page already exceeds Bluesky's
                          # ~1 MB and fit_image shrinks it to 1280 wide; at 1.00
                          # both pages are whole and the Cordele one is 2048
                          # tall, past the client's 2000 px cap. The band the
                          # model transcribes for the vocabulary check grows
                          # with it (about a minute at 0.32).


def clip_nameplate(lccn, date, ed=1, log=print):
    """The nameplate lane's crop, extended down into the top of the page.

    ⚠️ This reopens the one risk the nameplate lane never had. Its safety
    case was that a paper's name cannot be about a lynching; the band under
    it can, and the OCR cannot be trusted to say so (the Banner-Herald's
    unread headline). So the extension is transcribed by the model and
    scored against the vocabulary prefixes exactly as a headline is, and a
    hit sends the post to REVIEW (a refusal until 11 September 2026; his
    call: "I'd like to look at them"). The alt keeps the nameplate description
    and adds the transcription, labelled."""
    r = npc.clip(lccn, date, ed)
    page = ghn_api.front_page(lccn, date, ed)
    c = page.coords()
    cw, ch = c["width"], c["height"]
    band_h = int(r["band_fraction"] * ch)
    ext = (0, 0, cw, min(ch, band_h + int(NAMEPLATE_CONTEXT * ch)))
    below = (0, band_h, cw, ext[3] - band_h)
    _, strip = _fetch(page, below, width=1600)
    # ⚠️ Display type only (transcribe.BAND_PROMPT): the body text in the
    # strip is the OCR's to read and the page gate's to screen. An empty
    # string is a band with no display type, which is a pass; None is a
    # call that failed.
    # ⚠️ max_chars 8000, not 2000: at the fold (NAMEPLATE_CONTEXT 0.50) the
    # Dawson Journal's band came back at 2,701 and 2,118 characters and was
    # refused for LENGTH on 11 September 2026, so the poster skipped the one
    # page it was meant to repost. The band's words serve the vocabulary
    # check and are cut to 300 for the alt; length is no reason to refuse.
    words = transcribe.transcribe(strip, date[:4], log=log, max_chars=8000,
                                  prompt=transcribe.BAND_PROMPT)
    if words is None:
        raise npc.Refused("the band under the nameplate could not be transcribed")
    hits = vocabulary_hits(words)
    if hits:
        r["verdict"] = _review(r["verdict"], f"the band under the nameplate carries {sorted(hits)}")
        r["postable"] = False
    image_box, data = _fetch(page, ext, width=1600)
    r.update({"seq": 1, "words": _curl(cut_band(words)) if words else "",
              "generated": bool(words),
              "bytes": data, "image_box": image_box,
              "band_fraction": ext[3] / float(ch), "context": True})
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(data)); r["size"] = (im.width, im.height)
    return r


INNER_SHARE = 0.0        # share of headline and article draws that go to an
                         # inner page. His ask, 11 September 2026: "pull heds/
                         # articles from inside pages, too." ⚠️ MEASURED THE
                         # SAME DAY AND SET TO ZERO: 25 tries on pages 2, 3
                         # and 5 of six dailies, 1895-1926, gave five passes,
                         # of which one was news (Dr. Crippen's hanging, the
                         # Augusta Herald, 1910), one a poem, two soap and
                         # stove-wood advertisements the marker test could
                         # not see, and one a masthead. Inner pages in this
                         # corpus are advertising. The capability stays for a
                         # hand-picked page (`--seq` through clip()); raise
                         # this only with a better test for an ad than words.
INNER_MAX_SEQ = 8        # no deeper than this: past it a daily is classifieds
RUNNING_HEAD = 0.05      # the top of an inner page is the running head, skipped


def choose_page(lccn, date, ed, seq=None):
    """The page a headline or article is taken from. seq given: that page.
    Otherwise a seeded draw: the front page INNER_SHARE of the time less,
    else a random inner page up to INNER_MAX_SEQ. Seeded by the issue, so
    a dry run and the live run that follows it agree."""
    import random
    pages = ghn_api.issue_pages(lccn, date, ed)
    if seq:
        if seq < 1 or seq > len(pages):
            raise npc.Refused(f"no seq-{seq} in this issue")
        return pages[seq - 1]
    rng = random.Random(f"{lccn}:{date}:page")
    if len(pages) < 2 or rng.random() >= INNER_SHARE:
        return pages[0]
    return pages[rng.randint(2, min(len(pages), INNER_MAX_SEQ)) - 1]


def _headline_item(c, page):
    """(box, words inside) of the topmost display item below the nameplate
    that is not itself an advertisement, or None. On an inner page there is
    no nameplate, and the running head at the top is skipped instead."""
    floor = RUNNING_HEAD * c["height"] if page.seq > 1 else 0
    # ⚠️ "Below the nameplate" is now literal. On the Atlanta Georgian and
    # News of 3 July 1907 the topmost display item was the nameplate's own
    # lower half and dateline, and it POSTED at 18:41 KST on 11 September
    # 2026 as a headline reading "AND NEWS LANTA, GA., WEDNESDAY, JULY"
    # (deleted). A front page's floor is the bottom of the nameplate band the
    # nameplate lane itself finds, when it finds one.
    if page.seq == 1:
        np_box = nameplate.nameplate_box(c["words"], c["width"], c["height"])
        if np_box:
            floor = max(floor, np_box[1] + np_box[3])
    for s, raw, seg in items.snapped("headline", page, c):
        if s[1] < floor:
            continue
        inside = nameplate.words_in(c["words"], s)
        if len(ad_markers(ocr_text(inside))) >= AD_MARKERS:
            continue
        return s, inside
    return None


def strong_ad_markers(text):
    return {t for t in set(tokens(text)) if t in STRONG_AD}


def _check_transcription(words, what, ad_limit=2):
    """Refuses a transcription that is not a `what`; returns the sensitive
    vocabulary it carries, for the caller to turn into a REVIEW."""
    plain = [t for t in tokens(words) if t != "illegible"]
    if len(plain) < 3 or sum(1 for t in plain if len(t) >= 4) < 3:
        raise npc.Refused(f"transcription too short or too broken to be a {what}: {words!r}")
    if words.count("[illegible]") > len(plain) // 2:
        raise npc.Refused(f"transcription mostly illegible: {words!r}")
    # ⚠️ A headline with ONE unread word is not a headline a reader can
    # read: "U. S. TO [illegible] COMM[illegible] CAPITAL WOULD" passed the
    # half rule and reached the feed preview on 11 September 2026. An
    # article is a paragraph and keeps the half rule.
    if what == "headline" and "[illegible]" in words:
        raise npc.Refused(f"headline transcription has an unread word: {words!r}")
    if len(ad_markers(words)) >= ad_limit or strong_ad_markers(words):
        raise npc.Refused(f"transcription reads as an advertisement: {words!r}")
    return vocabulary_hits(words)


def _fold(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


DAYS = r"(?:MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)"
MONTHS = r"(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)"
DATELINE = re.compile(rf"\bGA\.?,?\s+{DAYS}\b|\b{DAYS}\s*(?:MORNING|EVENING)?,?\s+{MONTHS}\b", re.IGNORECASE)


def _refuse_own_title(words, meta, what):
    """A headline crop that carries the paper's own name has taken the
    nameplate: on the Americus Times-Recorder of 9 June 1915 a skyline
    headline above the masthead made the OCR band end above the real
    nameplate, and the "headline" beneath it read AMERICUS TIMES-RECORDER
    CITY EDITION. The geometry now stops at a taller line; this is the
    belt, on the words a reader would be given."""
    title = _fold(meta.get("title"))
    if len(title) >= 6 and title in _fold(words):
        raise npc.Refused(f"the {what} crop carries the paper's own name: {words[:80]!r}")
    # ⚠️ Whole-title containment slept through "AND NEWS LANTA, GA.,
    # WEDNESDAY, JULY" on the Atlanta Georgian and News (11 September 2026):
    # a crop that takes the FOOT of a nameplate carries a fragment of the
    # name, never the whole. Two belts: any two consecutive words of the
    # title appearing consecutively in the transcription, and a dateline
    # (GA. before a weekday, or a weekday before a month), which no headline
    # carries and every nameplate's underline does.
    tt = [t for t in re.findall(r"[a-z]+", (meta.get("title") or "").lower()) if t != "the"]
    wt = re.findall(r"[a-z]+", words.lower())
    pairs = {(a, b) for a, b in zip(tt, tt[1:]) if len(a) + len(b) >= 6}
    if any((a, b) in pairs for a, b in zip(wt, wt[1:])):
        raise npc.Refused(f"the {what} crop carries part of the paper's own name: {words[:80]!r}")
    if DATELINE.search(words):
        raise npc.Refused(f"the {what} crop carries a dateline: {words[:80]!r}")


def clip_headline(lccn, date, ed=1, seq=None, log=print):
    meta = _meta(lccn, date, "headline")
    page = choose_page(lccn, date, ed, seq)
    c = page.coords()
    chosen = _headline_item(c, page)
    if chosen is None:
        raise npc.Refused("no headline item below the nameplate")
    box, inside = chosen
    verdict, page_hits = _verdict("headline", lccn, date, inside, c["words"], True)
    if box[3] < 0.015 * c["height"]:
        raise npc.Refused("headline item too small")
    if box[3] > HEADLINE_MAX_FRAC * c["height"]:
        raise npc.Refused(f"headline item too deep ({box[3] / c['height']:.0%} of the page)")
    # ⚠️ The words come from the TIGHT crop and the picture is the loose one:
    # transcribing the loose crop put the story's first line into the
    # headline's alt ("...IS REPORT HUNTSVILLE, Ala., April 26.").
    _, tight = _fetch(page, box)
    words = transcribe.transcribe(tight, date[:4], log=log, prompt=transcribe.HEADLINE_PROMPT)
    if not words:
        raise npc.Refused("headline could not be transcribed")
    image_box, data = _fetch(page, _loosen(box, c, LOOSE_W, LOOSE_H))
    hits = _check_transcription(words, "headline")
    _refuse_own_title(words, meta, "headline")
    if hits:
        verdict = _review(verdict, f"the transcribed headline carries {sorted(hits)}")
    return _result("headline", page, meta, date, ed, box, image_box, data,
                   verdict, page_hits, _curl(words), True)


ARTICLE_LINES = 10       # lines of the paragraph, at most (14 ran a fifth of the page)
ARTICLE_MAX_FRAC = 0.22
TIGHT_GAP = 0.6          # lines closer than this (in body heights) are one paragraph
INDENT = 1.2             # a line starting this far right of the others begins a new one


def _lines(rows, med):
    """Merge the sub-rows rows_of() makes of one printed line (a wrapped
    word's box sits lower than its neighbours' and becomes a row of one)
    into lines: a row whose top is above the previous line's bottom joins
    it. Returns [(top, bottom, left, words)]."""
    out = []
    for rw in rows:
        top = min(w[1] for w in rw); bot = max(w[1] + w[3] for w in rw); left = min(w[0] for w in rw)
        if out and top < out[-1][1] - 0.2 * med:
            t, b, l, ws = out[-1]
            out[-1] = (min(t, top), max(b, bot), min(l, left), ws + list(rw))
        else:
            out.append((top, bot, left, list(rw)))
    return out


def clip_article(lccn, date, ed=1, seq=None, log=print):
    """The headline item plus its first paragraph. His ask, 11 September
    2026: "a headline and first graf."

    ⚠️ Decks and body are told apart by SPACING, not size. On the Macon
    Telegraph of 15 January 1897 the decks are bold body-height lines set
    two ems apart, and the paragraph is lines of the same height set tight;
    a height rule ended the crop inside the decks. So: everything under the
    headline down to the first run of three tight lines is furniture and
    is kept; the run is the paragraph; it ends at the next indented line
    (a new paragraph), a wider gap, or ARTICLE_LINES. Transcribed whole by
    the model."""
    meta = _meta(lccn, date, "article")
    page = choose_page(lccn, date, ed, seq)
    c = page.coords()
    chosen = _headline_item(c, page)
    if chosen is None:
        raise npc.Refused("no headline item below the nameplate")
    hbox, inside = chosen
    ch = c["height"]
    if hbox[3] > HEADLINE_MAX_FRAC * ch:
        raise npc.Refused("headline item too deep")
    med = nameplate.page_median_height(c["words"]) or 1
    x0, x1 = hbox[0], hbox[0] + hbox[2]
    hbot = hbox[1] + hbox[3]
    below = [w for w in c["words"] if x0 <= w[0] + w[2] / 2.0 < x1 and w[1] >= hbot - med]
    lines = [ln for ln in _lines(_rows(below), med) if ln[0] >= hbot - med]
    if len(lines) < 4:
        raise npc.Refused("no paragraph of body text under the headline")
    gaps = [lines[0][0] - hbot] + [lines[i][0] - lines[i - 1][1] for i in range(1, len(lines))]
    tight = lambda i: gaps[i] < TIGHT_GAP * med
    # the paragraph starts at the first line followed by two tight lines
    start = None
    for i in range(len(lines) - 2):
        if tight(i + 1) and tight(i + 2) and max(w[3] for w in lines[i][3]) < 1.6 * med:
            start = i
            break
        if lines[i][0] - hbot > ARTICLE_MAX_FRAC * ch:
            break
    if start is None:
        raise npc.Refused("no paragraph of body text under the headline")
    lefts = sorted(ln[2] for ln in lines[start:start + 12])
    left_mode = lefts[len(lefts) // 2]
    end = start
    for i in range(start + 1, len(lines)):
        if not tight(i):
            break
        if i - start >= 2 and lines[i][2] > left_mode + INDENT * med:
            break                               # an indented line: the next paragraph
        if lines[i][1] - hbox[1] > ARTICLE_MAX_FRAC * ch:
            break
        end = i
        if end - start + 1 >= ARTICLE_LINES:
            break
    if end - start + 1 < 3:
        raise npc.Refused("paragraph under the headline is under three lines")
    bottom = lines[end][1]
    box = (hbox[0], hbox[1], hbox[2], int(bottom + 0.6 * med) - hbox[1])
    words_in = nameplate.words_in(c["words"], box)
    verdict, page_hits = _verdict("article", lccn, date, words_in, c["words"], True)
    _, tight = _fetch(page, box)
    words = transcribe.transcribe(tight, date[:4], log=log)
    if not words:
        raise npc.Refused("article could not be transcribed")
    image_box, data = _fetch(page, _loosen(box, c, LOOSE_W, LOOSE_H))
    # ⚠️ Four markers for an article, not two: a news paragraph on the British
    # Order in Council "shutting off German trade" carried "trade" and
    # "orders" and was refused as an advertisement at two.
    hits = _check_transcription(words, "article", ad_limit=4)
    _refuse_own_title(words, meta, "article")
    if hits:
        verdict = _review(verdict, f"the transcribed article carries {sorted(hits)}")
    return _result("article", page, meta, date, ed, box, image_box, data,
                   verdict, page_hits, _curl(words), True)


def clip_ad(lccn, date, ed=1, seq=1, phrase=None, log=print):
    """With a phrase (from AD_PHRASES, via search): the block of set text
    around it, which is where legible advertising lives. Without one: the
    largest rule-closed display item on the front page whose OCR sells
    something, which on most pages the OCR cannot read well enough to say."""
    meta = _meta(lccn, date)
    pages = ghn_api.issue_pages(lccn, date, ed)
    if seq < 1 or seq > len(pages):
        raise npc.Refused(f"no seq-{seq} in this issue")
    page = pages[seq - 1]
    c = page.coords()
    area = float(c["width"] * c["height"])
    if phrase:
        hit = find_phrase(c["words"], phrase)
        if not hit:
            raise npc.Refused(f"phrase {phrase!r} not found on the page's OCR")
        pi = rules.PageInk(page)
        box = block_around(pi, c, hit, allow_display=True, log=log)
        if not box:
            raise npc.Refused("the advertisement could not be closed on the grid")
        inside = nameplate.words_in(c["words"], box)
        text = ocr_text(inside)
        if len(ad_markers(text)) < 2:
            raise npc.Refused("the block around the phrase does not read as an advertisement")
    else:
        best = None
        for s, raw, seg in items.snapped("ad", page, c):
            inside = nameplate.words_in(c["words"], s)
            text = ocr_text(inside)
            if len(ad_markers(text)) < AD_MARKERS:
                continue
            if s[2] * s[3] < MIN_AD_FRAC * area:
                continue
            if best is None or s[2] * s[3] > best[0][2] * best[0][3]:
                best = (s, inside, text)
        if best is None:
            raise npc.Refused("no rule-closed advertisement with advertising words")
        box, inside, text = best
    verdict, page_hits = _verdict("ad", lccn, date, inside, c["words"], True)
    image_box, data = _fetch(page, box)
    leg, n = legibility(inside)
    if leg >= LEGIBLE:
        words, generated = text, False
    else:
        words = transcribe.transcribe(data, date[:4], log=log)
        if not words:
            raise npc.Refused(f"advertisement OCR illegible ({leg:.0%}) and not transcribed")
        generated = True
        hits = vocabulary_hits(words)
        if hits:
            verdict = _review(verdict, f"the transcribed advertisement carries {sorted(hits)}")
    return _result("ad", page, meta, date, ed, box, image_box, data, verdict,
                   page_hits, _curl(words), generated, {"phrase": phrase})


def _rows(words):
    return [sorted(rw, key=lambda w: w[0])
            for rw in nameplate.rows_of(sorted(words, key=lambda w: (w[1], w[0])), row_tol=0.5)]


def block_around(pi, coords, seed, allow_display, log=print, max_frac=None):
    """The column block of set text around `seed` words: x from the page's
    gutters (rules.py), rows from the OCR, walking up and down from the
    seed's row while rows are close together and no printed rule lies
    between them. `allow_display` keeps display-size rows (an ad's own
    heading); without it a display row ends the block (the next item's
    heading ends a market table). Returns an OCR box or None.

    ⚠️ Rows, not pixels, for the vertical extent. The pixel gap walk found
    nothing to close on 17 of 40 market pages: body type is set with gaps
    smaller than any page-relative gap and the walk ran to its cap. Rows
    know where lines are; the pixels are asked only whether a rule sits
    between two of them."""
    cw, ch = coords["width"], coords["height"]
    words = coords["words"]
    med = nameplate.page_median_height(words) or 1
    x0 = min(w[0] for w in seed); x1 = max(w[0] + w[2] for w in seed)
    y0 = min(w[1] for w in seed); y1 = max(w[1] + w[3] for w in seed)
    cb = pi.column_bounds(pi.from_ocr((x0, y0, x1 - x0, y1 - y0)), mode="column")
    if cb is None or (cb[1] - cb[0]) > MAX_BLOCK_W * pi.w:
        return None
    per = pi.page.scale * pi.scale                    # small px per OCR unit
    cx0, cx1 = int(cb[0] / per), int(cb[1] / per)
    incol = [w for w in words if cx0 <= w[0] + w[2] / 2.0 < cx1]
    rows = _rows(incol)
    if not rows:
        return None
    # the row holding the seed
    sy = (y0 + y1) / 2.0
    idx = min(range(len(rows)), key=lambda i: abs(min(w[1] for w in rows[i]) + max(w[3] for w in rows[i]) / 2.0 - sy))
    cap = (max_frac or MAX_BLOCK_FRAC) * ch
    sx0, sx1 = cb

    def rule_between(ya, yb):
        # ⚠️ With a margin either side: OCR word boxes are taller than the
        # glyphs, so a rule sits INSIDE the box rows as often as between
        # them, and a search-driven ad crop chained three advertisements
        # through two clearly printed rules before the margin was added.
        a, b = pi.y_small(ya) - 4, pi.y_small(yb) + 4
        if b <= a:
            return False
        dark = pi.row_dark(sx0, sx1, a, b)
        return any(d >= rules.HRULE_MIN_DARK for d in dark)

    def row_top(i):
        return min(w[1] for w in rows[i])

    def row_bot(i):
        return max(w[1] + w[3] for w in rows[i])

    def row_h(i):
        return max(w[3] for w in rows[i])

    def is_display(i):
        return row_h(i) >= 1.6 * med

    lo = hi = idx
    while lo > 0:
        j = lo - 1
        gap = row_top(lo) - row_bot(j)
        if gap > 2.2 * med or rule_between(row_bot(j), row_top(lo)):
            break
        if is_display(j) and not allow_display:
            break
        if row_bot(hi) - row_top(j) > cap:
            # ⚠️ The top is the cap, not a rule or a gap: the block begins
            # mid-item ("ment is seven days the longest", Savannah Morning
            # News, 13 January 1871). Nothing to show.
            return None
        lo = j
        if is_display(j) and allow_display:
            continue
    paragraphs = 0
    while hi < len(rows) - 1:
        j = hi + 1
        gap = row_top(j) - row_bot(hi)
        if gap > 2.2 * med or rule_between(row_bot(hi), row_top(j)):
            break
        if is_display(j) and not allow_display and j > idx:
            break
        # ⚠️ A market report is its heading and the paragraph under it. The
        # Marietta Journal of 21 November 1878 ran "Marietta Market Report"
        # as the first item of its local notes, and the walk carried on
        # through the court week and a robbery. A paragraph break (a gap
        # over PARA_GAP of the body type) after at least three rows below
        # the seed ends the block when `allow_display` is off.
        if not allow_display and (gap > PARA_GAP * med and j - idx > 3 or j - idx > MARKET_ROWS):
            break
        if row_bot(j) - row_top(lo) > cap:
            break
        hi = j
    top, bot = row_top(lo), row_bot(hi)
    # ⚠️ A block is at least MIN_BLOCK_ROWS rows and MIN_BLOCK_FRAC of the
    # page: "MOTT'S LIVER PILLS cure torpidity" came back as a two-line
    # sliver 0.7% of the page deep, a reading notice cut from its column.
    if hi - lo + 1 < MIN_BLOCK_ROWS or (bot - top) < MIN_BLOCK_FRAC * ch:
        return None
    pad = int(1.0 * med)                 # 0.6 cut the top line of a Savannah
                                         # produce column through its figures
    return (cx0, max(0, top - pad), cx1 - cx0, min(ch, bot + pad) - max(0, top - pad))


def find_phrase(words, phrase):
    """The word boxes of the first occurrence of `phrase` in reading order."""
    toks = tokens(phrase)
    seq = reading_order(words)
    normed = [norm(w[4]).strip() for w in seq]
    # ⚠️ Prefix, not equality: the search stems, so "market report" is
    # answered with pages saying "market reports" and "Local Markets".
    for i in range(len(seq) - len(toks) + 1):
        if all(normed[i + k].startswith(toks[k]) for k in range(len(toks))):
            return seq[i:i + len(toks)]
    return None


def clip_market(lccn, date, ed=1, seq=1, phrase="cotton market", log=print):
    meta = _meta(lccn, date)
    pages = ghn_api.issue_pages(lccn, date, ed)
    if seq < 1 or seq > len(pages):
        raise npc.Refused(f"no seq-{seq} in this issue")
    page = pages[seq - 1]
    c = page.coords()
    hit = find_phrase(c["words"], phrase)
    if not hit:
        raise npc.Refused(f"phrase {phrase!r} not found on the page's OCR")
    pi = rules.PageInk(page)
    box = block_around(pi, c, hit, allow_display=False, log=log, max_frac=MARKET_MAX_FRAC)
    if not box:
        raise npc.Refused("the market item could not be closed on the grid")
    inside = nameplate.words_in(c["words"], box)
    leg, n = legibility(inside)
    if leg < LEGIBLE:
        raise npc.Refused(f"market OCR illegible ({leg:.0%} of {n} tokens)")
    # ⚠️ The phrase is shape, not genre: "cotton market" sits in prose about
    # a farmer's crop as readily as over a price list. A market report is a
    # TABLE, and a table is figures: a fifth of its tokens at least.
    tab = tabular(inside)
    if tab < TABULAR:
        raise npc.Refused(f"not a table: {tab:.0%} of tokens are figures")
    verdict, page_hits = _verdict("market", lccn, date, inside, c["words"], True)
    image_box, data = _fetch(page, box)
    return _result("market", page, meta, date, ed, box, image_box, data, verdict,
                   page_hits, _curl(ocr_text(inside)), False, {"phrase": phrase})


def clip(lane, lccn, date, ed=1, seq=1, phrase=None, log=print):
    if lane == "nameplate":
        return clip_nameplate(lccn, date, ed, log=log)
    if lane == "headline":
        return clip_headline(lccn, date, ed, seq if seq and seq > 1 else None, log=log)
    if lane == "article":
        return clip_article(lccn, date, ed, seq if seq and seq > 1 else None, log=log)
    if lane == "ad":
        return clip_ad(lccn, date, ed, seq, phrase, log=log)
    if lane == "market":
        return clip_market(lccn, date, ed, seq, phrase or MARKET_PHRASES[0], log=log)
    raise ValueError(f"unknown lane {lane!r}")


def market_candidates(rights, **kw):
    return search_candidates(MARKET_PHRASES, rights, **kw)


def ad_candidates(rights, **kw):
    return search_candidates(AD_PHRASES, rights, **kw)


def search_candidates(phrases, rights, date_lo="1867-01-01", date_hi="1930-12-31",
                      per_phrase=200, log=print):
    """(lccn, date, ed, seq, phrase) for search hits on postable issues.
    Cached searches, a few pages per phrase, the date window split by decade
    so no single window returns the whole corpus (README's date trap)."""
    out, seen = [], set()
    lo, hi = int(date_lo[:4]), int(date_hi[:4])
    for phrase in phrases:
        got = 0
        for y0 in range(lo, hi + 1, 10):
            y1 = min(hi, y0 + 9)
            d1 = f"{y0:04d}-01-01" if y0 > lo else date_lo
            d2 = f"{y1:04d}-12-31" if y1 < hi else date_hi
            try:
                hits = ghn_api.search(phrase, d1, d2, rows=50)
            except ghn_api.FetchError as e:
                log(f"  search {phrase!r} {y0}s: {e}")
                continue
            for it in hits:
                lccn = it.get("lccn"); d = it.get("date") or ""
                if len(d) != 8 or lccn not in rights or rights[lccn].get("postable") != "yes":
                    continue
                date = f"{d[:4]}-{d[4:6]}-{d[6:]}"
                key = (lccn, date, int(it.get("sequence") or 1))
                if key in seen:
                    continue
                seen.add(key)
                out.append((lccn, date, 1, key[2], phrase))
                got += 1
            if got >= per_phrase:
                break
    return out
