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

import ghn_api

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
GUTTER_CROSSED = 0.08    # a gutter is crossed on an item's rows when even its
                         # clearest column is this dark there
RULE_DARK = 0.45         # an interior column at least this dark down the whole
                         # page is a printed column rule, and a boundary
GUTTER_DARK = 0.10       # a column at most this dark down the whole page is
                         # a gutter: a headline or an advertisement crossing
                         # it adds a few percent, a column of text adds forty


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
    def vrules(self):
        """Column rules as (x, y_top, y_bottom) in small-image pixels: pixel
        columns holding a dark run at least MIN_VRULE of the page tall,
        merged when adjacent. The film edges are excluded by their darkness."""
        if self._vrules is not None:
            return self._vrules
        brk = max(2, int(self.h * VRULE_BREAK))
        need = int(self.h * MIN_VRULE)
        cd = self.col_dark()
        found = []
        for x in range(self.w):
            if cd[x] > EDGE_DARK:
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
        self._vrules = [(int(sum(c[0] for c in g) / len(g)),
                         min(c[1] for c in g), max(c[2] for c in g)) for g in merged]
        return self._vrules

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
        need = 2

        def walk(start, step):
            i, run = start, 0
            while 0 <= i < n:
                run = run + 1 if clear[i] else 0
                if run >= need:
                    return i - step * (need - 1)
                i += step
            return None

        el, er = x - lx, x + w - 1 - lx
        l = el if (0 <= el < n and clear[el]) else walk(el, -1)
        r_ = er if (0 <= er < n and clear[er]) else walk(er, 1)
        if l is None or r_ is None:
            return None
        return lx + l, lx + r_ + 1

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


def boxed(pi, sbox, reach=0.006, need=0.75):
    """Is the (small-image) box enclosed by printed rules on all four sides?
    Each side is searched within `reach` of the page width just outside the
    box for a line dark along at least `need` of the box's length. A cell
    bounded by two column rules and two item rules passes as readily as a
    bordered advertisement, which is the point: both are an item the page
    itself has closed off."""
    x, y, w, h = sbox
    r = max(2, int(pi.w * reach))
    def vline(xs):
        best = 0
        for xx in xs:
            if 0 <= xx < pi.w:
                d = sum(1 for yy in range(y, y + h) if 0 <= yy < pi.h and pi.is_ink(xx, yy)) / float(max(1, h))
                best = max(best, d)
        return best >= need
    def hline(ys):
        best = 0
        for yy in ys:
            if 0 <= yy < pi.h:
                d = sum(1 for xx in range(x, x + w) if 0 <= xx < pi.w and pi.is_ink(xx, yy)) / float(max(1, w))
                best = max(best, d)
        return best >= need
    return (vline(range(x - r, x + 2)) and vline(range(x + w - 2, x + w + r + 1))
            and hline(range(y - r, y + 2)) and hline(range(y + h - 2, y + h + r + 1)))
