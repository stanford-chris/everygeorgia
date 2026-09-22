#!/usr/bin/env python3
"""
rules.py -- the printed rule grid of a newspaper page, read from its pixels,
and the snapping of an OCR-derived box to the cell of that grid it sits in.

Why this exists. lanes.py builds candidate crops from OCR word boxes, and on
11 September 2026 those were drawn on three pages and looked at: the headline
boxes straddled columns and chained sideways into advertisements, the ad
boxes cut through their own borders, and on a small-town weekly whose front
page is all advertising the "headline" candidates were ads in display type.
lanes.py said as much in its own docstring ("position is a proxy and not a
classifier") and warned that its grid must never be used to ship a crop. What
separates one item from the next on a printed page is not the OCR: it is the
RULES, the vertical lines between columns and the horizontal lines between
items, and the borders around boxed advertisements. They are ink, so they are
in the image, and this reads them.

Everything is measured on ONE fetch of the whole page at PAGE_WIDTH, cached
like every other fetch here, and expressed as fractions of the page so no
constant is a pixel count. ⚠️ A rule is a dark run that is LONG and THIN: a
column rule runs at least MIN_VRULE of the page height in one pixel column
(with small breaks allowed, since microfilm drops pixels), a horizontal rule
spans at least MIN_HRULE of the span it is measured over. Letters are neither.

⚠️ THE SNAP GOES OUTWARD TO THE NEAREST RULE OR PAPER, NEVER ACROSS ONE. An
OCR box is roughly right and its edges cut ink; the cell it belongs to is
bounded by the nearest column rule on each side that actually spans it, and
by the nearest horizontal rule or clear gap above and below. A box that
straddles a column rule -- two columns' worth of words that the OCR chained
together -- is shrunk to the column holding its centre rather than grown to
both, because the words on the other side were never part of the item.
"""
import io
from bisect import bisect_left, bisect_right

PAGE_WIDTH = 1400        # the page image every measurement here is made on
INK_SHARE = 0.40         # a pixel is ink this share of the way from paper to
                         # the page's 5th-percentile pixel (nameplate_crop's
                         # rule, for the same washed-out-scan reason)
INK_MIN = 25
MIN_VRULE = 0.12         # a column rule spans at least this of the page height
VRULE_BREAK = 0.004      # ...allowing breaks up to this of the page height
MIN_HRULE = 0.80         # a horizontal rule spans this share of the cell width
HRULE_MIN_DARK = 0.45    # ...as a row whose dark share is at least this
                         # (0.60 walked straight through the broken rule
                         # between two advertisements on the Schley County
                         # Enterprise of 3 November 1887 and shipped both)
GAP_FRAC = 0.004         # a clear gap is this of the page height, in a run
CLEAR_MARGIN = 0.02      # a row/column is clear when its dark share is within
                         # this of the region's own floor
MAX_CELL_FRAC = 0.35     # a cell deeper than this is not one item (lanes.py's
                         # runaway-deck bound, kept)
MIN_CELL_W = 0.05        # narrower than this of the page is a sliver, not a
                         # cell (0.08 refused every column of an eight-column
                         # page: the Savannah Morning News runs 7% columns)
MIN_SPAN = 0.06          # column gutters are measured over at least this of
                         # the page height, so word spaces cannot line up
EDGE_DARK = 0.55         # a column dark down most of the page is film edge
PAPER_RUN = 0.002        # paper mode: an edge ends at this much clear paper
                         # beyond the OCR edge (2-3px at 1400). ⚠️ 0.006 asked
                         # for more paper than the Macon Telegraph's gutters
                         # hold and refused every headline on the page.
GUTTER_CROSSED = 0.08    # a gutter is crossed on an item's rows when even its
                         # clearest column is this dark there
RULE_DARK = 0.45         # an interior column at least this dark down the whole
                         # page is a printed column rule, and a boundary
GUTTER_DARK = 0.10       # a column at most this dark down the whole page is
                         # a gutter: a headline or an advertisement crossing
                         # it adds a few percent, a column of text adds forty

BORDER_BREAK = 0.02      # border_box(): an ornamental border is a chain of
                         # ornaments with paper between; breaks up to this
                         # of the page height are followed (the daisy
                         # border on the Douglas Enterprise of 13 July 1907
                         # has gaps up to 36 px of 2162, 0.017)
BORDER_INK = 0.20        # ...a row of the 5-px border strip is inked at
                         # this dark share: one pixel, so a hairline border
                         # counts and so does a dotted one (the Carlisle
                         # box's 2-px dots read 0.29 of a 7-px strip and
                         # failed at 0.30). A column of type passes too and
                         # is thrown out by BORDER_FILL below
BORDER_SNAP = 0.03       # ...a full-width rule this close to where the
                         # side borders end is the box's own edge
SEAM_MIN = 0.006         # ...a paper band this deep across the width,
                         # between two full-width rules, is the seam
                         # between two stacked boxes (measured 25 px
                         # between the Ever Crease box and the Tanner box,
                         # 0.012; a double hairline is 2-4 px apart)
BORDER_PAPER = 0.05      # ...a row is paper at this dark share or less
BORDER_MAX_W = 0.02      # ...a side border's ink is at most this of the page
                         # wide (28 px; borders measured 7-20, columns of
                         # type mistaken for one 90-173)
