#!/usr/bin/env python3
"""
pictures.py -- the cartoon lane: a drawing on any page of a daily, found by
the hole it leaves in the OCR, framed by the page's own grid, sorted by the
model, described by the model, and gated like every other lane.

Why a hole. Three attempts in August 2026 (reference_ghn_lane_findings) tried
to find cartoons in the ink and failed: line art is neither text-textured nor
continuous-toned, so an ink statistic cannot tell it from either. Measured
again on the Atlanta Georgian of 15 January 1919, page 10, on 12 September
2026: a syndicated strip is 0.18 ink and a column of body text 0.15. What
separates them is the OCR. Word boxes cover 0.51 of a text column, 0.30 to
0.41 of a display advertisement, and 0.22 of the strip, where the only
"words" are garbage read out of the speech balloons. So a cell of the page
is picture-like when its OCR-box coverage is under COVER_MAX and its ink is
between paper and solid black, and a picture is a connected block of such
cells big enough to be one. The two failures of the earlier attempts are
answered by machinery that did not exist then: rules.py reads the column
grid (attempt one leaked through the gutters), and the OCR raster marks a
letterspaced headline the OCR read as covered (attempt two took six of
them). A headline the OCR did NOT read is still a hole, and the model gate
below is what sorts it out.

⚠️ THE GEOMETRY FINDS PICTURES, NOT CARTOONS. A portrait halftone, an ad's
stove engraving and a map leave the same hole. The model is asked what KIND
of picture it is and only the cartoon kinds pass (KINDS_POSTED). That is a
model judgement and it will sometimes be wrong in both directions; the cost
of a wrong "photograph" is a candidate, the cost of a wrong "cartoon" is a
post, so the prompt lists the kinds it must NOT call a cartoon.

⚠️ A CARTOON IS THE ONE LANE WHOSE ALT TEXT IS A DESCRIPTION. Every other
lane's alt is the clip's own words. A drawing has few, so the model
describes what is drawn, labelled A.I.-described, and transcribes the title,
caption, balloons, signature and credit, labelled A.I.-transcribed, both in
the alt. The description is the model's, and post 4 of the pinned thread is
where that is disclosed in words.

⚠️ THE EDITORIAL TEST APPLIES HARDEST HERE. Cartoons of this era carry racial
caricature that no vocabulary prefix will catch, because a drawing needs no
word to do it. So the model is also asked, separately, whether the drawing
depicts anyone by racial or ethnic caricature, and a yes is REVIEW: a person
decides, the crop is queued, nothing posts. A prompt rule is not a fix
(CLAUDE.md, the alt-text verification pass); it is one belt beside the page
gate and the vocabulary pass over everything the model read, and the review
queue is the third.

Cost. A page costs its coordinates JSON; only a page whose OCR alone shows a
hole big enough costs the 1400px image; only a framed candidate costs a
crop and a model call (10-60 s). MODEL_CALLS_PER_ISSUE bounds the last.
"""
import re

import ghn_api
import nameplate
import nameplate_crop as npc
import rules
import transcribe

# ---- the cell grid ---------------------------------------------------------
CELL_W_FRAC = 1 / 40.0   # a cell is this of the page's width...
CELL_H_FRAC = 1 / 50.0   # ...and this of its height (about 35 x 33 px at 1400)
COVER_MAX = 0.30         # OCR-box coverage under this is not set text (text
                         # columns measure 0.51, display ads 0.30-0.41, the
                         # strip 0.22, all on the 1919 Georgian page)
INK_MAX = 0.90           # a cell inked more than this is film edge or a
                         # solid bar, never a drawing. ⚠️ 0.70 until the
                         # evening of 12 September 2026: the dense hatching
                         # of "Side Glances" (Griffin Daily News, 19 February
                         # 1930) runs past it, the panel came through as
                         # fragments, and one fragment shipped as the crop.
                         # Film black is 0.95 and up
INK_MEAN_MIN = 0.06      # ⚠️ Over the COMPONENT, not the cell. The first
                         # pass floored each cell at 0.03 ink and threw away
                         # the white inside the drawing (a balloon's interior,
                         # the sky), which cut the 1919 strip into fragments
                         # under FILL_MIN. Paper inside a picture is normal;
                         # a component that is paper THROUGHOUT (a blank
                         # column foot) is what this excludes, at a third of
                         # the strip's 0.18.
FILL_NEIGHBOURS = 5      # a cell with this many picture-like neighbours of 8
                         # joins them (a speech balloon is text inside a
                         # drawing; without this a strip is four fragments)
FILL_PASSES = 2
# ---- what counts as a picture ---------------------------------------------
MIN_AREA_FRAC = 0.02     # of the page: below it a portrait cut or an ornament
MAX_AREA_FRAC = 0.60     # above it the page's OCR failed, not a picture.
                         # ⚠️ 0.45 until 12 September 2026, evening: the
                         # Americus Times-Recorder's comic page of 9 February
                         # 1920 is four strips stacked, one component of 36
                         # percent of the page with ink and MORE without it,
                         # and the coordinates-only pass (which has no ink
                         # test) refused the whole page as "no hole". The
                         # cheap pass now applies no ceiling at all, since
                         # the ink pass, split_by_gaps and the clear-row share
                         # are the tests for a page whose OCR simply failed
MIN_W_FRAC = 0.10        # of the page's width (a column is 0.07-0.12)
MIN_H_FRAC = 0.05        # of its height
FILL_MIN = 0.35          # component cells over its bounding box's cells: an
                         # L-shaped hole is two items, not one. The 1919
                         # strip, its lettered balloons excluded, is 0.49;
                         # the Griffin Daily News sports cartoon of
                         # 19 February 1930, with its hand-lettered captions
                         # and a headline bridged to its corner, 0.449, and
                         # was refused at 0.45 (12 September 2026). A low
                         # floor costs model calls, never a wrong post
TOP_SKIP = {1: 0.10, "inner": 0.04}   # the nameplate band on a front page and
                         # the running head on an inner one are unread
                         # display type, and holes; skipped by position
CANDIDATES_PER_PAGE = 3
PAGES_PER_ISSUE = 16
MODEL_CALLS_PER_ISSUE = 3   # ⚠️ Spent on the LARGEST candidates across the
                         # whole issue, not page by page: on the 1919
                         # Georgian the front page offers an unread headline
                         # cluster with a portrait in it (a hole to the OCR,
                         # a "photograph" to the model) and page by page
                         # that would spend the budget before the strip on
                         # page 10 was looked at
