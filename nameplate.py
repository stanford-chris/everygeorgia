#!/usr/bin/env python3
"""
nameplate.py -- find the nameplate band on a newspaper front page, using OCR
word GEOMETRY rather than OCR text, and REFUSING whenever the geometry is not
clear.

⚠️⚠️ THE TEXT OF A NAMEPLATE IS OFTEN NOT READABLE, AND SOMETIMES ABSENT.
"THE ABBEVILLE CHRONICLE." OCRs as 't mraLE mK'. Worse, on ornate mastheads the
OCR engine skips the title ENTIRELY: on the Augusta paper of 8 March 1845 the
topmost text on the page is the dateline, 12% down, and the masthead above it
produced not one word box. So the detector matches size and position, never
words, and it must work when the thing it is looking for is invisible.

The consequence worth carrying to open question 2 (does this account need an
A.I. disclosure?): **this lane needs no model at all.** The crop is chosen by
arithmetic, and the caption can be built from the title, place and date the
archive already holds exactly.

⛔ A NAMEPLATE DETECTOR IS NOT A HEADLINE DETECTOR, and the difference is the
whole safety case for this lane. The same oversized-type test fires happily on
a banner headline. On the Griffin paper of 3 June 1916 a naive version chained
from the masthead straight down through a stack of 38-unit sports headlines and
returned a band 30% of the page deep. That was a baseball score. One page in
five carries lynching or slavery vocabulary, so the same bug on another day
crops a lynching headline and hands it back as furniture.

Three rules keep it honest, and each exists because a simpler version failed on
a real page measured 26 August 2026:

  1. **Size similarity.** A row joins the masthead cluster only if its type is
     comparable in size. The Griffin headlines are 0.39 of the masthead's
     height, so they are a different typographic object and do not join.
  2. **Never cross into a dense row.** The band stops at the first row of
     content below the cluster, and extends across it only if that row is
     SPARSE and small -- which a dateline is (8 words) and a headline block is
     not (27).
  3. **Two signals must agree.** The geometric band must finish above the point
     where body text starts, measured independently by word density. Where they
     disagree the page is refused, because a page this detector does not
     understand is not a page with a small nameplate.

⚠️ REFUSAL IS THE DESIGN, NOT A SHORTFALL. Roughly a third of pages are
refused. There are 218,505 postable pre-1931 NoC-US issues, so a strict
detector still leaves six figures of material: supply is not the constraint
here, selection is. See [[reference_bot_variety_is_selection_not_supply]].
"""
from statistics import median

# All tuned against a real sample; see crop_frequency.py --calibrate for the
# run that set them. Do not move one without re-running that.
DISPLAY_RATIO = 2.0      # display type is >= this multiple of the page median.
                         # ⚠️ NOT higher: nameplate-to-body ratio measured from
                         # 2.2 (Columbus Enquirer, 1849) to 13.9 (Griffin,
                         # 1916). A ratio of 3.0 refused the modest mastheads.
MIN_DISPLAY_FRAC = 0.012  # ...and at least this fraction of PAGE HEIGHT.
                         # ⚠️ Relative, never absolute: the OCR coordinate
                         # space is not the image space and is not even
                         # consistent between pages -- measured from 796x1190
                         # to 22839x31677, with page median word heights from
                         # 7 to 161. Any pixel constant here is meaningless.
TOP_FRACTION = 0.09      # the cluster must BEGIN within the top 9% of the page.
                         # ⚠️ MEASURED, not chosen: across 98 detections the
                         # cluster top ran min 0.8%, median 5.2%, p90 9.9%. It
                         # was 0.25 until 26 August 2026, and a quarter of a
                         # page is deep enough to contain a HEADLINE DECK. On
                         # the Athens Banner of 29 December 1908 the blackletter
                         # masthead produced no display boxes at all, so the
                         # detector locked onto the first thing that did -- the
                         # headlines at 10.4% -- and cropped "YOUNG NEGRO GIRL
                         # KILLED BENEATH SEABOARD ENGINE" as a nameplate. The
                         # Savannah Morning News of 20 October 1877 failed the
                         # same way at 9.7%. Both are excluded at 0.09, at a
                         # cost of about a tenth of the detections.
ROW_TOL = 0.6            # two display words share a row if their tops differ by
                         # less than this multiple of the taller one's height
ROW_GAP = 1.2            # two rows join if the gap between them is under this
                         # multiple of the upper row's height...
SIZE_SIM = 0.65          # ...and the lower row's type is at least this
                         # fraction of the first row height. Rule 1 above.
                         # ⚠️ 0.65, NOT 0.5: the Macon Telegraph of 8 June
                         # 1901 sets a headline at 0.52 of its masthead, and
                         # at 0.5 the detector swallowed it. That headline read
                         # "SHERIFF OF CARROLL FIRES ON THE MOB". Measured
                         # legitimate second lines run 0.74 and above.