BORDER_MARGIN = 0.12     # ...and within BORDER_MARGIN_W of it, inside or
BORDER_MARGIN_W = 0.005  # outside, some column is at most this dark (paper:
                         # a box's inner margin or the gutter beside it)
BORDER_FILL = 0.40       # ...a side border's darkest single pixel column is
                         # at least this inked over the box's rows (the
                         # four borders on the Douglas page 0.44-0.83, the
                         # nearest stem or text column 0.28)
HRULE_SPAN = 0.38        # ...a full-width rule's best row runs at least this
                         # of the width between the sides in one stroke
                         # (rules and borders 0.45-1.00, the Carlisle dotted
                         # border 0.41, body text 0.25 and under; see
                         # row_span. Display type runs further and is
                         # excluded by thickness instead)
HRULE_BREAK = 0.0045     # ...bridging breaks up to this of the page width
                         # (6 px: the rule under "Douglas, Georgia." is
                         # broken into 4-5 px gaps where it crosses the
                         # column and reads 0.39 at 4 px, 0.76 at 6)
HRULE_MIN_SHARE = 0.20   # ...a row at least this dark is part of a band
HRULE_REACH = 0.02       # ...and the rule's row carries ink within this of
                         # the page width of BOTH sides: a rule under one
                         # column of a two-column window is long enough to
                         # pass the span test (the Peterson bank's rule
                         # ran 0.48 of a window it filled half of) and
                         # touches one side only
RULE_THICK = 1.40        # ...and a band is a rule only if it is at most this
                         # of the text height tall: display type (1.6 text
                         # heights and up, clips.is_display) runs far enough
                         # to pass the span test; the thickest border on
                         # the Douglas page, the Greek key, is 19 rows to a
                         # 14.2-px text height, 1.34
MAX_BOX_FRAC = 0.60      # ...a box deeper than this is a page border
CORNER_TOUCH = 3         # ...a top or bottom rule that continues past a side
CORNER_EXT = 0.03        # for this many contiguous pixels and CORNER_SHARE
CORNER_SHARE = 0.60      # of the next CORNER_EXT of the page width makes
                         # that side an interior rule, not a corner
CROSS_EXT = 0.008        # ...and a rule crosses an interior column when
                         # CORNER_SHARE of the pixels within this of the
                         # page width on EACH side of it are ink (11 px:
                         # short, so that the gutter beside another box's
                         # border reads as paper and an ornament chain's
                         # gaps do not)
CORNER_GAP = 0.003       # ...the contiguous run may start this far past the
                         # side (4 px: the page rule on the Savannah Morning
                         # News of 14 February 1873 stops 4 px short of the
                         # column rule it runs up to; the nearest two boxes
                         # measured, Ever Crease and Carlisle, are 6 apart)
CORNER_SKEW = 0.003      # ...looked for this many rows of the page height
                         # either side of the rule's band, since a rule on
                         # a skewed scan drifts a few rows across the page
BOX_MIN_VRULE = 0.04     # ...a side border is a vrule at least this of the
                         # page tall, under MIN_VRULE (0.12) because a boxed
                         # advertisement is shorter than a column: the Ever
                         # Crease box on the same page is 0.097 tall, and at
                         # 0.12 its own border was never a candidate, so the
                         # box found for it spanned the Harrelson box beside
                         # it as well


