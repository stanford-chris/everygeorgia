#!/usr/bin/env python3
"""
lanes.py -- crop geometries for the advertisement and headline lanes, so their
exposure can be measured the way the nameplate lane's was.

⚠️⚠️ NEITHER LANE HAS BEEN DESIGNED YET, SO THESE ARE PROVISIONAL GEOMETRIES
AND THE MEASUREMENT IS ONLY AS GOOD AS THEY ARE. That is stated first because
it is the honest caveat: measuring a lane that does not exist means measuring an
assumption about it. The geometries below are drawn to be GENEROUS -- to find
more candidate crops rather than fewer -- so the resulting exposure figures are
upper-ish bounds on what a tighter lane would ship. Where a real design differs,
re-run this rather than quoting the old number.

⛔ THE NAMEPLATE'S STRUCTURAL PROTECTION DOES NOT TRANSFER. A nameplate is the
paper's own name in the top band: it cannot be about a lynching, which is why
that lane measured 0.0%. A headline is the loudest sentence on the page and an
advertisement is whatever somebody paid to print. Expect these numbers to be
bad, and read them as the reason those lanes are gated rather than as a defect
in the measurement.

Three geometries, because "an advertisement" has no single OCR signature:

  headline      a display-type cluster BELOW the nameplate and in the upper
                half of the page, plus its deck. Directly the headline lane.
  display ad    a display-type cluster in the LOWER half. In this corpus that
                is overwhelmingly a display advertisement: on the Banner-News
                of 23 September 1921 the only display type below the fold is
                "The Western Georgia Fair EXPOSITION".
  block         a column-shaped block of body text, on a grid. NOT a lane on
                its own: it is the BOUND on any lane that crops set text,
                which is where the dangerous advertising actually lives. A
                slave-sale notice is a few lines of body type in a classified
                column, not a display ad.

⚠️ Headline and display ad are separated by POSITION, which is a proxy and not
a classifier. A banner advertisement across the top of page one and a headline
at the foot of it would each be filed wrongly. The block measure does not care,
which is part of why it is here.
"""
import nameplate

UPPER_HALF = 0.5         # headline candidates begin above this; ads below
MIN_REAL_TOKEN = 3       # a display row must contain at least one token of
                         # this many letters.
                         # ⛔ There was a MIN_CLUSTER_WORDS = 2 beside this
                         # until 26 August 2026. It was dropped for two
                         # reasons: it survived its own mutation test, so
                         # nothing depended on it; and it was WRONG. A
                         # single-word banner headline is real, and in this
                         # corpus it is the loudest kind there is -- "LYNCHED",
                         # "HANGED", "MURDER". Requiring two words quietly
                         # excluded the worst crops from the measurement,
                         # which is the one direction an exposure figure must
                         # never be biased.
                         # ⚠️⚠️ THE TOKEN RULE IS THE ONE THAT WORKS, and the
                         # word count alone does not. On the Georgia Citizen of
                         # 27 January 1852 the only "display" type on the page
                         # was eleven single characters ('I', 'f', '1') at
                         # 26-31% down: column rules and printers' ornaments
                         # misread. They sit on a line, so they form a ROW of
                         # eleven and sail past any count threshold. What they
                         # cannot do is contain a word. A headline always can.
DECK_MIN = 0.30          # a deck line is at least this fraction of the head's
                         # height (below that it is body text)
DECK_GAP = 1.5           # ...and within this multiple of the head's height
X_PAD = 0.02             # horizontal padding, as a fraction of page width
GRID_COLS = 6
GRID_ROWS = 6
MAX_CROP_FRAC = 0.35     # a crop deeper than this is a runaway deck, not a
                         # headline or an advertisement, and is REFUSED rather
                         # than truncated. ⚠️ Measured over 145 headline crops:
                         # median 10.4%, p90 23.7%, p95 29.8%, and a maximum of
                         # 89.7% of the whole page. The deck loop can chain down
                         # a column of decreasing type until it has cropped most
                         # of the front page, which would carry the entire
                         # page's exposure into a crop labelled "a headline".


