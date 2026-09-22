#!/usr/bin/env python3
"""
test_border_box.py -- rules.PageInk.border_box() and clips.ad_box(), the
boxed-advertisement crop of 22 September 2026, on a synthetic page that
carries every shape the real Douglas Enterprise page (13 July 1907) and
the Atlanta Georgian (4 December 1908) taught it:

  - a wide boxed advertisement (A) with a display heading, a full-width
    INTERIOR rule, an interior column rule, body rows and a closing line;
  - a second box (B) stacked 20 px above it, close enough that their
    side borders read as one run, so only the paper SEAM between them
    says where B ends;
  - a box drawn with a DOTTED border (C), beside A with 6 px between;
  - a box with sides only (E) whose end rows of type the OCR read, and
    whose other rows are BROKEN bars (span) -- the Georgian shape;
  - a box with sides only (E2) whose end rows are rules reaching one
    side only (reach);
  - a column cell (F) under a rule wider than its column rules;
  - a column of dense type (D) with OCR, whose own columns are as dark
    as a border and as wide as the column;
  - the page's own margin, unboxed.

Stdlib and PIL only, no network. Run by path or by discovery.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import clips        # noqa: E402
import rules        # noqa: E402
import nameplate    # noqa: E402


class BoxedPage:
    """1400 wide so OCR space and small-image space coincide (scale 1.0),
    exactly as test_clips.MarketSectionPage relies on."""
    lccn, date, ed, seq = "sn00000003", "1907-07-13", 1, 2
    image_w, image_h = 1400, 1500
    url = "https://example/lccn/sn00000003/1907-07-13/ed-1/seq-2/"
    BODY_H = 14

    # geometry, in pixels, for the tests to assert against
    A = (300, 300, 1100, 820)          # the big box: x0, y0, x1, y1 (outer ink)
    B = (300, 80, 1100, 280)           # stacked above A, 20 px seam (under BORDER_BREAK)
    C = (1106, 300, 1330, 820)         # beside A, 6 px away, dotted border
    E = (300, 900, 700, 1150)          # sides only; broken bars at its ends
    E2 = (760, 900, 1100, 1150)        # sides only; short rules at its ends
    F = (300, 1240, 700, 1480)         # column rules under a wider rule
    D = (30, 300, 260, 1450)           # a column of dense type
    A_INTERIOR_RULE = 470              # full-width rule under A's heading
    A_COLUMN_RULE = 700                # interior column rule, x, in A's body

    def __init__(self):
        from PIL import Image, ImageDraw
        im = Image.new("L", (1400, self.image_h), 210)
        d = ImageDraw.Draw(im)
        words = []
        self.d = d

        def filler(x0, x1, y0, y1):
            for k, y in enumerate(range(y0, y1, 20)):
                jitter = (k * 4) % 9
                for x in range(x0 + jitter, x1, 9):
                    d.rectangle([x, y, x + 2, y + 10], fill=40)
        filler(30, 260, 20, 280)                          # a column of type, top left
        # (the right margin past C stays paper: a page's own margin)

        def row(x, y, h, text, bar_to=None):
            # a continuous bar under the words (a real line of type inks
            # across its measure) plus OCR word boxes: this is the shape
            # the OCR test exists for, since the bar alone reads as a rule
            if bar_to:
                d.rectangle([x, y, bar_to, y + h], fill=120)
            cx = x
            for tok in text.split():
                w = max(20, len(tok) * 12)
                d.rectangle([cx, y, cx + w, y + h], fill=30)
                words.append((cx, y, w, h, tok))
                cx += w + 8

        def solid_box(x0, y0, x1, y1, t=4):
            d.rectangle([x0, y0, x1, y0 + t], fill=20)
            d.rectangle([x0, y1 - t, x1, y1], fill=20)
            d.rectangle([x0, y0, x0 + t, y1], fill=20)
            d.rectangle([x1 - t, y0, x1, y1], fill=20)

        def dotted_box(x0, y0, x1, y1):
            for x in range(x0, x1, 6):
                d.rectangle([x, y0, x + 2, y0 + 2], fill=20)
                d.rectangle([x, y1 - 2, x + 2, y1], fill=20)
            for y in range(y0, y1, 6):
                d.rectangle([x0, y, x0 + 2, y + 2], fill=20)
                d.rectangle([x1 - 2, y, x1, y + 2], fill=20)

        # box A
        ax0, ay0, ax1, ay1 = self.A
        solid_box(ax0, ay0, ax1, ay1)
        row(ax0 + 60, ay0 + 30, 40, "TANNER MERCANTILE COMPANY")      # display, OCR'd
        d.rectangle([ax0 + 20, self.A_INTERIOR_RULE, ax1 - 20, self.A_INTERIOR_RULE + 3], fill=20)
        d.rectangle([self.A_COLUMN_RULE, self.A_INTERIOR_RULE + 20, self.A_COLUMN_RULE + 1, ay1 - 60], fill=20)
        y = self.A_INTERIOR_RULE + 30
        for i in range(5):
            row(ax0 + 30, y, self.BODY_H, f"for sale at low prices {i}", bar_to=self.A_COLUMN_RULE - 10)
            row(self.A_COLUMN_RULE + 10, y, self.BODY_H, f"kitchen furniture at right {i}", bar_to=ax1 - 30)
            y += self.BODY_H + 8
        # closing display line, set across the full measure so that only
        # its thickness says it is not a rule
        row(ax0 + 20, ay1 - 50, 30, "TANNER MERCANTILE COMPANY FURNITURE", bar_to=ax1 - 20)
        # box B, stacked above with a seam
        bx0, by0, bx1, by1 = self.B
        solid_box(bx0, by0, bx1, by1)
        y = by0 + 30
        for i in range(5):
            row(bx0 + 30, y, self.BODY_H, f"pressing club rates membership {i}", bar_to=bx1 - 30)
            y += self.BODY_H + 8
        # box C, dotted, 6 px to the right of A
        cx0, cy0, cx1, cy1 = self.C
        dotted_box(cx0, cy0, cx1, cy1)
        y = cy0 + 40
        for i in range(8):
            row(cx0 + 20, y, self.BODY_H, f"liver pills {i}")
            y += self.BODY_H + 8

        # box E: two side rules and NO top or bottom rule, with a line of
        # type just inside each end -- the Atlanta Georgian shape, where
        # a line of type sits within BORDER_SNAP of where the sides end
        # and its pixels alone would close a box. Two more rows near the
        # ends are BROKEN bars with no OCR (chunks with gaps wider than
        # HRULE_BREAK): the span test is what keeps those from closing it.
        ex0, ey0, ex1, ey1 = self.E
        d.rectangle([ex0, ey0, ex0 + 3, ey1], fill=20)
        d.rectangle([ex1 - 3, ey0, ex1, ey1], fill=20)
        row(ex0 + 20, ey0 + 12, self.BODY_H, "uncle sam becoming shoemaker", bar_to=ex1 - 20)
        for yb in (ey0 + 30, ey1 - 44):
            for xb in range(ex0 + 20, ex1 - 20, 50):
                d.rectangle([xb, yb, xb + 40, yb + 3], fill=20)
        row(ex0 + 20, ey0 + 110, self.BODY_H, "boots and shoes for the world", bar_to=ex1 - 20)
        row(ex0 + 20, ey1 - 26, self.BODY_H, "the number of pairs exported", bar_to=ex1 - 20)
        # box E2: sides only, and a SHORT rule at each end reaching the
        # left side but stopping well short of the right: reach is what
        # keeps those from closing it
        ex0, ey0, ex1, ey1 = self.E2
        d.rectangle([ex0, ey0, ex0 + 3, ey1], fill=20)
        d.rectangle([ex1 - 3, ey0, ex1, ey1], fill=20)
        for yb in (ey0 + 12, ey1 - 15):
            d.rectangle([ex0 + 4, yb, ex0 + int((ex1 - ex0) * 0.6), yb + 3], fill=20)
        row(ex0 + 20, ey0 + 110, self.BODY_H, "reach the far side", bar_to=ex1 - 20)
        # box F: column rules for sides, a rule WIDER than both of them on
        # top (a page rule), a column-local rule at the bottom, rows of
        # type between: a cell of the page, not a box
        fx0, fy0, fx1, fy1 = self.F
        d.rectangle([fx0, fy0 - 30, fx0 + 2, fy1 + 15], fill=20)     # 60 px clear of E's sides
        d.rectangle([fx1 - 2, fy0 - 30, fx1, fy1 + 15], fill=20)
        d.rectangle([fx0 - 40, fy0, fx1 + 40, fy0 + 3], fill=20)
        d.rectangle([fx0 + 20, fy1 - 3, fx1 - 20, fy1], fill=20)
        y = fy0 + 40
        for i in range(5):
            row(fx0 + 20, y, self.BODY_H, f"prices current cell {i}", bar_to=fx1 - 20)
            y += self.BODY_H + 8
        # column D: dense type with OCR, its own pixel columns as dark as a
        # border and 230 px wide -- the Savannah Morning News shape
        dx0, dy0, dx1, dy1 = self.D
        y = dy0
        for i in range(52):
            row(dx0, y, self.BODY_H, f"dense type here {i}", bar_to=dx1)
            y += self.BODY_H + 8

        self._im = im
        self._words = words
        self.scale = 1.0

    def coords(self):
        return {"width": 1400, "height": self.image_h, "words": list(self._words)}

    def to_image(self, box):
        x, y, w, h = box
        if w <= 0 or h <= 0:
            raise ValueError("empty box")
        return (int(x), int(y), int(w), int(h))

    def fetch_crop(self, image_box, width=1200):
        import io
        x, y, w, h = image_box
        crop = self._im.crop((x, y, x + w, y + h))
        if crop.width != width:
            crop = crop.resize((width, max(1, int(crop.height * width / crop.width))))
        buf = io.BytesIO(); crop.save(buf, format="JPEG", quality=92)
        return buf.getvalue()


class BorderBox(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = BoxedPage()
        cls.coords = cls.page.coords()
        cls.pi = rules.PageInk(cls.page)
        cls.words = [(w[0], w[1], w[2], w[3], w[4]) for w in cls.coords["words"]]
        cls.text_h = nameplate.page_median_height(cls.coords["words"])

    def _seed(self, phrase):
        hit = clips.find_phrase(self.coords["words"], phrase)
        self.assertIsNotNone(hit, phrase)
        x0 = min(w[0] for w in hit); x1 = max(w[0] + w[2] for w in hit)
        y0 = min(w[1] for w in hit); y1 = max(w[1] + w[3] for w in hit)
        return (x0, y0, x1 - x0, y1 - y0)

    def _box(self, phrase):
        return self.pi.border_box(self._seed(phrase), self.text_h, self.words)

    def assertBoxIs(self, box, want, tol=4):
        self.assertIsNotNone(box)
        for got, exp in zip(box, want):
            self.assertLessEqual(abs(got - exp), tol, (box, want))

    def test_a_seed_in_the_heading_gets_the_whole_box(self):
        self.assertBoxIs(self._box("mercantile company"), self.page.A)

    def test_a_seed_below_the_interior_rule_still_gets_the_whole_box(self):
        # the full-width rule under the heading is the ad's own; the
        # sides continue past it and nothing beyond it is a seam
        self.assertBoxIs(self._box("kitchen furniture"), self.page.A)
        self.assertBoxIs(self._box("mercantile co"), self.page.A)

    def test_a_seed_left_of_the_interior_column_rule_gets_the_whole_box(self):
        # the interior column rule is a hairline with type beside it,
        # not a border: BORDER_FILL and the paper-beside test
        self.assertBoxIs(self._box("low prices"), self.page.A)

    def test_the_box_stacked_above_is_its_own_box(self):
        self.assertBoxIs(self._box("pressing club"), self.page.B)

    def test_the_seam_keeps_the_stacked_boxes_apart(self):
        a = self._box("mercantile company"); b = self._box("pressing club")
        self.assertGreater(a[1], b[3])

    def test_a_dotted_border_is_a_border(self):
        self.assertBoxIs(self._box("liver pills"), self.page.C, tol=6)

    def test_the_box_beside_is_not_merged_in(self):
        # C sits 6 px from A, under SEAM_MIN, aligned top and bottom:
        # innermost-first is what keeps them apart (see the docstring's
        # step 5 for the outermost-first version that merged them)
        a = self._box("mercantile company"); c = self._box("liver pills")
        self.assertLessEqual(a[2], c[0])

    def test_a_seed_in_a_column_of_type_finds_no_box(self):
        # nothing in the filler column has OCR words; use a synthetic seed
        self.assertIsNone(self.pi.border_box((40, 500, 200, 14), self.text_h, self.words))

    def test_a_body_line_the_ocr_read_is_not_a_rule(self):
        # box E has sides and no top or bottom rule; each of its end lines
        # of type is drawn as a continuous bar the full measure, within
        # BORDER_SNAP of where the sides end, which passes every pixel
        # test for a rule. Only the OCR words on it say otherwise: with
        # them there is no box, without them the lines close one.
        seed = self._seed("boots and shoes")
        self.assertIsNone(self.pi.border_box(seed, self.text_h, self.words))
        box = self.pi.border_box(seed, self.text_h, [])
        self.assertIsNotNone(box)
        self.assertLessEqual(abs(box[0] - self.page.E[0]), 4)
        self.assertLessEqual(abs(box[2] - self.page.E[2]), 4)

    def test_a_broken_row_is_not_a_rule(self):
        # box E's end bars are chunks with 10-px gaps and no OCR: without
        # the span test they close it (both are within BORDER_SNAP of the
        # sides' ends), with it there is no box
        self.assertIsNone(self._box("boots and shoes"))

    def test_a_short_rule_is_not_a_rule(self):
        # box E2's end rules reach the left side and stop at 60 percent
        self.assertIsNone(self._box("reach the far"))

    def test_a_cell_under_a_wider_rule_is_not_a_box(self):
        self.assertIsNone(self._box("prices current"))

    def test_a_column_of_dense_type_is_not_a_side(self):
        self.assertIsNone(self._box("dense type here"))

    def test_a_page_deeper_than_the_cap_is_refused(self):
        with unittest_patch(rules, "MAX_BOX_FRAC", 0.30):
            self.assertIsNone(self._box("mercantile company"))      # A is 0.35 of the page
            self.assertBoxIs(self._box("pressing club"), self.page.B)

    def test_a_display_line_is_not_a_rule(self):
        # the closing line "TANNER MERCANTILE CO" is 30 px on a 14-px text
        # height and, like real display type, gets no OCR words here; it
        # must not close the box (thickness), so the walk reaches the
        # bottom border. With RULE_THICK lifted it closes on that line.
        seed = self._seed("kitchen furniture")
        body = [w for w in self.words if w[3] < 30]           # the body rows only
        box = self.pi.border_box(seed, self.text_h, body)
        self.assertLessEqual(abs(box[3] - self.page.A[3]), 4)
        with unittest_patch(rules, "RULE_THICK", 4.0):
            box = self.pi.border_box(seed, self.text_h, body)
            self.assertLess(box[3], self.page.A[3] - 15)     # closed on that line


class unittest_patch:
    def __init__(self, obj, name, value):
        self.obj, self.name, self.value = obj, name, value
    def __enter__(self):
        self.old = getattr(self.obj, self.name); setattr(self.obj, self.name, self.value)
    def __exit__(self, *a):
        setattr(self.obj, self.name, self.old)


class AdBox(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = BoxedPage()
        cls.coords = cls.page.coords()
        cls.pi = rules.PageInk(cls.page)

    def test_returns_the_border_in_ocr_space(self):
        hit = clips.find_phrase(self.coords["words"], "mercantile company")
        box = clips.ad_box(self.pi, self.coords, hit)
        self.assertIsNotNone(box)
        x0, y0, x1, y1 = self.page.A
        self.assertLessEqual(abs(box[0] - x0), 4)
        self.assertLessEqual(abs(box[1] - y0), 4)
        self.assertLessEqual(abs(box[0] + box[2] - x1), 4)
        self.assertLessEqual(abs(box[1] + box[3] - y1), 4)

    def test_no_border_means_none(self):
        self.assertIsNone(clips.ad_box(self.pi, self.coords, [(40, 500, 160, 14, "abc")]))

    def test_a_box_shallower_than_the_block_floor_is_none(self):
        hit = clips.find_phrase(self.coords["words"], "pressing club")
        with unittest_patch(clips, "MIN_BLOCK_FRAC", 0.50):
            self.assertIsNone(clips.ad_box(self.pi, self.coords, hit))


class ClipAdBoxed(unittest.TestCase):
    """clip_ad's phrase path: the border wins when there is one, the crop
    is the border plus BOX_MARGIN, the alt words are the border's own."""

    def _run(self, phrase):
        from unittest import mock
        page = BoxedPage()
        with mock.patch.object(clips.ghn_api, "issue_pages", return_value=[None, page]), \
             mock.patch.object(clips, "_meta", return_value={}), \
             mock.patch.object(clips, "_verdict", return_value=(clips.gates.Verdict("PASS", []) if hasattr(clips.gates, "Verdict") else None, [])):
            return clips.clip_ad(page.lccn, page.date, 1, 2, phrase=phrase, log=lambda *a: None)

    def test_a_boxed_ad_is_cropped_to_its_border_with_a_margin(self):
        r = self._run("mercantile company")
        self.assertTrue(r["boxed"])
        x0, y0, x1, y1 = BoxedPage.A
        ib = r["image_box"]
        mx, my = int(1400 * clips.BOX_MARGIN_W), int(1500 * clips.BOX_MARGIN_H)
        self.assertLessEqual(abs(ib[0] - (x0 - mx)), 5)
        self.assertLessEqual(abs(ib[1] - (y0 - my)), 5)
        self.assertLessEqual(abs(ib[0] + ib[2] - (x1 + mx)), 5)
        self.assertLessEqual(abs(ib[1] + ib[3] - (y1 + my)), 5)
        self.assertGreater(r["band_fraction"], clips.MAX_BLOCK_FRAC)  # over the block cap: none applies
        self.assertIn("kitchen furniture", r["words"].lower())     # the whole ad's words
        self.assertNotIn("pressing club", r["words"].lower())      # not the box above

    def test_an_unboxed_ad_takes_the_block_with_the_headline_margin(self):
        from unittest import mock
        page = BoxedPage()
        hit = clips.find_phrase(page.coords()["words"], "mercantile company")
        tight = (320, 480, 400, 100)
        with mock.patch.object(clips.ghn_api, "issue_pages", return_value=[None, page]), \
             mock.patch.object(clips, "_meta", return_value={}), \
             mock.patch.object(clips, "ad_box", return_value=None), \
             mock.patch.object(clips, "block_around", return_value=tight), \
             mock.patch.object(clips, "_verdict", return_value=(clips.gates.Verdict("PASS", []) if hasattr(clips.gates, "Verdict") else None, [])):
            r = clips.clip_ad(page.lccn, page.date, 1, 2, phrase="mercantile company", log=lambda *a: None)
        self.assertFalse(r["boxed"])
        ib = r["image_box"]
        self.assertEqual(ib[0], tight[0] - int(1400 * clips.LOOSE_W))
        self.assertEqual(ib[1], tight[1] - int(1500 * clips.LOOSE_H))


if __name__ == "__main__":
    unittest.main()
