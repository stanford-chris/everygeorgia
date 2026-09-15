#!/usr/bin/env python3
"""
Tests for pictures.py, the cartoon lane: the OCR-hole detector on a synthetic
page, the model reply's parser and the alt it becomes, the quote curler, and
the lane's place in the poster. Stdlib plus Pillow, no network, no model.

⚠️ THE KIND GATE IS THE POINT. The geometry finds pictures of every kind and
only the model's KIND line stands between an ad's stove engraving and the
feed; a reply whose kind is not in KINDS_POSTED must never reach a result, a
"yes" on the caricature line must be REVIEW, and both labels the alt promises
(A.I.-described for the drawing, A.I.-transcribed for its words) must be in
it, because bot_alt_check.py reads the second as the disclosure marker.
"""
import unittest
from unittest import mock

import pictures


def synthetic_coords(W=4000, H=6000, hole=None, extent=(100, 100, 3900, 5900)):
    """A page of body text as OCR word boxes on a grid, with a rectangle
    `hole` (x, y, w, h) left empty."""
    words = []
    x0, y0, x1, y1 = extent
    for y in range(y0, y1, 40):
        for x in range(x0, x1, 120):
            if hole and hole[0] <= x < hole[0] + hole[2] and hole[1] <= y < hole[1] + hole[3]:
                continue
            words.append((x, y, 100, 30, "word"))
    return {"width": W, "height": H, "words": words}


class Detector(unittest.TestCase):
    def test_a_picture_sized_hole_in_the_ocr_is_a_candidate(self):
        c = synthetic_coords(hole=(1000, 2000, 1200, 900))       # 30% x 15% of the page
        cands = pictures.candidates(c, None, seq=3)
        self.assertEqual(len(cands), 1)
        area, box = cands[0]
        self.assertAlmostEqual(box[0], 1000, delta=120)
        self.assertAlmostEqual(box[1], 2000, delta=140)
        self.assertGreater(area, pictures.MIN_AREA_FRAC)

    def test_a_page_of_text_has_no_candidate(self):
        self.assertEqual(pictures.candidates(synthetic_coords(), None, seq=3), [])

    def test_the_margins_are_never_a_hole(self):
        # a wide margin on every side is outside the OCR extent, not a picture
        c = synthetic_coords(extent=(800, 800, 3200, 5200))
        self.assertEqual(pictures.candidates(c, None, seq=3), [])

    def test_a_hole_too_small_or_too_thin_is_not_a_candidate(self):
        self.assertEqual(pictures.candidates(synthetic_coords(hole=(1000, 2000, 300, 300)), None, 3), [])
        self.assertEqual(pictures.candidates(synthetic_coords(hole=(1000, 2000, 3000, 200)), None, 3), [])

    def test_the_running_head_and_nameplate_band_are_clipped_not_dropped(self):
        c = synthetic_coords(hole=(1000, 120, 1200, 500))           # top 2% to 10%: too little left below
        self.assertEqual(pictures.candidates(c, None, seq=1), [])
        self.assertEqual(pictures.candidates(c, None, seq=5), [])
        c = synthetic_coords(hole=(1000, 120, 1200, 1500))          # top 2% to 27%: clipped to the skip line
        got = pictures.candidates(c, None, seq=5)
        self.assertEqual(len(got), 1)
        self.assertGreaterEqual(got[0][1][1] / 6000.0, pictures.TOP_SKIP["inner"] - 0.01)

    def test_a_paper_component_is_dropped_by_the_ink_mean(self):
        """With ink, a hole that is blank paper throughout is not a picture;
        the same hole with ink is."""
        c = synthetic_coords(hole=(1000, 2000, 1200, 900))
        cover, _, ncols, nrows = pictures.cell_grid(c, None)

        class Ink:
            def __init__(self, level):
                self.w, self.h, self.level = 1400, 2100, level
                self.page = type("P", (), {"scale": 1.0})(); self.scale = 0.35
            def is_ink(self, x, y):
                return self.level
            def film_edges(self):
                return (0, self.w)
            def row_dark(self, x0, x1, y0, y1):
                return [0.3 if self.level else 0.0] * max(0, y1 - y0)

        with mock.patch.object(pictures, "cell_grid") as cg:
            for level, expect in ((False, 0), (True, 1)):
                ink = [[0.3 if level else 0.0] * ncols for _ in range(nrows)]
                cg.return_value = (cover, ink, ncols, nrows)
                got = pictures.candidates(c, Ink(level), seq=3)
                self.assertEqual(len(got), expect, f"ink {level}")

    def test_the_balloon_lettering_is_closed_into_the_drawing(self):
        """A hole with a text patch inside it (a speech balloon) is still one
        component after the closing pass."""
        c = synthetic_coords(hole=(1000, 2000, 1200, 900))
        c["words"] += [(x, y, 100, 30, "HA") for y in range(2300, 2420, 40) for x in range(1400, 1700, 120)]
        cands = pictures.candidates(c, None, seq=3)
        self.assertEqual(len(cands), 1)
        self.assertGreater(cands[0][1][3], 800)


