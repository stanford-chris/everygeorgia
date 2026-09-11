#!/usr/bin/env python3
"""
items.py -- candidate items for the headline and advertisement lanes: rows of
display type, split at column gaps, boxed with their subordinate lines and
snapped to the page's own grid by rules.py.

⚠️ lanes.py's geometries were measurement tools and said so. Drawn on real
pages on 11 September 2026 they chained every column's headline into one box
across the page, because rows_of() groups display words by their tops and a
line of six column headlines shares one top. The split here is at horizontal
gaps wider than the words are tall: on a page of columns that is the gutter,
and inside one headline it never happens.
"""
import lanes
import nameplate
import rules

SPLIT_GAP = 1.2          # a gap between two display words wider than this
                         # multiple of their height ends the item
DECK_MIN, DECK_GAP = lanes.DECK_MIN, lanes.DECK_GAP
MIN_REAL_TOKEN = lanes.MIN_REAL_TOKEN
HEAD_LO, HEAD_HI = 0.0, 0.5
AD_LO, AD_HI = 0.5, 1.0
MAX_ITEM_FRAC = 0.30     # deeper than this of the page is a runaway, refused


def display_rows(words, page_height):
    """Rows of display words, as lanes._runs does, then split at column gaps."""
    med = nameplate.page_median_height(words)
    if not med or not page_height:
        return []
    cut = max(page_height * nameplate.MIN_DISPLAY_FRAC, med * nameplate.DISPLAY_RATIO)
    disp = sorted((w for w in words if w[3] >= cut), key=lambda w: (w[1], w[0]))
    out = []
    for row in nameplate.rows_of(disp):
        row = sorted(row, key=lambda w: w[0])
        seg = [row[0]]
        for w in row[1:]:
            prev = seg[-1]
            h = max(prev[3], w[3])
            if w[0] - (prev[0] + prev[2]) > SPLIT_GAP * h:
                out.append(seg)
                seg = [w]
            else:
                seg.append(w)
        out.append(seg)
    return [s for s in out
            if any(sum(ch.isalpha() for ch in w[4]) >= MIN_REAL_TOKEN for w in s)]


def _pieces(row):
    """A row of words split at gaps wider than SPLIT_GAP times their height,
    keeping only pieces with a real token: one piece is one line, more is a
    tier of separate items side by side."""
    row = sorted(row, key=lambda w: w[0])
    out, seg = [], [row[0]]
    for w in row[1:]:
        prev = seg[-1]
        if w[0] - (prev[0] + prev[2]) > SPLIT_GAP * max(prev[3], w[3]):
            out.append(seg); seg = [w]
        else:
            seg.append(w)
    out.append(seg)
    return [s for s in out
            if any(sum(ch.isalpha() for ch in w[4]) >= MIN_REAL_TOKEN for w in s)]


def gutter_counts(row, pi):
    """(gutters inside the row's span, of them straddled by ink) measured on
    the row's own band. A banner's letters straddle the gutters between its
    word spaces; column headlines set side by side clear them. On the
    Cordele Dispatch pages of 10 October 1919 and 26 April 1918 the banners
    measured 9, 10 and 21 straddled against 5, 4 and 8 clear; the tier of
    column headlines 3 against 6."""
    per = pi.page.scale * pi.scale
    row = sorted(row, key=lambda w: w[0])
    y0 = pi.y_small(min(w[1] for w in row))
    y1 = pi.y_small(max(w[1] + w[3] for w in row))
    cols = pi.col_dark_in(y0, max(y0 + 1, y1))
    xa, xz = row[0][0] * per, (row[-1][0] + row[-1][2]) * per
    inside = [g for g in pi.gutters() if xa < g[0] < xz]
    straddled = [g for g in inside if min(cols[g[0]:g[1]] or [0]) > rules.GUTTER_CROSSED]
    return inside, straddled, cols


def is_tier(line, pi):
    """Several items side by side, not one line: split by word gaps, or
    clearing at least as many gutters as it straddles."""
    if len(_pieces(line)) > 1:
        return True
    if pi is None:
        return False
    inside, straddled, _ = gutter_counts(line, pi)
    return bool(inside) and len(straddled) <= len(inside) - len(straddled)


