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
# ⚠️ The cartoon lane's search seed, 12 September 2026: the credit line a
# syndicated strip or cartoon carries in set type, which the OCR reads where
# it cannot read the drawing. Shape, never genre, as everywhere: a syndicate
# line sits under a feature column and a serial as readily as under a strip,
# so the hit only says which PAGE to look at; pictures.py's detector and the
# model's kind still decide. Measured on the corpus: none of these appears on
# any page before 1905, and together they mark 11,470 pages in 1915-1919.
CARTOON_PHRASES = ("International Feature Service", "Newspaper Feature Service",
                   "Registered U. S. Patent Office")
CARTOON_SEARCH_FROM = "1900-01-01"
# ⚠️ The classified lane's search seed, 20 September 2026, his ask on seeing
# the WANTS column beside the Brunswick News strip ("if there's a way to
# capture what's in the screenshot reliably, that's also a good vein"). Item
# phrases, never the department's own head: "WANTS", "WANT ADS" and the
# "one cent a word" rate line are display type the OCR did not read on that
# very page, while the items under them read at 79-92 percent. Each phrase
# below has no other life in a newspaper, and together they reach both the
# 1910s department (20,342 pages say "light housekeeping" in that decade)
# and the 19th-century notice ("apply at this office", 6,455 pages in the
# 1870s; "strayed or stolen", 1,183). Measured by decade in the session log.
CLASSIFIED_PHRASES = ("light housekeeping", "furnished rooms", "situation wanted",
                      "strayed or stolen", "apply at this office", "liberal reward")
# The words a classified item may open with, before its dash: "FOR SALE—",
# "LOST—", "ROOM—", "STRAYED OR STOLEN—", "WANTED—". A row opening with
# one to three of these and a dash is a classified item; a wire brief
# opens the same way with a CITY ("WASHINGTON—The"), which is why the
# lead is judged against a list and not by its shape alone.
CLASSIFIED_LEADS = frozenset("""
    for to or and sale rent let lease exchange trade wanted want lost found strayed stolen
    stray estray taken up room rooms board boarders boarding house houses home homes
    cottage cottages apartment apartments flat flats furnished unfurnished help
    situation situations position positions male female money loan loans land lands
    farm farms lot lots acres horse horses mule mules cow cows cattle hog hogs
    chickens eggs dog dogs seed hay wood coal automobile automobiles auto car cars
    piano typewriter furniture bargain bargains offer offered cheap free reward
    """.split())
CLASSIFIED_LEAD_RE = re.compile(
    r"^((?:[A-Za-z][A-Za-z.\']*\s+){0,3}[A-Za-z][A-Za-z.\']*)[.,:]?\s?([—–-]*)\s*(?=[A-Z0-9\$“\"])")
# A neighbouring item's lead, once the seed's own has passed the list: three
# or more capitals, then a dash within a few characters. The OCR reads the
# lead in display capitals worst of all ("FOR SAJ E—Nice fat fryers"), and
# an item that is rule-bound to a proven classified is not a wire brief.
CLASSIFIED_LOOSE_RE = re.compile(r"^[A-Z][A-Z .\']{1,20}[—–-]")
# The OCR reads a column rule's fragment as a one-letter token at the head
# of a row ("i ROOM—Large cool room", Brunswick 1927); stripped before the
# lead is judged. Never a digit or a capital, which can be real.
ROW_NOISE_RE = re.compile(r"^(?:[a-z|!¡;:,.'\"]\s+)+")
# ⚠️ A reward notice is where the classified lane meets what the page gate
# exists for. The first decade sample (20 September 2026) passed the Oconee
# Enterprise of 14 December 1880 as CLEAN: "$25 Reward... for the arrest and
# apprehension of one George Parks, col., who is under bond... charged with
# adultry, and has fled from justice. Description. He is of a rather
# 'ginger-cake' color..." -- a wanted notice for a Black man in the period's
# language, which the crop_frequency prefixes do not carry because "col." is
# an abbreviation. Any of these words in the block is REVIEW: a person
# decides, this is not a rejection (gates.py's rule).
CLASSIFIED_REVIEW = ("arrest", "arrested", "apprehension", "apprehended", "fugitive",
                     "escaped", "runaway", "jail", "sheriff", "convict", "convicted",
                     "chain gang", "col.", "mulatto", "description")
CLASSIFIED_REVIEW_RE = re.compile(          # "mouse colored" is a cat (Rome, 1895)
    r"\bcolou?red (man|woman|boy|girl|men|women|person|people|fellow|preacher|servant|cook)\b")
CLASSIFIED_MAX_FRAC = 0.15   # a run of items, never the whole department:
                             # three FOR SALE items on the Brunswick page
                             # are 0.09
CLASSIFIED_MAX_ITEMS = 6
CLASSIFIED_DISPLAY = 1.4     # a row this many body heights tall, under one that
                             # is not, starts a new item (a heading of some kind)
PAPER_ROW = 0.02             # _to_paper(): a small-image row at most this dark
                             # over the column is paper (leading between lines)
CLASSIFIED_PARA_GAP = 1.0    # a row gap over this many body heights starts a
                             # new item. ⚠️ Measured between two pages that
                             # pull opposite ways: the Augusta Chronicle of
                             # 8 March 1874 sets its notices 1.29 body heights
                             # apart with no rule between them (at PARA_GAP,
                             # 1.3, the whole column was one item), and the
                             # 1873 paper on sn85034215 leads its LINES 0.79
                             # apart (at 0.7 every line was an item). The
                             # Brunswick News of 1927: items 1.4-1.6, lines 0-0.3
CLASSIFIED_HEAD_WORDS = 4    # a one-row segment of this many words or fewer,
                             # from the list, is a heading: an item's own
                             # ("Wanted to Rent", 1873) or the category's
                             # subhead over LEAD— items ("FOR RENT", 1927)
CLASSIFIED_UNREAD_GAP = 3.0  # a gap between items of this many body heights
                             # holds something the OCR did not read -- the
                             # next category's subhead in display type -- and
                             # ends the run there
LOCAL_SPAN = 0.06            # local_column(): rows either side of the seed,
                             # of the page's height, over which a gutter is
                             # judged (about a dozen body lines)
LOCAL_REACH = 0.25           # ...and this much of the page's width either side
LOCAL_GUTTER = 0.001         # ...a run of this many clear image columns (5px
                             # on a 5,152px page, never under 4) is a gutter:
                             # word spaces in justified type do not line up
                             # over a dozen rows. The 20px Brunswick gutter
                             # holds 8 clear each side of its dotted rule; the
                             # Georgian's holds 4-5 each side of a solid one
LOCAL_SLICES = 4             # ...the band judged in this many horizontal
                             # slices, a boundary counted when at least
LOCAL_AGREE = 2              # ...this many of them carry it (a river wobbles
                             # out of line; a running head or banner empties
                             # a slice or two), within
LOCAL_DRIFT = 0.004          # ...this much of the page's width (17px on the
                             # Georgian, whose skew moves a rule 8px a slice)
LOCAL_CLEAR = 0.06           # ...clear meaning a column with at most this
                             # share of ink over the slice: dirty paper
                             # binarizes to none, the lightest body type on
                             # the Brunswick page to 0.05-0.20
LOCAL_WIDE = 0.006           # ...a clear run this wide (30px on the Brunswick
                             # page) is a gutter by itself. ⚠️ Not 0.003: the
                             # Brunswick News of 24 March 1930 sets its want
                             # ads so loose that a 17px river ran through
                             # them; every narrow gutter measured (Brunswick
                             # 1927, the Georgian, Augusta 1874) carries a
                             # rule, and the rule structure below finds it
LOCAL_RULE = 0.30            # ...and an inked body no wider than LOCAL_WIDE
                             # peaking at this much ink, with LOCAL_GUTTER of
                             # clear beyond it on each side, is a column rule
                             # in its gutter -- dotted (Brunswick) or solid
                             # (the Georgian, 1.0). ⚠️ At 0.15 the faint
                             # Brunswick text qualified column after column:
                             # a stroke is a row of ink, and paper 5px away
                             # is ordinary inside light type