# ---- the frame -------------------------------------------------------------
CAPTION_REACH = 0.05     # the crop may grow this far above and below the
                         # picture to take a title line or a caption: to a
                         # printed rule inside that reach, else up to
                         # CAPTION_LINES whole OCR lines set close together
                         # ("Penny Ante ... By Jean Knot" over its copyright
                         # line; a caption under an editorial cartoon); a
                         # story column under the picture is set closer than
                         # that but is cut at the line count, never mid-line
CAPTION_LINES = 4        # ⚠️ was 3 until 15 September 2026, and one too few:
                         # a title over a joke caption is commonly FOUR lines
                         # (a one-line title, then a two-to-three-line joke),
                         # and at 3 the Athens Banner's "FEMINISMS" cartoon of
                         # 20 August 1921 shipped with its whole third caption
                         # line ("pump 'em up to catch his train in the
                         # morning!") cut off at the crop's bottom edge --
                         # CAPTION_GAP and CAPTION_REACH both still had room,
                         # the count alone stopped it short. Bumped by one,
                         # not removed: the backstop against running into a
                         # genuine story column (see above) still applies
CAPTION_GAP = 1.5        # a line further than this many line heights from
                         # the last is not part of the caption
PAD_FRAC = 0.006
NEAR_GUTTER = 0.03       # a column boundary within this of the page's width
                         # from the picture's own edge is the crop's edge;
                         # further, the picture's edge plus a pad. ⚠️ Not the
                         # nearest UNCROSSED gutter (rules.column_bounds): a
                         # strip's frame line sits on its gutter and reads as
                         # crossing it, and the walk then took the next one
                         # and the whole column of type between
CAPTION_REAL_WORDS = 2   # a caption or title row carries this many real
                         # words; the OCR's reading of a drawing is rows of
                         # 'el i T' and '2 V g,g 7 4', and three of those
                         # used up the line allowance before the copyright
                         # line above the 1919 strip was reached
PAPER_ABS = 0.02         # a row this dark or less, across the picture's
                         # span, is paper: measured on the 1919 strip, the
                         # gap between it and the headline tier under it
                         # reads 0.004 and no row inside the drawing under
                         # 0.027 (the balloon tails and outlines cross every
                         # row). A rule test cannot do this: the dark-suited
                         # figures read 0.45-0.72, as a rule does.
TRIM_ZONE = 0.30         # a paper gap inside the outer zones of the
                         # component's height splits off what lies beyond it
                         # (an unread headline tier is a hole to the OCR too,
                         # and joins the drawing above it)
TYPE_CLEAR_MAX = 0.25    # ⚠️ The share of a component's rows that are paper
                         # ACROSS ITS WHOLE WIDTH (PAPER_ABS) is what tells
                         # unread display type from a drawing: the leading
                         # between lines of type is clear from edge to edge,
                         # a drawing's is not. Measured 12 September 2026 on
                         # the two dry runs' candidates, by the kind the model
                         # gave each: the 1919 strip 0.00; seven blocks the
                         # model called text-only 0.06 to 0.45; nineteen
                         # advertisement engravings 0.02 to 0.16. Above this
                         # a candidate is dropped unseen; below it the share
                         # is the FIRST ranking key, so drawings are looked
                         # at before type. One strip is one sample of the
                         # positive class, which is why this ranks rather
                         # than cuts near it: a strip in two rows of panels
                         # has a clear band between them.
CAPTION_ABOVE_H = 8.0    # a title line above may be display type, up to this
                         # many page medians tall ("Penny Ante ... By Jean Knot")
CAPTION_BELOW_H = 3.0    # a caption beneath is body type; a taller line under
                         # a picture is the next item's headline
CROP_WIDTH = 1200

# ---- the model -------------------------------------------------------------
PREFIX_DESCRIBED = "A.I.-described"
KINDS = ("editorial-cartoon", "comic-strip", "sports-cartoon", "humorous-drawing",
         "illustration", "photograph", "engraving", "advertisement", "map", "diagram",
         "ornament", "text-only", "other")
# ⚠️ "illustration" was added after the lane's second dry run (12 September
# 2026) named a serial-story illustration in the Augusta Daily Herald of
# 24 January 1914 a comic-strip: a realistic pen drawing of a man peering at
# a picture, signed Parker, the story's caption beneath. Without a kind for
# what it was, the model chose the nearest cartoon kind, and it would have
# posted. The cartoon kinds now say what makes them cartoons (exaggeration,
# panels, balloons, a joke or a comment), and the refused list says what a
# story illustration is.
KINDS_POSTED = {"editorial-cartoon": "editorial cartoon", "comic-strip": "comic strip",
                "sports-cartoon": "sports cartoon", "humorous-drawing": "cartoon"}
PICTURE_PROMPT = (
    "The file {name} in this directory is a clipping from a Georgia newspaper "
    "printed in {year}, selected automatically because it appears to contain a "
    "picture. Answer in exactly five lines, each beginning with its label.\n"
    "KIND: one of editorial-cartoon (a single drawn panel in a cartoonist's "
    "exaggerated style commenting on news, politics or public life, often with "
    "labels on the figures), comic-strip (a humorous drawing in a sequence of "
    "panels, or with speech balloons, in a cartoonist's style), sports-cartoon "
    "(a cartoonist's panel about sport, often several small caricatured "
    "drawings with hand lettering), humorous-drawing (another drawn joke in a "
    "cartoonist's style, usually with a joke caption), illustration (a "
    "realistic drawing that illustrates a story, serial, poem or article and "
    "is not a joke or a comment, whoever signed it), photograph (a halftone "
    "photograph, including a portrait), engraving (a realistic engraved or "
    "woodcut picture that is not a joke or a comment), advertisement (any "
    "picture that is part of an advertisement, whatever its style), map, "
    "diagram, ornament, text-only (no picture, only type), other. A drawing "
    "is a cartoon kind only if it is drawn to amuse or to comment; a realistic "
    "drawing that accompanies a story is illustration, not comic-strip.\n"
    "TITLE: the printed title or heading of the picture exactly as printed, or NONE.\n"
    "WORDS: every other word printed inside, above or beneath the picture "
    "(captions, speech balloons, labels, the artist's signature, the syndicate "
    "or copyright line), exactly as printed, in reading order, on this one "
    "line, with a vertical bar | between one balloon, caption, label or line "
    "and the next; write [illegible] for a word you cannot read; or NONE.\n"
    "PICTURE: one or two plain sentences saying what is drawn or shown, for a "
    "reader who cannot see it: the figures, what they are doing, the setting. "
    "Describe only what is visible; do not explain the joke or the politics.\n"
    "CARICATURE: yes if any person is drawn as a racial or ethnic caricature "
    "(exaggerated features standing for a race or nationality), otherwise no.\n"
    "Reply with those five lines and nothing else: no preamble, no commentary, "
    "no markdown. If the image is unreadable reply exactly CANNOT_READ."
)
LINE_RE = re.compile(r"^\s*(KIND|TITLE|WORDS|PICTURE|CARICATURE)\s*:\s*(.*?)\s*$",
                     re.IGNORECASE | re.MULTILINE)
