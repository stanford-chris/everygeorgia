#!/usr/bin/env python3
"""
nameplate_crop.py -- produce one nameplate clipping: the image, the caption and
the alt text, from a Georgia Historic Newspapers issue.

⛔ THIS SCRIPT CANNOT POST. Nothing here imports atproto or holds a credential.
Posting lives in everygeorgia_post.py, which calls clip() and nothing else
from here, so this stays a one-shot research tool that writes files and
prints. (UGA's permission to publish arrived on 10 September 2026, with one
condition: credit the Digital Library of Georgia. Until then this docstring
said none existed, which was the reason for the split. The split stays for a
different reason: a tool anyone runs by hand to look at a crop must not be
one keypress from a public post.)

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
  4. ink edge   ⚠️ the band must END IN PAPER, not through ink. The geometry
                is built from OCR word boxes, and an ornate masthead the OCR
                cannot read leaves no boxes: on "The Sunny South" (Atlanta,
                12 May 1894) the engraved title runs 20% down the page, the
                OCR saw only the small "THE" above it, and a 5.3% band passed
                every gate and sliced the lettering in half. The Augusta
                Herald of 15 June 1921 lost the bottom of its "HOME EDITION"
                box the same way. So the crop's own pixels are read: if the
                bottom rows of the band carry ink, the band is walked down to
                the first clear gap of paper, bounded by where body text
                starts and by MAX_BAND_FRAC; if no gap comes before the bound
                the page is refused. Found by looking at the crops, which is
                the thing HANDOFF.md says to do, on 11 September 2026.
  5. shape      a nameplate is a wide, shallow strip. A crop that comes back
                nearly square means the band was wrong whatever the maths said.
  6. arrival    the bytes are a real JPEG of the size asked for. A curl 200 is
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
MIN_ASPECT = 2.5          # gate 5: width/height of a nameplate strip
WIDTH_SLACK = 3           # gate 6: the IIIF server rounds. 1599 and 1597 were
                          # both returned for a 1600 request on 11 September
                          # 2026, and both crops were the right region. A
                          # wrong region does not arrive 1px narrower; it
                          # arrives a different shape, which gate 5 catches.

# Gate 4, the ink edge. All relative to the page, never absolute pixels.
INK_EDGE_COLUMN = 0.55    # a column this dark down the whole probe is film edge
INK_BELOW_PAPER = 25      # a pixel at least this much darker than the paper
                          # median (0-255) is ink, and at least...
INK_SHARE = 0.40          # ...this share of the way from paper to the page's
                          # own 5th-percentile pixel: 45 on a washed-out
                          # 1928 scan, 72 on a crisp one, so texture and
                          # foxing stay paper on both
CROSS_FRAC = 0.004        # "the ink continues downward" is measured this
                          # fraction of PAGE height below each row (about 9
                          # rows on a 1600px-wide probe, 30px on the page).
                          # ⚠️ Not 3 rows: at 3 a thick horizontal rule
                          # "continued" and five clean bands were refused
                          # for ending on one. A rule is a few pixels deep;
                          # a glyph or a box side is dozens.
CLEAR_MARGIN = 0.005      # a row is clear within this of the page's own floor
BIG_INK = 0.08            # a row whose continuing ink exceeds this is large
                          # type or an engraving: measured 0.1-0.3 on two
                          # unread headlines, 0.25 on the Sunny South's
                          # engraving, 0.03-0.05 on datelines and taglines
GAP_FRAC = 0.004          # a gap is this fraction of PAGE height of clear rows
                          # in a run (about 30px on a 7,500px page): the space
                          # between a masthead and the rule or dateline under
                          # it is typically 1%, a gap inside an engraving is not
EDGE_FRAC = 0.002         # how much of the band's bottom is inspected
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


SMALL_WORDS = {"a", "an", "and", "the", "of", "for", "on", "in", "at", "to",
               "by", "or", "&", "de", "la"}


def display_title(catalog):
    """The roster's catalogue form -> a title as a reader expects it.

    The roster carries library sentence case ("The Abbeville chronicle.",
    "Daily chronicle & sentinel.", "The DeKalb news."). Every word is
    capitalised except the small ones after the first; internal capitals are
    kept, so DeKalb and DuPont survive; hyphenated halves are capitalised
    separately (Advertiser-Republican); the trailing full stop goes and the
    apostrophe curls. ⚠️ Not str.title(), which would give Mcduffie."""
    t = (catalog or "").strip().rstrip(".").strip()
    out = []
    for i, w in enumerate(t.split(" ")):
        if not w:
            continue
        if i and w.lower() in SMALL_WORDS:
            out.append(w.lower())
            continue
        out.append("-".join(p[:1].upper() + p[1:] if p else p for p in w.split("-")))
    return " ".join(out).replace("'", "’")


def describe(meta, date, page):
    """Caption and alt text, assembled from archive metadata only.

    ⚠️ House style: work titles take quotation marks, not italics, and the
    newspaper's own name is the work here. Dates are UK order."""
    title = display_title(meta.get("title"))
    city = (meta.get("city") or "").strip()
    county = (meta.get("county") or "").strip()
    where = f"{city}, Georgia" if city else "Georgia"
    caption = (f"“{title},” {where}, {uk_date(date)}.")
    # ⚠️ Nothing here is asserted that the archive does not hold exactly. An
    # earlier version ended "Scanned from microfilm; the page is worn and the
    # ink uneven", which was true of the one crop it was written beside and
    # unverified for every other. The words of the clip are the paper's name,
    # which is what post 4 of the pinned thread promises the alt carries.
    alt = (f"The nameplate of “{title},” a newspaper published in {where}"
           + (f" ({county} County)" if county else "")
           + f", as printed on {uk_date(date)}: the paper’s name in large "
           "display type, cropped from the top of the front page.")
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


