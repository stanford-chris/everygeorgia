#!/usr/bin/env python3
"""
Tests for clips.py, items.py and rules.py: the text passes every new lane
depends on, the display-row split, and the grid snapping on a synthetic page.

⚠️ THE TOKENISATION TESTS ARE THE POINT. crop_frequency.norm() returns ONE
token, the longest alphabetic run of a single OCR word, and the first
version of clips.py fed it whole transcriptions: every advertisement had no
advertising words and a transcription carrying "negro" reached REVIEW
instead of REFUSE. Both are pinned here against the real function.

Stdlib plus Pillow, no network, no model.
"""
import io
import unittest

from PIL import Image, ImageDraw

import clips
import gates
import items
import nameplate_crop as npc
import rules


class HeadlineWords(unittest.TestCase):
    def test_periods_between_items_do_not_disturb_the_headline_checks(self):
        import transcribe
        words = transcribe.join_items(["MOB LYNCHES TWO NEAR MACON", "Sheriff Powerless, Says Report"])
        self.assertEqual(clips._check_transcription(words, "headline"), {"lynch"})
        clips._refuse_own_title(words, {"title": "The Macon telegraph."}, "headline")  # no raise
        with self.assertRaises(clips.npc.Refused):
            clips._refuse_own_title(transcribe.join_items(["MACON TELEGRAPH", "CITY EDITION"]),
                                    {"title": "The Macon telegraph."}, "headline")


class CutBand(unittest.TestCase):
    """The 300-character cut for the alt falls on an item boundary when the
    items are period-separated (12 September 2026), not mid-headline."""
    def test_short_words_pass_whole(self):
        self.assertEqual(clips.cut_band("A. B. C."), "A. B. C.")

    def test_cut_falls_on_an_item_boundary_and_drops_that_period(self):
        items = [f"HEADLINE NUMBER {i} SAYS SOMETHING OF NOTE." for i in range(12)]
        words = " ".join(items)
        out = clips.cut_band(words)
        self.assertTrue(len(out) <= clips.BAND_ALT_CHARS + 1)
        self.assertTrue(out.endswith("OF NOTE…"), out[-30:])
        self.assertNotIn(".…", out)
        # every item kept is whole
        kept = out[:-1]
        self.assertTrue(words.startswith(kept))
        self.assertTrue(words[len(kept):].startswith(". "))

    def test_without_a_boundary_in_the_second_half_it_cuts_at_a_word(self):
        words = "SHORT. " + " ".join(["WORD"] * 100)
        out = clips.cut_band(words)
        self.assertTrue(out.endswith("WORD…"))
        self.assertNotIn("WOR…", out)


class Tokens(unittest.TestCase):
    def test_whole_text_is_tokenised_not_reduced_to_one_word(self):
        self.assertEqual(clips.tokens("The negro vote, with the white"),
                         ["the", "negro", "vote", "with", "the", "white"])

    def test_vocabulary_hits_see_a_word_anywhere_in_a_transcription(self):
        t = ("Emory Speer was one of the most brilliant young men in Georgia. "
             "At that time the negro vote could have controlled politics.")
        self.assertIn("negro", clips.vocabulary_hits(t))
        self.assertEqual(clips.vocabulary_hits("VIGOROUS TO BE PROTEST OF U. S."), set())
        self.assertIn("lynch", clips.vocabulary_hits("MOB LYNCHES TWO"))

    def test_ad_markers_count_distinct_words_and_prices(self):
        m = clips.ad_markers("POPULAR GOODS. Popular Prices. PURE DRUGS. We sell the best goods at the lowest prices, 25 cents")
        self.assertTrue({"goods", "prices", "sell", "$"} <= m)
        self.assertLess(len(clips.ad_markers("REESE IS ON THE RACK For Wetting His Throat")), 2)

    def test_tabular_share(self):
        rows = [(0, 0, 1, 1, t) for t in "Cotton 8 1/2 Corn 65 Wheat $1.10 Bacon 12".split()]
        self.assertGreaterEqual(clips.tabular(rows), 0.4)
        prose = [(0, 0, 1, 1, t) for t in "the cotton market was quiet all week".split()]
        self.assertEqual(clips.tabular(prose), 0.0)

    def test_legibility(self):
        good = [(0, 0, 1, 1, t) for t in "We solicit the patronage of all and guarantee satisfaction".split()]
        bad = [(0, 0, 1, 1, t) for t in "jgF EXPRESS AND f t~ 1 mK a".split()]
        self.assertGreater(clips.legibility(good)[0], clips.LEGIBLE)
        self.assertLess(clips.legibility(bad)[0], clips.LEGIBLE)
        self.assertEqual(clips.legibility(good[:3])[0], 0.0)      # under MIN_TOKENS

    def test_find_phrase_matches_every_word_of_the_phrase(self):
        words = [(10, 0, 30, 10, "Prices"), (45, 0, 30, 10, "Current."), (10, 20, 30, 10, "Cotton"),
                 (10, 40, 30, 10, "Current")]
        hit = clips.find_phrase(words, "prices current")
        self.assertEqual([w[4] for w in hit], ["Prices", "Current."])
        self.assertIsNone(clips.find_phrase(words, "cotton market"))


class Lines(unittest.TestCase):
    def test_wrapped_word_subrows_merge_into_one_line(self):
        """rows_of() puts a wrapped word ("and", sitting low) in a row of its
        own; _lines() folds it back, which is what lets line SPACING tell a
        deck from a paragraph on the Macon Telegraph of 15 January 1897."""
        rows = [[(10, 100, 40, 12, "The"), (60, 100, 40, 12, "judge")],
                [(110, 106, 20, 10, "and")],
                [(10, 130, 40, 12, "denies")]]
        lines = clips._lines(rows, 12)
        self.assertEqual(len(lines), 2)
        self.assertEqual([w[4] for w in lines[0][3]], ["The", "judge", "and"])
        self.assertEqual(lines[0][1], 116)

    def test_one_strong_marker_refuses_a_headline_or_article(self):
        for text in ("GROVER GRAHAM DYSPEPSIA REMEDY will instantly remove all distress. A 25-cent trial bottle convinces.",
                     "A MERRY CHRISTMAS WITHOUT A BOX OF Huyler's CANDIES"):
            with self.assertRaises(clips.npc.Refused):
                clips._check_transcription(text, "article", ad_limit=4)
        self.assertIn("$", clips.ad_markers("A 25-cent trial bottle"))

    def test_a_transcription_carrying_the_vocabulary_is_returned_not_refused(self):
        """Since 11 September 2026 the caller turns the hits into a REVIEW; the
        check itself refuses only what is not a headline or article."""
        self.assertEqual(clips._check_transcription("MOB LYNCHES TWO NEAR MACON", "headline"), {"lynch"})
        self.assertEqual(clips._check_transcription("COUNTRY SOLID IN SUPPORT OF WILSON", "headline"), set())
        v = clips._review(gates.Verdict(gates.PASS), "the transcribed headline carries ['lynch']")
        self.assertEqual(v.outcome, gates.REVIEW)
        self.assertFalse(v.postable)

    def test_article_transcription_allows_news_vocabulary(self):
        """"trade" and "orders" in a story about the Order in Council are
        not an advertisement; the article lane asks for four markers."""
        text = "VIGOROUS PROTEST Washington.—The British Order in Council, shutting off German trade, orders"
        clips._check_transcription(text, "article", ad_limit=4)     # no raise
        with self.assertRaises(clips.npc.Refused):
            clips._check_transcription(text, "headline")