TOOL_TALK = re.compile(r"\bthis tool\b|\bzoom\b|\bas an ai\b|\bi(?:'|’)?m (?:unable|not able|sorry)\b",
                       re.IGNORECASE)
MAX_WORDS_CHARS = 1500
MAX_PICTURE_CHARS = 600


# ============================================================ the geometry ==


def cell_grid(coords, pi=None, cw_frac=CELL_W_FRAC, ch_frac=CELL_H_FRAC):
    """Per cell of the page, (ocr_cover, ink): the share of the cell under an
    OCR word box, and the share of its pixels that are ink (None without a
    PageInk). Cells outside the OCR's own text extent read as covered, so
    the margins are never a hole. Cell coordinates are fractions of the
    page, so the same grid is drawn on the OCR space and the small image."""
    W, H = coords["width"], coords["height"]
    words = coords["words"]
    ncols, nrows = int(round(1 / cw_frac)), int(round(1 / ch_frac))
    cover = [[0.0] * ncols for _ in range(nrows)]
    if not words or not W or not H:
        return cover, None, ncols, nrows
    # ⚠️ Rasterize at 4x the cell grid, not per cell: a word box is smaller
    # than a cell, and "any word in the cell" would read a balloon's one
    # word as a full cell of text.
    sub = 4
    sw, sh = ncols * sub, nrows * sub
    raster = [[0] * sw for _ in range(sh)]
    for x, y, w, h, _ in words:
        x0 = max(0, int(x * sw / W)); x1 = min(sw, int((x + w) * sw / W) + 1)
        y0 = max(0, int(y * sh / H)); y1 = min(sh, int((y + h) * sh / H) + 1)
        for yy in range(y0, y1):
            row = raster[yy]
            for xx in range(x0, x1):
                row[xx] = 1
    for r in range(nrows):
        for c in range(ncols):
            s = 0
            for yy in range(r * sub, (r + 1) * sub):
                s += sum(raster[yy][c * sub:(c + 1) * sub])
            cover[r][c] = s / float(sub * sub)
    # the text extent: outside it, covered
    tx0 = min(w[0] for w in words); tx1 = max(w[0] + w[2] for w in words)
    ty0 = min(w[1] for w in words); ty1 = max(w[1] + w[3] for w in words)
    c0, c1 = int(tx0 * ncols / W), int(tx1 * ncols / W)
    r0, r1 = int(ty0 * nrows / H), int(ty1 * nrows / H)
    for r in range(nrows):
        for c in range(ncols):
            if not (c0 <= c <= c1 and r0 <= r <= r1):
                cover[r][c] = 1.0
    ink = None
    if pi is not None:
        ink = [[0.0] * ncols for _ in range(nrows)]
        for r in range(nrows):
            y0, y1 = int(r * pi.h / nrows), int((r + 1) * pi.h / nrows)
            for c in range(ncols):
                x0, x1 = int(c * pi.w / ncols), int((c + 1) * pi.w / ncols)
                n = dark = 0
                for yy in range(y0, y1, 2):
                    for xx in range(x0, x1, 2):
                        n += 1
                        if pi.is_ink(xx, yy):
                            dark += 1
                ink[r][c] = dark / float(n or 1)
    return cover, ink, ncols, nrows


def picture_cells(cover, ink, ncols, nrows):
    """Which cells are picture-like, after one closing pass."""
    like = [[cover[r][c] < COVER_MAX and (ink is None or ink[r][c] <= INK_MAX)
             for c in range(ncols)] for r in range(nrows)]
    for _ in range(FILL_PASSES):
        out = [row[:] for row in like]
        for r in range(nrows):
            for c in range(ncols):
                if like[r][c]:
                    continue
                n = 0
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if (dr or dc) and 0 <= r + dr < nrows and 0 <= c + dc < ncols and like[r + dr][c + dc]:
                            n += 1
                if n >= FILL_NEIGHBOURS:
                    out[r][c] = True
        like = out
    return like


def components(like, ncols, nrows):
    """4-connected components of picture-like cells: [(cells, (c0, r0, c1, r1))]
    with the box inclusive."""
    seen = [[False] * ncols for _ in range(nrows)]
    out = []
    for r in range(nrows):
        for c in range(ncols):
            if seen[r][c] or not like[r][c]:
                continue
            stack, cells = [(r, c)], []
            seen[r][c] = True
            while stack:
                rr, cc = stack.pop()
                cells.append((rr, cc))
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = rr + dr, cc + dc
                    if 0 <= nr < nrows and 0 <= nc < ncols and like[nr][nc] and not seen[nr][nc]:
                        seen[nr][nc] = True
                        stack.append((nr, nc))
            rs = [p[0] for p in cells]; cs = [p[1] for p in cells]
            out.append((cells, (min(cs), min(rs), max(cs), max(rs))))
    return out


NECK_FRAC = 0.30         # a cell column holding picture-like cells in fewer
                         # than this share of the component's rows is a
                         # bridge, not part of the picture
NECK_MIN_RUN = 3         # ...when at least this many consecutive columns or
                         # rows are. Two rows of hand lettering inside a
                         # cartoon ("OLD BATTLEFIELDS OF THE 1928 CAMPAIGN"
                         # and the cannon's labels, the Brunswick News,
                         # 11 June 1930) are boxed by the OCR and read as a
                         # neck two cells thick, and the cartoon was cut in
                         # two at it; every bridge measured (the Banner-
                         # Herald masthead, the Americus page banner, the
                         # Brunswick portrait chain) is three to eight