SPARSE_N = 12            # a row of at most this many words may be taken into
                         # the band (a dateline); a denser one stops it
PAD_RATIO = 0.35         # breathing room below the cluster, as a multiple of
                         # its height, never crossing the next row
MAX_BAND_FRAC = 0.22     # a band deeper than this is not a nameplate
DENSE_SHARE = 0.025      # a horizontal band holding this share of the page's
                         # words is body text
DENSE_BANDS = 40         # resolution of the density scan


def page_median_height(words):
    hs = [w[3] for w in words if w[3] > 0]
    return median(hs) if hs else 0


def display_words(words, page_height, ratio=DISPLAY_RATIO,
                  top_fraction=TOP_FRACTION, min_frac=MIN_DISPLAY_FRAC):
    """Oversized words in the top band of the page, in reading order."""
    med = page_median_height(words)
    if not med or not page_height:
        return []
    cut = max(page_height * min_frac, med * ratio)
    limit = page_height * top_fraction
    return sorted((w for w in words if w[3] >= cut and w[1] <= limit),
                  key=lambda w: (w[1], w[0]))


def rows_of(display, row_tol=ROW_TOL):
    """Group display words into rows by their tops."""
    rows = []
    for w in display:
        if rows and abs(w[1] - rows[-1][0][1]) <= row_tol * max(rows[-1][0][3], w[3]):
            rows[-1].append(w)
        else:
            rows.append([w])
    return rows


def cluster(display, row_gap=ROW_GAP, size_sim=SIZE_SIM):
    """The topmost run of display rows that belong to one typographic object."""
    rows = rows_of(display)
    if not rows:
        return []
    first_h = max(w[3] for w in rows[0])
    run = [rows[0]]
    for prev, row in zip(rows, rows[1:]):
        prev_bottom = max(w[1] + w[3] for w in prev)
        prev_h = max(w[3] for w in prev)
        row_h = max(w[3] for w in row)
        if row[0][1] - prev_bottom > row_gap * prev_h:
            break
        if row_h < size_sim * first_h:      # rule 1: a different object
            break
        run.append(row)
    return [w for row in run for w in row]


def body_start(words, page_height, share=DENSE_SHARE, bands=DENSE_BANDS):
    """The y at which body text begins, by word density. None if never dense.

    ⚠️ Two consecutive dense bands are required. A single dense strip is a
    headline deck or a row of column heads, not the start of the body."""
    if not words or not page_height:
        return None
    need = max(3, len(words) * share)
    step = page_height / bands
    counts = [0] * bands
    for w in words:
        b = int(w[1] / step)
        if 0 <= b < bands:
            counts[b] += 1
    for i in range(bands - 1):
        if counts[i] >= need and counts[i + 1] >= need:
            return i * step
    return None


def nameplate_box(words, page_width, page_height,
                  pad_ratio=PAD_RATIO, max_frac=MAX_BAND_FRAC):
    """The nameplate band in OCR space as (x, y, w, h), or None.

    ⚠️ Returns None rather than a guess, and the caller must skip the page. A
    silent fallback is how a lane starts publishing whatever happens to sit at
    the top of a page it could not read.

    ⚠️ The band runs the FULL page width. Volume and number on one side and the
    price on the other are part of the nameplate and sit outside the title's own
    bounding box.
    """
    if not page_width or not page_height:
        return None
    run = cluster(display_words(words, page_height))
    if not run:
        return None
    bottom = max(w[1] + w[3] for w in run)
    top = min(w[1] for w in run)
    height = bottom - top
    if height <= 0:
        return None

    # Rule 2: never cross into a dense row. Look at what sits below the cluster
    # and take it only if it is sparse, small furniture -- a dateline.
    below = [w for w in words if w[1] > bottom]
    limit = page_height
    if below:
        nxt = min(w[1] for w in below)
        row = [w for w in below if w[1] < nxt + ROW_TOL * height]
        small = max((w[3] for w in row), default=0) <= height
        if len(row) <= SPARSE_N and small:
            after = [w for w in below if w[1] > max(x[1] + x[3] for x in row)]
            limit = min(after, key=lambda w: w[1])[1] if after else page_height
        else:
            limit = nxt
    band_bottom = min(limit, bottom + pad_ratio * height, page_height)
    if band_bottom <= 0:
        return None

    # Rule 3: the two signals must agree.
    bs = body_start(words, page_height)
    if bs is not None and band_bottom > bs:
        return None
    if band_bottom > page_height * max_frac:
        return None
    return (0, 0, int(page_width), int(round(band_bottom)))


def words_in(words, box):
    """Words whose CENTRE falls inside `box`.

    ⚠️ Centre, not overlap. A word clipped by the band edge is scored once, by
    where most of it sits; an overlap test double-counts it into both the
    nameplate and the body, and an enclosure test drops it from both."""
    x, y, w, h = box
    return [t for t in words
            if x <= t[0] + t[2] / 2 < x + w and y <= t[1] + t[3] / 2 < y + h]
