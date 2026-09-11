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


def box_with_deck(seg, words, page_width, page_height):
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
        cands = [w for w in words
                 if cur < w[1] <= cur + DECK_GAP * h
                 and w[0] + w[2] > x0 and w[0] < x1]
        same = [w for w in cands if w[3] >= 0.85 * h]
        deck = [w for w in cands if max(DECK_MIN * h, 1.6 * med) <= w[3] < 0.85 * h]
        take = []
        if same:
            lo = min(w[0] for w in same); hi = max(w[0] + w[2] for w in same)
            if (min(hi, x1) - max(lo, x0)) / span >= 0.6:
                take = same
        if not take:
            take = deck
        if not take:
            break
        cur = max(w[1] + w[3] for w in take)
        if cur - y0 > 6 * h:
            break
    y1 = cur
    if (y1 - y0) > MAX_ITEM_FRAC * page_height:
        return None
    return (x0, y0, x1 - x0, y1 - y0)


def candidates(lane, words, page_width, page_height, nameplate_bottom=0):
    """(box_ocr, seg) for each candidate, in reading order (top first)."""
    lo, hi = (HEAD_LO, HEAD_HI) if lane == "headline" else (AD_LO, AD_HI)
    out = []
    for seg in display_rows(words, page_height):
        top = min(w[1] for w in seg)
        if not (lo * page_height <= top < hi * page_height):
            continue
        if lane == "headline" and top <= nameplate_bottom:
            continue
        b = box_with_deck(seg, words, page_width, page_height)
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
    bounds = sorted(g[0] for g in pi.gutters())
    out = []
    for b, seg in cands:
        seg = sorted(seg, key=lambda w: w[0])
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
            nb = box_with_deck(p, words, cw, ch)
            if nb:
                out.append((nb, p))
    out.sort(key=lambda t: (t[0][1], t[0][0]))
    return out


def snapped(lane, page, coords, pi=None):
    """Candidates snapped to the grid: [(snapped_box, raw_box, seg)]."""
    pi = pi or rules.PageInk(page)
    cw, ch = coords["width"], coords["height"]
    nb = nameplate.nameplate_box(coords["words"], cw, ch)
    mode = "paper" if lane == "headline" else "column"
    out = []
    cands = candidates(lane, coords["words"], cw, ch, nb[3] if nb else 0)
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