def _split_axis(cells, axis):
    """Pieces of `cells` cut at every index along `axis` (0 rows, 1 columns)
    that holds picture-like cells in under NECK_FRAC of the extent along
    the other axis. One piece back when there is no neck."""
    idx = [c[axis] for c in cells]; other = [c[1 - axis] for c in cells]
    span = max(other) - min(other) + 1
    per = {}
    for c in cells:
        per[c[axis]] = per.get(c[axis], 0) + 1
    thin = [i for i in range(min(idx), max(idx) + 1) if per.get(i, 0) < NECK_FRAC * span]
    necks, run = [], []
    for i in thin + [None]:
        if run and (i is None or i != run[-1] + 1):
            if len(run) >= NECK_MIN_RUN:
                necks.extend(run)
            run = []
        if i is not None:
            run.append(i)
    if not necks:
        return [cells]
    groups = {}
    for c in cells:
        if c[axis] in necks:
            continue
        k = sum(1 for x in necks if c[axis] > x)
        groups.setdefault(k, []).append(c)
    return list(groups.values()) or [cells]


def split_at_necks(cells):
    """Every piece of a component once it is cut, repeatedly, at its necks
    in both directions: a column or row of cells picture-like in under
    NECK_FRAC of the component's other extent is a bridge, not picture.

    Columns: on the Banner-Herald's editorial page of 22 January 1925 the
    cartoon and the paper's own masthead block beside it were bridged by
    three rows of unread display type and became one component, and the
    crop carried the editorial next to the drawing. Rows: on the Brunswick
    News of 11 June 1930 a cartoon, a feature column and a strip stacked in
    one column chained through the column's ornament and portrait into one
    component 21 percent of the page, and the crop was 3,411 px tall; on the
    Americus Times-Recorder's comic page of 9 February 1920 four strips
    chained up into the unread page banner, touched the top of the page and
    were skipped whole by the running-head rule. (A page gutter judged
    clear on the component's rows was tried first and could not fire: the
    ragged edge of a column of type inks every gutter column on 14 percent
    of the rows.) Every piece is returned; candidates() sizes each."""
    pieces, changed = [cells], True
    while changed:
        changed, out = False, []
        for piece in pieces:
            parts = _split_axis(piece, 1)
            if len(parts) == 1:
                parts = _split_axis(piece, 0)
            if len(parts) > 1 or len(parts[0]) < len(piece):
                changed = True
            out.extend(parts)
        pieces = out
    return pieces


def _pieces(comp, pi, coords, W, H, ncols, nrows):
    """A component as the pieces a candidate is judged on: cut at its
    necks, then (with the image) each piece parted into bands at paper
    gaps, and each band neck-cut on columns once more, since a band's
    columns are not the whole piece's. ⚠️ The Griffin Daily News sports
    panel of 19 February 1930 shipped as a slice across the text column
    beside it: the piece was wide because an unread headline bridged the
    two at the top, and the band that held the panel kept that width."""
    out = []
    for piece in split_at_necks(comp):
        if pi is None:
            out.append(piece)
            continue
        rs = [r for r, _ in piece]; cs = [c for _, c in piece]
        sbox = (int(min(cs) * pi.w / ncols), int(min(rs) * pi.h / nrows),
                int((max(cs) - min(cs) + 1) * pi.w / ncols), int((max(rs) - min(rs) + 1) * pi.h / nrows))
        for band in split_by_gaps(pi, sbox, coords):
            ra, rb = int(band[1] * nrows / pi.h), int((band[1] + band[3]) * nrows / pi.h + 0.999)
            in_band = [(r, c) for r, c in piece if ra <= r < rb]
            if not in_band:
                continue
            best = max(_split_axis(in_band, 1), key=len)
            # ⚠️ The band's rows are the extent, not the cells': the solid
            # black monument at the top of the Griffin sports panel is over
            # INK_MAX and not a picture-like cell, and a box rebuilt from
            # the cells began halfway down the panel.
            cs = [c for _, c in best]
            out.append([(r, c) for r in range(ra, min(rb, nrows)) for c in range(min(cs), max(cs) + 1)
                        if (r, c) in set(best) or True])
    return out


def candidates(coords, pi=None, seq=1):
    """Picture candidates as (area, box) with the box in OCR space, largest
    first, after the size, fill, ink and position rules. Without a PageInk
    the ink tests are skipped (the cheap first pass, on the coordinates
    alone)."""
    cover, ink, ncols, nrows = cell_grid(coords, pi)
    like = picture_cells(cover, ink, ncols, nrows)
    W, H = coords["width"], coords["height"]
    skip = TOP_SKIP[1] if seq == 1 else TOP_SKIP["inner"]
    out = []
    for comp, _ in components(like, ncols, nrows):
      for cells in _pieces(comp, pi, coords, W, H, ncols, nrows):
        rs = [r for r, _ in cells]; cs = [c for _, c in cells]
        c0, r0, c1, r1 = min(cs), min(rs), max(cs), max(rs)
        bw, bh = c1 - c0 + 1, r1 - r0 + 1
        area = len(cells) / float(ncols * nrows)
        if area < MIN_AREA_FRAC or (ink is not None and area > MAX_AREA_FRAC):
            continue
        if bw / float(ncols) < MIN_W_FRAC or bh / float(nrows) < MIN_H_FRAC:
            continue
        if len(cells) / float(bw * bh) < FILL_MIN:
            continue
        if r0 / float(nrows) < skip:
            # ⚠️ Clip the rows in the running head or the nameplate band,
            # never drop the piece: the Americus comic page's strips reach
            # the top row through the unread page banner, and the whole
            # page was skipped for it
            cells = [(r, c) for r, c in cells if r / float(nrows) >= skip]
            if not cells:
                continue
            rs = [r for r, _ in cells]; cs = [c for _, c in cells]
            c0, r0, c1, r1 = min(cs), min(rs), max(cs), max(rs)
            bw, bh = c1 - c0 + 1, r1 - r0 + 1
            area = len(cells) / float(ncols * nrows)
            if area < MIN_AREA_FRAC or bh / float(nrows) < MIN_H_FRAC:
                continue
        if ink is not None and sum(ink[r][c] for r, c in cells) / len(cells) < INK_MEAN_MIN:
            continue
        box = (int(c0 * W / ncols), int(r0 * H / nrows),
               int(bw * W / ncols), int(bh * H / nrows))
        out.append((area, box))
    out.sort(key=lambda t: -t[0])
    return out


