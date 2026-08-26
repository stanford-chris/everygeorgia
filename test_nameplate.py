#!/usr/bin/env python3
"""
Tests for the everygeorgia nameplate lane: ghn_api geometry, the nameplate
detector, the vocabulary scoring and the crop pipeline's gates.

⚠️ THE REFUSAL TESTS ARE THE POINT. Every failure mode in this lane is silent.
A wrong scale factor returns a real JPEG of the wrong part of the page with
HTTP 200; a detector that chains into a headline returns a plausible band; a
crop that swallows a lynching headline looks exactly like a nameplate to
everything except a person. So most of what is pinned here is the code
declining to answer.

Three cases are regressions against real pages measured 26 August 2026 and are
named as such. Do not "simplify" the thresholds they defend without re-running
crop_frequency.py --calibrate.

Stdlib only. No network: every word list is synthetic, built to the geometry
actually observed on the page it is named after.
"""
import unittest

import ghn_api
import nameplate
from crop_frequency import NEGRO_PREFIXES, SUBJECT_PREFIXES, norm, score
import nameplate_crop as npc


def W(x, y, w, h, t="x"):
    return (x, y, w, h, t)


def body_block(n, y0, step, h, width=700, start_x=20):
    """A block of body-sized words, used to give a page a sane median."""
    out = []
    for i in range(n):
        out.append(W(start_x + (i * 37) % width, y0 + (i // 12) * step, 20, h))
    return out


class Scaling(unittest.TestCase):
    """⚠️ The OCR coordinate space is not the image space, and on the pages
    measured it was both 3.9x smaller AND 3x larger than the image."""

    def page(self, cw, ch, iw, ih):
        p = ghn_api.Page("sn00000001", "1898-01-06", 1, 1, iw, ih, "svc")
        p._coords = {"width": cw, "height": ch, "words": []}
        return p

    def test_scale_up(self):
        p = self.page(796, 1190, 3080, 4607)
        self.assertAlmostEqual(p.scale, 3080 / 796, places=6)
        self.assertEqual(p.to_image((0, 0, 796, 200)), (0, 0, 3080, 774))

    def test_scale_down(self):
        """The Columbus Enquirer of 1849: coords 3x LARGER than the image."""
        p = self.page(14637, 19305, 4879, 6435)
        self.assertLess(p.scale, 1)
        x, y, w, h = p.to_image((0, 0, 14637, 2400))
        self.assertEqual((x, y, w), (0, 0, 4879))
        self.assertEqual(h, round(2400 * 4879 / 14637))

    def test_box_is_clamped_to_the_page(self):
        p = self.page(796, 1190, 3080, 4607)
        self.assertEqual(p.to_image((0, 0, 9999, 9999)), (0, 0, 3080, 4607))

    def test_empty_box_refuses(self):
        p = self.page(796, 1190, 3080, 4607)
        with self.assertRaises(ValueError):
            p.to_image((10, 10, 0, 0))

    def test_scale_without_widths_raises_rather_than_assuming_one(self):
        p = self.page(0, 0, 3080, 4607)
        with self.assertRaises(ghn_api.FetchError):
            _ = p.scale


class Identifiers(unittest.TestCase):
    def test_bad_lccn_refused_before_a_request_is_made(self):
        with self.assertRaises(ValueError):
            ghn_api.check_ident("not-an-lccn", "1898-01-06")

    def test_bad_date_refused(self):
        with self.assertRaises(ValueError):
            ghn_api.check_ident("sn89053135", "1898-1-6")

    def test_good_pair_accepted(self):
        ghn_api.check_ident("sn89053135", "1898-01-06")

    def test_service_path_is_read_not_reconstructed(self):
        svc = ("https://iiif-ha.galib.uga.edu/iiif/2/newspapers"
               "%2Fbatch_gu_x01_ver01%2Fdata%2Fsn1%2F11000001%2F1898010601%2F0001.jp2")
        p = ghn_api.Page("sn89053135", "1898-01-06", 1, 1, 3080, 4607, svc)
        self.assertEqual(
            p.service_path,
            "newspapers/batch_gu_x01_ver01/data/sn1/11000001/1898010601/0001.jp2")
        url = p.crop_url((0, 0, 3080, 700), 1200)
        self.assertIn("/0,0,3080,700/1200,/0/default.jpg", url)
        self.assertIn("%2Fbatch_gu_x01_ver01%2F", url)

    def test_unrecognised_service_refuses(self):
        p = ghn_api.Page("sn89053135", "1898-01-06", 1, 1, 10, 10, "https://x/y")
        with self.assertRaises(ghn_api.FetchError):
            _ = p.service_path


class Detector(unittest.TestCase):
    def test_abbeville_masthead_is_found(self):
        """The Abbeville Chronicle, 6 Jan 1898. Masthead OCRs as garbage
        ('mK', 'mraLE') at h=62-70 against a page median of 7."""
        words = [W(98, 96, 23, 62, "t"), W(148, 96, 227, 68, "mraLE"),
                 W(402, 94, 184, 70, "mK")]
        words += [W(192, 188, 80, 12, "BBEVILLE"), W(316, 187, 85, 11, "THURSDAY"),
                  W(469, 187, 36, 10, "1898")]
        words += body_block(400, 215, 16, 7)
        box = nameplate.nameplate_box(words, 796, 1190)
        self.assertIsNotNone(box)
        self.assertEqual(box[0:3], (0, 0, 796))
        self.assertLess(box[3], 1190 * 0.22)
        self.assertGreater(box[3], 164)

    def test_macon_headline_is_not_swallowed(self):
        """REGRESSION, Macon Telegraph 8 June 1901. A headline at 0.52 of the
        masthead height chained into the cluster at SIZE_SIM=0.5 and the crop
        came out reading 'SHERIFF OF CARROLL FIRES ON THE MOB'."""
        words = [W(1200, 630, 3000, 588, "TELEGRAPH"), W(600, 640, 500, 560, "THE")]
        words += [W(400, 1797, 900, 306, "SHERIFF"), W(1400, 1800, 700, 300, "CARROLL")]
        words += [W(400, 2181, 800, 300, "FIRES"), W(1400, 2185, 600, 295, "MOB")]
        words += body_block(2000, 2607, 90, 60, width=10000)
        box = nameplate.nameplate_box(words, 11058, 17253)
        self.assertIsNotNone(box)
        self.assertLess(box[3], 1797,
                        "the band must stop above the headline row")

    def test_griffin_headline_block_is_not_swallowed(self):
        """REGRESSION, Griffin Daily News 3 June 1916. A 23-row chain down the
        page produced a band 30% deep. The headline type is 0.39 of the
        masthead's, so it is a different typographic object."""
        words = [W(400, 138, 300, 97, "fwm")]
        words += [W(100 + i * 60, 285 + (i // 6) * 96, 55, 38, "SERIES")
                  for i in range(18)]
        words += body_block(1500, 700, 10, 7, width=1400)
        box = nameplate.nameplate_box(words, 1418, 1936)
        if box is not None:
            self.assertLess(box[3], 285, "must stop above the headline block")

    def test_display_floor_scales_with_the_page(self):
        """⚠️ A pixel constant is meaningless here: page median word heights
        measured from 7 to 161, across coordinate spaces from 796x1190 to
        22839x31677. The SAME absolute height must read as display type on a
        small page and as body text on a large one."""
        small = [W(100, 20, 300, 60, "TITLE")] + body_block(300, 200, 15, 7)
        self.assertTrue([w for w in nameplate.display_words(small, 1190)
                         if w[3] == 60],
                        "60 units is display type on a 1190-unit page")
        big = [W(2000, 300, 3000, 60, "title")] + body_block(300, 4000, 200, 60,
                                                             width=20000)
        self.assertFalse([w for w in nameplate.display_words(big, 31677)
                          if w[3] == 60],
                         "the same 60 units is body text on a 31677-unit page")

    def test_augusta_invisible_masthead_is_refused_not_guessed(self):
        """REGRESSION, Augusta paper of 8 March 1845. The ornate masthead
        produced NO word boxes at all: the topmost text on the page is the
        dateline, 12% down, at 2.3x the page median. That clears the ratio test
        and fails the relative floor, so the page is refused.

        ⚠️ Refusing is the right answer, and the reason is worth keeping. The
        detector cannot see the masthead, so it cannot know where it ends; a
        band drawn from the only thing it CAN see would be a guess dressed as a
        measurement. There are 218,505 postable issues. Skipping this one costs
        nothing."""
        words = [W(7606, 3921, 1400, 255, "AUGUSTA"), W(9175, 3935, 500, 222, "GA"),
                 W(11598, 3950, 1500, 274, "MORNING"), W(14773, 4020, 700, 217, "1845")]
        words += body_block(2000, 4280, 200, 109, width=20000)
        self.assertIsNone(nameplate.nameplate_box(words, 22839, 31677))

    def test_no_display_type_refuses(self):
        words = body_block(500, 50, 20, 60, width=14000)
        self.assertIsNone(nameplate.nameplate_box(words, 14637, 19305))

    def test_cluster_below_the_top_band_refuses(self):
        words = [W(100, 900, 400, 90, "LATE")]
        words += body_block(300, 1000, 15, 7)
        self.assertIsNone(nameplate.nameplate_box(words, 796, 1190))

    def test_athens_headline_deck_is_refused(self):
        """REGRESSION, Athens Banner 29 December 1908. The blackletter masthead
        produced NO display boxes, so the detector locked onto the headline
        deck 10.4% down and cropped "YOUNG NEGRO GIRL KILLED BENEATH SEABOARD
        ENGINE" as a nameplate. The vocabulary gate caught it; the geometry
        should not have offered it.

        ⚠️ This is the failure this lane exists to avoid, and it was found by
        reading two flagged crops by eye rather than by any assertion."""
        words = [W(1000, 2289, 3000, 400, "YOUNG"), W(4200, 2295, 2500, 390, "NEGRO")]
        words += body_block(2000, 3456, 200, 190, width=20000)
        box = nameplate.nameplate_box(words, 21000, 21963)
        self.assertIsNone(box, "a cluster starting at 10.4% is not a masthead")

    def test_a_masthead_at_the_measured_median_is_still_accepted(self):
        """The bound must not be so tight that real mastheads are refused:
        median measured start is 5.2% of page height."""
        words = [W(100, int(1190 * 0.052), 600, 70, "TITLE")]
        words += body_block(400, 300, 15, 7)
        self.assertIsNotNone(nameplate.nameplate_box(words, 796, 1190))

    def test_band_deeper_than_max_fraction_refuses(self):
        """MAX_BAND_FRAC on its own. ⚠️ This needs a page that passes every
        OTHER rule, or it tests nothing: an earlier version of this test used a
        single huge word, which was refused for having no display cluster at
        all, and the whole threshold could be deleted with the suite still
        green. Measured band heights on real pages run 7.4% to 15.1%."""
        words = [W(80, 10, 600, 200, "ENORMOUS")]
        words += body_block(300, 400, 12, 7)
        self.assertIsNotNone(
            nameplate.cluster(nameplate.display_words(words, 1190)),
            "precondition: this page must have a real display cluster")
        self.assertIsNone(nameplate.nameplate_box(words, 796, 1190))
        self.assertIsNotNone(
            nameplate.nameplate_box(words, 796, 1190, max_frac=0.9),
            "and it must be the depth rule doing the refusing, nothing else")

    def test_disagreement_with_body_start_refuses(self):
        """Rule 3: dense body text beginning inside the geometric band means
        the two signals disagree, so the page is refused."""
        words = [W(100, 10, 600, 80, "TITLE")]
        words += body_block(600, 60, 4, 7)
        self.assertIsNone(nameplate.nameplate_box(words, 796, 1190))

    def test_empty_page_refuses(self):
        self.assertIsNone(nameplate.nameplate_box([], 796, 1190))
        self.assertIsNone(nameplate.nameplate_box([W(1, 1, 1, 1)], 0, 0))

    def test_body_start_needs_two_consecutive_dense_bands(self):
        """A single dense strip is a headline deck, not the body."""
        words = body_block(30, 100, 1, 7)          # one tight strip
        words += [W(i * 3, 1000 + i, 5, 7) for i in range(200)]
        self.assertIsNotNone(nameplate.body_start(words, 1190))
        self.assertGreater(nameplate.body_start(words, 1190), 100)


class WordsIn(unittest.TestCase):
    def test_centre_rule_not_overlap_and_not_enclosure(self):
        """⚠️ A word straddling the band edge is scored once, where most of it
        sits. Overlap double-counts it; enclosure drops it from both."""
        box = (0, 0, 100, 100)
        mostly_in = W(10, 90, 10, 15)        # centre y = 97.5
        mostly_out = W(10, 96, 10, 15)       # centre y = 103.5
        got = nameplate.words_in([mostly_in, mostly_out], box)
        self.assertIn(mostly_in, got)
        self.assertNotIn(mostly_out, got)


class Vocabulary(unittest.TestCase):
    def test_prefixes_over_match_on_purpose(self):
        for t in ("slaves", "slavery", "lynched", "lynchings", "klux"):
            self.assertTrue(score([W(0, 0, 1, 1, t)], SUBJECT_PREFIXES), t)
        for t in ("negro", "negroes", "negre"):
            self.assertTrue(score([W(0, 0, 1, 1, t)], NEGRO_PREFIXES), t)

    def test_punctuation_and_case_are_folded(self):
        self.assertTrue(score([W(0, 0, 1, 1, "LYNCHING,")], SUBJECT_PREFIXES))
        self.assertEqual(norm("“Negro.”"), "negro")

    def test_short_tokens_never_match(self):
        """'ku' alone is OCR noise, which is why 'klux' is the Klan marker."""
        self.assertFalse(score([W(0, 0, 1, 1, "ku")], SUBJECT_PREFIXES))

    def test_unrelated_words_do_not_match(self):
        for t in ("chronicle", "telegraph", "savannah", "slate", "lynn"):
            self.assertFalse(score([W(0, 0, 1, 1, t)], SUBJECT_PREFIXES), t)


class Gates(unittest.TestCase):
    def test_vocabulary_gate_refuses_and_names_the_term(self):
        box = (0, 0, 796, 200)
        words = [W(10, 10, 50, 60, "THE"), W(100, 120, 40, 12, "lynching")]
        with self.assertRaises(npc.Refused) as cm:
            npc.check_words(words, box)
        self.assertIn("lynch", str(cm.exception))

    def test_vocabulary_gate_ignores_words_below_the_band(self):
        box = (0, 0, 796, 200)
        words = [W(10, 10, 50, 60, "THE"), W(100, 900, 40, 12, "lynching")]
        self.assertEqual(len(npc.check_words(words, box)), 1)

    def test_shape_gate_refuses_a_squarish_crop(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        import io
        buf = io.BytesIO()
        Image.new("L", (400, 400), 255).save(buf, "JPEG")
        with self.assertRaises(npc.Refused):
            npc.check_image(buf.getvalue(), 400)

    def test_shape_gate_accepts_a_strip(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        import io
        buf = io.BytesIO()
        Image.new("L", (1600, 376), 255).save(buf, "JPEG")
        self.assertEqual(npc.check_image(buf.getvalue(), 1600), (1600, 376))

    def test_wrong_width_refuses(self):
        """The server returning a size we did not ask for means the region or
        the scaling was wrong, whatever the bytes look like."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        import io
        buf = io.BytesIO()
        Image.new("L", (800, 200), 255).save(buf, "JPEG")
        with self.assertRaises(npc.Refused):
            npc.check_image(buf.getvalue(), 1600)

    def test_non_image_bytes_refuse(self):
        with self.assertRaises(npc.Refused):
            npc.check_image(b"<html>not an image</html>", 1600)


class Captions(unittest.TestCase):
    def test_uk_date_order_no_ordinal(self):
        self.assertEqual(npc.uk_date("1898-01-06"), "6 January 1898")
        self.assertEqual(npc.uk_date("1845-03-08"), "8 March 1845")

    def test_caption_uses_curly_quotes_for_the_work_title(self):
        """House style: titles of works take quotation marks, not italics."""
        meta = {"title": "The Abbeville chronicle.", "city": "Abbeville",
                "county": "Wilcox"}
        page = ghn_api.Page("sn89053135", "1898-01-06", 1, 1, 1, 1, "s")
        caption, alt, credit = npc.describe(meta, "1898-01-06", page)
        self.assertIn("“The Abbeville chronicle,”", caption)
        self.assertNotIn("chronicle.,", caption)
        self.assertIn("6 January 1898", caption)
        self.assertIn("Wilcox County", alt)
        self.assertIn("gahistoricnewspapers", credit)

    def test_no_em_dash_anywhere_in_reader_facing_text(self):
        meta = {"title": "The Macon telegraph.", "city": "Macon", "county": "Bibb"}
        page = ghn_api.Page("sn89053320", "1901-06-08", 1, 1, 1, 1, "s")
        for s in npc.describe(meta, "1901-06-08", page):
            self.assertNotIn("—", s)


if __name__ == "__main__":
    unittest.main()