MAX_BLOCK_FRAC = 0.25
MAX_BLOCK_W = 0.45       # a block wider than this of the page is not one item
MARKET_MAX_FRAC = 0.40   # a market crop runs from its own section heading to
                         # the next one, an ad or unrelated matter, or this
                         # much of the page, whichever comes first. Raised
                         # from 0.15 on 13 September 2026, his complaint on
                         # the Augusta Herald of 19 February 1918 ("this
                         # crop was fine, but it could have been wider") --
                         # the real ceiling now, since the row walk below
                         # stops at the next section heading well before
                         # this in the ordinary case.
MIN_BLOCK_ROWS = 4
PARA_GAP = 1.3           # a row gap this many body heights is a paragraph break
MARKET_ROWS = 80         # ...and failing one (a market section with no
                         # visible paragraph gap at all -- the Marietta
                         # Journal sets its own with no extra lead), this
                         # many rows past the hit before the walk gives up
                         # looking for one. Raised from 10 the same day:
                         # that figure capped the walk at a couple of short
                         # paragraphs and was what kept a market crop from
                         # ever reaching the next section's own heading.
                         # MARKET_MAX_FRAC is the real ceiling now.
HEADLINE_MAX_FRAC = 0.16 # a headline item deeper than this has taken a second
                         # headline or a story with it
MIN_BLOCK_FRAC = 0.015
RULE_ISOLATION = 2       # small-image rows either side of a candidate rule
                         # row that must themselves read close to paper
RULE_PAPER_MAX = 0.15    # ...that close.
RULE_CANDIDATE_MIN_DARK = 0.30
                         # a row this dark is worth testing for isolation.
                         # ⚠️ LOWER than rules.HRULE_MIN_DARK (0.45) on
                         # purpose, and only safe because isolation does
                         # the real discriminating now: on the Augusta
                         # Herald of 19 February 1918, 13 September 2026,
                         # the real rule above a "PRODUCE MARKET" heading
                         # measured 0.430 -- BELOW the old bare
                         # HRULE_MIN_DARK test, so it was missed entirely
                         # -- while two rows up, tight body-text leading
                         # with no rule at all measured 0.475, ABOVE it,
                         # and was wrongly read as one. A bare threshold on
                         # any row in the gap cannot tell a thin printed
                         # rule from a dense line of type, because on a
                         # page this compressed a single text row is only
                         # a few small-image pixels tall and both can
                         # cross it. Shape is what tells them apart,
                         # measured on the same page: the real rule's own
                         # near neighbours read 0.00-0.01 (isolated), every
                         # false one's read 0.31-0.48 (part of a multi-row
                         # glyph cluster) -- which is also why the floor
                         # can safely drop: RULE_PAPER_MAX rejects a
                         # non-isolated candidate regardless of how dark
                         # its own row reads.
RULE_MAX_RUN = 2         # a run of CONSECUTIVE candidate-dark rows longer
                         # than this is not a printed rule, whatever sits
                         # outside the run. ⚠️ Found the same day: the
                         # rule under the left half of a split two-column
                         # "COTTON MARKET" banner (13 September 2026, see
                         # wide_heading_split() below) prints TWO rows
                         # wide, and checking each of its rows against its
                         # immediate ±RULE_ISOLATION neighbour made them
                         # shadow each other -- row 1 of the pair sees row
                         # 2 as a dark neighbour and fails isolation, and
                         # row 2 sees row 1 the same way, so a real rule
                         # was missed by the very isolation check meant to
                         # find it. Checking the whole RUN's outside edges
                         # instead fixes that -- but checked naively (no
                         # run-length cap) it also wrongly reads the false
                         # rule's own glyph cluster as one big rule, since
                         # what sits OUTSIDE that whole 4-row cluster is
                         # paper too. The two real rules measured here run
                         # 1 and 2 rows; the false ones run 3 and 4 -- so
                         # a cap of 2 keeps both without reopening that.


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
MARKET_ALT_CHARS = 1600  # everygeorgia_post.py's ALT_MAX is 1900 and the
                         # market alt's own wrapper ("Market report from
                         # ..., reading: ...") runs to about 150-250 chars
                         # of that depending on the title, so this leaves
                         # headroom. Added 13 September 2026 when the
                         # section-walk widened the crop (and so the OCR
                         # text it carries) well past what alt_text()'s own
                         # blunt end-of-string truncation could cut
                         # cleanly; that truncation stays as a backstop,
                         # this is what actually does the cutting now.


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


def _headline_item(c, page, diagnostics=None):
    """(box, words inside) of the topmost display item below the nameplate
    that is not itself an advertisement, or None. On an inner page there is
    no nameplate, and the running head at the top is skipped instead.

    `diagnostics`: passed through to items.box_with_deck() for crop_closure_
    check.py's own use -- see closure_margins() below. items.snapped()
    already ran box_with_deck once, undiagnosed, to build the candidate
    list this walks; the winning candidate's own `seg` is run through it a
    SECOND time, with diagnostics on, rather than instrumenting the first
    pass for every candidate this never returns. Pure and cheap (no
    network, no image fetch), so the redundant call costs nothing on the
    hot posting path, where no caller ever passes diagnostics."""
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
        if diagnostics is not None:
            pi = rules.PageInk(page)
            items.box_with_deck(seg, c["words"], c["width"], c["height"], pi,
                                diagnostics=diagnostics)
        return s, inside
    return None


def headline_closure_margins(c, page):
    """ADVISORY ONLY, mirroring closure_margins() below but for the headline
    item's own down-walk (items.box_with_deck): why did it stop growing the
    item past its heading and deck lines? `None` if there is no headline
    item on this page at all -- nothing for a caller to have asked about."""
    diagnostics = {}
    chosen = _headline_item(c, page, diagnostics=diagnostics)
    if chosen is None:
        return None
    return diagnostics


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


def _article_span(c, page, diagnostics=None):
    """The headline item's box plus the row range of its first paragraph, as
    clip_article() builds it -- factored out so crop_closure_check.py can
    re-derive just the geometry, with `diagnostics` on, without spending a
    model call (the same reasoning closure_margins() below has for block_
    around). Raises npc.Refused exactly as clip_article() would when there
    is nothing to find. Returns (hbox, box).

    ⚠️ Decks and body are told apart by SPACING, not size. On the Macon
    Telegraph of 15 January 1897 the decks are bold body-height lines set
    two ems apart, and the paragraph is lines of the same height set tight;
    a height rule ended the crop inside the decks. So: everything under the
    headline down to the first run of three tight lines is furniture and
    is kept; the run is the paragraph; it ends at the next indented line
    (a new paragraph), a wider gap, or ARTICLE_LINES.

    `diagnostics`, filled the same way block_around's own is (at the SAME
    break this already takes, never reconstructed): only "gap" -- the
    paragraph's own closing line spacing, TIGHT_GAP*med -- carries a ratio
    worth comparing to a floor. "indent" (the next paragraph starting),
    "cap" (ARTICLE_MAX_FRAC) and "row-count-cap" (ARTICLE_LINES) are
    confident, structural stops, exactly as their namesakes are for
    block_around."""
    def _note(reason, ratio=None, text=None):
        if diagnostics is not None:
            diagnostics["bottom"] = None if reason is None else \
                {"reason": reason, "ratio": ratio, "text": text}

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
            ratio = (gaps[i] - TIGHT_GAP * med) / (TIGHT_GAP * med)
            _note("gap", ratio, ocr_text(lines[i][3]))
            break
        if i - start >= 2 and lines[i][2] > left_mode + INDENT * med:
            _note("indent", None, ocr_text(lines[i][3]))
            break                               # an indented line: the next paragraph
        if lines[i][1] - hbox[1] > ARTICLE_MAX_FRAC * ch:
            _note("cap")
            break
        end = i
        if end - start + 1 >= ARTICLE_LINES:
            _note("row-count-cap")
            break
    else:
        _note(None)      # ran out of lines on the page; nothing outside
    if end - start + 1 < 3:
        raise npc.Refused("paragraph under the headline is under three lines")
    bottom = lines[end][1]
    box = (hbox[0], hbox[1], hbox[2], int(bottom + 0.6 * med) - hbox[1])
    return hbox, box