class DisplayRows(unittest.TestCase):
    def body(self):
        return [(20 + (i * 31) % 600, 400 + (i // 20) * 14, 25, 10, "the") for i in range(200)]

    def test_a_line_of_column_headlines_is_split_at_the_gutters(self):
        words = self.body() + [
            (20, 100, 60, 30, "FIRE"), (85, 100, 70, 30, "DOWNTOWN"),
            (320, 100, 60, 30, "SENATE"), (385, 100, 60, 30, "VOTES"),
        ]
        rows = items.display_rows(words, 1000)
        self.assertEqual(len(rows), 2)
        self.assertEqual([w[4] for w in rows[0]], ["FIRE", "DOWNTOWN"])

    def test_deck_joins_same_size_lines_only_when_aligned_and_never_body(self):
        words = self.body() + [
            (20, 100, 60, 30, "FIRE"), (85, 100, 70, 30, "DOWNTOWN"),   # head
            (20, 140, 130, 28, "TONIGHT"),                              # same size, aligned
            (20, 180, 120, 16, "Blaze"), (150, 180, 60, 16, "spreads"), # deck
            (20, 210, 25, 10, "the"), (50, 210, 25, 10, "body"),        # body text
        ]
        rows = items.display_rows(words, 1000)
        seg = rows[0]
        b = items.box_with_deck(seg, words, 700, 1000)
        self.assertGreaterEqual(b[1] + b[3], 196)      # through the deck
        self.assertLess(b[1] + b[3], 210)              # not into the body
        # a same-size line in the next column does not join
        words2 = self.body() + [(20, 100, 60, 30, "FIRE"), (85, 100, 70, 30, "DOWNTOWN"),
                                (400, 140, 130, 28, "OTHER")]
        b2 = items.box_with_deck(items.display_rows(words2, 1000)[0], words2, 700, 1000)
        self.assertLess(b2[1] + b2[3], 140)


class Banners(unittest.TestCase):
    """The Cordele Dispatch of 10 October 1919 shipped "U. S. TO" out of a
    banner across eight columns, and its second banner was left behind."""

    def test_headline_with_an_unread_word_is_refused(self):
        with self.assertRaises(clips.npc.Refused):
            clips._check_transcription("U. S. TO [illegible] COMM[illegible] CAPITAL WOULD", "headline")
        clips._check_transcription("U. S. TO ADD 15 MILLIONS FOR GREAT WORLD AIR ROUTES", "headline")
        # an article is a paragraph and keeps the half rule
        clips._check_transcription("The council met [illegible] night and voted the bonds through.", "article", ad_limit=4)

    def head(self):
        return [(20, 100, 60, 30, "FIRE"), (85, 100, 70, 30, "DOWNTOWN"), (160, 100, 90, 30, "TONIGHT")]

    def test_a_taller_line_beneath_is_another_item_not_a_continuation(self):
        """The Americus Times-Recorder of 9 June 1915: a skyline headline
        above the masthead, and the nameplate beneath it read as its
        second line."""
        body = DisplayRows.body(self)
        nameplate = [(20, 140, 100, 42, "AMERICUS"), (130, 140, 120, 42, "TIMES")]
        words = body + self.head() + nameplate
        b = items.box_with_deck(items.display_rows(words, 1000)[0], words, 700, 1000)
        self.assertLess(b[1] + b[3], 140)

    def test_a_headline_carrying_the_papers_own_name_is_refused(self):
        meta = {"title": "Americus Times-Recorder"}
        with self.assertRaises(clips.npc.Refused):
            clips._refuse_own_title("COUNTRY SOLID IN SUPPORT OF WILSON CITY EDITION AMERICUS TIMES-RECORDER", meta, "headline")
        clips._refuse_own_title("COUNTRY SOLID IN SUPPORT OF WILSON", meta, "headline")   # no raise

    def test_a_second_line_is_judged_by_its_tallest_word_not_word_by_word(self):
        """Seven of the second banner's eight words were under 0.85 of the
        head and one was over: judged per word the line fell in two."""
        body = DisplayRows.body(self)
        second = [(20, 140, 60, 24, "MILLS"), (85, 140, 70, 24, "CLOSE"), (160, 140, 90, 28, "TODAY")]
        words = body + self.head() + second
        b = items.box_with_deck(items.display_rows(words, 1000)[0], words, 700, 1000)
        self.assertGreaterEqual(b[1] + b[3], 168)

    def test_a_tier_of_several_items_is_not_a_deck(self):
        body = DisplayRows.body(self)
        tier = [(20, 140, 60, 18, "CAPITAL"), (85, 140, 60, 18, "WOULD"),
                (200, 140, 60, 18, "MEXICO"), (265, 140, 60, 18, "SENDS")]   # two heads, a wide gap
        words = body + self.head() + tier
        b = items.box_with_deck(items.display_rows(words, 1000)[0], words, 700, 1000)
        self.assertLess(b[1] + b[3], 140)
        deck = [(20, 140, 60, 18, "Blaze"), (85, 140, 60, 18, "spreads")]     # one line
        words = body + self.head() + deck
        b = items.box_with_deck(items.display_rows(words, 1000)[0], words, 700, 1000)
        self.assertGreaterEqual(b[1] + b[3], 158)

    def test_a_row_straddling_the_gutters_is_a_banner_and_is_not_split(self):
        """Ink across a gutter is what tells a banner from column headlines
        set a word space apart; a word space over a gutter is white either
        way."""
        pi = rules.PageInk(BannerPage())
        # the banner's words, one word space over each gutter (430-500, 900-970)
        banner = [(30, 100, 380, 30, "FRENCH"), (440, 100, 440, 30, "COUNTER"), (910, 100, 300, 30, "FOR"), (1220, 100, 150, 30, "KEMMEL")]
        inside, straddled, _ = items.gutter_counts(banner, pi)
        self.assertGreater(len(straddled), len(inside) - len(straddled))
        cands = [(items.box_with_deck(banner, banner, 1400, 2000), banner)]
        out = items.split_at_gutters(cands, banner, 1400, 2000, pi)
        self.assertEqual(len(out), 1)
        # column headlines on a clear row split at the gutters as before
        tier = [(30, 300, 180, 30, "FRENCH"), (215, 300, 200, 30, "DESTROY"), (510, 300, 180, 30, "MEMORIAL"), (700, 300, 100, 30, "DAY")]
        inside, straddled, _ = items.gutter_counts(tier, pi)
        self.assertLessEqual(len(straddled), len(inside) - len(straddled))
        out = items.split_at_gutters([(items.box_with_deck(tier, tier, 1400, 2000), tier)], tier, 1400, 2000, pi)
        self.assertEqual([" ".join(w[4] for w in seg) for _, seg in out], ["FRENCH DESTROY", "MEMORIAL DAY"])


class FakePage:
    """A page whose image is a synthetic newspaper: three columns of grey
    text blocks separated by paper gutters, a rule under one block."""
    lccn, date, ed, seq = "sn00000001", "1890-01-01", 1, 1
    image_w, image_h = 1400, 2000
    url = "https://example/lccn/sn00000001/1890-01-01/ed-1/seq-1/"

    def __init__(self):
        im = Image.new("L", (1400, 2000), 210)
        d = ImageDraw.Draw(im)
        for cx in (0, 470, 940):
            for k, y in enumerate(range(120, 1900, 24)):      # lines of "text",
                jitter = (k * 4) % 9                            # never aligned
                for x in range(cx + 30 + jitter, cx + 430, 9):  # a third dark
                    d.rectangle([x, y, x + 2, y + 12], fill=40)
        d.rectangle([470 + 20, 800, 470 + 440, 803], fill=20)   # a rule in column 2
        d.rectangle([470 + 20, 560, 470 + 440, 563], fill=20)   # and one above
        for y in range(804, 860):                              # paper under it
            d.rectangle([470 + 20, y, 470 + 440, y], fill=210)
        self._im = im
        self.scale = 1.0                                       # OCR units == image px

    def coords(self):
        return {"width": 1400, "height": 2000, "words": []}

    def to_image(self, box):
        x, y, w, h = box
        if w <= 0 or h <= 0:
            raise ValueError("empty box")
        return (int(x), int(y), int(w), int(h))

    def fetch_crop(self, image_box, width=1200):
        x, y, w, h = image_box
        crop = self._im.crop((x, y, x + w, y + h))
        if crop.width != width:
            crop = crop.resize((width, max(1, int(crop.height * width / crop.width))))
        buf = io.BytesIO(); crop.save(buf, format="JPEG", quality=92)
        return buf.getvalue()


class BannerPage(FakePage):
    """FakePage with a banner across all three columns at y 100-130: ink
    across both gutters on that band, paper on every other."""
    def __init__(self):
        super().__init__()
        d = ImageDraw.Draw(self._im)
        d.rectangle([30, 100, 1370, 130], fill=40)   # display type across the page, gutters included
        for x in (200, 700, 1100):                   # word spaces, none over a gutter
            d.rectangle([x, 100, x + 15, 130], fill=210)


class Grid(unittest.TestCase):
    def setUp(self):
        self.pi = rules.PageInk(FakePage())

    def test_column_bounds_stop_at_the_gutters(self):
        # a box inside column 2 (x 470..940 in image px; gutter is 430-500)
        x0, x1 = self.pi.column_bounds(self.pi.from_ocr((600, 300, 100, 200)), mode="column")
        self.assertGreater(x0, self.pi.from_ocr((440, 0, 1, 1))[0])
        self.assertLess(x1, self.pi.from_ocr((960, 0, 1, 1))[0])
        self.assertLessEqual(x0, self.pi.from_ocr((504, 0, 1, 1))[0])

    def test_vertical_walk_stops_at_a_rule(self):
        sb = self.pi.from_ocr((520, 600, 300, 150))
        x0, x1 = self.pi.column_bounds(sb, mode="column")
        vb = self.pi.vertical_bounds(sb, x0, x1, rules_only=True)
        self.assertIsNotNone(vb)
        self.assertLessEqual(vb[1], self.pi.y_small(803))
        self.assertGreater(vb[1], self.pi.y_small(760))

    def test_a_box_in_the_third_column_snaps_to_it(self):
        s = rules.snap(self.pi, (1000, 300, 60, 50), mode="column", rules_only=False)
        self.assertIsNotNone(s)
        self.assertGreaterEqual(s[0], 930)
        self.assertLessEqual(s[0] + s[2], 1400)


class RuleIsolation(unittest.TestCase):
    """clips.row_has_rule: a rule is an ISOLATED dark row with paper close
    on both sides, not any row past a bare darkness floor. Both arrays
    below are pi.row_dark() readings taken directly off the Augusta Herald
    of 19 February 1918, 13 September 2026 -- the incident that prompted
    the isolation rule, not synthetic data. The old bare
    `any(d >= HRULE_MIN_DARK)` test got both backwards from one threshold:
    it missed the real rule (peak 0.430, just under 0.45) and caught the
    false one (peak 0.475, just over it)."""

    class FakePI:
        """Duck-types just enough of rules.PageInk for row_has_rule: OCR
        space equals small-image space, and row_dark returns a canned
        reading keyed by y regardless of x0/x1."""
        def __init__(self, dark_by_y):
            self._dark = dark_by_y

        def y_small(self, y):
            return y

        def row_dark(self, x0, x1, y0, y1):
            return [self._dark.get(y, 0.0) for y in range(y0, y1)]

    # "New York.--The cotton market...renewed steadiness..." on the
    # Augusta Herald: two tight-leaded body lines with no rule between
    # them at all.
    FALSE_RULE = {
        552: 0.000, 553: 0.000, 554: 0.134, 555: 0.006, 556: 0.000,
        557: 0.000, 558: 0.000, 559: 0.128, 560: 0.430, 561: 0.475,
        562: 0.413, 563: 0.307, 564: 0.000, 565: 0.000, 566: 0.050,
        567: 0.318, 568: 0.458, 569: 0.380, 570: 0.341, 571: 0.028,
        572: 0.000, 573: 0.078, 574: 0.330, 575: 0.464, 576: 0.358,
    }

    # "...December 27.85" -> "PRODUCE MARKET" on the same page: the real
    # printed rule above that section heading.
    REAL_RULE = {
        678: 0.017, 679: 0.078, 680: 0.151, 681: 0.134, 682: 0.106,
        683: 0.117, 684: 0.006, 685: 0.000, 686: 0.000, 687: 0.000,
        688: 0.000, 689: 0.430, 690: 0.011, 691: 0.000, 692: 0.006,
        693: 0.335, 694: 0.436, 695: 0.285, 696: 0.279, 697: 0.324,
    }

    def test_tight_body_text_leading_is_not_read_as_a_rule(self):
        pi = self.FakePI(self.FALSE_RULE)
        self.assertFalse(clips.row_has_rule(pi, 0, 1, 558, 571))

    def test_a_real_rule_below_the_old_bare_threshold_is_still_found(self):
        pi = self.FakePI(self.REAL_RULE)
        self.assertTrue(clips.row_has_rule(pi, 0, 1, 684, 692))

    def test_an_all_paper_gap_has_no_rule(self):
        pi = self.FakePI({})
        self.assertFalse(clips.row_has_rule(pi, 0, 1, 100, 120))

    def test_an_isolated_spike_with_clear_paper_either_side_is_a_rule(self):
        dark = {y: 0.0 for y in range(90, 111)}
        dark[100] = 0.9
        pi = self.FakePI(dark)
        self.assertTrue(clips.row_has_rule(pi, 0, 1, 96, 104))


class MarketSectionPage:
    """A synthetic page with TWO market sections stacked in one column:
    each a tall boxed heading with a real printed rule above it, a
    body-height subhead partway down, and tabular body rows -- the shape
    the market lane's section walk (13 September 2026) is meant to cross,
    stopping at the SECOND section's own heading rather than running into
    it or stopping short at the first subhead.

    ⚠️ image_w stays exactly PAGE_WIDTH (1400): PageInk always fetches at
    that width, and a fixture whose image is already that wide is never
    resized, keeping OCR space and small-image space identical (scale
    1.0) the way FakePage's own fixture relies on. image_h is shrunk
    instead, to keep the column's own ink a large enough share of the
    page for column_bounds to read it as ink rather than as more paper."""
    lccn, date, ed, seq = "sn00000002", "1900-01-01", 1, 1
    image_w, image_h = 1400, 450
    url = "https://example/lccn/sn00000002/1900-01-01/ed-1/seq-1/"
    COL_X0, COL_X1 = 470, 940     # matches FakePage's column 2

    def __init__(self):
        from PIL import Image, ImageDraw
        im = Image.new("L", (1400, self.image_h), 210)
        d = ImageDraw.Draw(im)
        words = []

        # filler "text" in the columns either side, same shape as
        # FakePage's, so column_bounds finds a real gutter on both sides
        # of the market column rather than running to the page edge.
        for cx in (0, 940):
            for k, y in enumerate(range(20, self.image_h - 20, 20)):
                jitter = (k * 4) % 9
                for x in range(cx + 30 + jitter, cx + 430, 9):
                    d.rectangle([x, y, x + 2, y + 10], fill=40)

        def draw_row(x, y, h, text):
            # a full-width bar under the row (what a real printed line
            # of type inks across its column, for the pixel-level rule
            # and gutter tests) plus one word box per space-separated
            # token on top, at the OCR-realistic positions find_phrase
            # and the row grouping actually need -- find_phrase matches
            # consecutive WORDS, not a substring of one merged string.
            d.rectangle([self.COL_X0 + 10, y, self.COL_X1 - 10, y + h], fill=120)
            cx = x
            for tok in text.split():
                w = max(20, len(tok) * 14)
                d.rectangle([cx, y, cx + w, y + h], fill=30)
                words.append((cx, y, w, h, tok))
                cx += w + 8

        def rule(y):
            d.rectangle([self.COL_X0 + 10, y, self.COL_X1 - 10, y + 3], fill=20)

        BODY_H = 14
        HEAD_H = 40

        def heading(y, text):
            rule(y - 20)                            # clear paper either side
            draw_row(self.COL_X0 + 20, y, HEAD_H, text)
            return y + HEAD_H + 10

        def body_row(y, text):
            draw_row(self.COL_X0 + 20, y, BODY_H, text)
            return y + BODY_H + 6

        y = heading(40, "MARKET ONE")
        for i in range(3):
            y = body_row(y, f"PRICE {10 + i} AND {20 + i}")
        y = body_row(y, "SUBHEAD A")                 # body-height, non-display
        for i in range(3):
            y = body_row(y, f"QUOTE {30 + i} FOR {40 + i}")
        y = heading(y + 30, "MARKET TWO")
        for i in range(3):
            y = body_row(y, f"RATE {50 + i} TO {60 + i}")

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


class MarketSectionWalk(unittest.TestCase):
    def setUp(self):
        self.page = MarketSectionPage()
        self.coords = self.page.coords()
        self.pi = rules.PageInk(self.page)

    def _box_for(self, phrase):
        hit = clips.find_phrase(self.coords["words"], phrase)
        self.assertIsNotNone(hit, phrase)
        return clips.block_around(self.pi, self.coords, hit, allow_display=False,
                                  max_frac=clips.MARKET_MAX_FRAC)

    def test_the_crop_starts_at_its_own_heading_not_a_prior_sections_tail(self):
        box = self._box_for("market one")
        self.assertIsNotNone(box)
        words_in = clips.nameplate.words_in(self.coords["words"], box)
        text = clips.ocr_text(words_in)
        self.assertIn("MARKET ONE", text)

    def test_the_crop_runs_past_a_subhead_to_the_next_sections_heading(self):
        box = self._box_for("market one")
        words_in = clips.nameplate.words_in(self.coords["words"], box)
        text = clips.ocr_text(words_in)
        self.assertIn("SUBHEAD A", text)             # a within-section subhead: kept
        self.assertIn("QUOTE 30", text)               # the rows after it: kept
        self.assertNotIn("MARKET TWO", text)           # the NEXT section: not swallowed
        self.assertNotIn("RATE 50", text)

    def test_a_hit_in_the_second_section_does_not_reach_back_into_the_first(self):
        box = self._box_for("market two")
        words_in = clips.nameplate.words_in(self.coords["words"], box)
        text = clips.ocr_text(words_in)
        self.assertIn("MARKET TWO", text)
        self.assertNotIn("QUOTE 30", text)
        self.assertNotIn("MARKET ONE", text)


class FlatHeadingPage(MarketSectionPage):
    """The same two-section shape as MarketSectionPage, but with NEITHER a
    rule between the sections NOR a heading tall enough to read as display
    (18px against a 14px body -- 1.29x, under is_display's 1.6x floor):
    the shape of the Savannah Morning News of 18 April 1873, where
    "Sandersville Prices Current" measured 1.37x its page median and nothing
    else separated it from the unrelated advertisement above it either.
    Only the paragraph-gap guard can catch a section boundary here."""
    lccn, date = "sn00000003", "1900-01-02"

    def __init__(self):
        from PIL import Image, ImageDraw
        im = Image.new("L", (1400, self.image_h), 210)
        d = ImageDraw.Draw(im)
        words = []

        for cx in (0, 940):
            for k, y in enumerate(range(20, self.image_h - 20, 20)):
                jitter = (k * 4) % 9
                for x in range(cx + 30 + jitter, cx + 430, 9):
                    d.rectangle([x, y, x + 2, y + 10], fill=40)

        def draw_row(x, y, h, text):
            d.rectangle([self.COL_X0 + 10, y, self.COL_X1 - 10, y + h], fill=120)
            cx = x
            for tok in text.split():
                w = max(20, len(tok) * 14)
                d.rectangle([cx, y, cx + w, y + h], fill=30)
                words.append((cx, y, w, h, tok))
                cx += w + 8

        BODY_H = 14
        HEAD_H = 18                                   # NOT tall enough to be "display"

        def heading(y, text):                          # no rule() call at all
            draw_row(self.COL_X0 + 20, y, HEAD_H, text)
            return y + HEAD_H + 10

        def body_row(y, text):
            draw_row(self.COL_X0 + 20, y, BODY_H, text)
            return y + BODY_H + 6

        y = heading(40, "MARKET ONE")
        for i in range(3):
            y = body_row(y, f"PRICE {10 + i} AND {20 + i}")
        # a gap over PARA_GAP*med (~18) but under the walk's own hard
        # 2.2*med cutoff (~31) -- big enough that only the paragraph-gap
        # guard this test exists to pin can catch it, small enough that
        # it looks like ordinary extra lead rather than a different item.
        y = heading(y + 15, "MARKET TWO")
        for i in range(3):
            y = body_row(y, f"RATE {50 + i} TO {60 + i}")

        self._im = im
        self._words = words
        self.scale = 1.0


class MarketSectionWalkNoRuleNoDisplay(unittest.TestCase):
    """The paragraph-gap guard (13 September 2026) is what has to catch
    this shape, since neither of the other two signals fire."""
    def setUp(self):
        self.page = FlatHeadingPage()
        self.coords = self.page.coords()
        self.pi = rules.PageInk(self.page)

    def test_the_gap_alone_stops_the_climb_at_the_next_sections_heading(self):
        hit = clips.find_phrase(self.coords["words"], "market two")
        box = clips.block_around(self.pi, self.coords, hit, allow_display=False,
                                 max_frac=clips.MARKET_MAX_FRAC)
        self.assertIsNotNone(box)
        words_in = clips.nameplate.words_in(self.coords["words"], box)
        text = clips.ocr_text(words_in)
        self.assertIn("MARKET TWO", text)
        self.assertNotIn("MARKET ONE", text)            # the whole point: no reach-back
        self.assertNotIn("PRICE 10", text)


class AdHeadingGapPage:
    """One column holding a single item: a display heading, then a gap far
    wider than any ordinary body-line leading, then plain body rows -- the
    shape of "Important to the Public" over "GO TO COOKE'S..." on the Daily
    Constitutionalist of 1 October 1872 (the ad his 14 September 2026 crop
    complaint was about). The real gap there measured 652 units against a
    94-unit page median, 6.9x; HEAD_GAP below is sized the same way, well
    past the walk's ordinary 2.2x body-line ceiling.

    ⚠️ image_h is 1000, not bigger: column_bounds' own gutter detection
    reads darkness averaged over the WHOLE page height, and a page tall
    enough to dilute this fixture's sparse content below GUTTER_DARK reads
    the ad's own column as more paper -- at image_h 1200 column_bounds
    returned (31, 1371), nearly the whole page, instead of the ad's own
    (480, 931). 1000 keeps both real: enough headroom under the up-walk's
    own 0.25-of-page height cap for HEAD_GAP to clear it, and enough ink
    density in the column for the gutters on either side to still read."""
    lccn, date, ed, seq = "sn00000005", "1900-01-04", 1, 1
    image_w, image_h = 1400, 1000
    url = "https://example/lccn/sn00000005/1900-01-04/ed-1/seq-1/"
    COL_X0, COL_X1 = 470, 940

    def __init__(self):
        from PIL import Image, ImageDraw
        im = Image.new("L", (1400, self.image_h), 210)
        d = ImageDraw.Draw(im)
        words = []

        for cx in (0, 940):
            for k, y in enumerate(range(20, self.image_h - 20, 20)):
                jitter = (k * 4) % 9
                for x in range(cx + 30 + jitter, cx + 430, 9):
                    d.rectangle([x, y, x + 2, y + 10], fill=40)

        def draw_row(x, y, h, text):
            d.rectangle([self.COL_X0 + 10, y, self.COL_X1 - 10, y + h], fill=120)
            cx = x
            for tok in text.split():
                w = max(20, len(tok) * 14)
                d.rectangle([cx, y, cx + w, y + h], fill=30)
                words.append((cx, y, w, h, tok))
                cx += w + 8

        HEAD_H, BODY_H, HEAD_GAP = 40, 14, 100   # HEAD_GAP >> 2.2 * a 14-unit median

        draw_row(self.COL_X0 + 20, 40, HEAD_H, "AD HEADING")
        y = 40 + HEAD_H + HEAD_GAP
        for i in range(4):
            draw_row(self.COL_X0 + 20, y, BODY_H, f"BODY LINE {i}")
            y += BODY_H + 6

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


class AdHeadingGap(unittest.TestCase):
    """block_around's up-walk, allow_display=True: an ad's own display
    heading must be admitted whatever the gap below it, per the function's
    own docstring ("allow_display keeps display-size rows"). Before the fix
    the plain `gap > 2.2 * med` test broke the climb before allow_display
    ever got a say, and the Cooke's clothing ad shipped on Bluesky missing
    "Important to the Public" entirely."""
    def setUp(self):
        self.page = AdHeadingGapPage()
        self.coords = self.page.coords()
        self.pi = rules.PageInk(self.page)
        self.hit = clips.find_phrase(self.coords["words"], "body line 0")
        self.assertIsNotNone(self.hit)

    def test_the_heading_is_admitted_across_the_wide_gap_when_allow_display(self):
        box = clips.block_around(self.pi, self.coords, self.hit, allow_display=True)
        self.assertIsNotNone(box)
        words_in = clips.nameplate.words_in(self.coords["words"], box)
        text = clips.ocr_text(words_in)
        self.assertIn("AD HEADING", text)
        self.assertIn("BODY LINE 0", text)

    def test_the_same_wide_gap_still_stops_the_climb_without_allow_display(self):
        # allow_display=False is the market lane's call, never the ad
        # lane's, but the gate must hold: the new allowance is keyed to
        # is_display(j) AND allow_display, not to is_display(j) alone.
        box = clips.block_around(self.pi, self.coords, self.hit, allow_display=False)
        self.assertIsNotNone(box)
        words_in = clips.nameplate.words_in(self.coords["words"], box)
        text = clips.ocr_text(words_in)
        self.assertNotIn("AD HEADING", text)
        self.assertIn("BODY LINE 0", text)


class AdTailGapPage:
    """Mirror of AdHeadingGapPage for the DOWN-walk: plain body rows, then
    a gap far wider than any ordinary body-line leading, then a display
    CLOSING signature -- the shape of "Children Cry For / K CASTORIA" at
    the foot of a Castoria ad (sn89053972, 15 September 1919), found by
    crop_closure_check.py's own first live run the same day the up-walk
    fix shipped. Same image_h=1000 constraint as AdHeadingGapPage, same
    reason."""
    lccn, date, ed, seq = "sn00000008", "1900-01-07", 1, 1
    image_w, image_h = 1400, 1000
    url = "https://example/lccn/sn00000008/1900-01-07/ed-1/seq-1/"
    COL_X0, COL_X1 = 470, 940

    def __init__(self):
        from PIL import Image, ImageDraw
        im = Image.new("L", (1400, self.image_h), 210)
        d = ImageDraw.Draw(im)
        words = []

        for cx in (0, 940):
            for k, y in enumerate(range(20, self.image_h - 20, 20)):
                jitter = (k * 4) % 9
                for x in range(cx + 30 + jitter, cx + 430, 9):
                    d.rectangle([x, y, x + 2, y + 10], fill=40)

        def draw_row(x, y, h, text):
            d.rectangle([self.COL_X0 + 10, y, self.COL_X1 - 10, y + h], fill=120)
            cx = x
            for tok in text.split():
                w = max(20, len(tok) * 14)
                d.rectangle([cx, y, cx + w, y + h], fill=30)
                words.append((cx, y, w, h, tok))
                cx += w + 8

        TAIL_H, BODY_H, TAIL_GAP = 40, 14, 100   # TAIL_GAP >> 2.2 * a 14-unit median
        y = 40
        for i in range(4):
            draw_row(self.COL_X0 + 20, y, BODY_H, f"BODY LINE {i}")
            y += BODY_H + 6
        y += TAIL_GAP
        draw_row(self.COL_X0 + 20, y, TAIL_H, "AD SIGNATURE")

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


class AdTailGap(unittest.TestCase):
    """block_around's down-walk, allow_display=True: an ad's own CLOSING
    signature must be admitted whatever the gap above it, mirroring
    AdHeadingGap. Before this fix (15 September 2026, same day as the
    up-walk one) the Castoria ad's "K CASTORIA" wordmark shipped cut off
    the same way "Important to the Public" had."""
    def setUp(self):
        self.page = AdTailGapPage()
        self.coords = self.page.coords()
        self.pi = rules.PageInk(self.page)
        self.hit = clips.find_phrase(self.coords["words"], "body line 0")
        self.assertIsNotNone(self.hit)

    def test_the_signature_is_admitted_across_the_wide_gap_when_allow_display(self):
        box = clips.block_around(self.pi, self.coords, self.hit, allow_display=True)
        self.assertIsNotNone(box)
        words_in = clips.nameplate.words_in(self.coords["words"], box)
        text = clips.ocr_text(words_in)
        self.assertIn("AD SIGNATURE", text)
        self.assertIn("BODY LINE 0", text)

    def test_the_same_wide_gap_still_stops_the_climb_without_allow_display(self):
        box = clips.block_around(self.pi, self.coords, self.hit, allow_display=False)
        self.assertIsNotNone(box)
        words_in = clips.nameplate.words_in(self.coords["words"], box)
        text = clips.ocr_text(words_in)
        self.assertNotIn("AD SIGNATURE", text)
        self.assertIn("BODY LINE 0", text)


class BannerHeadingPage:
    """A banner heading ("BANNER HEAD") set across two narrower columns,
    each holding its OWN unrelated content at the SAME row heights, split
    by a real vertical rule -- the shape of "COTTON MARKET" on the Augusta
    Herald of 19 February 1918, which is a banner over an Augusta cotton
    price table on the left and, on the right, an unrelated advertisement
    then a different cotton report. Same-height rows on both sides are
    what make nameplate.rows_of merge them into one nonsense row without
    the split ("AUGUSTACOTTON COTTONSEED FOR" was one such row, on the
    real page)."""
    lccn, date, ed, seq = "sn00000004", "1900-01-03", 1, 1
    # ⚠️ image_h and the rule's own length are both sized deliberately,
    # not just "big enough": PageInk's vrules() excludes any column
    # averaging above EDGE_DARK(0.55) of the WHOLE page as "film edge"
    # (a solid synthetic rule spanning most of a short page trips this --
    # the real Augusta Herald rule this fixture is modelled on averaged
    # only 0.20 dark despite a "run" 1655px long, because a real printed
    # rule is thin and imperfectly inked at small-image resolution, so a
    # short, solid stand-in rule must be sized to land in the same range
    # a real one measures in, not merely long enough for MIN_VRULE), while
    # column_bounds' own gutter detection needs the CONTENT column dark
    # enough on average to read as ink at all (above GUTTER_DARK 0.10) --
    # which is why there are a dozen body rows, not four: enough inked
    # height for that average to clear the floor on a page tall enough
    # to keep the rule's average under its own ceiling.
    image_w, image_h = 1400, 1000
    url = "https://example/lccn/sn00000004/1900-01-03/ed-1/seq-1/"
    COL_X0, COL_X1 = 470, 940       # the banner's own full width
    SPLIT_X = 705                    # the interior rule's OCR x
    ROWS = 12

    def __init__(self):
        from PIL import Image, ImageDraw
        im = Image.new("L", (1400, self.image_h), 210)
        d = ImageDraw.Draw(im)
        words = []

        for cx in (0, 940):
            for k, y in enumerate(range(20, self.image_h - 20, 20)):
                jitter = (k * 4) % 9
                for x in range(cx + 30 + jitter, cx + 430, 9):
                    d.rectangle([x, y, x + 2, y + 10], fill=40)

        def draw_row(x, y, h, text, x1=None):
            d.rectangle([x, y, (x1 or self.COL_X1 - 10), y + h], fill=120)
            cx = x
            for tok in text.split():
                w = max(20, len(tok) * 14)
                d.rectangle([cx, y, cx + w, y + h], fill=30)
                words.append((cx, y, w, h, tok))
                cx += w + 8

        HEAD_H = 40
        BODY_H = 14

        # the banner: one heading straddling both sub-columns
        draw_row(self.COL_X0 + 20, 40, HEAD_H, "BANNER HEAD")

        # the interior rule, well below the heading's own bottom and
        # comfortably past the content zone, but not the whole page
        d.rectangle([self.SPLIT_X, 100, self.SPLIT_X + 2, 400], fill=20)

        # two unrelated streams at the SAME row y-positions either side
        y = 95   # a proportionate heading-to-body gap: ~1.1x med (14), not
                 # the 60px a literal "140" made -- 4.3x med, which tripped
                 # block_around's own unconditional 2.2x hard gap cutoff
        for i in range(self.ROWS):
            draw_row(self.COL_X0 + 20, y, BODY_H, f"LEFT {i}", x1=self.SPLIT_X - 10)
            draw_row(self.SPLIT_X + 20, y, BODY_H, f"RIGHT {i}", x1=self.COL_X1 - 10)
            y += BODY_H + 6

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


class NearEdgeBannerHeadingPage(BannerHeadingPage):
    """The same banner shape, but with its interior rule sitting close to
    the LEFT edge of the banner's own bounds -- the shape of a boxed
    display ad's own decorative border rule, not a genuine two-column
    banner divider. "sarsaparilla" on the Augusta Chronicle of 10-18 May
    1871 (the same title, five dates) measured this at 3.0-6.1% of the
    banner's width; SPLIT_X here sits at 4.3% (20 of 470), comfortably
    inside that range and MIN_SPLIT_FRAC's own 30% floor."""
    lccn, date = "sn00000006", "1900-01-05"
    SPLIT_X = 505    # 35 of 470 = 7.4% from COL_X0 -- a border, not a banner


class AdWithNeighborsPage:
    """One column: a confidently-excluded row well above the ad (a large,
    over-2.2x-median gap, no rule), four ad-body rows, then a
    confidently-excluded row well below -- for closure_margins()'s
    healthy, non-flagged case. image_h stays at 700, the same "not too
    tall to dilute the column's own ink density" constraint as
    AdHeadingGapPage and BannerHeadingPage."""
    lccn, date, ed, seq = "sn00000007", "1900-01-06", 1, 1
    image_w, image_h = 1400, 700
    url = "https://example/lccn/sn00000007/1900-01-06/ed-1/seq-1/"
    COL_X0, COL_X1 = 470, 940

    def __init__(self):
        from PIL import Image, ImageDraw
        im = Image.new("L", (1400, self.image_h), 210)
        d = ImageDraw.Draw(im)
        words = []

        for cx in (0, 940):
            for k, y in enumerate(range(20, self.image_h - 20, 20)):
                jitter = (k * 4) % 9
                for x in range(cx + 30 + jitter, cx + 430, 9):
                    d.rectangle([x, y, x + 2, y + 10], fill=40)

        def draw_row(x, y, h, text):
            d.rectangle([self.COL_X0 + 10, y, self.COL_X1 - 10, y + h], fill=120)
            cx = x
            for tok in text.split():
                w = max(20, len(tok) * 14)
                d.rectangle([cx, y, cx + w, y + h], fill=30)
                words.append((cx, y, w, h, tok))
                cx += w + 8

        BODY_H, GAP = 14, 60   # GAP >> 2.2 * a 14-unit median
        draw_row(self.COL_X0 + 20, 40, BODY_H, "EARLIER ITEM TAIL")
        y = 40 + BODY_H + GAP
        for i in range(4):
            draw_row(self.COL_X0 + 20, y, BODY_H, f"AD BODY LINE {i}")
            y += BODY_H + 6
        y += GAP
        draw_row(self.COL_X0 + 20, y, BODY_H, "LATER ITEM HEAD")

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


class MarketNeighborsPage:
    """One market column: a display heading immediately above with only a
    SMALL gap and no rule (market's own display-boundary case -- a
    display row the up-walk excludes purely because allow_display is
    False, whatever the gap), then the seed row and three more body rows,
    then a further row spaced just past PARA_GAP*med with the down-walk's
    own 3-row grace period satisfied (market's paragraph-gap case)."""
    lccn, date, ed, seq = "sn00000010", "1900-01-09", 1, 1
    image_w, image_h = 1400, 700
    url = "https://example/lccn/sn00000010/1900-01-09/ed-1/seq-1/"
    COL_X0, COL_X1 = 470, 940

    def __init__(self):
        from PIL import Image, ImageDraw
        im = Image.new("L", (1400, self.image_h), 210)
        d = ImageDraw.Draw(im)
        words = []

        for cx in (0, 940):
            for k, y in enumerate(range(20, self.image_h - 20, 20)):
                jitter = (k * 4) % 9
                for x in range(cx + 30 + jitter, cx + 430, 9):
                    d.rectangle([x, y, x + 2, y + 10], fill=40)

        def draw_row(x, y, h, text):
            d.rectangle([self.COL_X0 + 10, y, self.COL_X1 - 10, y + h], fill=120)
            cx = x
            for tok in text.split():
                w = max(20, len(tok) * 14)
                d.rectangle([cx, y, cx + w, y + h], fill=30)
                words.append((cx, y, w, h, tok))
                cx += w + 8

        HEAD_H, BODY_H, SMALL_GAP = 40, 14, 10   # SMALL_GAP << 2.2 * a 14-unit median
        draw_row(self.COL_X0 + 20, 40, HEAD_H, "PREV HEADING")
        y = 40 + HEAD_H + SMALL_GAP
        draw_row(self.COL_X0 + 20, y, BODY_H, "MARKET BODY ZERO")   # the seed row
        y += BODY_H + 6
        for i in (1, 2, 3):
            draw_row(self.COL_X0 + 20, y, BODY_H, f"MARKET BODY {i}")
            y += BODY_H + 6
        y += 16   # total gap to the next row: 22, between PARA_GAP*med (18.2) and 2.2*med (30.8)
        draw_row(self.COL_X0 + 20, y, BODY_H, "NEXT ITEM HEAD")

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


class ClosureMargins(unittest.TestCase):
    """closure_margins() is advisory-only and never gates a post. Since
    15 September 2026 it runs block_around ITSELF (with instrumentation
    on) rather than reconstructing a reason from an already-finished box
    -- these pin what it reports for the shapes a periodic audit needs to
    tell apart, in both lanes."""

    def test_a_confidently_excluded_neighbor_reports_a_healthy_positive_ratio(self):
        page = AdWithNeighborsPage()
        coords = page.coords()
        pi = rules.PageInk(page)
        hit = clips.find_phrase(coords["words"], "ad body line 0")
        margins = clips.closure_margins(pi, coords, hit, allow_display=True)
        self.assertIsNotNone(margins)
        self.assertEqual(margins["top"]["reason"], "gap")
        self.assertGreater(margins["top"]["ratio"], 0.5)
        self.assertEqual(margins["bottom"]["reason"], "gap")
        self.assertGreater(margins["bottom"]["ratio"], 0.5)

    def test_a_neighbor_across_a_printed_rule_reports_rule_not_gap(self):
        # A gap over 2.2*med is checked FIRST in block_around's own real
        # precedence (short-circuit: rule_test is never even called once
        # the gap alone is enough to stop it), so a "rule" reason can only
        # be reached where the gap itself is small -- MarketNeighborsPage's
        # own top boundary (a 10-unit gap, well under 2.2*med) is exactly
        # that shape. A forced-True stub keyed on that gap's own width (no
        # other gap in this fixture is 10 units) fires ONLY there, so the
        # rest of the walk still runs on its real gaps and produces a real
        # box rather than refusing outright the way an unconditional
        # forced-True stub does (it stops every direction on its very
        # first candidate).
        page = MarketNeighborsPage()
        coords = page.coords()
        pi = rules.PageInk(page)
        hit = clips.find_phrase(coords["words"], "market body zero")
        margins = clips.closure_margins(
            pi, coords, hit, allow_display=False, max_frac=clips.MARKET_MAX_FRAC,
            rule_test=lambda pi, sx0, sx1, ya, yb: (yb - ya) == 10)
        self.assertIsNotNone(margins)
        self.assertEqual(margins["top"]["reason"], "rule")
        self.assertIsNone(margins["top"]["ratio"])
        self.assertIn("PREV HEADING", margins["top"]["text"])

    def test_no_neighbor_reports_none_rather_than_a_fabricated_ratio(self):
        page = AdHeadingGapPage()
        coords = page.coords()
        pi = rules.PageInk(page)
        hit = clips.find_phrase(coords["words"], "body line 0")
        margins = clips.closure_margins(pi, coords, hit, allow_display=True)
        self.assertIsNotNone(margins)
        self.assertIsNone(margins["top"])       # AD HEADING is INSIDE the box
        self.assertIsNone(margins["bottom"])    # nothing below BODY LINE 3

    def test_none_is_returned_when_the_crop_itself_is_refused(self):
        # An empty page: block_around finds no rows at all and refuses,
        # so closure_margins has no box to have diagnosed anything about.
        page = MarketSectionPage()
        coords = page.coords()
        coords["words"] = []
        pi = rules.PageInk(page)
        margins = clips.closure_margins(pi, coords, [(0, 0, 10, 10, "x")], allow_display=True)
        self.assertIsNone(margins)

    def test_the_ad_lanes_own_display_tail_admission_leaves_nothing_to_flag(self):
        # The REAL, correct call (allow_display=True): AD SIGNATURE is
        # already inside the box via the display-tail allowance, so there
        # is nothing outside that edge to report at all -- the shape the
        # 15 September Castoria fix produces on a real post.
        page = AdTailGapPage()
        coords = page.coords()
        pi = rules.PageInk(page)
        hit = clips.find_phrase(coords["words"], "body line 0")
        margins = clips.closure_margins(pi, coords, hit, allow_display=True)
        self.assertIsNotNone(margins)
        self.assertIsNone(margins["bottom"])

    def test_a_display_row_excluded_by_the_cap_reports_cap_not_a_near_miss(self):
        # Found on closure_margins' own first live run, 15 September 2026:
        # a Castoria ad's closing wordmark was correctly admitted by the
        # down-walk fix, and the UNRELATED item below it was correctly
        # excluded by the block-height cap. A tiny max_frac forces the
        # same shape here: admitting "AD SIGNATURE" would exceed it, so
        # the walk itself stops there and reports "cap" directly -- no
        # separate "display-excluded-by-cap" category is needed once the
        # reason comes from the walk itself rather than a reconstruction.
        page = AdTailGapPage()
        coords = page.coords()
        pi = rules.PageInk(page)
        hit = clips.find_phrase(coords["words"], "body line 0")
        # 0.08: small enough to exclude "AD SIGNATURE" via the cap, large
        # enough that the four body rows themselves still clear
        # MIN_BLOCK_ROWS and the walk doesn't refuse outright.
        margins = clips.closure_margins(pi, coords, hit, allow_display=True, max_frac=0.08)
        self.assertIsNotNone(margins)
        self.assertEqual(margins["bottom"]["reason"], "cap")
        self.assertIsNone(margins["bottom"]["ratio"])
        self.assertIn("AD SIGNATURE", margins["bottom"]["text"])

    def test_market_excludes_a_close_display_heading_as_a_boundary_not_a_near_miss(self):
        page = MarketNeighborsPage()
        coords = page.coords()
        pi = rules.PageInk(page)
        hit = clips.find_phrase(coords["words"], "market body zero")
        margins = clips.closure_margins(pi, coords, hit, allow_display=False,
                                        max_frac=clips.MARKET_MAX_FRAC)
        self.assertIsNotNone(margins)
        self.assertEqual(margins["top"]["reason"], "display-boundary")
        self.assertIsNone(margins["top"]["ratio"])
        self.assertIn("PREV HEADING", margins["top"]["text"])

    def test_market_stops_at_its_own_narrower_paragraph_gap_ceiling(self):
        page = MarketNeighborsPage()
        coords = page.coords()
        pi = rules.PageInk(page)
        hit = clips.find_phrase(coords["words"], "market body zero")
        margins = clips.closure_margins(pi, coords, hit, allow_display=False,
                                        max_frac=clips.MARKET_MAX_FRAC)
        self.assertIsNotNone(margins)
        self.assertEqual(margins["bottom"]["reason"], "paragraph-gap")
        self.assertGreater(margins["bottom"]["ratio"], 0)
        self.assertIn("NEXT ITEM HEAD", margins["bottom"]["text"])

    def test_market_row_count_cap_is_confident_not_flagged(self):
        # MARKET_ROWS is an 80-row backstop, impractical to reach with a
        # real pixel fixture -- lowered here just for this test (with
        # MIN_BLOCK_ROWS too, so the smaller box it produces still clears
        # the floor rather than refusing outright), the cheapest way to
        # exercise the branch directly.
        page = MarketNeighborsPage()
        coords = page.coords()
        pi = rules.PageInk(page)
        hit = clips.find_phrase(coords["words"], "market body zero")
        orig_rows, orig_min = clips.MARKET_ROWS, clips.MIN_BLOCK_ROWS
        clips.MARKET_ROWS, clips.MIN_BLOCK_ROWS = 2, 1
        try:
            margins = clips.closure_margins(pi, coords, hit, allow_display=False,
                                            max_frac=clips.MARKET_MAX_FRAC)
        finally:
            clips.MARKET_ROWS, clips.MIN_BLOCK_ROWS = orig_rows, orig_min
        self.assertIsNotNone(margins)
        self.assertEqual(margins["bottom"]["reason"], "row-count-cap")
        self.assertIsNone(margins["bottom"]["ratio"])


class WideHeadingSplit(unittest.TestCase):
    def setUp(self):
        self.page = BannerHeadingPage()
        self.coords = self.page.coords()
        self.pi = rules.PageInk(self.page)
        self.hit = clips.find_phrase(self.coords["words"], "banner head")
        self.assertIsNotNone(self.hit)

    def _seed_box(self):
        x0 = min(w[0] for w in self.hit); x1 = max(w[0] + w[2] for w in self.hit)
        y0 = min(w[1] for w in self.hit); y1 = max(w[1] + w[3] for w in self.hit)
        return x0, y0, x1 - x0, y1 - y0

    def test_wide_heading_split_finds_the_interior_rule(self):
        x0, y0, w, h = self._seed_box()
        cb = self.pi.column_bounds(self.pi.from_ocr((x0, y0, w, h)), mode="column")
        split = clips.wide_heading_split(self.pi, cb, self.pi.y_small(y0), self.pi.y_small(y0 + h))
        self.assertIsNotNone(split)
        self.assertEqual(split[0], cb[0])
        self.assertLess(split[1], cb[1])

    def test_without_the_split_both_sides_merge_into_one_nonsense_row(self):
        box = clips.block_around(self.pi, self.coords, self.hit, allow_display=False,
                                 max_frac=clips.MARKET_MAX_FRAC)
        # split_wide_headings defaults False: reproduces the bug
        if box is not None:
            words_in = clips.nameplate.words_in(self.coords["words"], box)
            text = clips.ocr_text(words_in)
            self.assertIn("RIGHT 0", text)         # both sides present...
            self.assertIn("LEFT 0", text)
            self.assertTrue(text.index("LEFT 0") < text.index("RIGHT 0") or
                            "LEFT 0 RIGHT 0" in text or "RIGHT 0 LEFT 0" in text)

    def test_with_the_split_only_the_left_columns_content_is_kept(self):
        box = clips.block_around(self.pi, self.coords, self.hit, allow_display=False,
                                 max_frac=clips.MARKET_MAX_FRAC, split_wide_headings=True)
        self.assertIsNotNone(box)
        words_in = clips.nameplate.words_in(self.coords["words"], box)
        text = clips.ocr_text(words_in)
        self.assertIn("BANNER", text)
        self.assertIn("LEFT 0", text)
        self.assertIn("LEFT 3", text)
        self.assertNotIn("RIGHT", text)                # the unrelated column: gone entirely

    def test_an_ordinary_single_column_heading_is_untouched_by_the_flag(self):
        # split_wide_headings=True must be a no-op wherever there is
        # nothing to split -- MarketSectionPage has no interior rule at
        # all, so passing the flag must produce the identical box.
        page = MarketSectionPage()
        coords = page.coords()
        pi = rules.PageInk(page)
        hit = clips.find_phrase(coords["words"], "market one")
        with_flag = clips.block_around(pi, coords, hit, allow_display=False,
                                       max_frac=clips.MARKET_MAX_FRAC, split_wide_headings=True)
        without_flag = clips.block_around(pi, coords, hit, allow_display=False,
                                          max_frac=clips.MARKET_MAX_FRAC)
        self.assertIsNotNone(with_flag)
        self.assertEqual(with_flag, without_flag)

    def test_the_ad_lane_gets_the_same_split_when_allow_display_is_true(self):
        # 15 September 2026: wired into clip_ad too, once measured. Same
        # fixture, same assertion as the market-lane test above, just
        # allow_display=True -- an ad's own banner heading merges an
        # unrelated column exactly the way a market section's does.
        box = clips.block_around(self.pi, self.coords, self.hit, allow_display=True,
                                 split_wide_headings=True)
        self.assertIsNotNone(box)
        words_in = clips.nameplate.words_in(self.coords["words"], box)
        text = clips.ocr_text(words_in)
        self.assertIn("BANNER", text)
        self.assertIn("LEFT 0", text)
        self.assertNotIn("RIGHT", text)

    def test_a_rule_near_the_edge_is_a_border_not_a_banner_divider(self):
        # A boxed ad's own decorative border rule sits close to one edge
        # of its column, not near the middle -- MIN_SPLIT_FRAC declines a
        # candidate that lopsided rather than returning a sliver of the ad.
        page = NearEdgeBannerHeadingPage()
        coords = page.coords()
        pi = rules.PageInk(page)
        hit = clips.find_phrase(coords["words"], "banner head")
        self.assertIsNotNone(hit)
        x0 = min(w[0] for w in hit); x1 = max(w[0] + w[2] for w in hit)
        y0 = min(w[1] for w in hit); y1 = max(w[1] + w[3] for w in hit)
        cb = pi.column_bounds(pi.from_ocr((x0, y0, x1 - x0, y1 - y0)), mode="column")
        split = clips.wide_heading_split(pi, cb, pi.y_small(y0), pi.y_small(y1))
        self.assertIsNone(split)


class Policies(unittest.TestCase):
    def test_market_lane_has_the_ad_lanes_era_floor(self):
        self.assertEqual(gates.earliest("market"), gates.earliest("ad"))
        self.assertEqual(gates.check("market", "sn89053135", "1860-01-01").outcome, gates.REFUSE)


if __name__ == "__main__":
    unittest.main()


class OwnTitleFragments(unittest.TestCase):
    """The Atlanta Georgian and News of 3 July 1907: the foot of the nameplate
    posted as a headline on 11 September 2026. Pinned here."""
    META = {"title": "Atlanta Georgian and news."}

    def test_a_fragment_of_the_title_is_refused(self):
        with self.assertRaises(npc.Refused):
            clips._refuse_own_title("AND NEWS LANTA, GA., WEDNESDAY, JULY", self.META, "headline")

    def test_a_dateline_alone_is_refused(self):
        with self.assertRaises(npc.Refused):
            clips._refuse_own_title("CITY EDITION. MACON, GA., THURSDAY MORNING", self.META, "headline")
        with self.assertRaises(npc.Refused):
            clips._refuse_own_title("WEDNESDAY, JULY 3, 1907", self.META, "headline")

    def test_a_real_headline_with_one_title_word_passes(self):
        clips._refuse_own_title("NEWS OF THE STRIKE REACHES ATLANTA", self.META, "headline")
        clips._refuse_own_title("FRENCH COUNTER FOR KEMMEL HILL", {"title": "The Cordele dispatch."}, "headline")