def _runs(words, page_height, lo, hi):
    """Display-word clusters whose top falls in [lo, hi] as page fractions."""
    med = nameplate.page_median_height(words)
    if not med or not page_height:
        return []
    cut = max(page_height * nameplate.MIN_DISPLAY_FRAC,
              med * nameplate.DISPLAY_RATIO)
    band = [w for w in words
            if w[3] >= cut and lo * page_height <= w[1] < hi * page_height]
    band.sort(key=lambda w: (w[1], w[0]))
    out = []
    for r in nameplate.rows_of(band):
        if not any(sum(ch.isalpha() for ch in w[4]) >= MIN_REAL_TOKEN for w in r):
            continue
        out.append(r)
    return out


def _box_of(row, words, page_width, page_height, with_deck):
    x0 = min(w[0] for w in row)
    x1 = max(w[0] + w[2] for w in row)
    y0 = min(w[1] for w in row)
    y1 = max(w[1] + w[3] for w in row)
    h = y1 - y0
    if with_deck:
        # the deck: smaller-but-not-body lines directly beneath, in the same
        # horizontal span. This is what makes a headline crop readable.
        cur = y1
        for _ in range(4):
            below = [w for w in words
                     if cur < w[1] <= cur + DECK_GAP * h
                     and w[0] + w[2] > x0 and w[0] < x1
                     and w[3] >= DECK_MIN * h]
            if not below:
                break
            cur = max(w[1] + w[3] for w in below)
        y1 = cur
    pad = X_PAD * page_width
    X0 = max(0, int(x0 - pad))
    X1 = min(page_width, int(x1 + pad))
    Y0 = max(0, int(y0 - 0.15 * h))
    Y1 = min(page_height, int(y1 + 0.15 * h))
    if X1 <= X0 or Y1 <= Y0:
        return None
    if page_height and (Y1 - Y0) > MAX_CROP_FRAC * page_height:
        return None
    return (X0, Y0, X1 - X0, Y1 - Y0)


def headline_boxes(words, page_width, page_height, nameplate_bottom=0):
    """Candidate headline crops: display clusters below the nameplate, upper
    half of the page, each with its deck."""
    lo = max(nameplate_bottom / page_height if page_height else 0, 0.0)
    out = []
    for row in _runs(words, page_height, lo, UPPER_HALF):
        if row[0][1] <= nameplate_bottom:
            continue
        b = _box_of(row, words, page_width, page_height, with_deck=True)
        if b:
            out.append(b)
    return out


def display_ad_boxes(words, page_width, page_height):
    """Candidate display-advertisement crops: display clusters in the lower
    half, with their deck (an ad's subordinate lines read the same way)."""
    out = []
    for row in _runs(words, page_height, UPPER_HALF, 1.0):
        b = _box_of(row, words, page_width, page_height, with_deck=True)
        if b:
            out.append(b)
    return out


def text_blocks(words, page_width, page_height, cols=GRID_COLS, rows=GRID_ROWS):
    """A grid of column-shaped blocks over the page's text area.

    ⚠️ A GRID, NOT REAL COLUMNS. Column boundaries vary by title and era and
    are invisible to OCR (they are printed rules). For scoring which words fall
    inside a crop-sized region this barely matters; for actually SHIPPING a
    clipping it would matter a lot, because a crop that straddles a rule is
    unreadable. Do not reuse this to produce a real advertisement crop."""
    if not words:
        return []
    x0 = min(w[0] for w in words)
    x1 = max(w[0] + w[2] for w in words)
    y0 = min(w[1] for w in words)
    y1 = max(w[1] + w[3] for w in words)
    if x1 <= x0 or y1 <= y0:
        return []
    cw = (x1 - x0) / cols
    ch = (y1 - y0) / rows
    out = []
    for c in range(cols):
        for r in range(rows):
            out.append((int(x0 + c * cw), int(y0 + r * ch),
                        max(1, int(cw)), max(1, int(ch))))
    return out