def frame(pi, coords, box_ocr, diagnostics=None):
    """The crop for a picture box: out to the nearest column boundary the
    picture does not cross on each side, and above and below to the nearest
    gap or rule within CAPTION_REACH, so a title line above or a caption
    beneath comes with it. ⚠️ The vertical reach is bounded and falls back
    to the picture's own edge: a walk that only stopped at a gap would run
    through the body text under an editorial cartoon, whose line gaps are
    narrower than any gap this looks for.

    `diagnostics`: an optional dict filled IN PLACE with {"top": info_or_
    None, "bottom": info_or_None}, the same shape and the same "filled at
    the moment of the SAME decision this function already takes" contract
    as clips.block_around's own -- see closure_margins() there for why a
    reconstruction from the outside is the wrong way to build this. "rule"
    (a printed rule closed this side) is confident and structural, like its
    namesake in block_around; only "gap" and "caption-count-cap" (there was a
    real next caption line, past CAPTION_LINES, that this did not take)
    carry a ratio worth comparing to a floor. "reach" (CAPTION_REACH itself)
    is confident too -- a fixed structural bound, like block_around's own
    "cap". No cost when omitted.

    ⚠️ A CAPTION LINE CAN BE WIDER THAN THE PICTURE, AND THE CROP MUST WIDEN
    FOR IT. `x0`/`x1` are set from the picture's own OCR box before any
    caption is pulled in, and a title or caption typeset to the full column
    width runs past a narrower picture's edges. On the Athens Banner's
    "FEMINISMS" cartoon of 20 August 1921 that shipped the byline ("By
    Annette Bradshaw") and two caption words ("exercise", "to") each cut off
    mid-glyph at the crop's own edge -- every check that gates the crop
    passed, because none of them asked whether the box was wide enough for
    what it had just decided to include. `_caption_edge` now also returns the
    full word extent (not just the centre `span` was already filtered on) of
    the lines it accepted, and `x0`/`x1` widen to cover them, bounded to
    `near` beyond the picture's own edge so one wildly mis-OCR'd box cannot
    balloon the crop into a neighbouring column."""
    sbox = trim_by_gaps(pi, pi.from_ocr(box_ocr))
    x, y, w, h = sbox
    pad = max(2, int(pi.w * PAD_FRAC))
    near = int(pi.w * NEAR_GUTTER)
    gl = [g for g in pi.gutters() if g[1] <= x + pad and g[0] >= x - near]
    gr = [g for g in pi.gutters() if g[0] >= x + w - pad and g[1] <= x + w + near]
    x0 = gl[-1][0] if gl else max(0, x - pad)
    x1 = gr[0][1] if gr else min(pi.w, x + w + pad)
    reach = int(pi.h * CAPTION_REACH)
    gap = max(2, int(pi.h * rules.GAP_FRAC))
    top_lim, bot_lim = max(0, y - reach), min(pi.h, y + h + reach)
    dark = pi.row_dark(x0, x1, top_lim, bot_lim)
    base = sorted(dark)[len(dark) // 10] if dark else 0.0
    clear = [d <= base + rules.CLEAR_MARGIN for d in dark]
    rule = thin_rules(dark)

    def walk(start, step):
        """From the picture's edge outward: past the edge's own clear rows,
        then to the next run of `gap` clear rows or a rule; the edge is the
        near side of that. None when the reach runs out first."""
        i = start
        while 0 <= i < len(dark) and clear[i]:
            i += step                                  # off the edge's own paper
        passed_ink = False
        run = 0
        while 0 <= i < len(dark):
            if rule[i]:
                return i + step                        # keep the rule inside
            if clear[i]:
                run += 1
                if run >= gap and passed_ink:
                    return i - step * (run - 1)
            else:
                run = 0
                passed_ink = True
            i += step
        return None

    # a rule inside the reach closes the crop (a boxed cartoon keeps its box)
    yt = walk(y - top_lim, -1)
    yb = walk(y + h - 1 - top_lim, 1)
    ruled_top = yt is not None and rule[max(0, min(len(rule) - 1, yt - 1))]
    ruled_bot = yb is not None and rule[max(0, min(len(rule) - 1, yb + 1))]
    y0 = top_lim + yt if ruled_top else max(0, y - pad)
    y1 = top_lim + yb + 1 if ruled_bot else min(pi.h, y + h + pad)
    if diagnostics is not None:
        if ruled_top:
            diagnostics["top"] = {"reason": "rule", "ratio": None, "text": None}
        if ruled_bot:
            diagnostics["bottom"] = {"reason": "rule", "ratio": None, "text": None}
    # else whole OCR lines, a few, set close together
    per = pi.page.scale * pi.scale                 # small px per OCR unit
    span = [w for w in coords["words"] if x0 <= (w[0] + w[2] / 2.0) * per < x1]
    med = (nameplate.page_median_height(coords["words"]) or 1) * per
    x_lo = x_hi = None
    if not ruled_top:
        top_edge, (lo, hi) = _caption_edge(span, per, y, -1, reach, med,
                                           diagnostics=diagnostics, direction="top")
        y0 = min(y0, top_edge)
        if lo is not None:
            x_lo = lo if x_lo is None else min(x_lo, lo)
        if hi is not None:
            x_hi = hi if x_hi is None else max(x_hi, hi)
    if not ruled_bot:
        bot_edge, (lo, hi) = _caption_edge(span, per, y + h, 1, reach, med,
                                           diagnostics=diagnostics, direction="bottom")
        y1 = max(y1, bot_edge)
        if lo is not None:
            x_lo = lo if x_lo is None else min(x_lo, lo)
        if hi is not None:
            x_hi = hi if x_hi is None else max(x_hi, hi)
    if x_lo is not None:
        x0 = max(0, x0 - near, min(x0, int(x_lo) - pad))
    if x_hi is not None:
        x1 = min(pi.w, x1 + near, max(x1, int(x_hi) + pad))
    y0, y1 = max(0, min(y0, y)), min(pi.h, max(y1, y + h))
    return pi.to_ocr((x0, y0, x1 - x0, y1 - y0))


def clear_share(pi, sbox):
    """The share of the box's rows that are paper across its width."""
    x, y, w, h = sbox
    x0, x1 = _inside_film(pi, x, w)
    dark = pi.row_dark(x0, x1, y, y + h)
    return sum(1 for d in dark if d <= PAPER_ABS) / float(len(dark) or 1)


BAND_GAP_ROWS = 3        # a paper run this tall parts two bands: strips are
                         # stacked with three or four rows of paper between
                         # a strip's bottom rule and the next one's title
                         # line at 1400px (the Americus comic page), under
                         # rules.GAP_FRAC's seven, which left three strips
                         # in one crop
MIN_BAND_FRAC = 0.04     # a band of a component under this of the page's
                         # height is a title line or a caption, not a picture
PANEL_GAP = 0.012        # two adjacent tall bands parted by paper shorter
                         # than this of the page are one picture (the rows
                         # of panels of one strip)
BOX_EDGE = 0.04          # a paper row with ink in the outer this-much of the
                         # span on BOTH sides is inside a boxed picture, not
                         # a gap: the sky in the Brunswick News cartoon
                         # "'Twas Loaded" (11 June 1930) reads 0.005 dark
                         # across 420 px because only its two border lines
                         # cross those rows, and the cartoon was halved
                         # there. Between two strips, and between two rows
                         # of one strip's panels, no border crosses the gap


def _inside_film(pi, x, w):
    """(x0, x1) of the span with the film edge cut off: a black margin
    inside the span makes every row read as ink, and on the Banner-Herald
    of 24 October 1930 a column whose component began at the page's edge
    had no paper row anywhere, so two stacked cartoons and a want-ad box
    shipped as one crop 3,821 px tall."""
    fl, fr = pi.film_edges()
    x0, x1 = max(x, fl), min(x + w, fr)
    # ⚠️ And the outermost SPAN_INSET of the span on each side: a column
    # rule at the crop's edge, or a black stripe the page-level film test
    # missed (the Banner-Herald of 24 October 1930, columns 6-18 inked on
    # every row of the lower page), keeps every row off paper.
    inset = max(3, int((x1 - x0) * SPAN_INSET))
    x0, x1 = x0 + inset, x1 - inset
    return (x0, x1) if x1 > x0 else (x, x + w)


SPAN_INSET = 0.05
def split_by_gaps(pi, sbox, coords=None):
    """The box as bands parted by paper gaps across its width, short bands
    dropped, and adjacent bands rejoined when the paper between them is
    under PANEL_GAP. ⚠️ On the Americus Times-Recorder's comic page of
    9 February 1920 four strips stacked down the page came through as ONE
    component (their title lines are half-read display type and bridge
    them), and the paper between the strips put its clear-row share over
    TYPE_CLEAR_MAX, so a page of nothing but cartoons was "no picture-sized
    hole". Each strip parted by paper is a band.

    ⚠️ A paper row inside a BOX is not a gap (BOX_EDGE): that is what
    keeps a boxed cartoon whole across its sky. The rejoin under PANEL_GAP
    is otherwise unconditional between adjacent tall bands; a short band
    between (a title line, a caption) breaks adjacency and parts them.
    Two cleverer rules
    were measured and dropped on 12 September 2026, on this page, the
    Brunswick News of 11 June 1930, the Griffin Daily News of 19 February
    1930 and the Banner-Herald of 24 October 1930: refusing to rejoin when
    the lower band opens with display type cut the Brunswick cartoon
    "'Twas Loaded" in half at "OLD BATTLEFIELDS OF THE 1928 CAMPAIGN",
    since hand lettering in a cartoon is taller than any title; and
    parting bands at printed rules as well as paper fired on rows inside
    drawings and halved three of the six. Two strips set tight, title
    against the strip above with no paper between, stay one band; the
    model still calls that a comic strip, and a reader sees two. Adjacency
    is what keeps a cartoon from rejoining the strip below it across a
    column of type: the type is bands too short to keep, and a dropped
    band breaks the chain. `coords` is accepted and unused, kept for the
    signature the caller has."""
    x, y, w, h = sbox
    x0, x1 = _inside_film(pi, x, w)
    dark = pi.row_dark(x0, x1, y, y + h)
    edge = max(2, int((x1 - x0) * BOX_EDGE))

    def boxed_row(i):
        yy = y + i
        return (any(pi.is_ink(xx, yy) for xx in range(x0, x0 + edge))
                and any(pi.is_ink(xx, yy) for xx in range(x1 - edge, x1)))

    gap = BAND_GAP_ROWS
    bands, start, paper = [], None, 0
    for i, d in enumerate(dark + [0.0] * gap):
        if d <= PAPER_ABS and not (i < len(dark) and boxed_row(i)):
            paper += 1
            if start is not None and paper >= gap:
                bands.append((start, i - paper + 1))
                start = None
        else:
            paper = 0
            if start is None:
                start = i
    min_h = int(pi.h * MIN_BAND_FRAC)
    merged, last_end = [], None
    for a, b in bands:
        tall = b - a >= min_h
        if tall and merged and last_end == merged[-1][1] and a - merged[-1][1] < pi.h * PANEL_GAP:
            merged[-1] = (merged[-1][0], b)
        elif tall:
            merged.append((a, b))
        last_end = b
    return [(x, y + a, w, b - a) for a, b in merged] or [sbox]


def trim_by_gaps(pi, sbox):
    """The component's box with anything beyond a paper gap in its outer
    zones cut off: see PAPER_ABS. The larger part is kept; a cut that would
    keep under half is not made."""
    x, y, w, h = sbox
    x0, x1 = _inside_film(pi, x, w)
    dark = pi.row_dark(x0, x1, y, y + h)
    gap = max(2, int(pi.h * rules.GAP_FRAC))
    runs, start = [], None
    for i, d in enumerate(dark + [1.0]):
        if d <= PAPER_ABS:
            start = i if start is None else start
        elif start is not None:
            if i - start >= gap:
                runs.append((start, i))
            start = None
    top, bot = 0, h
    zone = int(h * TRIM_ZONE)
    for a, b in runs:
        if b <= zone and h - b >= h / 2:
            top = max(top, b)
        if a >= h - zone and a - top >= h / 2:
            bot = min(bot, a)
    return (x, y + top, w, bot - top)


RULE_MAX_ROWS = 2        # a printed rule is at most this many rows tall at
                         # 1400px; a line of bold caption type across a
                         # narrow span reads as dark as a rule (the Parker
                         # illustration in the Augusta Daily Herald of
                         # 24 January 1914, 209 px wide: rows 610-613 at
                         # 0.46) and its x-height band is FOUR rows, so the
                         # frame stopped "just past the rule" in the middle
                         # of the caption at a limit of 4


def thin_rules(dark, max_rows=RULE_MAX_ROWS):
    """Which rows are a printed rule: dark as one, in a run no taller than
    a rule is."""
    hot = [d >= rules.HRULE_MIN_DARK for d in dark]
    out = [False] * len(dark)
    i = 0
    while i < len(dark):
        if hot[i]:
            j = i
            while j < len(dark) and hot[j]:
                j += 1
            if j - i <= max_rows:
                for k in range(i, j):
                    out[k] = True
            i = j
        else:
            i += 1
    return out


def _caption_edge(span, per, edge, step, reach, med, diagnostics=None, direction=None):
    """The far edge (small px) of up to CAPTION_LINES OCR lines beyond
    `edge` in direction `step`, each within CAPTION_GAP line heights of the
    last and inside `reach`; a line the edge itself cuts is the first. The
    edge unchanged when there is no such line.

    Also returns (lo, hi): the full left/right extent (small px, not just
    the word centres `span` was already filtered on) of the accepted lines,
    or (None, None) when none were. A caption or title set to the full
    column width can run past a narrower picture's own edges -- see frame()'s
    own docstring -- and the caller widens the crop to match.

    `diagnostics`/`direction`: see frame()'s own docstring. Filled at the
    exact break this function already takes -- including the for loop's own
    natural end, which is where CAPTION_LINES itself can be the reason a
    real caption line was left out (see CAPTION_LINES' own history: it was
    3 until a title-over-joke caption measured four lines deep and shipped
    cut off). That case gets a real "caption-count-cap" ratio, computed the
    same way "gap" is, against whatever line sits just past the cap -- not
    folded into the confident, ratio-less reasons, because unlike
    block_around's MARKET_ROWS this cap is regularly close enough to bite."""
    def _note(reason, ratio=None, text=None):
        if diagnostics is not None and direction is not None:
            diagnostics[direction] = None if reason is None else \
                {"reason": reason, "ratio": ratio, "text": text}

    lines = []
    for rw in nameplate.rows_of(sorted(span, key=lambda w: (w[1], w[0])), row_tol=0.5):
        if sum(1 for w in rw if sum(ch.isalpha() for ch in w[4]) >= 3) < CAPTION_REAL_WORDS:
            continue                                   # the OCR's reading of ink
        top = min(w[1] for w in rw) * per; bot = max(w[1] + w[3] for w in rw) * per
        if bot - top > (CAPTION_ABOVE_H if step < 0 else CAPTION_BELOW_H) * med:
            continue                                   # a headline, not a caption
        lines.append((top, bot, rw))
    # ⚠️ Outside the picture, whole: a row reaching into it is a balloon
    tol = 4
    if step < 0:
        lines = [(t, b, rw) for t, b, rw in lines if b <= edge + tol and b > edge - reach]
        lines.sort(key=lambda l: -l[1])
    else:
        lines = [(t, b, rw) for t, b, rw in lines if t >= edge - tol and t < edge + reach]
        lines.sort(key=lambda l: l[0])
    out, last = edge, edge
    lo = hi = None
    for i, (t, b, rw) in enumerate(lines[:CAPTION_LINES]):
        hgt = max(1.0, b - t)
        gap = (last - b) if step < 0 else (t - last)
        if i and gap > CAPTION_GAP * hgt:
            _note("gap", (gap - CAPTION_GAP * hgt) / (CAPTION_GAP * hgt),
                 " ".join(w[4] for w in sorted(rw, key=lambda w: w[0])))
            break
        near_side = b if step < 0 else t              # the side facing the picture
        if near_side < edge - reach or near_side > edge + reach:
            _note("reach", None, " ".join(w[4] for w in sorted(rw, key=lambda w: w[0])))
            break
        out = (t if step < 0 else b) + step * 2
        last = t if step < 0 else b
        row_lo = min(w[0] for w in rw) * per
        row_hi = max(w[0] + w[2] for w in rw) * per
        lo = row_lo if lo is None else min(lo, row_lo)
        hi = row_hi if hi is None else max(hi, row_hi)
    else:
        if len(lines) > CAPTION_LINES:
            nt, nb, nrw = lines[CAPTION_LINES]
            hgt = max(1.0, nb - nt)
            gap = (last - nb) if step < 0 else (nt - last)
            _note("caption-count-cap", (gap - CAPTION_GAP * hgt) / (CAPTION_GAP * hgt),
                 " ".join(w[4] for w in sorted(nrw, key=lambda w: w[0])))
        else:
            _note(None)          # nothing further out there to have missed
    return out, (lo, hi)


def cartoon_closure_margins(pi, c, page):
    """ADVISORY ONLY: crop_closure_check.py's own entry point for this
    lane, mirroring clips.headline_closure_margins/article_closure_margins.
    Re-picks candidates on THIS page exactly as clip_cartoon() does (its
    own TYPE_CLEAR_MAX filter, largest first) and reports frame()'s own
    diagnostics for the one surviving candidate -- the one clip_cartoon
    would hand the model first.

    `None` when there is no picture-sized hole on this page at all, OR when
    more than one candidate survives the filter: a second candidate means
    which one the model actually picked cannot be reproduced without
    spending the call this audit exists to avoid (see pictures.py's own
    "cost" paragraph), so this reports NOT CHECKED rather than guess."""
    cands = [b for _, b in candidates(c, pi, page.seq)]
    survivors = [b for b in cands if clear_share(pi, pi.from_ocr(b)) <= TYPE_CLEAR_MAX]
    if len(survivors) != 1:
        return None
    diagnostics = {}
    frame(pi, c, survivors[0], diagnostics=diagnostics)
    return diagnostics


# =============================================================== the model ==


def parse_reply(text):
    """{'kind', 'title', 'words', 'picture', 'caricature'} or None."""
    if not text or "CANNOT_READ" in text:
        return None
    found = {m.group(1).lower(): m.group(2).strip() for m in LINE_RE.finditer(text)}
    if "kind" not in found or "picture" not in found:
        return None
    kind = re.sub(r"[^a-z-]", "", found["kind"].lower().split()[0] if found["kind"].split() else "")
    if kind not in KINDS:
        # the model sometimes answers "comic strip" or "Comic-strip (a ...)"
        folded = found["kind"].lower().replace(" ", "-")
        kind = next((k for k in KINDS if folded.startswith(k)), None)
        if kind is None:
            return None
    def none(s):
        return "" if s.strip().upper() in ("NONE", "N/A", "") else s.strip().strip('"“”')
    # ⚠️ The balloons come back separated by bars and go out separated by
    # periods (transcribe.join_items), his rule for the band and the
    # headline lane on 12 September 2026: a screen reader gets no pause at
    # a space, and nine balloons as one clause is a wall.
    words = transcribe.join_items(t.strip() for t in none(found.get("words", "")).split("|"))
    return {"kind": kind, "title": none(found.get("title", "")),
            "words": words, "picture": found["picture"],
            "caricature": found.get("caricature", "").strip().lower().startswith("y")}


def classify(image_bytes, year, log=print):
    """The model's reading of one candidate, parsed, or None."""
    for attempt in range(2):
        raw = transcribe.ask(image_bytes, year, PICTURE_PROMPT, log=log)
        if raw is None:
            return None
        r = parse_reply(raw)
        if r is None:
            log(f"  (picture reply unparseable: {raw[:80]!r})")
            continue
        if TOOL_TALK.search(r["words"] + " " + r["picture"]):
            log(f"  (picture reply reads as tool talk: {r['picture'][:80]!r})")
            continue
        if len(r["words"]) > MAX_WORDS_CHARS:
            r["words"] = r["words"][:MAX_WORDS_CHARS].rsplit(" ", 1)[0] + "…"
        if len(r["picture"]) > MAX_PICTURE_CHARS:
            r["picture"] = r["picture"][:MAX_PICTURE_CHARS].rsplit(" ", 1)[0] + "…"
        return r
    return None


QUOTE_OPEN = re.compile(r'(^|[\s(\[])"')


def curl(s):
    """Quotes curled by position, not clips._curl(), which closes every
    double quote: the model's description carries pairs ("a frame labeled
    "1914,"") and the first alt shipped an opening quote closed."""
    s = QUOTE_OPEN.sub(r"\1“", s or "")
    s = s.replace('"', "”")
    s = re.sub(r"(^|[\s(\[])'", r"\1‘", s)
    return s.replace("'", "’")


def compose_alt(meta, date, seq, r):
    """The alt: the description, labelled as the model's; the title and the
    printed words, labelled as transcribed. ⚠️ Both labels are load-bearing:
    bot_alt_check.py's marker for this account is transcribe.PREFIX anywhere
    in the alt, and PREFIX_DESCRIBED is what tells a reader the sentence
    about the drawing is not the paper's."""
    import clips
    title = npc.display_title(meta.get("title"))
    city = (meta.get("city") or "").strip()
    where = f"{city}, Georgia" if city else "Georgia"
    what = KINDS_POSTED[r["kind"]]
    picture = curl(r["picture"].rstrip(".") + ".")
    alt = (f"{PREFIX_DESCRIBED} {what} from “{title},” {where}, {npc.post_date(date)}, "
           f"page {seq}. {picture}")
    parts = []
    if r["title"]:
        parts.append(f"titled “{curl(r['title'])}”")
    if r["words"]:
        parts.append(f"the words read: “{curl(r['words'])}”")
    if parts:
        alt += f" {transcribe.PREFIX}, " + "; ".join(parts) + ("" if alt.endswith("”") else "")
        if not alt.endswith("”"):
            alt += "."
    return alt


# ================================================================ the lane ==


def clip_cartoon(lccn, date, ed=1, seq=None, log=print):
    """One cartoon from any page of the issue, or Refused. With `seq`, that
    page only. Pages are walked in order; the first candidate the model
    calls a cartoon kind wins, subject to the gates."""
    import clips
    meta = clips._meta(lccn, date, "cartoon")
    pages = ghn_api.issue_pages(lccn, date, ed)
    if seq:
        if seq < 1 or seq > len(pages):
            raise npc.Refused(f"no seq-{seq} in this issue")
        pages = [pages[seq - 1]]
    found = []                              # (area, page, coords, pi, box)
    for page in pages[:PAGES_PER_ISSUE]:
        c = page.coords()
        if not c["words"]:
            continue
        # the cheap pass: coordinates only, no image
        if not candidates(c, None, page.seq):
            continue
        pi = rules.PageInk(page)
        for area, box in candidates(c, pi, page.seq)[:CANDIDATES_PER_PAGE]:
            found.append((area, page, c, pi, box))
    # ⚠️ Advertisements last, then by size: an engraving in a shoe
    # advertisement is a hole the same as a strip, and on the 1919 Georgian
    # two of them outrank the strip by area. The framed crop's own OCR words
    # say "shoes", "$7", "values"; a strip's say nothing of the kind. Ranked
    # behind, never dropped: the model still decides, this only decides
    # what it looks at first.
    ranked = []
    for area, page, c, pi, box in found:
        band = pi.from_ocr(box)
        clear = clear_share(pi, band)
        if clear > TYPE_CLEAR_MAX:
            log(f"  picture p{page.seq}: lines of type, not looked at ({clear:.0%} of rows clear)")
            continue
        fbox = frame(pi, c, box)
        ad = len(clips.ad_markers(clips.ocr_text(nameplate.words_in(c["words"], fbox))))
        ranked.append((round(clear, 2), ad, -area, page, c, pi, fbox))
    ranked.sort(key=lambda t: (t[0], t[1], t[2]))
    kinds_seen = []
    for clear, ad, _, page, c, pi, fbox in ranked[:MODEL_CALLS_PER_ISSUE]:
        try:
            image_box, data = clips._fetch(page, fbox, width=CROP_WIDTH)
        except (ValueError, ghn_api.FetchError) as e:
            log(f"  picture p{page.seq}: crop failed ({e})")
            continue
        r = classify(data, date[:4], log=log)
        if r is None:
            log(f"  picture p{page.seq}: the model gave no reading")
            continue
        if r["kind"] not in KINDS_POSTED:
            kinds_seen.append(f"p{page.seq} {r['kind']}")
            log(f"  picture p{page.seq}: {r['kind']}, not a cartoon")
            continue
        inside = nameplate.words_in(c["words"], fbox)
        verdict, page_hits = clips._verdict("cartoon", lccn, date, inside, c["words"], True)
        read = " ".join(t for t in (r["title"], r["words"], r["picture"]) if t)
        hits = clips.vocabulary_hits(read)
        if hits:
            verdict = clips._review(verdict, f"the model's reading of the cartoon carries {sorted(hits)}")
        if r["caricature"]:
            verdict = clips._review(verdict, "the model reads the drawing as racial or ethnic caricature")
        words = read
        res = clips._result("cartoon", page, meta, date, ed, fbox, image_box, data, verdict,
                            page_hits, curl(words), True,
                            {"kind": r["kind"], "picture": r["picture"], "title": r["title"],
                             "printed": r["words"], "caricature": r["caricature"]})
        res["alt"] = compose_alt(meta, date, page.seq, r)
        return res
    if kinds_seen:
        raise npc.Refused(f"pictures found but none a cartoon: {', '.join(kinds_seen)}")
    raise npc.Refused("no picture-sized hole in the OCR on any page looked at")