def article_closure_margins(c, page):
    """ADVISORY ONLY, mirroring closure_margins() below but for the article
    lane's own paragraph-closing loop (_article_span). `None` if there is
    no article to be had on this page at all -- nothing for a caller to
    have asked about (the same npc.Refused cases _article_span itself
    raises)."""
    diagnostics = {}
    try:
        _article_span(c, page, diagnostics=diagnostics)
    except npc.Refused:
        return None
    return diagnostics


def clip_article(lccn, date, ed=1, seq=None, log=print):
    """The headline item plus its first paragraph. His ask, 11 September
    2026: "a headline and first graf." See _article_span() above for how
    the paragraph itself is found and closed."""
    meta = _meta(lccn, date, "article")
    page = choose_page(lccn, date, ed, seq)
    c = page.coords()
    hbox, box = _article_span(c, page)
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


BOX_MARGIN_W = 0.012     # a boxed advertisement's crop: paper beyond its
BOX_MARGIN_H = 0.008     # border, of the page's width and of its height


def ad_box(pi, coords, seed):
    """The printed border enclosing `seed`, as an OCR-space box, or None:
    rules.PageInk.border_box() with the page's text height read off the
    OCR. A box shallower than MIN_BLOCK_FRAC is a boxed notice, not an
    advertisement crop, and is left to block_around like everything
    else. Shared by clip_ad() and crop_closure_check.py, so the audit
    asks the same question the poster did."""
    med = nameplate.page_median_height(coords["words"]) or 1
    x0 = min(w[0] for w in seed); x1 = max(w[0] + w[2] for w in seed)
    y0 = min(w[1] for w in seed); y1 = max(w[1] + w[3] for w in seed)
    per = pi.page.scale * pi.scale                    # small px per OCR unit
    text_h = med * per
    words = [(w[0] * per, w[1] * per, w[2] * per, w[3] * per, w[4]) for w in coords["words"]]
    b = pi.border_box(pi.from_ocr((x0, y0, x1 - x0, y1 - y0)), text_h, words)
    if b is None:
        return None
    box = pi.to_ocr((b[0], b[1], b[2] - b[0], b[3] - b[1]))
    if box[3] < MIN_BLOCK_FRAC * coords["height"]:
        return None
    return box


def clip_ad(lccn, date, ed=1, seq=1, phrase=None, log=print):
    """With a phrase (from AD_PHRASES, via search): the printed BORDER
    around it if the advertisement is boxed (ad_box), else the block of
    set text around it (block_around), which is where legible advertising
    lives. Without one: the largest rule-closed display item on the front
    page whose OCR sells something, which on most pages the OCR cannot
    read well enough to say.

    ⚠️ The border comes first and no size cap applies to it, his rule of
    22 September 2026 on the Tanner Mercantile advertisement (Douglas
    Enterprise, 13 July 1907): "err on the side of looser rather than
    tighter crops that fall precisely along column gutters". That ad is
    a box across the whole page and 40 percent of its height; block_around
    shipped one column of it, cut at MAX_BLOCK_FRAC, because MAX_BLOCK_W
    and MAX_BLOCK_FRAC exist to bound a walk that found no boundary, and
    a border IS the boundary. See rules.PageInk.border_box for how one is
    read. The block path keeps its caps and now takes the same margin a
    headline gets (LOOSE_W, LOOSE_H), so a crop that does stop on a
    gutter shows the gutter rather than cutting the B of "Best" off.
    ⚠️ The alt text and the advertising-word check read the words inside
    the TIGHT box, never the margin: the margin is the neighbour's."""
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
        box = ad_box(pi, c, hit)
        boxed = box is not None
        if boxed:
            crop = _loosen(box, c, BOX_MARGIN_W, BOX_MARGIN_H)
        else:
            box = block_around(pi, c, hit, allow_display=True, log=log,
                               split_wide_headings=True)
            if not box:
                raise npc.Refused("the advertisement could not be closed on the grid")
            crop = _loosen(box, c, LOOSE_W, LOOSE_H)
        inside = nameplate.words_in(c["words"], box)
        text = ocr_text(inside)
        if len(ad_markers(text)) < 2:
            raise npc.Refused("the block around the phrase does not read as an advertisement")
    else:
        boxed = False
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
        crop = box
    verdict, page_hits = _verdict("ad", lccn, date, inside, c["words"], True)
    image_box, data = _fetch(page, crop)
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
                   page_hits, _curl(words), generated, {"phrase": phrase, "boxed": boxed})


def _rows(words):
    return [sorted(rw, key=lambda w: w[0])
            for rw in nameplate.rows_of(sorted(words, key=lambda w: (w[1], w[0])), row_tol=0.5)]


def row_has_rule(pi, sx0, sx1, ya, yb):
    """Is there a printed horizontal rule between OCR rows at `ya` and `yb`,
    over columns [sx0, sx1) of `pi`?

    ⚠️ A margin either side of the gap: OCR word boxes are taller than the
    glyphs, so a rule sits INSIDE the box rows as often as between them,
    and a search-driven ad crop chained three advertisements through two
    clearly printed rules before the margin was added.

    ⚠️ Isolation, not a bare darkness threshold, is what makes a row the
    rule. See RULE_PAPER_MAX above: on a dense page a single row of tight
    body-text leading measures just as dark as a printed rule over the
    padded window, and a bare `any(d >= HRULE_MIN_DARK)` cannot tell them
    apart -- it missed a real rule at 0.430 and caught a false one at
    0.475 on the same page, in opposite directions, from one threshold.
    A rule is a thin, ISOLATED spike with paper close on both sides; tight
    body text is a multi-row cluster of glyph ink with no such isolation,
    even where its darkest single row clears the threshold.

    ⚠️ Isolation is checked on the RUN of consecutive candidate-dark rows,
    not row by row: see RULE_MAX_RUN above. A rule two rows wide has each
    of its rows sitting right next to the other, so testing each row's
    own ±RULE_ISOLATION neighbours in isolation makes the two rows shadow
    each other and the rule vanishes. The run's OUTSIDE edges are what
    isolation actually means; RULE_MAX_RUN is what stops that same test
    reading a whole multi-row glyph cluster as one wide rule."""
    pad = 4 + RULE_ISOLATION
    a, b = max(0, pi.y_small(ya) - pad), pi.y_small(yb) + pad
    if b <= a:
        return False
    dark = pi.row_dark(sx0, sx1, a, b)
    n = len(dark)
    i = 0
    while i < n:
        if dark[i] < RULE_CANDIDATE_MIN_DARK:
            i += 1
            continue
        j = i
        while j < n and dark[j] >= RULE_CANDIDATE_MIN_DARK:
            j += 1
        if j - i <= RULE_MAX_RUN:
            before = dark[max(0, i - RULE_ISOLATION):i]
            after = dark[j:j + RULE_ISOLATION]
            if (not before or max(before) <= RULE_PAPER_MAX) and \
               (not after or max(after) <= RULE_PAPER_MAX):
                return True
        i = j
    return False


MIN_SPLIT_FRAC = 0.30    # ⚠️ Added 15 September 2026, measuring the AD lane's
                         # own candidates before turning this on there: a
                         # boxed display ad's own decorative border rule
                         # sits a few px inside its column's edge, and
                         # without a width floor wide_heading_split() reads
                         # it as a banner divider and returns a ~10px sliver
                         # of the ad rather than declining. Measured on 5
                         # real hits (all "sarsaparilla" on the same title,
                         # a boxed patent-medicine ad), the false candidate's
                         # own half ran 3.0-6.1% of cb's width; the two real
                         # banner splits measured here (the Augusta Herald's
                         # "COTTON MARKET" and a "sewing machines" ad on the
                         # Union Recorder of 27 February 1906) both ran
                         # 49-51%. 0.30 sits with a wide margin either side
                         # of both real numbers seen so far.