def _open_image(data):
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
    return im


def check_image(data, want_width):
    """Gates 5 and 6. Returns (width, height)."""
    im = _open_image(data)
    if abs(im.width - want_width) > WIDTH_SLACK:
        raise Refused(f"server returned width {im.width}, asked for {want_width}")
    if im.height <= 0 or im.width / im.height < MIN_ASPECT:
        raise Refused(f"shape gate: {im.width}x{im.height} is not a nameplate strip")
    return im.width, im.height


def row_crossing(im, page_rows, edge_col=INK_EDGE_COLUMN,
                 below=INK_BELOW_PAPER, cross_frac=CROSS_FRAC):
    """For every row, the fraction of columns where a dark pixel has another
    dark pixel `stride` rows beneath it: ink that CONTINUES downward. Pure
    PIL, no numpy.

    ⚠️ Continuation, not the row's darkness. Measured on five pages, 11
    September 2026: a band cut through the Sunny South's engraved lettering
    reads 0.25 at its edge; through the Augusta Herald's corner box, 0.01;
    the Middle Georgia Argus, whose band ends on a rule line over a torn,
    taped page, reads 0.002 -- and a plain darkness count put that clean
    edge at 5-7%, indistinguishable from the cut box, because tape and
    foxing are dark too. A rule is dark for a few rows and then stops; a
    glyph or a box side keeps going. That is the difference between an edge
    that happens to sit on ink and an edge that cuts something.

    ⚠️ Film edge columns are excluded by measurement, not by a fixed margin.
    A fixed 10% margin was tried first and hid that same box, which sits in
    the outer 10% of the page."""
    g = im.convert("L")
    w, h = g.size
    px = g.load()
    col_dark = [sum(px[x, y] for y in range(h)) / (255.0 * h) for x in range(w)]
    cols = [x for x in range(w) if 1 - col_dark[x] < edge_col]
    if len(cols) < w // 2:
        cols = list(range(w))              # a probe this dark has no edges to find
    # Paper level: the median pixel over the kept columns is paper on any page
    # that is mostly paper, which a top-of-page probe always is.
    sample = sorted(px[x, y] for y in range(0, h, 3) for x in cols[::4])
    paper, ink = sample[len(sample) // 2], sample[len(sample) // 20]
    # ⚠️ Relative to THIS page's contrast, not a fixed step below paper. The
    # Pembroke Journal of 3 February 1928 is a washed-out scan whose letters
    # sit at 124-135 on paper at 184: a fixed 70 below paper called every one
    # of them paper, the whole title read as clear rows, and the crop cut
    # through its lettering with the gate looking straight at it. The
    # threshold is now a share of the distance from paper to the page's own
    # dark end (its 5th-percentile pixel), which on a normal page lands where
    # the fixed step did.
    thresh = paper - max(below, int(INK_SHARE * (paper - ink)))
    n = float(len(cols))
    stride = max(4, int(round(page_rows * cross_frac)))
    out = []
    for y in range(h):
        yy = min(h - 1, y + stride)
        out.append(sum(1 for x in cols if px[x, y] < thresh and px[x, yy] < thresh) / n)
    return out


def first_gap(rows, from_row, page_rows, gap_frac=GAP_FRAC, margin=CLEAR_MARGIN):
    """The first row at or below `from_row` that starts a run of `gap` clear
    rows, or None. Clear is relative to the probe's own 10th percentile,
    because a mottled microfilm never reads zero anywhere."""
    n = len(rows)
    if n == 0:
        return None
    base = sorted(rows)[n // 10]
    gap = max(3, int(round(page_rows * gap_frac)))
    run = 0
    for y in range(max(0, int(from_row)), n):
        run = run + 1 if rows[y] <= base + margin else 0
        if run >= gap:
            return y - gap + 1
    return None


BIG = "big"     # ink_bottom()'s third answer: the walk met large type
FILM_EDGE = 0.8  # a row this dark across the page is the black film edge
TALL_FRAC = 0.009  # a body of ink this tall (of the page) is title- or
                   # headline-sized: about 20 rows on a 1600px probe, 67px on
                   # the page, where small type runs 10-15


def large_objects(rows, upto, page_rows, gap_frac=GAP_FRAC, margin=CLEAR_MARGIN,
                  tall_frac=TALL_FRAC, film=FILM_EDGE):
    """How many separate TALL bodies of ink sit in rows[:upto], where
    "separate" means parted by a run of `gap` clear rows and "tall" means the
    body spans at least `tall_frac` of the page: a title or a headline, not
    a dateline or a tagline. Things side by side (a title and the boxes
    flanking it) share rows and count once.

    ⚠️ Height, not darkness. The first version counted bodies of large
    CONTINUING ink and missed the Banner-Herald's own title, a light serif
    face reading 0.05 against the 0.08 floor, so the heavy sans headline
    under it was the band's only "large" object and the band passed. A
    headline is as tall as a title whatever its weight.

    The black film edge at the top of a microfilm frame is dark across the
    whole width and is not counted; a title is never that dark."""
    n = min(len(rows), max(0, int(upto)))
    if n == 0:
        return 0
    base = sorted(rows)[len(rows) // 10]
    gap = max(3, int(round(page_rows * gap_frac)))
    tall = max(4, int(round(page_rows * tall_frac)))
    # ⚠️ A segment is film edge only if MOST of its rows are that dark. The
    # Banner-Herald's masthead segment holds one black rule reading 0.9
    # across the page, and a version that disqualified a segment on any
    # such row threw the title away and counted the headline alone: one
    # object, band passed.
    # ⚠️ The film edge is stripped from the FRONT: the leading rows darker
    # than `film`, plus the soft tail under them, which reads as large ink
    # for a dozen rows on the Crawfordville, Calhoun and Augusta pages and
    # was being counted as a title in its own right. The tail is bounded at
    # two gaps so a real title touching the film edge is not stripped with
    # it -- a title is far taller than a gradient.
    # ⚠️ ...whether or not a row reads as film at all. On the Macon Telegraph
    # of 15 January 1897 and the Chronicle & Sentinel of 5 November 1856 the
    # frame's top is dark across part of the width only, so no row clears
    # the film threshold, and the large-ink rows at row 0 plus the mottled
    # gradient under them read as a tall body with big rows in it: a second
    # object, and a clean page refused. Large ink at the very first row is
    # never a title (a title has paper above it), so the leading large-ink
    # run is stripped too, bounded at three gaps so a title flush against a
    # dark frame keeps most of itself.
    # ⚠️ And after a TRUE film edge the strip is unbounded: the Pembroke
    # Journal of 3 February 1928 and the Schley County Enterprise of
    # 3 November 1887 carry a torn, dark top edge 35-45 rows deep under the
    # black frame, and a bound of three gaps left a third of it standing as
    # a body. Nothing that begins with black across the page is a title.
    y0 = 0
    while y0 < n and rows[y0] > film:
        y0 += 1
    stop = n if y0 else min(n, 3 * gap)
    while y0 < stop and rows[y0] > BIG_INK:
        y0 += 1
    count, run, seg, in_seg = 0, 0, [], False
    for y in range(y0, n):
        r = rows[y]
        if r <= base + margin:
            run += 1
            if in_seg and run >= gap:
                count += 1 if _is_body(seg, tall, film) else 0
                in_seg, seg = False, []
        else:
            in_seg = True
            run = 0
            seg.append(r)
    if in_seg and _is_body(seg, tall, film):
        count += 1
    return count


def _is_body(seg, tall, film, min_big=3):
    """A tall segment with some rows of large continuing ink in it. ⚠️ The
    second condition is what keeps a smear from counting: the torn top edge
    of the Crawfordville Democrat of 27 July 1883 reads as 23 rows of faint
    ink, taller than a title, with not one row of it large."""
    return (len(seg) >= tall
            and sum(1 for r in seg if r > BIG_INK) >= min_big
            and sorted(seg)[len(seg) // 2] <= film)


def ink_bottom(rows, band_rows, page_rows, cluster_rows=None, gap_frac=GAP_FRAC,
               edge_frac=EDGE_FRAC, margin=CLEAR_MARGIN, big=BIG_INK,
               cross_frac=CROSS_FRAC):
    """Gate 4. `rows` is row_crossing() of a probe crop of the top of the
    page, `band_rows` the detected band's bottom in that crop's rows,
    `page_rows` the whole page height in the same units.

    Returns the row the band should end at: `band_rows` itself when the band
    already ends clear, or the start of the first run of `gap` clear rows
    below it, PLUS the stride. Returns None when no such run comes before the
    probe ends, which the caller must treat as a refusal: a band that cannot
    find paper under the masthead does not know where the masthead ends.
    Returns BIG when the walk would have to cross a row of large continuing
    ink to get there: the extension is for a box's cut bottom or a
    dateline's baseline, never for a headline the OCR did not read (the
    Atlanta Georgian of 27 December 1919 shipped "LEAGUE TO GO TO PEOPLE AS
    1920 ISSUE" that way before this rule existed).

    ⚠️ THE CROSSING MEASURE IS BLIND FOR THE LAST `stride` ROWS OF ANY INK:
    a row reads as continuing only if ink sits `stride` rows beneath it, so
    the bottom of every glyph reads clear. The first version ended the band
    where the clear run began and the Independent Press of 13 January 1855
    came back with the feet of its letters cut off. So the edge is judged
    `stride` rows up, and the end returned is the gap's start plus `stride`,
    which is where the ink actually stops."""
    n = len(rows)
    band_rows = max(0, min(int(band_rows), n))
    if band_rows == 0 or n == 0:
        return None
    base = sorted(rows)[n // 10]
    clear = [r <= base + margin for r in rows]
    gap = max(3, int(round(page_rows * gap_frac)))
    edge = max(2, int(round(page_rows * edge_frac)))
    stride = max(4, int(round(page_rows * cross_frac)))
    probe = max(0, band_rows - stride)

    if all(clear[max(0, probe - edge):probe]):
        return band_rows
    # ⚠️ A band whose own edge is IN large ink is cutting the masthead itself
    # (large ink after a gap inside the band was refused before this was
    # called), so the walk may continue through that ink until paper: the
    # Savannah Daily Republican of 4 March 1858, a blackletter title the OCR
    # read the top of. A band whose edge is in small ink -- a dateline -- may
    # NOT walk into large ink: that is the Georgian's unread headline. Once
    # a clear row has been seen the licence ends either way.
    # ⚠️ ...and only if that ink is CONTIGUOUS with the cluster: no clear row
    # between the cluster's bottom and the edge. The Banner-Herald's band
    # ended inside its unread headline, which is large ink too, and a
    # licence judged at the edge alone let it through. The headline is
    # separated from the masthead by paper; the blackletter's lower half is
    # not.
    edge_big = any(rows[y] > big for y in range(max(0, probe - edge), probe))
    contiguous = (cluster_rows is not None and
                  not any(clear[max(0, int(cluster_rows)):probe]))
    through_big = edge_big and contiguous
    run = 0
    for y in range(probe, n):
        if rows[y] > big and not through_big:
            return BIG
        if clear[y]:
            through_big = False
            run += 1
        else:
            run = 0
        if run >= gap:
            return min(n, y - gap + 1 + stride)
    return None


def refine_band(page, box, coords, width=CROP_WIDTH):
    """Apply gate 4 to an OCR-space band. Returns (band, jpeg_bytes) or raises
    Refused. One image fetch: the probe is the top MAX_BAND_FRAC of the page
    at the final width, and the crop is cut from it locally, so a candidate
    page costs manifest + coordinates + one image, never two images."""
    ch, cw = coords["height"], coords["width"]
    probe_h_ocr = int(round(ch * nameplate.MAX_BAND_FRAC))
    probe_box = page.to_image((0, 0, cw, probe_h_ocr))
    data = page.fetch_crop(probe_box, width)
    im = _open_image(data)
    if abs(im.width - width) > WIDTH_SLACK:
        raise Refused(f"server returned width {im.width}, asked for {width}")
    per_ocr = im.height / float(probe_h_ocr)      # probe rows per OCR unit
    rows = row_crossing(im, ch * per_ocr)
    band_rows = box[3] * per_ocr
    # ⚠️⚠️ A NAMEPLATE BAND HOLDS ONE LARGE OBJECT. Two is a refusal. The band
    # may run below the masthead only over sparse small furniture
    # (nameplate.py rule 2), so a second body of large continuing ink,
    # separated from the first by paper, is something the OCR never read:
    # on the Banner-Herald of 20 November 1921 it was the banner headline
    # "CHINA'S CLAIMS ARE GIVEN CONFERENCE SYMPATHY", unread, taken as a
    # dateline because the one word the OCR did read on that row was the
    # "LARRY GANTT'S COLUMN" box beside it -- and the geometry then called
    # THAT the masthead cluster, so no rule anchored on the cluster could
    # see the problem. The Atlanta Georgian of 27 December 1919 did the
    # same with "LEAGUE TO GO TO PEOPLE AS 1920 ISSUE". Neither headline
    # could reach the vocabulary gate, because that gate reads the OCR too:
    # on another day that is a lynching headline passing as furniture.
    run = nameplate.cluster(nameplate.display_words(coords["words"], ch))
    cluster_rows = max(w[1] + w[3] for w in run) * per_ocr if run else band_rows
    if large_objects(rows, int(band_rows), ch * per_ocr) > 1:
        raise Refused("ink edge: two bodies of large type inside the band, "
                      "and the OCR read only one of them")
    end = ink_bottom(rows, band_rows, ch * per_ocr, cluster_rows)
    if end == BIG:
        raise Refused("ink edge: the band ends in ink and the next clear gap "
                      "is beyond large type the OCR did not read")
    if end is None:
        raise Refused("ink edge: the band ends in ink and no clear gap follows "
                      f"before {nameplate.MAX_BAND_FRAC:.0%} of the page")
    band = box
    if end > band_rows:
        # ⚠️⚠️ THE EXTENSION MAY NOT REACH DISPLAY TYPE THE OCR DID READ BELOW
        # THE BAND. The gap walk knows only pixels, and on the Banner-Herald
        # of 20 November 1921 and the Atlanta Georgian of 27 December 1919 it
        # walked through the dateline, found no gap wide enough under it, and
        # stopped under the banner HEADLINE instead -- "CHINA'S CLAIMS ARE
        # GIVEN CONFERENCE SYMPATHY" cropped as part of the nameplate, which
        # is the exact failure nameplate.py's three rules exist to prevent,
        # reintroduced by the gate meant to improve the crop. The extension
        # exists for ink the OCR could NOT see (an engraved title, the bottom
        # of a box's letters) and for the small furniture the band already
        # half-took (the Chronicle & Sentinel's dateline of 5 November 1856,
        # cut through its baseline). Headline-sized type below the band is
        # content the detector chose not to take, and the walk stops above
        # it; body text is bounded separately. If the cap leaves the edge
        # still in ink, the cut is real and unfixable from here: refuse.
        # ⚠️ Capping at ANY word below the band was tried first and refused
        # four of five clean pages, every one for a tagline or dateline the
        # gap sat just beneath.
        under = [w[1] for w in nameplate.display_words(coords["words"], ch)
                 if w[1] + w[3] / 2.0 > box[3]]
        if under:
            cap = int(min(under) * per_ocr) - 1
            if cap < end:
                end = cap
                edge = max(2, int(round(ch * per_ocr * EDGE_FRAC)))
                base = sorted(rows)[len(rows) // 10]
                if end <= band_rows or any(
                        r > base + CLEAR_MARGIN
                        for r in rows[max(0, end - edge):end]):
                    raise Refused("ink edge: the band cuts ink and display "
                                  "type sits under it, so it cannot be "
                                  "extended to a clear gap")
        # ⚠️ And the band as extended must still hold ONE tall body of ink:
        # a light-face headline the walk crossed without meeting BIG ink
        # would otherwise arrive here as furniture.
        if large_objects(rows, int(end), ch * per_ocr) > 1:
            raise Refused("ink edge: extending to the next clear gap takes in "
                          "a second body of large type")
        new_h = int(round(end / per_ocr))
        # ⚠️ Nor cross into body text (nameplate.py's rule 3, applied again
        # because the band just moved), nor past the cap.
        bs = nameplate.body_start(coords["words"], ch)
        if bs is not None and new_h > bs:
            raise Refused("ink edge: the first clear gap is below where body "
                          "text starts")
        if new_h > ch * nameplate.MAX_BAND_FRAC:
            raise Refused("ink edge: the first clear gap is deeper than a nameplate")
        band = (box[0], box[1], box[2], new_h)
    crop = im.crop((0, 0, im.width, max(1, int(round(min(end, im.height))))))
    buf = io.BytesIO()
    crop.convert("RGB").save(buf, format="JPEG", quality=90, optimize=True)
    return band, buf.getvalue()


def clip(lccn, date, ed=1, width=CROP_WIDTH, lane="nameplate", refine=True):
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

    if refine:
        band, data = refine_band(page, box, c, width)
        image_box = page.to_image(band)
    else:
        band = box
        image_box = page.to_image(band)
        data = page.fetch_crop(image_box, width)
    w, h = check_image(data, width)
    caption, alt, credit = describe(meta, date, page)
    return {
        "lccn": lccn, "date": date, "edition": ed, "lane": lane,
        "verdict": verdict, "postable": verdict.postable,
        "band_fraction": band[3] / page.coords()["height"],
        "extended": band[3] > box[3],
        "meta": meta, "url": page.url,
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
    print(f"  band       {r['band_fraction']*100:.1f}% of page"
          f"{' (extended to the ink edge)' if r['extended'] else ''}, "
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