class ThinRules(unittest.TestCase):
    def test_a_thin_dark_run_is_a_rule_and_a_thick_one_is_type(self):
        dark = [0.1] * 5 + [0.6] * 2 + [0.1] * 5 + [0.6] * 4 + [0.1] * 3   # 4 rows is bold type's x-height
        got = pictures.thin_rules(dark)
        self.assertEqual(got[5:7], [True, True])
        self.assertFalse(any(got[12:16]))


class ClearShare(unittest.TestCase):
    def test_lines_of_type_read_high_and_a_drawing_low(self):
        class PI:
            w = 1400
            def film_edges(self):
                return (0, 1400)
            def row_dark(self, x0, x1, y0, y1):
                # ten rows of type, each followed by two rows of leading
                return [0.3, 0.3, 0.01, 0.01] * 10
        self.assertAlmostEqual(pictures.clear_share(PI(), (0, 0, 10, 40)), 0.5)
        class Drawing:
            w = 1400
            def film_edges(self):
                return (0, 1400)
            def row_dark(self, x0, x1, y0, y1):
                return [0.1] * 40
        self.assertEqual(pictures.clear_share(Drawing(), (0, 0, 10, 40)), 0.0)


class Necks(unittest.TestCase):
    def test_a_bridge_of_few_rows_is_cut_and_both_pieces_come_back(self):
        big = [(r, c) for r in range(0, 18) for c in range(10, 24)]      # the drawing
        small = [(r, c) for r in range(0, 18) for c in range(0, 6)]      # the masthead block
        bridge = [(r, c) for r in range(0, 3) for c in range(6, 10)]     # unread display type
        got = sorted(sorted(p) for p in pictures.split_at_necks(big + small + bridge))
        self.assertEqual(got, sorted([sorted(small), sorted(big)]))

    def test_stacked_pictures_bridged_by_a_thin_chain_are_cut_on_rows(self):
        top = [(r, c) for r in range(0, 12) for c in range(0, 20)]
        chain = [(r, 3) for r in range(12, 20)]                          # a portrait's column
        bottom = [(r, c) for r in range(20, 30) for c in range(0, 20)]
        got = sorted(sorted(p) for p in pictures.split_at_necks(top + chain + bottom))
        self.assertEqual(got, sorted([sorted(top), sorted(bottom)]))

    def test_a_solid_component_is_untouched(self):
        big = [(r, c) for r in range(0, 18) for c in range(10, 24)]
        self.assertEqual([sorted(p) for p in pictures.split_at_necks(big)], [sorted(big)])

    def test_a_single_thin_row_inside_a_picture_is_not_a_neck(self):
        big = [(r, c) for r in range(0, 18) for c in range(10, 24) if r not in (9, 10) or c in (10, 11)]   # rows 9-10: lettering
        self.assertEqual(len(pictures.split_at_necks(big)), 1)