def wide_heading_split(pi, cb, y0_small, y1_small):
    """If `cb` (small-image x0,x1) is a BANNER spanning two real, narrower
    print columns -- straddled by a genuine interior vertical rule that
    continues well past the heading's own bottom (`y1_small`) -- return
    the LEFT half of `cb` to follow instead. None if there is no such
    rule, it is not roughly centred (MIN_SPLIT_FRAC on both sides), or
    there is more than one candidate (ambiguous; leave `cb` alone).

    "COTTON MARKET" on the Augusta Herald of 19 February 1918 is set as a
    banner across two narrower columns whose CONTENT below it is two
    unrelated streams: a cotton-price table on the left, an unrelated
    advertisement then a different cotton report on the right.
    nameplate.rows_of groups both sides' words into one "row" wherever
    their y happens to line up, which reads as neither -- "AUGUSTACOTTON
    COTTONSEED FOR" was one such row, the OCR of two unrelated columns'
    words merged as if they were one line. `column_bounds` correctly
    returns the banner's own OUTER bounds (it does not stop at an interior
    rule the SEED itself crosses, by design -- a multi-column advertisement
    or headline keeps going to the next gutter), so nothing upstream of
    here ever sees the split.

    LEFT, not a choice keyed to the search hit: ordinary reading order for
    a multi-column layout under one banner is to read the first (leftmost)
    column top to bottom before the next, exactly as `find_phrase`'s own
    reading order already assumes elsewhere."""
    candidates = [(x, t, b) for x, t, b in pi.vrules()
                  if cb[0] + 4 < x < cb[1] - 4 and b > y1_small + rules.MIN_SPAN * pi.h]
    if len(candidates) != 1:
        return None
    vx = candidates[0][0]
    width = cb[1] - cb[0]
    if width <= 0 or min(vx - cb[0], cb[1] - vx) < MIN_SPLIT_FRAC * width:
        return None
    return (cb[0], vx)