class PageInk:
    """The page as a small grayscale image plus its ink threshold."""

    def __init__(self, page, width=PAGE_WIDTH):
        from PIL import Image
        self.page = page
        data = page.fetch_crop((0, 0, page.image_w, page.image_h), width)
        self.im = Image.open(io.BytesIO(data)).convert("L")
        self.w, self.h = self.im.size
        self.px = self.im.load()
        self.scale = self.w / float(page.image_w)        # small px per image px
        sample = sorted(self.px[x, y] for y in range(0, self.h, 4) for x in range(0, self.w, 4))
        paper, dark = sample[len(sample) // 2], sample[len(sample) // 20]
        self.thresh = paper - max(INK_MIN, int(INK_SHARE * (paper - dark)))
        self._col_dark = None
        self._vrules = None

    # ---- coordinate helpers: OCR space -> small image space ----------------
    def from_ocr(self, box):
        x, y, w, h = self.page.to_image(box)
        s = self.scale
        return (int(x * s), int(y * s), max(1, int(w * s)), max(1, int(h * s)))

    def y_small(self, y_ocr):
        """One OCR-space y -> small-image row. A one-unit box through
        from_ocr() rounds to nothing (an OCR unit is a third of an image
        pixel on some pages), so rows are mapped directly."""
        return int(y_ocr * self.page.scale * self.scale)

    def to_ocr(self, sbox):
        """small image box -> OCR box, via the page's own scale."""
        s = self.scale
        ps = self.page.scale                                # image px per OCR unit
        x, y, w, h = sbox
        return (int(round(x / s / ps)), int(round(y / s / ps)),
                int(round(w / s / ps)), int(round(h / s / ps)))

    # ---- profiles ----------------------------------------------------------
    def is_ink(self, x, y):
        return self.px[x, y] < self.thresh

    def col_dark(self):
        """Dark share of every pixel column over the whole page."""
        if self._col_dark is None:
            h = self.h
            self._col_dark = [sum(1 for y in range(0, h, 2) if self.is_ink(x, y)) / (h / 2.0)
                              for x in range(self.w)]
        return self._col_dark

    def row_dark(self, x0, x1, y0=0, y1=None):
        """Dark share of each row over columns [x0, x1)."""
        y1 = self.h if y1 is None else y1
        n = float(max(1, x1 - x0))
        return [sum(1 for x in range(x0, x1) if self.is_ink(x, y)) / n for y in range(y0, y1)]

    def col_dark_in(self, y0, y1, x0=0, x1=None):
        """Dark share of each column over rows [y0, y1)."""
        x1 = self.w if x1 is None else x1
        n = float(max(1, y1 - y0))
        return [sum(1 for y in range(y0, y1) if self.is_ink(x, y)) / n for x in range(x0, x1)]

    # ---- page-level gutters --------------------------------------------------
    def film_edges(self):
        """(left, right): the columns inside which the page's ink lives, the
        black film edge stripped from each side. ⚠️ Only the dark run
        CONTIGUOUS with the page edge is film. An interior column that is
        dark down the whole page is a printed rule, and treating it as film
        left the eight-column Savannah Morning News of 20 September 1872
        with no boundaries at all: a block spanned the page."""
        if getattr(self, "_film", None) is not None:
            return self._film
        cd = self.col_dark()
        l = 0
        while l < self.w and cd[l] > EDGE_DARK:
            l += 1
        r = self.w
        while r > l and cd[r - 1] > EDGE_DARK:
            r -= 1
        self._film = (l, r)
        return self._film

    def gutters(self):
        """Column boundaries as (x0, x1) runs in small-image pixels: runs of
        pixel columns that are paper down MOST of the page (the gutters),
        and interior columns that are ink down most of it (the rules).
        Measured over the whole page, where word spaces never line up but
        gutters and rules do.

        ⚠️ Not over the item's own rows. Measured over a few lines of an
        advertisement, the white space between its own words read as a
        gutter and three of three search-driven ad crops were cut on the
        right through their own lettering, 11 September 2026."""
        if getattr(self, "_gutters", None) is not None:
            return self._gutters
        cd = self.col_dark()
        fl, fr = self.film_edges()
        out, start, kind = [], None, None
        for x in range(fl, fr):
            k = "paper" if cd[x] <= GUTTER_DARK else ("rule" if cd[x] >= RULE_DARK else None)
            if k != kind:
                if start is not None and (kind == "rule" or x - start >= 2):
                    out.append((start, x))
                start, kind = (x, k) if k else (None, None)
        if start is not None and (kind == "rule" or fr - start >= 2):
            out.append((start, fr))
        self._gutters = out
        return self._gutters

    # ---- vertical rules -----------------------------------------------------
    def vrules(self, min_frac=MIN_VRULE, skip_dark=True):
        """Column rules as (x, y_top, y_bottom) in small-image pixels: pixel
        columns holding a dark run at least `min_frac` of the page tall,
        merged when adjacent. With `skip_dark`, a column dark down more
        than EDGE_DARK of the page is left out as film edge. Cached per
        (`min_frac`, `skip_dark`): border_box() asks with BOX_MIN_VRULE,
        since a boxed advertisement's own border is shorter than a column
        rule, and with skip_dark False, since two boxed ads stacked on the
        same margin share a border column dark down most of the page (the
        Tanner and Harrelson borders on the Douglas Enterprise of 13 July
        1907 read 0.51 together, a taller box from the 0.55 cut) and only
        a column touching the page edge is film -- film_edges() says which."""
        if self._vrules is None:
            self._vrules = {}
        key = (min_frac, skip_dark)
        if key in self._vrules:
            return self._vrules[key]
        brk = max(2, int(self.h * VRULE_BREAK))
        need = int(self.h * min_frac)
        cd = self.col_dark()
        found = []
        fl, fr = self.film_edges()
        for x in range(self.w):
            if skip_dark and cd[x] > EDGE_DARK:
                continue
            if not skip_dark and not fl <= x < fr:
                continue
            best, run, gap, start, cur_start = 0, 0, 0, 0, None
            bs = be = None
            for y in range(self.h):
                if self.is_ink(x, y):
                    if cur_start is None:
                        cur_start = y
                    run += 1
                    gap = 0
                else:
                    gap += 1
                    if cur_start is not None and gap > brk:
                        length = y - gap - cur_start
                        if length > best:
                            best, bs, be = length, cur_start, y - gap
                        cur_start, run = None, 0
            if cur_start is not None:
                length = self.h - gap - cur_start
                if length > best:
                    best, bs, be = length, cur_start, self.h - gap
            if best >= need:
                found.append((x, bs, be))
        # merge adjacent columns into one rule at their mean x
        merged = []
        for x, t, b in found:
            if merged and x - merged[-1][-1][0] <= 2:
                merged[-1].append((x, t, b))
            else:
                merged.append([(x, t, b)])
        self._vrules[key] = [(int(sum(c[0] for c in g) / len(g)),
                              min(c[1] for c in g), max(c[2] for c in g)) for g in merged]
        return self._vrules[key]

    def column_bounds(self, sbox, mode="column", pad_frac=0.08):
        """(x0, x1) for the item, from the box outward.

        mode "column": the nearest page-level gutter on each side that the
        item does NOT cross, judged over the item's own rows (a gutter an
        item crosses is dark on those rows: a multi-column advertisement or
        banner headline keeps going to the next one). The Macon Telegraph
        of 15 January 1897 has seven columns and not one printed rule
        between them, which is why gutters and not rules.

        mode "paper": keep an edge that already sits in paper, else walk to
        the first clear run (a headline whose OCR box is right)."""
        x, y, w, h = sbox
        y0, y1 = max(0, y), min(self.h, y + h)
        if mode == "column":
            span = int(self.h * MIN_SPAN)
            if y1 - y0 < span:
                mid = (y0 + y1) // 2
                y0, y1 = max(0, mid - span // 2), min(self.h, mid + span // 2)
            cols = self.col_dark_in(y0, y1)
            cd = self.col_dark()
            # ⚠️ Absolute, not relative to the window's own floor: on a dense
            # page the floor is itself a few percent and every gutter read
            # as crossed, so two advertisement crops came back as strips
            # across four columns of other people's advertisements. A rule
            # is crossed when the paper beside it is inked on these rows
            # (the rule itself is always dark), so it is judged on its
            # neighbours.
            def crossed(g):
                a, b = g
                if cd[a] >= RULE_DARK:
                    a, b = max(0, a - 2), min(self.w, b + 2)
                    sample = cols[a:g[0]] + cols[g[1]:b]
                    return bool(sample) and min(sample) > GUTTER_CROSSED
                return min(cols[a:b]) > GUTTER_CROSSED
            left = [g for g in self.gutters() if g[1] <= x and not crossed(g)]
            right = [g for g in self.gutters() if g[0] >= x + w and not crossed(g)]
            if not left and not right:
                # ⚠️ No boundary on either side is a page whose grid could not
                # be read, not an item the width of the page: the Savannah
                # Morning News of 13 January 1871 came back as a strip across
                # all of its advertisements.
                return None
            page_l, page_r = self.film_edges()
            x0 = left[-1][1] if left else page_l
            x1 = right[0][0] if right else page_r
            return (x0, x1) if x1 > x0 else None
        pad = int(self.w * pad_frac)
        lx, rx = max(0, x - pad), min(self.w, x + w + pad)
        cols = self.col_dark_in(y0, y1, lx, rx)
        n = len(cols)
        if n == 0:
            return None
        base = sorted(cols)[n // 10]
        clear = [c <= base + CLEAR_MARGIN for c in cols]

        # ⚠️ Always walk, never keep the OCR edge: a display word's OCR box
        # is narrower than its glyphs, and "MANY MINERS ARE ENTOMBE[D]" and
        # "[S]PEAKS APRIL 27" shipped with a letter cut off each side when a
        # clear-looking edge was kept. From the first clear column the walk
        # continues to a run of PAPER_RUN clear columns, then pads.
        el, er = x - lx, x + w - 1 - lx
        need = max(2, int(self.w * PAPER_RUN))
        def walk_out(start, step):
            i, run = start, 0
            while 0 <= i < n:
                run = run + 1 if clear[i] else 0
                if run >= need:
                    return i - step * (need - 1)
                i += step
            return None
        l = walk_out(el, -1)
        r_ = walk_out(er, 1)
        if l is None or r_ is None:
            return None
        pad = max(2, int(self.w * 0.004))
        return max(0, lx + l - pad), min(self.w, lx + r_ + 1 + pad)

    # ---- vertical extent ----------------------------------------------------
    def vertical_bounds(self, sbox, x0, x1, rules_only=False, keep_clear=False):
        """(y0, y1) for the item: from the box, out to the nearest horizontal
        rule or clear gap above and below, within [x0, x1). None if the item
        cannot be closed within MAX_CELL_FRAC of the page.

        ⚠️ `rules_only` walks to a RULE and ignores gaps, for advertisements:
        a display ad is mostly paper inside, and on the Schley County News of
        23 December 1897 the gap walk ended "POPULAR GOODS ... PURE DRUGS"
        at the white space before "TOILET ARTICLES", a third of the way
        through the same advertisement. What closes an ad is the rule under
        it, or its own border."""
        x, y, w, h = sbox
        cap = int(self.h * MAX_CELL_FRAC)
        top_lim, bot_lim = max(0, y + h - cap), min(self.h, y + cap)
        rows = self.row_dark(x0, x1, top_lim, bot_lim)
        off = top_lim
        base = sorted(rows)[len(rows) // 10] if rows else 0.0
        clear = [r <= base + CLEAR_MARGIN for r in rows]
        rule = [r >= HRULE_MIN_DARK for r in rows]
        gap = max(2, int(self.h * GAP_FRAC))

        def walk(start, step):
            # ⚠️ keep_clear: an edge already in paper stays where the OCR put
            # it. The headline lane's box is right by construction (its lines
            # come from the OCR), and walking to "the next gap" from a clear
            # edge cut "VIGOROUS TO BE PROTEST OF U. S. ON BRITAIN'S REFUSAL"
            # after its fourth line, because display lines are spaced wider
            # than the gap the walk was looking for.
            if keep_clear and 0 <= start < len(rows) and clear[start] and not rule[start]:
                return start
            run = 0
            i = start
            while 0 <= i < len(rows):
                if rule[i]:
                    return i - step * 1            # stop just before the rule
                if not rules_only:
                    run = run + 1 if clear[i] else 0
                    if run >= gap:
                        return i - step * (gap - 1)    # the near edge of the gap
                i += step
            return None

        yt = walk(max(0, y - off), -1)
        yb = walk(min(len(rows) - 1, y + h - off), 1)
        if yt is None or yb is None:
            return None
        return off + yt, off + yb + 1


    # ---- boxed items --------------------------------------------------------
    def ink_rows(self):
        """Per row, a prefix count of ink pixels across the row, so the dark
        share of any [x0, x1) on any row is two lookups. Built once, for
        border_box(), whose walks ask about thousands of row spans."""
        if getattr(self, "_ink_rows", None) is None:
            from array import array
            rows = []
            for y in range(self.h):
                acc = array("I", [0]) * (self.w + 1)
                n = 0
                for x, p in enumerate(self.im.crop((0, y, self.w, y + 1)).getdata()):
                    if p < self.thresh:
                        n += 1
                    acc[x + 1] = n
                rows.append(acc)
            self._ink_rows = rows
        return self._ink_rows

    def row_share(self, y, x0, x1):
        acc = self.ink_rows()[y]
        return (acc[x1] - acc[x0]) / float(max(1, x1 - x0))

    def row_span(self, y, x0, x1, brk):
        """The longest run of ink along row `y` over [x0, x1), breaks up to
        `brk` pixels bridged, as a share of the width. A printed rule is one
        stroke; a line of type is many short ones. Measured on the Douglas
        Enterprise of 13 July 1907: the best row of every real rule or
        border reads 0.45-0.98 (a dotted border 0.40), every line of type
        0.19 or under, including the 0.44-dark display line "We are
        headquarters for anything you want" that a bare darkness test
        reads as a rule."""
        best = cur = gap = 0
        for x in range(x0, x1):
            if self.is_ink(x, y):
                cur += gap + 1
                gap = 0
                if cur > best:
                    best = cur
            else:
                gap += 1
                if gap > brk:
                    cur = gap = 0
        return best / float(max(1, x1 - x0))

    def border_box(self, sbox, text_h, words):
        """The printed BORDER enclosing `sbox` (small-image x, y, w, h), as
        (x0, y0, x1, y1) in small-image pixels, the outer edges of the
        border ink; None when no closed box holds the seed. `text_h` is
        the page's median text height in small-image pixels and `words`
        the OCR's word boxes as (x, y, w, h, text) in the same pixels,
        both from the OCR the caller already holds. A display
        advertisement set inside a rule or an ornamental border is one
        item however wide or deep it is, and the border is the printer's
        own statement of where it ends -- so a caller that finds one crops
        to it and lets no column gutter or size cap argue.

        Built 22 September 2026, his instruction on the Tanner Mercantile
        advertisement (Douglas Enterprise, 13 July 1907, page 2): a boxed
        ad spanning the whole page width and 40 percent of its height
        shipped as one column of it, capped at clips.MAX_BLOCK_FRAC, with
        the left edge cutting into the B of "Best". Nothing that closed
        that crop was real: the sides were 2-px "gutters" (word gaps lined
        up down a page that is mostly display ads), the bottom was the
        cap, and none of the ad's four printed rules was seen, each being
        3-4 px thick against clips.RULE_MAX_RUN of 2.

        How the box is read; every constant was set on that page and the
        four other boxed items on it (see the test fixture):

        1. SIDE candidates are vrules(BOX_MIN_VRULE): columns holding a
           dark run at least that share of the page tall, a lower floor
           than a column rule's because a boxed ad is shorter than a
           column. The seed's rows must fall in a run of the candidate's
           7-px strip, breaks up to BORDER_BREAK bridged, since an
           ornamental border is a chain of ornaments with paper between
           (the daisy border here has gaps up to 36 px).

        2. TOP and BOTTOM are full-width rules, walked to from the seed.
           A rule is a band of rows at least HRULE_MIN_SHARE dark that is
           THIN, at most RULE_THICK of the text height, and whose best row
           runs at least HRULE_SPAN of the width between the sides in one
           stroke (row_span, breaks up to HRULE_BREAK bridged), carrying
           ink within HRULE_REACH of both sides so a rule under one
           column of a wider window does not count, and one the OCR read
           no word on. ⚠️ The OCR test is the decisive one for body text,
           added on the Atlanta Georgian of 4 December 1908: in a
           one-column window its justified 6.7-px type has word gaps
           under the 6-px break tolerance, and a line of it bridged into
           a "rule" 0.40 of the width. No tolerance fits both that page
           and the Douglas Enterprise's broken rules; the OCR does,
           reading 7-9 words on every line of type measured and none on
           any of the seven real rules and borders. The two pixel tests
           still stand because display type is what the OCR misses, and
           type fails them one at a time: a line of body text is thin
           enough but its best row runs 0.25 or under (word gaps); a
           display heading runs 0.35 ("Notice to the Public", bridged at
           any tolerance) but is 1.6 text heights tall or more, where the
           Greek-key border on the same page, the thickest here, is 1.34.
           ⚠️ A bare darkness test cannot do this -- the faint rule
           under "Douglas, Georgia." reads 0.47 dark and the display line
           "We are headquarters" 0.44 -- and where the side borders END
           cannot either: at the break tolerance an ornamental border
           needs, this ad's right border merges with the right border of
           the Carlisle box stacked 26 px above it.

        3. ⚠️ An ad's OWN interior rules are full-width too (the rule under
           "Douglas, Georgia." spans the whole box), so a full-width rule
           closes the box only if the side borders end there (within
           BORDER_SNAP of the strip run's end) or what lies beyond it is
           a SEAM: paper at least SEAM_MIN deep across the width, then
           another full-width rule, the next box's own border. A double
           hairline is 2-4 px apart, under SEAM_MIN. The walk passes a
           rule that does neither.

        4. Each side is then VERIFIED over the box's rows: its darkest
           single pixel column must be at least BORDER_FILL inked, which
           tells a border from a display letter's stem or a column of
           type on a sparse page (0.44-0.83 for the four borders on the
           Douglas page, 0.28 or under for everything else there). ⚠️ On
           a dense page a column of type is as dark as a border (the
           Savannah Morning News of 13 January 1871 closed a "box" whose
           left side ran through the middle of an advertisement's text),
           so the side's ink must also be NARROW -- its run of inked
           columns at most BORDER_MAX_W, where every real border measured
           7-20 px and the three false sides 90-173 -- and have PAPER
           beside it within BORDER_MARGIN_W on one side or the other, the
           box's inner margin or the gutter outside.

        5. Pairs are tried from the innermost outward and the FIRST closed
           box wins. ⚠️ Preferring the outermost was tried and measured
           wrong: the Ever Crease and Carlisle boxes on this page sit 6 px
           apart, their tops within a rule of each other, and the outer
           pair closed as one box holding both. Adjacent boxed ads are
           what an advertising page is made of. What innermost-first
           costs is a seed in one column of a boxed ad whose interior
           column rule is solid (the Tanner one is a faint hairline and
           fails step 4): the innermost pair closes that column's CELL.
           So a closed pair is refused when BOTH its top rule and its
           bottom rule RUN THROUGH a side -- contiguous ink for
           CORNER_TOUCH pixels past the side's outer edge and CORNER_SHARE
           of the next CORNER_EXT -- since a box's rules stop at its
           corners and an interior rule's neighbours cross it; the next
           pair out then closes the whole box. Both, not either: a box
           can share its top rule with the box beside it (the Augusta
           Cotton Exchange, Augusta Herald, 6 October 1927) and still be
           a box. Contiguity is what keeps the 6-px neighbour from
           reading as a continuation. A pair is also refused when the
           window holds ANOTHER BOX'S BORDER: a border-dark column, paper
           beside it, that the top rule or the bottom rule stops at
           rather than crosses (CROSS_EXT pixels of ink on each side of
           it, on some row of the rule's band). The Athens Banner of
           19 October 1913 closed a column of type together with the
           boxed "Georgia State Fair" advertisement beside it, because a
           boxed header in that column carried rules aligned with the
           advertisement's own; the advertisement's left border, which
           those rules stop at, is what says the window is two items.
           This box's own interior column rule is crossed by both rules
           and passes; the older test, two dark columns with a paper
           band between them, saw nothing here. Nor may a top or bottom
           rule run on past BOTH sides: that is the page's rule or a
           section's, wider than the pair, and the sides are column rules
           with a cell of the page between them -- the Savannah Morning
           News of 14 February 1873 closed one a column wide and half
           the page deep under the page's own rule, and the Vidalia
           Advance of 10 August 1921 three columns of news under its
           dateline. ⚠️ Requiring a side to be the box's OWN border (its
           run starting at the top rule and ending at the bottom) was
           tried for the same cases and measured wrong: a column-width
           boxed ad on a 1920s page borrows the column rules as its sides
           (the Augusta Cotton Exchange on the Twin City Citizen of
           17 September 1927, stacked over a bank's box in the same
           column), and every such ad was refused. The older seam test,
           two dark columns with a paper band at least SEAM_MIN wide
           between them, is gone: it saw nothing on the Athens page and
           the stops-at test above covers what it was for.

        6. A box deeper than MAX_BOX_FRAC is refused: a border round a
           whole page is not an advertisement."""
        x, y, w, h = (int(v) for v in sbox)
        sy0, sy1 = max(0, y), min(self.h, y + h)
        if sy1 <= sy0:
            return None
        brk = max(2, int(self.h * BORDER_BREAK))
        snap_px = max(2, int(self.h * BORDER_SNAP))
        seam = max(2, int(self.h * SEAM_MIN))
        hbrk = max(2, int(self.w * HRULE_BREAK))
        thick = max(2, int(RULE_THICK * text_h))
        reach = max(4, int(self.w * HRULE_REACH))
        # OCR word centres, for the "no word on a rule" test; only real
        # tokens, since an ornament can OCR as a stray mark
        centres = [(wx + ww / 2.0, wy + wh / 2.0) for wx, wy, ww, wh, t in words
                   if sum(ch.isalpha() for ch in t) >= 3]
        centres.sort(key=lambda p: p[1])
        centre_ys = [p[1] for p in centres]
        cands = self.vrules(BOX_MIN_VRULE, skip_dark=False)
        lefts = sorted((r[0] for r in cands if r[0] < x), reverse=True)
        rights = sorted(r[0] for r in cands if r[0] >= x + w)

        def side_run(rx):
            """The inked run of a 7-px border strip through the seed's rows,
            breaks up to `brk` bridged: (top, bottom) or None."""
            a, b = max(0, rx - 2), min(self.w, rx + 3)
            dark = [self.row_share(yy, a, b) for yy in range(self.h)]
            if not any(d >= BORDER_INK for d in dark[sy0:sy1]):
                return None
            t, gap = sy0, 0
            while t > 0:
                gap = 0 if dark[t - 1] >= BORDER_INK else gap + 1
                if gap > brk:
                    break
                t -= 1
            t += gap
            bt, gap = sy1 - 1, 0
            while bt < self.h - 1:
                gap = 0 if dark[bt + 1] >= BORDER_INK else gap + 1
                if gap > brk:
                    break
                bt += 1
            bt -= gap
            return t, bt

        left_runs = [(lx, side_run(lx)) for lx in lefts]
        left_runs = [(lx, r) for lx, r in left_runs if r]
        right_runs = [(rx, side_run(rx)) for rx in rights]
        right_runs = [(rx, r) for rx, r in right_runs if r]
        if not left_runs or not right_runs:
            return None

        rule_cache = {}

        def is_rule(yy, xa, xb):
            key = (yy, xa, xb)
            if key not in rule_cache:
                ok = False
                if self.row_share(yy, xa, xb) >= HRULE_MIN_SHARE:
                    # the band of dark rows this row sits in must be thin
                    a = yy
                    while a > 0 and self.row_share(a - 1, xa, xb) >= HRULE_MIN_SHARE:
                        a -= 1
                    b = yy
                    while b < self.h - 1 and self.row_share(b + 1, xa, xb) >= HRULE_MIN_SHARE:
                        b += 1
                    # ⚠️ Reach is judged over the whole band, not this row:
                    # the page is skewed, and the Tanner top border's ink
                    # sits at the left end on rows 1135-1137 and at the
                    # right end on rows 1134 and 1139, never on one row
                    ok = (b - a + 1 <= thick
                          and not any(xa <= centres[i][0] < xb
                                      for i in range(bisect_left(centre_ys, a),
                                                     bisect_right(centre_ys, b)))
                          and self.row_span(yy, xa, xb, hbrk) >= HRULE_SPAN
                          and max(self.row_share(r, xa, xa + reach) for r in range(a, b + 1)) * reach >= 3
                          and max(self.row_share(r, xb - reach, xb) for r in range(a, b + 1)) * reach >= 3)
                rule_cache[key] = ok
            return rule_cache[key]

        def edge(start, step, run_end, xa, xb):
            """From `start` in `step`'s direction to the first full-width
            rule that closes the box (step 3): (far row, near row) of that
            rule's own run of rule rows, or None."""
            i = start
            while 0 <= i < self.h:
                if not is_rule(i, xa, xb):
                    i += step
                    continue
                j = i
                while 0 <= j + step < self.h and is_rule(j + step, xa, xb):
                    j += step
                beyond = j + step
                closes = abs(j - run_end) <= snap_px
                if not closes:
                    # count paper rows up to the next band; a fringe row
                    # under a rule (0.15 dark on the row below the Carlisle
                    # box's bottom border) is neither and is walked past
                    k, n = beyond, 0
                    while 0 <= k < self.h and self.row_share(k, xa, xb) < HRULE_MIN_SHARE:
                        if self.row_share(k, xa, xb) <= BORDER_PAPER:
                            n += 1
                        k += step
                    # the next box's border is a band; its first row need
                    # not be its best, so any row within a rule's thickness
                    # of the paper's end counts
                    closes = n >= seam and any(is_rule(kk, xa, xb)
                                               for kk in range(k, k + step * thick, step)
                                               if 0 <= kk < self.h)
                if closes:
                    return j, i
                i = beyond
            return None

        ext = max(6, int(self.w * CORNER_EXT))
        near = max(4, int(self.w * CROSS_EXT))

        def crosses(rows, x0, x1):
            """Does a rule in `rows` cross the column run [x0, x1]: at
            least CORNER_SHARE ink in the CROSS_EXT pixels on EACH side
            of it? A box's border inside a wider window is where the
            window's rules stop; this box's own interior column rule is
            what they run across. The window is short, and judged on
            share alone, so an ornamental border's own gaps do not read
            as a stop (see the docstring's step 5)."""
            for yy in rows:
                l = [x0 - k for k in range(1, near + 1) if 0 <= x0 - k]
                r = [x1 + k for k in range(1, near + 1) if x1 + k < self.w]
                if l and r and \
                   sum(1 for xx in l if self.is_ink(xx, yy)) >= CORNER_SHARE * len(l) and \
                   sum(1 for xx in r if self.is_ink(xx, yy)) >= CORNER_SHARE * len(r):
                    return True
            return False

        def runs_through(rows, x_from, step):
            """Does a rule in `rows` continue past `x_from` in `step`'s
            direction: contiguous ink for the first CORNER_TOUCH pixels
            and at least CORNER_SHARE of the next `ext`? A box's top and
            bottom rules stop at its corners; an interior column rule's
            neighbours run through it (step 5). `rows` is widened by
            CORNER_SKEW either way: the Vidalia Advance of 10 August 1921
            is scanned askew and its dateline rule sits two rows lower
            at the column rule than over the window's own best rows."""
            skew = max(2, int(self.h * CORNER_SKEW))
            gap = max(1, int(self.w * CORNER_GAP))
            for yy in range(max(0, min(rows) - skew), min(self.h, max(rows) + skew + 1)):
                xs = [x_from + step * k for k in range(1, ext + 1)]
                xs = [xx for xx in xs if 0 <= xx < self.w]
                if len(xs) < CORNER_TOUCH + gap:
                    continue
                ink = [self.is_ink(xx, yy) for xx in xs]
                touch = any(all(ink[k:k + CORNER_TOUCH]) for k in range(gap + 1))
                if touch and sum(ink) >= CORNER_SHARE * len(xs):
                    return True
            return False

        for lx, lr in left_runs:
            for rx, rr in right_runs:
                if rx - lx < self.w * MIN_CELL_W:
                    continue
                run_t, run_b = max(lr[0], rr[0]), min(lr[1], rr[1])
                if run_t > sy0 or run_b < sy1 - 1:
                    continue
                xa, xb = lx + 4, rx - 3
                if xb - xa < 8:
                    continue
                top_edge = edge(sy0 - 1, -1, run_t, xa, xb)
                if top_edge is None:
                    continue
                bot_edge = edge(sy1, 1, run_b, xa, xb)
                if bot_edge is None:
                    continue
                top, bot = top_edge[0], bot_edge[0]
                if bot - top > self.h * MAX_BOX_FRAC:
                    continue
                top_rows = range(top, top_edge[1] + 1)
                bot_rows = range(bot_edge[1], bot + 1)
                cd = self.col_dark_in(top, bot + 1)
                if max(cd[max(0, lx - 2):lx + 3]) < BORDER_FILL or \
                   max(cd[max(0, rx - 2):rx + 3]) < BORDER_FILL:
                    continue
                # the sides' own ink, walked outward to paper for the box
                # and inward for the seam scan below
                ox0 = lx
                while ox0 > 0 and cd[ox0 - 1] >= BORDER_INK:
                    ox0 -= 1
                ox1 = rx
                while ox1 < self.w - 1 and cd[ox1 + 1] >= BORDER_INK:
                    ox1 += 1
                ix0 = lx
                while ix0 < rx and cd[ix0 + 1] >= BORDER_INK:
                    ix0 += 1
                ix1 = rx
                while ix1 > lx and cd[ix1 - 1] >= BORDER_INK:
                    ix1 -= 1
                # a corner, not a T-junction: a side that BOTH the top rule
                # and the bottom rule run on past is an interior rule
                # (step 5). One of them may: the Augusta Cotton Exchange
                # box on the Augusta Herald of 6 October 1927 shares its
                # top rule with the box beside it, and its bottom stops
                # at its corner
                if any(runs_through(top_rows, ox, step) and runs_through(bot_rows, ox, step)
                       for ox, step in ((ox0, -1), (ox1, 1))):
                    continue
                # and no rule wider than the pair: a top or bottom rule that
                # runs on past BOTH sides is the page's or a section's,
                # and the sides are column rules with a cell between them
                if any(runs_through(rows, ox0, -1) and runs_through(rows, ox1, 1)
                       for rows in (top_rows, bot_rows)):
                    continue
                # a border is a narrow stroke with paper beside it; a
                # column of dense type is as dark and runs on for a
                # hundred columns (step 4)
                bw = max(2, int(self.w * BORDER_MAX_W))
                if ix0 - ox0 + 1 > bw or ox1 - ix1 + 1 > bw:
                    continue

                def paper_beside(a, b):
                    seg = cd[max(0, a):max(0, min(self.w, b))]
                    return bool(seg) and min(seg) <= BORDER_MARGIN

                m = max(3, int(self.w * BORDER_MARGIN_W))
                if not (paper_beside(ox0 - m, ox0) or paper_beside(ix0 + 1, ix0 + 1 + m)):
                    continue
                if not (paper_beside(ox1 + 1, ox1 + 1 + m) or paper_beside(ix1 - m, ix1)):
                    continue
                # another box's border inside the window: a border-dark
                # column with paper beside it that the top rule or the
                # bottom rule STOPS AT rather than crosses (step 5); an
                # interior column rule of this box is crossed by both
                seamed = False
                xx = ix0 + 2
                while xx < ix1 - 1:
                    if cd[xx] >= BORDER_FILL:
                        e = xx
                        while e + 1 < ix1 - 1 and cd[e + 1] >= BORDER_INK:
                            e += 1
                        if e - xx + 1 <= bw and \
                           paper_beside(xx - m, xx) and paper_beside(e + 1, e + 1 + m) and \
                           not all(crosses(rows, xx, e) for rows in (top_rows, bot_rows)):
                            seamed = True
                            break
                        xx = e + 1
                    else:
                        xx += 1
                if seamed:
                    continue
                return (ox0, top, ox1 + 1, bot + 1)
        return None


def snap(pi, box_ocr, mode="column", rules_only=False, include_border=False, vmode=None):
    """Snap an OCR-space box to its cell: (x, y, w, h) in OCR space, or None
    when the cell cannot be closed. The cell is at least MIN_CELL_W wide.
    With `include_border` the printed rules around the cell are kept inside
    the crop (an advertisement's border is part of the advertisement)."""
    sbox = pi.from_ocr(box_ocr)
    cb = pi.column_bounds(sbox, mode=mode)
    if cb is None:
        return None
    x0, x1 = cb
    if x1 - x0 < pi.w * MIN_CELL_W:
        return None
    vb = pi.vertical_bounds(sbox, x0, x1, rules_only=rules_only,
                            keep_clear=(vmode or mode) == "paper")
    if vb is None:
        return None
    y0, y1 = vb
    if y1 - y0 <= 0 or (y1 - y0) > pi.h * MAX_CELL_FRAC:
        return None
    if include_border:
        m = max(3, int(pi.w * 0.006))
        x0, x1 = max(0, x0 - m), min(pi.w, x1 + m)
        y0, y1 = max(0, y0 - m), min(pi.h, y1 + m)
    return pi.to_ocr((x0, y0, x1 - x0, y1 - y0))