class Bands(unittest.TestCase):
    class PI:
        w, h = 1400, 2000
        def __init__(self, rows, boxed=()):
            self.rows, self.boxed = rows, set(boxed)
        def film_edges(self):
            return (0, self.w)
        def row_dark(self, x0, x1, y0, y1):
            return self.rows[y0:y1]
        def is_ink(self, x, y):
            return y in self.boxed            # border lines at the span's edges on these rows

    def test_stacked_strips_become_bands_and_panel_rows_stay_one(self):
        ink, paper = 0.2, 0.0
        rows = ([ink] * 150 + [paper] * 10 + [ink] * 150      # strip A: two rows of panels, 10 px apart
                + [paper] * 12 + [ink] * 30 + [paper] * 12    # a full-width title line between
                + [ink] * 200)                                # strip B
        bands = pictures.split_by_gaps(self.PI(rows), (0, 0, 100, len(rows)))
        self.assertEqual([(b[1], b[3]) for b in bands], [(0, 310), (364, 200)])

    def test_paper_inside_a_box_is_not_a_gap(self):
        ink, paper = 0.2, 0.0
        rows = [ink] * 150 + [paper] * 12 + [ink] * 30 + [paper] * 12 + [ink] * 200   # a boxed cartoon's sky and lettering
        boxed = range(0, len(rows))                                                    # border lines on every row
        bands = pictures.split_by_gaps(self.PI(rows, boxed), (0, 0, 100, len(rows)))
        self.assertEqual([(b[1], b[3]) for b in bands], [(0, 404)])

    def test_bands_across_a_column_of_type_do_not_rejoin(self):
        ink, paper, line = 0.2, 0.0, 0.3
        rows = [ink] * 200 + [paper] * 4 + ([line] * 6 + [paper] * 4) * 10 + [ink] * 200
        bands = pictures.split_by_gaps(self.PI(rows), (0, 0, 100, len(rows)))
        self.assertEqual([(b[1], b[3]) for b in bands], [(0, 200), (304, 200)])

    def test_a_solid_picture_is_one_band(self):
        rows = [0.2] * 300
        self.assertEqual(pictures.split_by_gaps(self.PI(rows), (5, 0, 100, 300)), [(5, 0, 100, 300)])


class Trim(unittest.TestCase):
    def test_a_paper_gap_in_the_outer_zone_cuts_the_component(self):
        class PI:
            h, w = 2000, 1400
            def film_edges(self):
                return (0, 1400)
            def row_dark(self, x0, x1, y0, y1):
                # 300 rows: ink, then 12 rows of paper at 240, then ink
                return [0.004 if 240 <= y < 252 else 0.2 for y in range(y0, y1)]
        self.assertEqual(pictures.trim_by_gaps(PI(), (10, 0, 100, 300)), (10, 0, 100, 240))

    def test_a_gap_in_the_middle_does_not_cut(self):
        class PI:
            h, w = 2000, 1400
            def film_edges(self):
                return (0, 1400)
            def row_dark(self, x0, x1, y0, y1):
                return [0.004 if 140 <= y < 160 else 0.2 for y in range(y0, y1)]
        self.assertEqual(pictures.trim_by_gaps(PI(), (10, 0, 100, 300)), (10, 0, 100, 300))


def _row(y, h, spans):
    """A synthetic OCR row: one word per (x, w) span, all real (3+ letters)."""
    return [(x, y, w, h, "word") for x, w in spans]