def block_around(pi, coords, seed, allow_display, log=print, max_frac=None,
                 rule_test=row_has_rule, split_wide_headings=False, diagnostics=None):
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
    between two of them.

    `split_wide_headings`: narrow a banner heading to its left column
    before building rows at all -- see wide_heading_split(). Market lane
    since 13 September 2026; the ad lane's own phrase hits sit inside a
    wide banner-style heading too (large display ads spanning most of the
    page), and 15 September 2026 measured a real instance -- a "sewing
    machines" ad merged with an unrelated LOCAL MENTION column of grocery
    notices via exactly this shape -- so it is wired in there as well.

    `diagnostics`: an optional dict this function fills IN PLACE (never
    read) with {"top": info_or_None, "bottom": info_or_None} recording
    exactly why each direction's walk stopped -- see closure_margins(),
    which is the only real caller. Filled at the moment of the SAME break
    or return this function already takes, so it can never drift out of
    sync with the box actually returned the way a caller reconstructing
    the reason from the finished box alone would risk doing (found the
    hard way, 15 September 2026: on a dense market table, the finished
    box's own +1-med padding routinely overlapped the very next EXCLUDED
    row, so a reconstruction keyed on the box's y-range picked the wrong
    row as "included" and reported a phantom near-miss with a zero
    gap). No cost when omitted (`is not None` guards every write)."""
    cw, ch = coords["width"], coords["height"]
    words = coords["words"]
    med = nameplate.page_median_height(words) or 1
    x0 = min(w[0] for w in seed); x1 = max(w[0] + w[2] for w in seed)
    y0 = min(w[1] for w in seed); y1 = max(w[1] + w[3] for w in seed)
    cb = pi.column_bounds(pi.from_ocr((x0, y0, x1 - x0, y1 - y0)), mode="column")
    if cb is None or (cb[1] - cb[0]) > MAX_BLOCK_W * pi.w:
        return None
    if split_wide_headings:
        split = wide_heading_split(pi, cb, pi.y_small(y0), pi.y_small(y1))
        if split is not None:
            cb = split
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
        return rule_test(pi, sx0, sx1, ya, yb)

    def row_top(i):
        return min(w[1] for w in rows[i])

    def row_bot(i):
        return max(w[1] + w[3] for w in rows[i])

    def row_h(i):
        return max(w[3] for w in rows[i])

    def is_display(i):
        return row_h(i) >= 1.6 * med

    def _note(direction, j, reason, ratio):
        if diagnostics is not None:
            diagnostics[direction] = {"reason": reason, "text": ocr_text(rows[j]), "ratio": ratio}

    lo = hi = idx
    while lo > 0:
        j = lo - 1
        gap = row_top(lo) - row_bot(j)
        # ⚠️ An ad's own heading is admitted whatever the gap below it, not
        # just up to the ordinary 2.2*med body-line ceiling: the whitespace
        # a printer sets between a display headline and the body under it
        # routinely dwarfs body-line leading, and this docstring already
        # promises a display row is kept when allow_display. "Important to
        # the Public" on the Daily Constitutionalist of 1 October 1872 (the
        # Cooke's clothing ad, 14 September 2026, his flagged crop) sits 652
        # units -- 6.9x the page median -- above "FOR CLOTHING AND HATS",
        # and the plain gap test cut the heading off before allow_display
        # ever got a say. rule_between() and the block-height cap below are
        # still the backstops: a real printed rule, or the block simply
        # growing too tall, still stops the climb.
        display_head = allow_display and is_display(j)
        if gap > 2.2 * med and not display_head:
            _note("top", j, "gap", (gap - 2.2 * med) / (2.2 * med))
            break
        if rule_between(row_bot(j), row_top(lo)):
            _note("top", j, "rule", None)
            break
        if is_display(j) and not allow_display:
            _note("top", j, "display-boundary", None)
            break
        # ⚠️ The down-walk's own paragraph-break guard, mirrored upward,
        # but WITHOUT its "j - idx > 3" grace period. Without a guard at
        # all, a market section whose own heading reads no taller than
        # its body (an older, cruder typeset -- "Sandersville Prices
        # Current" measured 1.37x the page median on the Savannah Morning
        # News of 18 April 1873, under the 1.6x is_display floor) has NO
        # backstop at all in this direction: neither a rule nor a display
        # row ever fires, and the climb ran straight through an unrelated
        # advertisement and two OTHER towns' price lists above it, all the
        # way to the top of the column. ⚠️ The grace period itself is
        # wrong to mirror: down-walk needs it because the row right below
        # a heading (its own byline or subhead) often carries extra lead
        # from the heading, not because a section starts more than three
        # rows from its hit -- but when the hit itself IS the heading
        # (the common case here), the gap directly ABOVE it is exactly
        # the previous section's own boundary, and a grace period is what
        # let the climb sail straight past it (126 units against a
        # 105-unit PARA_GAP threshold, dropped because it fell on the
        # very first row considered) before finally stopping four
        # sections later.
        if not allow_display and gap > PARA_GAP * med:
            _note("top", j, "paragraph-gap", (gap - PARA_GAP * med) / (PARA_GAP * med))
            break
        if not allow_display and idx - j > MARKET_ROWS:
            _note("top", j, "row-count-cap", None)
            break
        if row_bot(hi) - row_top(j) > cap:
            # ⚠️ The top is the cap, not a rule or a gap: the block begins
            # mid-item ("ment is seven days the longest", Savannah Morning
            # News, 13 January 1871). Nothing to show. Diagnostics are moot:
            # there is no box for a caller to have asked about this one.
            return None
        lo = j
        if is_display(j) and allow_display:
            continue
    else:
        if diagnostics is not None:
            diagnostics["top"] = None       # reached the column's own top; nothing outside
    paragraphs = 0
    while hi < len(rows) - 1:
        j = hi + 1
        gap = row_top(j) - row_bot(hi)
        # ⚠️ Mirrors the up-walk's own display_head allowance (15 September
        # 2026): an ad's own CLOSING signature is set in display type with
        # oversized leading above it, exactly as its opening heading is
        # below it. Found by crop_closure_check.py's first live run, on a
        # Castoria ad (sn89053972, 15 September 1919) whose crop ended
        # "...Philadelphia Bulletin Children Cry For" -- cut off one row
        # short of the stylized "CASTORIA" wordmark that line is the
        # caption for. Same backstops as the up-walk: rule_between() and
        # the height cap below still stop the walk.
        display_tail = allow_display and is_display(j)
        if gap > 2.2 * med and not display_tail:
            _note("bottom", j, "gap", (gap - 2.2 * med) / (2.2 * med))
            break
        if rule_between(row_bot(hi), row_top(j)):
            _note("bottom", j, "rule", None)
            break
        if is_display(j) and not allow_display and j > idx:
            _note("bottom", j, "display-boundary", None)
            break
        # ⚠️ A market report is its heading and the paragraph under it. The
        # Marietta Journal of 21 November 1878 ran "Marietta Market Report"
        # as the first item of its local notes, and the walk carried on
        # through the court week and a robbery. A paragraph break (a gap
        # over PARA_GAP of the body type) after at least three rows below
        # the seed ends the block when `allow_display` is off.
        if not allow_display and gap > PARA_GAP * med and j - idx > 3:
            _note("bottom", j, "paragraph-gap", (gap - PARA_GAP * med) / (PARA_GAP * med))
            break
        if not allow_display and j - idx > MARKET_ROWS:
            _note("bottom", j, "row-count-cap", None)
            break
        if row_bot(j) - row_top(lo) > cap:
            _note("bottom", j, "cap", None)
            break
        hi = j
    else:
        if diagnostics is not None:
            diagnostics["bottom"] = None    # reached the column's own bottom; nothing outside
    top, bot = row_top(lo), row_bot(hi)
    # ⚠️ A block is at least MIN_BLOCK_ROWS rows and MIN_BLOCK_FRAC of the
    # page: "MOTT'S LIVER PILLS cure torpidity" came back as a two-line
    # sliver 0.7% of the page deep, a reading notice cut from its column.
    if hi - lo + 1 < MIN_BLOCK_ROWS or (bot - top) < MIN_BLOCK_FRAC * ch:
        return None
    pad = int(1.0 * med)                 # 0.6 cut the top line of a Savannah
                                         # produce column through its figures
    return (cx0, max(0, top - pad), cx1 - cx0, min(ch, bot + pad) - max(0, top - pad))


def closure_margins(pi, coords, seed, allow_display, log=print, max_frac=None,
                    rule_test=row_has_rule, split_wide_headings=False):
    """ADVISORY ONLY, never a gate: runs `block_around` ITSELF, with its
    `diagnostics` instrumentation on, and returns just the diagnostics --
    why did the walk stop on each side? Built 15 September 2026 for a
    periodic audit, after a crop that closed cleanly by every existing
    check (rights, vocabulary, ad_markers, legibility) still shipped
    truncated -- the walk's own stopping decision was never itself a
    thing anyone asked about. Takes the SAME arguments as block_around
    (not a pre-built box) and calls it directly, which is what makes the
    answer trustworthy: the reason reported is the box's ACTUAL reason,
    not a reconstruction that can drift out of sync with it.

    ⚠️ A reconstruction WAS tried first, keyed off the finished box's own
    y-range, and it was wrong on real data: on a dense market table the
    box's own +1-med padding routinely overlapped the very next EXCLUDED
    row, so the reconstruction picked the wrong row as "included" and
    reported a phantom near-miss with a zero gap on posts that were
    actually fine. Reusing block_around's own walk instead of guessing
    at its result from the outside closes that off by construction.

    Possible reasons, both lanes now (extended to market 15 September
    2026, once this instrumented approach made it safe to):

      "rule"              a printed rule -- confident, structural
      "gap"               the ordinary 2.2*med gap ceiling; `ratio` is
                          how far past it the actual gap fell -- near 0
                          is a near miss, large is confident
      "display-boundary"  `not allow_display` only: a display row is
                          NEVER admitted there by design (the next
                          item's own heading ends a market table) --
                          confident, not a miss of any kind
      "paragraph-gap"     `not allow_display` only: PARA_GAP's own
                          narrower ceiling (with the down-walk's 3-row
                          grace period); `ratio` against PARA_GAP*med
                          the same way "gap"'s is
      "row-count-cap"     `not allow_display` only: MARKET_ROWS --
                          confident, an 80-row backstop essentially
                          never meant to be the real reason
      "cap"               the block already as tall as `max_frac` of
                          the page allows -- confident, structural

    `None` on a side means the walk reached the column's own edge with
    nothing outside it. The whole result is `None` (not a dict) if
    `block_around` itself refused the crop -- there is no box for a
    caller to have asked about. A person reading a flagged case decides;
    this only narrows down what to look at."""
    diagnostics = {}
    box = block_around(pi, coords, seed, allow_display, log=log, max_frac=max_frac,
                       rule_test=rule_test, split_wide_headings=split_wide_headings,
                       diagnostics=diagnostics)
    if box is None:
        return None
    return diagnostics


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
    box = block_around(pi, c, hit, allow_display=False, log=log, max_frac=MARKET_MAX_FRAC,
                       split_wide_headings=True)
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
    words = cut_band(ocr_text(inside), MARKET_ALT_CHARS)
    return _result("market", page, meta, date, ed, box, image_box, data, verdict,
                   page_hits, _curl(words), False, {"phrase": phrase})


def local_column(pi, coords, seed):
    """(x0, x1) in OCR units: the column the seed words sit in, read from
    the pixels of a band of the page around them at the image's own
    resolution, never from the page's gutters. Walking outward from the
    seed's centre along the band's column-darkness profile, the first run
    of LOCAL_GUTTER columns averaging under LOCAL_CLEAR is a gutter, and
    the column ends at its near side. None if either walk reaches the
    band's edge, which is a column that could not be read, not one the
    width of the band.

    ⚠️ Exists because a want-ad department is set at its own measure
    inside a border, so its internal column rule is on no page-level
    gutter: on the Brunswick News of 14 July 1927 the grid's column began
    in the neighbouring column's tail and cut the last word off every line.
    ⚠️ At the image's resolution, not PageInk's 1400px page, and not from
    the OCR either. Measured on that page: the gutter between the LOST
    and FOR SALE columns is about 20 image pixels with a dotted rule down
    its middle, which is 5 pixels at 1400 and reads as grain, and the OCR
    boxes of the two columns come within 5-8 units of each other, the
    same as its inter-word gaps. The band costs one fetch a candidate.
    ⚠️ It reads NARROW on the left of a hanging-indented column, since only
    first lines ink the indent. classified_block() therefore widens the
    word test by an em on that side and takes the box's edges from the
    words of the rows it keeps; this only says which words are in the
    column."""
    from PIL import Image
    import io
    page = pi.page
    x0 = min(w[0] for w in seed); x1 = max(w[0] + w[2] for w in seed)
    y0 = min(w[1] for w in seed); y1 = max(w[1] + w[3] for w in seed)
    ix, iy, iw, ih = page.to_image((x0, y0, x1 - x0, y1 - y0))
    cx, cy = ix + iw // 2, iy + ih // 2
    reach, half = int(page.image_w * LOCAL_REACH), int(page.image_h * LOCAL_SPAN)
    bx0, bx1 = max(0, cx - reach), min(page.image_w, cx + reach)
    by0, by1 = max(0, cy - half), min(page.image_h, cy + half)
    data = page.fetch_crop((bx0, by0, bx1 - bx0, by1 - by0), width=bx1 - bx0)
    im = Image.open(io.BytesIO(data)).convert("L")
    ink = im.point(lambda v: 255 if v < pi.thresh else 0)
    n, h = ink.size
    # ⚠️ Binarized ink share per column, in LOCAL_SLICES horizontal slices.
    # Ink share and not gray means: on the faint Brunswick scan the gutter's
    # paper is dirtier (gray 205) than the mean of a text column (206), and
    # on the dense Georgian the band's brightest column means are text, so
    # a gray "paper" level is wrong on both; dirty paper binarizes to no
    # ink at all. Slices, because a banner crossing the band spoils one
    # slice's profile and the scans are skewed (the Georgian's rule moves
    # 8px a slice), so boundaries are found per slice and matched across
    # them with `drift`.
    step_h = max(1, h // LOCAL_SLICES)
    slices = []
    for k in range(LOCAL_SLICES):
        part = ink.crop((0, k * step_h, n, min(h, (k + 1) * step_h)))
        slices.append([v / 255.0 for v in part.resize((n, 1), Image.BOX).get_flattened_data()])
    start = cx - bx0
    need = max(4, int(page.image_w * LOCAL_GUTTER))
    wide = max(2 * need, int(page.image_w * LOCAL_WIDE))
    pad = max(2, int(page.image_w * 0.001))
    drift = max(need, int(page.image_w * LOCAL_DRIFT))

    def boundaries(s):
        """Boundary x's in one slice. ⚠️ Two structures count, and a bare
        clear run of `need` does not: a WIDE clear run, or an inked column
        with `need` of clear on BOTH sides (a column rule, dotted or solid,
        in its gutter). The Brunswick column carries a typographic river,
        a wobbly white channel 4-8px wide through "occupies", "Close in."
        and "rooms for", present in three slices of four, and a run test
        read it as the gutter. A river is never 13px wide and never has a
        rule down its middle."""
        out = set()
        clear = [v <= LOCAL_CLEAR for v in s]
        run = 0
        for x in range(n):
            if clear[x]:
                run += 1
                continue
            if run >= wide:
                out.add(x - run); out.add(x - 1)             # the run's two ends,
                out.add(x - run // 2)                        # and its middle, which is
            run = 0                                          # where another slice's
        if run >= wide:                                      # rule mark lands
            out.add(n - run); out.add(n - run // 2)
        x = 0
        while x < n:
            if s[x] < LOCAL_RULE:
                x += 1
                continue
            # the rule's own body: a scanned rule is 3-8px wide with gray
            # shoulders (the Georgian's peaks 0.99 over two columns and
            # ramps 0.11-0.8 for three either side), so the body is every
            # inked column touching the peak, and the clear flanks begin
            # beyond it
            a = x
            while a > 0 and not clear[a - 1]:
                a -= 1
            b = x
            while b + 1 < n and not clear[b + 1]:
                b += 1
            if (b - a + 1) <= wide and a - need >= 0 and b + need < n \
                    and all(clear[a - need:a]) and all(clear[b + 1:b + need + 1]):
                out.add((a + b) // 2)
            x = b + 1
        return sorted(out)

    marks = [boundaries(s) for s in slices]
    ks = min(LOCAL_SLICES - 1, max(0, (cy - by0) // step_h))    # the seed's own slice

    def agreed(x, k0):
        """The slices besides `k0` with a boundary within `drift` of x."""
        return sum(1 for k, m in enumerate(marks) if k != k0 and any(abs(x - y) <= drift for y in m))

    def walk(step):
        """The seed slice's own nearest boundary that one other slice
        corroborates. ⚠️ Only when the seed slice has no boundary at all
        on this side does any other slice's, corroborated by a third,
        stand in: a seed near the top of the page puts the running head in
        its own slice (the Georgian of 1 October 1908, whose seed slice
        held no structure while the two below it held both rules). Not
        "any two slices" outright: the white around the WANTS lettering
        above the Brunswick LOST column gave two slices a wide run whose
        ends agreed, in the middle of the seed slice's own words."""
        own = sorted((x for x in marks[ks] if (x - start) * step >= iw // 2),
                     key=lambda x: abs(x - start))
        for x in own:
            if agreed(x, ks) >= 1:
                return x - step * pad
        if own:
            return None
        rest = sorted({x for k, m in enumerate(marks) if k != ks
                       for x in m if (x - start) * step >= iw // 2},
                      key=lambda x: abs(x - start))
        for x in rest:
            if agreed(x, None) >= LOCAL_AGREE:
                return x - step * pad
        return None

    left, right = walk(-1), walk(1)
    if left is None or right is None or right - left < need:
        return None
    s = page.scale                                     # image px per OCR unit
    return (int((bx0 + max(0, left)) / s), int((bx0 + min(n, right + 1)) / s))


def classified_lead_rows(rows, loose=False):
    """The rows that open a classified item the 20th-century way: one to
    three lead words from CLASSIFIED_LEADS, a dash, and a capital or
    figure. "FOR SALE—Nice fat fryers" and "ROOM—Large cool room" count;
    "WASHINGTON—The Senate" does not, since a city is not a lead. ⚠️ The
    dash is optional when the lead is set in capitals: the OCR dropped it
    from "FOR RENT — Three unfurnished" on the Brunswick page. With
    `loose`, CLASSIFIED_LOOSE_RE counts as well."""
    out = []
    for r in rows:
        text = ROW_NOISE_RE.sub("", ocr_text(r))
        m = CLASSIFIED_LEAD_RE.match(text)
        if m:
            lead = [t for t in re.split(r"[\s.']+", m.group(1).lower()) if t]
            if lead and all(t in CLASSIFIED_LEADS for t in lead) and (m.group(2) or m.group(1).isupper()):
                out.append(r)
                continue
        if loose and CLASSIFIED_LOOSE_RE.match(text):
            out.append(r)
    return out


def classified_heading(row):
    """Whether a row is a classified item's own heading, the 19th-century
    way: "Lost", "TO RENT", "Horse Stolen", "Wanted to Rent" set over a
    paragraph whose first word is in small capitals and carries no dash
    (the Augusta Chronicle of 8 March 1874, the Savannah Morning News of
    7 November 1868). Up to CLASSIFIED_HEAD_WORDS tokens, at least one of
    them a list word and none of them anything else -- a token that BEGINS
    with a list word passes, since the OCR read "TO rentT" for TO RENT."""
    toks = [re.sub(r"[^a-z]", "", w[4].lower()) for w in row]
    toks = [t for t in toks if t]
    if not toks or len(toks) > CLASSIFIED_HEAD_WORDS:
        return False
    hits = 0
    for t in toks:
        if t in CLASSIFIED_LEADS:
            hits += 1
        elif not any(t.startswith(l) and len(l) >= 4 for l in CLASSIFIED_LEADS):
            return False
    return hits >= 1


def heading_text(row):
    """A heading's words as the list words the test matched: "TO rentT" is
    "TO RENT". The OCR reads display capitals worst, and the alt is read
    aloud; a token the list did not match is kept as read."""
    out = []
    for w in row:
        t = re.sub(r"[^a-z]", "", w[4].lower())
        if not t:
            continue
        if t not in CLASSIFIED_LEADS:
            t = next((l for l in sorted(CLASSIFIED_LEADS, key=len, reverse=True)
                      if t.startswith(l) and len(l) >= 4), t)
        out.append(t.upper())
    return " ".join(out)


def _to_paper(pi, sx0, sx1, y_ocr, step, med, reach=2.5):
    """From OCR row `y_ocr`, out (up if step < 0) through inked small-image
    rows to the first paper row, no further than `reach` body heights; the
    OCR edge itself if paper is nearer than a line's height, or never
    comes. Returns OCR units."""
    per = pi.page.scale * pi.scale
    y = int(y_ocr * per)
    limit = int(reach * med * per)
    line = max(1, int(0.5 * med * per))
    if not (0 <= y < pi.h) or sx1 <= sx0:
        return y_ocr
    stop = y + step * limit
    lo, hi = (min(y, stop), max(y, stop))
    lo, hi = max(0, lo), min(pi.h, hi)
    dark = pi.row_dark(sx0, sx1, lo, hi)
    seq = list(range(y, stop, step))
    inked = 0
    for k, yy in enumerate(seq):
        if not (lo <= yy < hi):
            break
        if dark[yy - lo] <= PAPER_ROW:
            if inked >= line:
                return int(yy / per)
            return y_ocr
        inked += 1
    return y_ocr


def classified_block(pi, coords, seed, log=print, column=None, rule_test=row_has_rule):
    """(box, items, rows, head) for the run of classified items around
    `seed`, or None; `head` is the category subhead row when one heads the
    block. The column is local_column()'s; its rows are cut into ITEMS at
    printed rules and paragraph gaps, and a one-row heading is joined to
    the paragraph under it; the seed's item must LEAD -- open with LEAD—
    (classified_lead_rows) or carry a heading of its own
    (classified_heading) -- or this is not a classified; then whole
    neighbouring items are added below and above while each leads, until
    a display row, a category subhead over a LEAD— item (which is kept,
    and heads the block), a gap wide enough to hold an unread subhead,
    or the caps. The box's x comes from the kept rows' own words, padded,
    never from the pixel column: see local_column()'s hanging-indent note.
    `column` and `rule_test` are for the tests, which have no page. A
    heading the OCR could not read ("rm KLM" for FOR RENT) stays in the
    crop and out of the words, since the alt is what a reader hears."""
    words = coords["words"]
    med = nameplate.page_median_height(words) or 1
    if column is None:
        column = local_column(pi, coords, seed)
    if column is None:
        return None
    cx0, cx1 = column[0] - med, column[1]        # an em of slack on the left:
    incol = [w for w in words if cx0 <= w[0] + w[2] / 2.0 < cx1]   # hanging indents
    rows = _rows(incol)
    if not rows:
        return None
    per = pi.page.scale * pi.scale                # small px per OCR unit, for the rule test
    sx0, sx1 = int(column[0] * per), int(column[1] * per)
    top = lambda i: min(w[1] for w in rows[i])
    bot = lambda i: max(w[1] + w[3] for w in rows[i])
    def high(i):
        # ⚠️ The second-tallest word, not the tallest, on a row of three or
        # more: the 19th-century notice opens with its first word in small
        # capitals ("ONE LARGE STORE", the Augusta Chronicle of 8 March
        # 1874, an initial twice the body height), and the tallest word
        # alone called every such item display type and refused it.
        hs = sorted((w[3] for w in rows[i]), reverse=True)
        return hs[1] if len(hs) >= 2 else hs[0]     # (the smaller of two: "lanta 4510"
                                                    # carried one tall digit box)
    text_left = min(w[0] for r in rows for w in r)   # the column's own text edge

    def caps_heading(i):
        # a row of one to four words set in capitals, no dash: "LAUNDRY
        # MISPLACED Lost" (Macon 1924), "MASONIC NOTICE" (Savannah 1868),
        # "STORAGE" (Augusta 1874). It heads the paragraph under it; whether
        # the item then LEADS is judged in leads()
        toks = [w[4].strip(".,;:") for w in rows[i]]
        caps = [t for t in toks if t.isupper() and len(t) >= 2]
        return 1 <= len(toks) <= CLASSIFIED_HEAD_WORDS and len(caps) >= max(1, len(toks) - 1) \
            and sum(len(t) for t in caps) >= 4 and not CLASSIFIED_LOOSE_RE.match(ocr_text(rows[i])) \
            and high(i) < 1.6 * med \
            and min(w[0] for w in rows[i]) <= text_left + 3 * med
        # ...not display type (a running head or banner), and flush left: a
        # notice signs off in capitals set to the right ("THOS. HARRISON,
        # Columbus, Ga.", Savannah 1868), and that is a signature, not the
        # heading of what follows

    def heading(i):
        return (classified_heading(rows[i]) or caps_heading(i)) and not classified_lead_rows([rows[i]])

    # rows -> segments: a rule, a paragraph gap, or a heading row starts a
    # new one. ⚠️ A heading starts one whatever the gap above it: on the
    # Augusta page "TO RENT" sits 0.5 body heights under the previous
    # notice's dateline and 1.3 above its own paragraph, so by gaps alone
    # it belonged to the wrong item.
    segs = [[0]]
    for i in range(1, len(rows)):
        gap = top(i) - bot(i - 1)
        # ⚠️ The rule test only where the rows do not overlap: a drop
        # capital or a descender makes the boxes of two consecutive rows
        # overlap, and an inverted range handed to row_has_rule() split
        # the Savannah "Lost" notice of 1868 in two mid-sentence.
        toks = [w[4].strip(".,;:") for w in rows[i]]
        if len(toks) <= 2 and all(len(t) <= 3 for t in toks) and \
                (len(toks) == 1 or any(ch.isdigit() for t in toks for ch in t)):
            segs[-1].append(i)                    # "14", "tf", "07 1t": the item's own key.
            continue                              # Not "rm KLM": that is an unread subhead
        rule = gap > 0 and rule_test(pi, sx0, sx1, bot(i - 1), top(i))
        # ...and so does a row set larger than the one above it: the next
        # notice's own heading ("STORAGE", 1.58 body heights, not on the
        # list) sat 0.9 under "Apply at this office" and rode into the item.
        taller = high(i) >= CLASSIFIED_DISPLAY * med > high(i - 1)
        if heading(i) or taller or gap > CLASSIFIED_PARA_GAP * med or rule:
            segs.append([i])
        else:
            segs[-1].append(i)
    # segments -> items: a heading row heads the paragraph under it, in
    # its own segment or the next
    items = []
    for s in segs:
        if items and items[-1]["head"] is not None and not items[-1]["rows"] and not heading(s[0]):
            items[-1]["rows"] = s
            continue
        if heading(s[0]):
            items.append({"head": s[0], "rows": s[1:]})
        else:
            items.append({"head": None, "rows": s})
    items = [it for it in items if it["rows"]]        # a heading over a heading is dropped
    if not items:
        return None
    first = lambda it: it["rows"][0] if it["head"] is None else it["head"]
    last = lambda it: it["rows"][-1]
    sy = (min(w[1] for w in seed) + max(w[1] + w[3] for w in seed)) / 2.0
    si = min(range(len(items)),
             key=lambda k: min(abs(top(first(items[k])) - sy), abs(bot(last(items[k])) - sy)))
    if not (top(first(items[si])) - med <= sy <= bot(last(items[si])) + med):
        return None

    def dash_led(it, loose=False):
        return bool(classified_lead_rows([rows[it["rows"][0]]], loose=loose))

    def leads(it, loose=False):
        # ⚠️ A heading counts only at display size: the want-ad heads
        # measured run 2.0-2.3 body heights (Augusta 1874, Savannah 1868,
        # sn85034215 1873), while a column of local notes sets bold
        # body-size heads ("Situation Wanted.", "Dog Collars.", "Mayor's
        # Hours", the Savannah Republican of 21 May 1867) and read as items.
        if it["head"] is not None:
            h = rows[it["head"]]
            if classified_heading(h) and high(it["head"]) >= CLASSIFIED_DISPLAY * med:
                return True
            # a capitals heading leads when a list word is in it ("LAUNDRY
            # MISPLACED Lost"); "MASONIC NOTICE" and "ANNOUNCEMENT" do not
            toks = [re.sub(r"[^a-z]", "", w[4].lower()) for w in h]
            if any(t in CLASSIFIED_LEADS and t not in ("for", "to", "or", "and") for t in toks):
                return True
        return dash_led(it, loose)

    def catchline(it):
        # a reader advertisement opens with a word or two in capitals and
        # runs on: "HAVE your pictures framed", "COME IN and look", "I HAVE
        # the largest" (the Macon Telegraph of 1 December 1895). A local
        # note does not ("To Kill the Curculio.", "Dog Collars.")
        r = rows[it["rows"][0]]
        text = ocr_text(r)
        if re.match(r"^[A-Z][A-Za-z ,.']{0,24}[—–-]", text):
            return False                          # a dateline: "WASHINGTON, Dec. 1.—"
        toks = [w[4] for w in r]
        for n in (1, 2):                          # the capitals, then a lower-case word on the row
            caps = " ".join(toks[:n]).strip(".,;:")
            if len(toks) > n and len(caps.replace(" ", "")) >= 3 and caps.isupper() \
                    and toks[n][:1].islower():
                return True
        return False                              # "MASONIC NOTICE" alone on its row is a heading

    def indented(it):
        # a paragraph that continues an item opens indented; the block's
        # own left edge is where its leads begin
        r = rows[it["rows"][0]]
        return min(w[0] for w in r) >= left_edge + 0.8 * med

    def is_display(it):
        # any row at display size, or the FIRST row merely taller: "STORAGE"
        # over the next merchant's notice measured 1.58 body heights, a hair
        # under the 1.6 the rest of this module calls display, and rode in
        return (any(high(i) >= 1.6 * med for i in it["rows"])
                or high(it["rows"][0]) >= CLASSIFIED_DISPLAY * med)

    def is_centred_head(it):
        # a one-row item, short and centred in the column, is a subhead the
        # OCR could not read ("rm KLM" for FOR RENT on the Brunswick page):
        # kept in the crop when it heads the block, never walked through
        if it["head"] is not None or len(it["rows"]) != 1:
            return False
        r = rows[it["rows"][0]]
        rx0 = min(w[0] for w in r); rx1 = max(w[0] + w[2] for w in r)
        width = cx1 - cx0
        return (rx1 - rx0) <= 0.6 * width and abs((rx0 + rx1) / 2.0 - (cx0 + cx1) / 2.0) <= 0.12 * width

    def is_subhead(it):
        # a heading over a LEAD— item is the CATEGORY's subhead, not the item's own
        return it["head"] is not None and dash_led(it, loose=True)

    if not leads(items[si]) or is_display(items[si]):
        return None
    left_edge = min(w[0] for i in items[si]["rows"] for w in rows[i])
    lo = hi = si
    count = 1
    cap = CLASSIFIED_MAX_FRAC * coords["height"]
    height = lambda a, b: bot(last(items[b])) - top(first(items[a]))
    grow = {"down": True, "up": not is_subhead(items[si])}
    while grow["down"] or grow["up"]:
        for side in ("down", "up"):
            if not grow[side]:
                continue
            k = hi + 1 if side == "down" else lo - 1
            if k < 0 or k >= len(items) or count >= CLASSIFIED_MAX_ITEMS:
                grow[side] = False
                continue
            gap = (top(first(items[k])) - bot(last(items[hi])) if side == "down"
                   else top(first(items[lo])) - bot(last(items[k])))
            a, b = (lo, k) if side == "down" else (k, hi)
            if gap > CLASSIFIED_UNREAD_GAP * med or height(a, b) > cap:
                grow[side] = False
                continue
            if is_display(items[k]) or (side == "down" and is_centred_head(items[k])):
                grow[side] = False
                continue
            if side == "up" and is_centred_head(items[k]):
                lo = k                            # an unread subhead heads the block
                grow[side] = False
                continue
            if not leads(items[k], loose=True):
                if items[k]["head"] is not None:
                    grow[side] = False            # headed, so its own thing: "ANNOUNCEMENT"
                    continue                      # over the Cadillac agent's paragraph
                # A plain paragraph with no lead is one of two things, told
                # apart by its first line. Opening with a catchline in
                # capitals and no dash it is a sibling reader ad ("HAVE your
                # pictures framed cheap", Macon 1895) and joins as an item.
                # INDENTED, it is the neighbouring item's second paragraph
                # (the Savannah "Horse Stolen" notice of 1868 sets its
                # reward line a paragraph apart, 1.2 body heights in, and
                # the crop ended mid-notice without this): going down it
                # continues the item just taken; going up it belongs to the
                # leading item above it, which is taken with it. Anything
                # else -- a bold body-size head over a local note, a flush
                # paragraph of someone else's matter, a dateline -- ends the
                # walk. ⚠️ Not "a rule between them": the printed rules of
                # the Macon column were not all found, and a rule that IS
                # found says only that two things are separate, which a
                # paragraph gap says as well.
                if catchline(items[k]) and not is_centred_head(items[k]):
                    if side == "down":
                        hi = k
                    else:
                        lo = k
                    count += 1
                    continue
                if indented(items[k]):
                    if side == "down":
                        hi = k
                        continue
                    if k - 1 >= 0 and leads(items[k - 1], loose=True) and not is_display(items[k - 1]) \
                            and height(k - 1, hi) <= cap and count < CLASSIFIED_MAX_ITEMS:
                        lo = k - 1
                        count += 1
                        if is_subhead(items[lo]):
                            grow[side] = False
                        continue
                grow[side] = False
                continue
            if side == "down":
                if is_subhead(items[k]):          # the next category begins: stop short
                    grow[side] = False
                    continue
                hi = k
            else:
                lo = k
                if is_subhead(items[k]):          # this category's subhead: keep it, stop
                    grow[side] = False
            count += 1
    head = rows[items[lo]["head"]] if is_subhead(items[lo]) else None
    kept_items = items[lo:hi + 1]
    body = [w for it in kept_items if not is_centred_head(it) for i in it["rows"] for w in rows[i]]
    body += [w for it in kept_items if it["head"] is not None and rows[it["head"]] is not head
             for w in rows[it["head"]]]
    pad = int(0.6 * med)
    # ⚠️ x padded no further than the pixel column: on the Georgian the
    # gutter is 12px, under an em of padding, and the crop took a sliver
    # of the neighbouring column's letters
    x0 = max(0, min(w[0] for w in body) - pad, column[0])
    x1 = min(coords["width"], max(w[0] + w[2] for w in body) + pad, column[1])
    y0 = top(first(items[lo])); y1 = bot(last(items[hi]))
    # ⚠️ Each edge walked out to paper on the pixels, a little way: the
    # OCR read nothing of "lanta 4510.", the last line of the Georgian's
    # fourth item, and the crop cut that line in half. A row of type the
    # OCR missed is still ink; the walk stops at the first paper row, or
    # gives up and keeps the OCR edge if none comes within reach.
    y0 = _to_paper(pi, sx0, sx1, y0, -1, med)
    y1 = _to_paper(pi, sx0, sx1, y1, +1, med)
    y0 = max(0, y0 - pad); y1 = min(coords["height"], y1 + pad)
    box = (x0, y0, x1 - x0, y1 - y0)
    out_rows = []
    for it in kept_items:
        if is_centred_head(it):
            continue                              # unread; nothing to say aloud
        if it["head"] is not None and rows[it["head"]] is not head:
            h = rows[it["head"]]                  # an item's own heading, as its list words
            out_rows.append([(h[0][0], h[0][1], h[0][2], h[0][3], heading_text(h) + ".")])
        out_rows += [rows[i] for i in it["rows"]]
    return box, count, out_rows, head


def clip_classified(lccn, date, ed=1, seq=1, phrase=None, log=print):
    """A run of classified items -- LOST, FOR SALE, FOR RENT and what is
    under them -- found by search on an item phrase and closed by
    classified_block(). OCR only, like the market lane: the items on the
    page that prompted this read at 79-92 percent."""
    phrase = phrase or CLASSIFIED_PHRASES[0]
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
    got = classified_block(pi, c, hit, log=log)
    # ⚠️ The phrase is shape, not genre, as everywhere here: "furnished
    # rooms" sits in a hotel's display advertisement and "liberal reward"
    # in a story about a lost child. classified_block() refuses unless the
    # item holding the phrase opens LEAD—, from CLASSIFIED_LEADS.
    if got is None:
        raise npc.Refused("the phrase is not inside a classified item")
    box, n_items, rows, head = got
    inside = [w for r in rows for w in r]
    leg, n = legibility(inside)
    if leg < LEGIBLE:
        raise npc.Refused(f"classified OCR illegible ({leg:.0%} of {n} tokens)")
    text = ocr_text(inside)
    if head is not None:
        text = heading_text(head) + ". " + text
        inside = list(head) + inside
    verdict, page_hits = _verdict("classified", lccn, date, inside, c["words"], True)
    low = " " + re.sub(r"\s+", " ", text.lower()) + " "
    flagged = sorted(w for w in CLASSIFIED_REVIEW if f" {w}" in low or f" {w}," in low)
    if CLASSIFIED_REVIEW_RE.search(low):
        flagged.append(CLASSIFIED_REVIEW_RE.search(low).group(0))
    if flagged:
        verdict = _review(verdict, f"the block reads like a wanted notice: {flagged}")
    image_box, data = _fetch(page, box)
    words = cut_band(text, MARKET_ALT_CHARS)
    return _result("classified", page, meta, date, ed, box, image_box, data, verdict,
                   page_hits, _curl(words), False,
                   {"phrase": phrase, "items": n_items})


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
    if lane == "classified":
        return clip_classified(lccn, date, ed, seq, phrase, log=log)
    if lane == "cartoon":
        import pictures                      # imports this module; resolved late
        return pictures.clip_cartoon(lccn, date, ed, seq if seq and seq > 1 else None, log=log)
    raise ValueError(f"unknown lane {lane!r}")


def market_candidates(rights, **kw):
    return search_candidates(MARKET_PHRASES, rights, **kw)


def ad_candidates(rights, **kw):
    return search_candidates(AD_PHRASES, rights, **kw)


def classified_candidates(rights, **kw):
    # ⚠️ per_phrase high enough to walk EVERY decade: search_candidates()
    # stops a phrase once it has per_phrase hits, and at 50 a decade the ad
    # lane's 200 reaches 1906 and never the 1910s, where the want-ad
    # department lives (20,342 pages say "light housekeeping" in that
    # decade against 1,582 in the 1890s). Seven decades, 50 each, is 350.
    kw.setdefault("per_phrase", 400)
    return search_candidates(CLASSIFIED_PHRASES, rights, **kw)


def cartoon_candidates(rights, **kw):
    kw.setdefault("date_lo", CARTOON_SEARCH_FROM)
    return search_candidates(CARTOON_PHRASES, rights, **kw)


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
                if not ghn_api.LCCN_RE.match(lccn):
                    continue            # The Red and Black is "gua1179162": the
                                        # client refuses it, so it is not a candidate
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