def box_with_deck(seg, words, page_width, page_height, pi=None):
    """The segment's box plus the smaller-but-not-body lines directly under
    it in the same horizontal span (lanes._box_of, minus its padding: the
    snap supplies the real edges)."""
    x0 = min(w[0] for w in seg)
    x1 = max(w[0] + w[2] for w in seg)
    y0 = min(w[1] for w in seg)
    y1 = max(w[1] + w[3] for w in seg)
    h = max(w[3] for w in seg)
    med = nameplate.page_median_height(words) or 1
    span = float(x1 - x0)
    cur = y1
    top_prev, h_prev = y0, h
    # ⚠️ Three kinds of line sit under a headline's first row, and each is
    # told apart by size and alignment, measured on the Augusta Herald of
    # 16 March 1915 and the Banner-Herald of 20 November 1921:
    #   the headline's own next line: the same size, and it fills the same
    #     span (overlap >= 0.6). A same-size line filling under half the span
    #     is the next column's headline ("DRESDEN LIES AT BOTTOM OFF CHILE
    #     ISLAND" joined "'UNBEARABLE' ARE MEXIC CONDITIONS" this way);
    #   a deck line: smaller than the head but clearly display, at least
    #     1.6x the page's body type. 1.3x let body text join on a page whose
    #     median word is small, and the Banner-Herald's crop ran a fifth of
    #     the page deep into its story;
    #   body text: never.
    for _ in range(8):
        # ⚠️ The next line's tops can sit a little ABOVE this line's measured
        # bottom (a descender, a speck): on the Cordele Dispatch of
        # 10 October 1919 the second banner's words start 10 units above the
        # first's bottom, and "cur < w[1]" kept every word of it but the
        # last, so the crop stopped at one banner. A word is below the line
        # if its top is under the line's top by half the line's height.
        cands = [w for w in words
                 if top_prev + 0.5 * h_prev < w[1] <= cur + DECK_GAP * h
                 and w[0] + w[2] > x0 and w[0] < x1]
        if not cands:
            break
        # ⚠️ ONE LINE AT A TIME, judged by its tallest word. Judged per word,
        # the second banner on the 1919 Cordele page came out seven deck
        # words and one same-size word ("PROBLEMS", the only one over 0.85
        # of the head), and the window took the column tier beneath along
        # with it. The line is the unit a reader sees.
        line = nameplate.rows_of(sorted(cands, key=lambda w: (w[1], w[0])))[0]
        hl = max(w[3] for w in line)
        take = []
        if hl >= 0.85 * h:
            lo = min(w[0] for w in line); hi = max(w[0] + w[2] for w in line)
            if (min(hi, x1) - max(lo, x0)) / span >= 0.6:
                take = line
        elif max(DECK_MIN * h, 1.6 * med) <= hl:
            take = line
        if not take:
            break
        # ⚠️ A tier of SEVERAL items under a banner is the next row of column
        # headlines, not the banner's deck. Under "U. S. TO ADD 15 MILLIONS
        # FOR GREAT WORLD AIR ROUTES" (Cordele Dispatch, 10 October 1919)
        # sit five column headlines of deck size, and taking them ran the
        # crop into the columns and their words into the alt. A deck is one
        # line: gap-split as display_rows does, and two real pieces end it.
        if is_tier(take, pi):
            break
        cur = max(w[1] + w[3] for w in take)
        top_prev, h_prev = min(w[1] for w in take), max(w[3] for w in take)
        if cur - y0 > 6 * h:
            break
    y1 = cur
    if (y1 - y0) > MAX_ITEM_FRAC * page_height:
        return None
    return (x0, y0, x1 - x0, y1 - y0)


def candidates(lane, words, page_width, page_height, nameplate_bottom=0, pi=None):
    """(box_ocr, seg) for each candidate, in reading order (top first)."""
    lo, hi = (HEAD_LO, HEAD_HI) if lane == "headline" else (AD_LO, AD_HI)
    out = []
    for seg in display_rows(words, page_height):
        top = min(w[1] for w in seg)
        if not (lo * page_height <= top < hi * page_height):
            continue
        if lane == "headline" and top <= nameplate_bottom:
            continue
        b = box_with_deck(seg, words, page_width, page_height, pi)
        if b:
            out.append((b, seg))
    out.sort(key=lambda t: (t[0][1], t[0][0]))
    return out