class Caption(unittest.TestCase):
    """The Athens Banner's "FEMINISMS" cartoon of 20 August 1921 shipped with
    its whole third caption line cut off (CAPTION_LINES was one short of a
    title-plus-three-line joke) and its byline and two caption words cut off
    mid-glyph on the right (the crop never widened for a caption wider than
    the picture). Both bugs, and the fix, in one shape: a title line and
    three joke-caption lines below the picture, the second caption line
    carrying one word that runs wider than every other row."""

    def _span(self):
        # title, then three caption lines; heights/gaps modelled on the real
        # page's own numbers (med=10, well inside CAPTION_BELOW_H/CAPTION_GAP)
        title = _row(1010, 15, [(400, 80), (500, 90)])
        cap1 = _row(1030, 18, [(350, 90), (460, 90), (560, 90)])
        cap2 = _row(1052, 18, [(350, 90), (460, 90), (680, 100)])   # runs to 780
        cap3 = _row(1074, 18, [(350, 90), (460, 90), (560, 90)])
        return title + cap1 + cap2 + cap3

    def test_a_title_plus_three_line_caption_is_not_cut_at_the_third_line(self):
        out, extent = pictures._caption_edge(self._span(), 1, 1000, 1, 200, 10)
        self.assertGreaterEqual(out, 1074 + 18)         # the third line's own bottom
        self.assertIsNotNone(extent[1])

    def test_at_the_old_line_count_the_third_line_was_dropped(self):
        # pins the regression: at CAPTION_LINES=3 the walk stopped after the
        # second caption line, well short of the third's bottom (1092)
        with mock.patch.object(pictures, "CAPTION_LINES", 3):
            out, _ = pictures._caption_edge(self._span(), 1, 1000, 1, 200, 10)
        self.assertLess(out, 1074)

    def test_a_word_wider_than_the_picture_widens_the_reported_extent(self):
        # the picture's own x-range was (350, 700); "exercise"/"to" on the
        # real page ran past it the same way this synthetic word (680-780) does
        _, (lo, hi) = pictures._caption_edge(self._span(), 1, 1000, 1, 200, 10)
        self.assertEqual(lo, 350)
        self.assertEqual(hi, 780)

    def test_no_accepted_line_reports_no_extent(self):
        out, extent = pictures._caption_edge([], 1, 1000, 1, 200, 10)
        self.assertEqual(out, 1000)
        self.assertEqual(extent, (None, None))


