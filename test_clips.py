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
import rules


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


class Policies(unittest.TestCase):
    def test_market_lane_has_the_ad_lanes_era_floor(self):
        self.assertEqual(gates.earliest("market"), gates.earliest("ad"))
        self.assertEqual(gates.check("market", "sn89053135", "1860-01-01").outcome, gates.REFUSE)


if __name__ == "__main__":
    unittest.main()