def split_at_gutters(cands, words, cw, ch, pi):
    """Split a display segment wherever a page gutter or column rule lies
    between two of its words. The gap test misses column headlines set
    close either side of a rule: "FRENCH DESTROY | MEMORIAL DAY | TWO"
    on the Cordele Dispatch of 26 April 1918 was one row to the OCR and
    three headlines to a reader."""
    per = pi.page.scale * pi.scale                 # small px per OCR unit
    out = []
    for b, seg in cands:
        seg = sorted(seg, key=lambda w: w[0])
        # ⚠️ Only a gutter that is clear on THIS segment's rows splits it. A
        # page-level gutter can run under a headline from a table lower
        # down the column, and it cut "REESE IS ON THE RACK" in two.
        # ⚠️ ...and "this segment's rows" means the display row itself, NOT
        # the box with its deck. The box reaches down into the tier beneath,
        # where every gutter is clear, and judged there a banner is cut at
        # the first gutter: the Cordele Dispatch of 10 October 1919 shipped
        # "U. S. TO" out of "U. S. TO ADD 15 MILLIONS FOR GREAT WORLD AIR
        # ROUTES" that way (found 11 September 2026).
        inside, straddled, cols = gutter_counts(seg, pi)
        # ⚠️ And a word space is white top to bottom, so on the row itself a
        # gutter under a word space reads as clear whether the row is one
        # banner or two column headlines: "TO ADD" and "FRENCH DESTROY |
        # MEMORIAL" both measure 0.000 dark there, at gaps of 0.35h and
        # 0.55h. What tells them apart is INK ACROSS A GUTTER: a banner's
        # letters straddle the gutters between its word spaces, and column
        # headlines straddle one only by accident of the grid ("MEMORIAL
        # DAY" on the 1918 page sits over a gutter the columns below it do
        # not share). So it is a count: banners measured 9, 10 and 21
        # straddled against 5, 4 and 8 clear; the column tier 3 against 6.
        # A row that straddles more gutters than it clears spans columns
        # and is not split at all.
        if len(straddled) > len(inside) - len(straddled):
            nb = box_with_deck(seg, words, cw, ch, pi)
            if nb:
                out.append((nb, seg))
            continue
        bounds = sorted(g[0] for g in pi.gutters()
                        if min(cols[g[0]:g[1]] or [1]) <= rules.GUTTER_CROSSED)
        pieces, cur = [], [seg[0]]
        for w in seg[1:]:
            prev = cur[-1]
            a, z = (prev[0] + prev[2]) * per, w[0] * per
            if any(a < gx < z for gx in bounds):
                pieces.append(cur); cur = [w]
            else:
                cur.append(w)
        pieces.append(cur)
        for p in pieces:
            nb = box_with_deck(p, words, cw, ch, pi)
            if nb:
                out.append((nb, p))
    out.sort(key=lambda t: (t[0][1], t[0][0]))
    return out


def snapped(lane, page, coords, pi=None):
    """Candidates snapped to the grid: [(snapped_box, raw_box, seg)]."""
    pi = pi or rules.PageInk(page)
    cw, ch = coords["width"], coords["height"]
    nb = nameplate.nameplate_box(coords["words"], cw, ch) if page.seq == 1 else None
    mode = "paper" if lane == "headline" else "column"
    out = []
    cands = candidates(lane, coords["words"], cw, ch, nb[3] if nb else 0, pi)
    if lane == "headline":
        cands = split_at_gutters(cands, coords["words"], cw, ch, pi)
    for b, seg in cands:
        if lane == "ad":
            # ⚠️ An advertisement is an item the page has CLOSED with rules on
            # all four sides, walked to those rules and never to white space.
            # Position alone filed the Augusta Herald's second-tier headlines
            # as advertisements; a boxed test does not, and a headline is
            # never boxed.
            # (A boxed-on-four-sides test was tried first and dropped: on
            # microfilm a rule is broken more often than not, and it found
            # no advertisement on any page. The rules the walk DOES reach,
            # above and below, plus the advertising words in clips.py, are
            # the test.)
            s = rules.snap(pi, b, mode="column", rules_only=True, include_border=True)
        else:
            s = rules.snap(pi, b, mode=mode)
        if s and s[3] <= MAX_ITEM_FRAC * ch:
            out.append((s, b, seg))
    return out