class CaptionDiagnostics(unittest.TestCase):
    """_caption_edge's own diagnostics, added 15 September 2026 for
    crop_closure_check.py's cartoon-lane audit -- filled at the exact
    break this function already takes, mirroring clips.block_around's
    own contract. Every row here carries two real words (CAPTION_REAL_
    WORDS): a one-word row, like Caption's own gap/reach fixtures used
    above, is filtered out before any of this is even reached."""

    def test_a_line_just_past_the_gap_ceiling_is_a_near_miss(self):
        # CAPTION_GAP*hgt = 1.5*15 = 22.5; the second line's own gap (25)
        # clears it by 2.5, a near miss.
        line0 = _row(1000, 15, [(400, 80), (500, 90)])
        line1 = _row(1040, 15, [(400, 80), (500, 90)])
        diag = {}
        pictures._caption_edge(line0 + line1, 1, 1000, 1, 200, 10,
                               diagnostics=diag, direction="bottom")
        info = diag["bottom"]
        self.assertEqual(info["reason"], "gap")
        self.assertAlmostEqual(info["ratio"], (25 - 22.5) / 22.5, places=4)

    def test_a_line_outside_reach_is_a_confident_stop_not_a_miss(self):
        # A tiny `reach` (2) smaller than the function's own fixed
        # pre-filter tolerance (4) is what lets a line past the pre-
        # filter and into the in-loop reach check itself -- see the
        # test's own comment in the production code's docstring.
        line0 = _row(997, 15, [(400, 80), (500, 90)])
        diag = {}
        pictures._caption_edge(line0, 1, 1000, 1, 2, 10,
                               diagnostics=diag, direction="bottom")
        self.assertEqual(diag["bottom"]["reason"], "reach")
        self.assertIsNone(diag["bottom"]["ratio"])

    def test_a_real_fifth_line_past_caption_lines_is_a_near_miss(self):
        # Five lines, five-unit gaps throughout (well inside CAPTION_GAP):
        # the cap alone excludes the fifth, not any gap of its own -- a
        # negative ratio, the clearest possible near miss.
        lines = []
        for i in range(5):
            lines += _row(1000 + i * 20, 15, [(400, 80), (500, 90)])
        diag = {}
        with mock.patch.object(pictures, "CAPTION_LINES", 4):
            pictures._caption_edge(lines, 1, 1000, 1, 200, 10,
                                   diagnostics=diag, direction="bottom")
        info = diag["bottom"]
        self.assertEqual(info["reason"], "caption-count-cap")
        self.assertLess(info["ratio"], 0)

    def test_exactly_caption_lines_with_nothing_further_reports_none(self):
        diag = {}
        pictures._caption_edge(self.Caption_span(), 1, 1000, 1, 200, 10,
                               diagnostics=diag, direction="bottom")
        self.assertIsNone(diag["bottom"])

    def Caption_span(self):
        title = _row(1010, 15, [(400, 80), (500, 90)])
        cap1 = _row(1030, 18, [(350, 90), (460, 90), (560, 90)])
        cap2 = _row(1052, 18, [(350, 90), (460, 90), (680, 100)])
        cap3 = _row(1074, 18, [(350, 90), (460, 90), (560, 90)])
        return title + cap1 + cap2 + cap3

    def test_diagnostics_none_by_default_costs_nothing_and_changes_nothing(self):
        span = self.Caption_span()
        plain = pictures._caption_edge(span, 1, 1000, 1, 200, 10)
        instrumented = pictures._caption_edge(span, 1, 1000, 1, 200, 10, diagnostics={})
        self.assertEqual(plain, instrumented)


class Reply(unittest.TestCase):
    GOOD = ("KIND: comic-strip\nTITLE: Penny Ante\nWORDS: HA! HA! | OH BOY | NEVER MIND.\n"
            "PICTURE: Five men sit around a card table.\nCARICATURE: no")

    def test_parses_all_five_lines_and_joins_balloons_with_periods(self):
        r = pictures.parse_reply(self.GOOD)
        self.assertEqual(r["kind"], "comic-strip")
        self.assertEqual(r["title"], "Penny Ante")
        self.assertEqual(r["words"], "HA! HA! OH BOY. NEVER MIND.")
        self.assertFalse(r["caricature"])

    def test_none_and_yes(self):
        r = pictures.parse_reply("KIND: Editorial-cartoon (single panel)\nTITLE: NONE\nWORDS: NONE\n"
                                 "PICTURE: A man.\nCARICATURE: Yes, the figure is drawn as a caricature.")
        self.assertEqual(r["kind"], "editorial-cartoon")
        self.assertEqual(r["title"], "")
        self.assertEqual(r["words"], "")
        self.assertTrue(r["caricature"])

    def test_unparseable_and_cannot_read_are_none(self):
        self.assertIsNone(pictures.parse_reply("I think this is a cartoon of some men."))
        self.assertIsNone(pictures.parse_reply("CANNOT_READ"))
        self.assertIsNone(pictures.parse_reply("KIND: painting\nPICTURE: x\n"))

    def test_classify_rejects_tool_talk_then_gives_up(self):
        bad = "KIND: comic-strip\nTITLE: NONE\nWORDS: NONE\nPICTURE: I'm unable to zoom in.\nCARICATURE: no"
        with mock.patch.object(pictures.transcribe, "ask", return_value=bad) as ask:
            self.assertIsNone(pictures.classify(b"x", "1919", log=lambda m: None))
            self.assertEqual(ask.call_count, 2)


class Alt(unittest.TestCase):
    META = {"title": "Atlanta Georgian.", "city": "Atlanta"}

    def test_both_labels_and_curly_quotes(self):
        r = pictures.parse_reply(Reply.GOOD)
        alt = pictures.compose_alt(self.META, "1919-01-15", 10, r)
        self.assertTrue(alt.startswith("A.I.-described comic strip from “Atlanta Georgian,” Atlanta, Georgia, January 15, 1919, page 10. "))
        self.assertIn(pictures.transcribe.PREFIX, alt)
        self.assertIn("titled “Penny Ante”", alt)
        self.assertIn("the words read: “HA! HA! OH BOY. NEVER MIND.”", alt)
        self.assertNotIn('"', alt)
        self.assertNotIn("'", alt)

    def test_quotes_curl_by_position(self):
        self.assertEqual(pictures.curl('a frame labeled "1914," and \'so\' it\'s'),
                         "a frame labeled “1914,” and ‘so’ it’s")

    def test_kinds_posted_are_all_cartoon_kinds(self):
        # "illustration" since the second dry run: a serial-story drawing
        # (Augusta Daily Herald, 24 January 1914) was called a comic-strip
        # when there was no kind for what it was
        for k in ("illustration", "photograph", "engraving", "advertisement", "map", "text-only", "other"):
            self.assertNotIn(k, pictures.KINDS_POSTED)
        for k in ("editorial-cartoon", "comic-strip", "sports-cartoon"):
            self.assertIn(k, pictures.KINDS_POSTED)
            self.assertIn(k, pictures.KINDS)


class Lane(unittest.TestCase):
    """clip_cartoon against stubbed pages: the kind gate, the caricature
    REVIEW and the vocabulary REVIEW, with no network and no model."""

    def _run(self, reply, kinds_seen_expected=None):
        import clips
        import gates
        c = synthetic_coords(hole=(1000, 2000, 1200, 900))

        class Page:
            lccn, date, ed, seq = "sn89053729", "1919-01-15", 1, 3
            image_w, image_h, scale = 4000, 6000, 1.0
            url = "https://x/seq-3/"
            def coords(self):
                return c
            def to_image(self, box):
                return box

        class PI:
            w, h = 1400, 2100
            page = Page()
            scale = 0.35
            def gutters(self):
                return []
            def film_edges(self):
                return (0, 1400)
            def row_dark(self, x0, x1, y0, y1):
                return [0.2] * max(0, y1 - y0)
            def from_ocr(self, box):
                return tuple(int(v * 0.35) for v in box)
            def to_ocr(self, box):
                return tuple(int(v / 0.35) for v in box)

        from PIL import Image
        import io
        buf = io.BytesIO(); Image.new("L", (50, 40), 255).save(buf, "JPEG")
        with mock.patch.object(pictures.ghn_api, "issue_pages", return_value=[Page()]), \
             mock.patch.object(pictures.rules, "PageInk", return_value=PI()), \
             mock.patch.object(pictures, "candidates", return_value=[(0.05, (1000, 2000, 1200, 900))]), \
             mock.patch.object(pictures, "frame", return_value=(1000, 2000, 1200, 900)), \
             mock.patch.object(clips, "_fetch", return_value=((1000, 2000, 1200, 900), buf.getvalue())), \
             mock.patch.object(clips, "_meta", return_value={"title": "Atlanta Georgian.", "city": "Atlanta", "postable": "yes"}), \
             mock.patch.object(gates, "roster", return_value={"sn89053729": {"postable": "yes"}}), \
             mock.patch.object(pictures.transcribe, "ask", return_value=reply):
            return pictures.clip_cartoon("sn89053729", "1919-01-15", log=lambda m: None)

    def test_a_cartoon_kind_passes_with_its_alt(self):
        r = self._run(Reply.GOOD)
        self.assertTrue(r["postable"])
        self.assertEqual(r["lane"], "cartoon")
        self.assertEqual(r["seq"], 3)
        self.assertIn("A.I.-described comic strip", r["alt"])
        self.assertTrue(r["generated"])

    def test_a_photograph_is_refused_and_named(self):
        with self.assertRaises(pictures.npc.Refused) as cm:
            self._run(Reply.GOOD.replace("comic-strip", "photograph"))
        self.assertIn("p3 photograph", str(cm.exception))

    def test_caricature_is_review_never_posted(self):
        r = self._run(Reply.GOOD.replace("CARICATURE: no", "CARICATURE: yes"))
        self.assertFalse(r["postable"])
        self.assertEqual(r["verdict"].outcome, "REVIEW")
        self.assertTrue(any("caricature" in x for x in r["verdict"].reasons))

    def test_vocabulary_in_the_models_reading_is_review(self):
        r = self._run(Reply.GOOD.replace("Five men", "A lynching party of men"))
        self.assertFalse(r["postable"])
        self.assertEqual(r["verdict"].outcome, "REVIEW")

    def test_the_lane_is_in_the_rotation_and_draws_from_dailies(self):
        import everygeorgia_post as ep
        self.assertIn("cartoon", ep.LANES)
        self.assertEqual(ep.LANE_LABEL["cartoon"], "Cartoon")
        self.assertNotIn("cartoon", ep.SEARCH_LANES)
        import gates
        self.assertEqual(gates.earliest("cartoon"), "1900-01-01")


class CartoonClosureMargins(unittest.TestCase):
    """cartoon_closure_margins(), crop_closure_check.py's own entry point
    for this lane. `candidates`/`clear_share`/`frame` are mocked, since
    what this dispatch function owns is picking the SAME single survivor
    clip_cartoon would hand the model first, and refusing to guess when
    there is more than one -- not the geometry inside frame() itself,
    which CaptionDiagnostics above already covers."""

    class Page:
        seq = 3

    class PI:
        """Just enough of rules.PageInk for cartoon_closure_margins' own
        dispatch code: from_ocr() is called before clear_share()/frame()
        run (both mocked below), so it needs a real, if trivial, method."""
        def from_ocr(self, box):
            return box

    def test_one_survivor_gets_framed_with_diagnostics_on(self):
        with mock.patch.object(pictures, "candidates",
                               return_value=[(0.05, (100, 100, 200, 200))]), \
             mock.patch.object(pictures, "clear_share", return_value=0.1), \
             mock.patch.object(pictures, "frame", return_value=(90, 90, 220, 220)) as fr:
            margins = pictures.cartoon_closure_margins(self.PI(), {"words": []}, self.Page())
        self.assertIsInstance(margins, dict)
        fr.assert_called_once()
        self.assertEqual(fr.call_args[1].get("diagnostics"), margins)

    def test_no_candidate_at_all_reports_none(self):
        with mock.patch.object(pictures, "candidates", return_value=[]):
            self.assertIsNone(pictures.cartoon_closure_margins(self.PI(), {"words": []}, self.Page()))

    def test_every_candidate_reading_as_type_reports_none(self):
        with mock.patch.object(pictures, "candidates",
                               return_value=[(0.05, (100, 100, 200, 200))]), \
             mock.patch.object(pictures, "clear_share", return_value=0.9):   # > TYPE_CLEAR_MAX
            self.assertIsNone(pictures.cartoon_closure_margins(self.PI(), {"words": []}, self.Page()))

    def test_more_than_one_survivor_reports_none_rather_than_guess(self):
        with mock.patch.object(pictures, "candidates",
                               return_value=[(0.05, (100, 100, 200, 200)),
                                            (0.03, (500, 500, 150, 150))]), \
             mock.patch.object(pictures, "clear_share", return_value=0.1), \
             mock.patch.object(pictures, "frame") as fr:
            self.assertIsNone(pictures.cartoon_closure_margins(self.PI(), {"words": []}, self.Page()))
        fr.assert_not_called()


if __name__ == "__main__":
    unittest.main()
