#!/usr/bin/env python3
"""
test_headline_spread.py -- clips._headline_spread(), the headline lane's
two-column crop of 5 October 2026 (his call, on the Macon News of 21 June
1898 with his own crop as the reference), on a synthetic front page of three
columns with paper gutters between them:

  - a dateline row of small type across the top;
  - column A: a two-line headline, a deck, then body type;
  - column B: a one-line headline, then body type sooner than A's;
  - column C: body type from the top;
  - a variant with a banner across all three columns.

And the bottom's rules on their own: a display word the bottom crosses
carries it down (_no_cut), body type does not, and in the pixels a headline
is not ended between its lines (_settle_bottom).

Stdlib and PIL only, no network. Run by path or by discovery.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import clips        # noqa: E402
import rules        # noqa: E402


class SpreadPage:
    """1400 wide so OCR space and small-image space coincide (scale 1.0)."""
    lccn, date, ed, seq = "sn00000005", "1898-06-21", 1, 1
    image_w, image_h = 1400, 2000
    url = "https://example/lccn/sn00000005/1898-06-21/ed-1/seq-1/"

    A, B, C = (100, 440), (480, 820), (860, 1200)
    BODY_H, BODY_STEP = 7, 16           # body type about a third ink, as printed
    DATELINE_Y = 100
    A_BODY = 330           # where column A's story starts
    B_BODY = 230

    def __init__(self, banner=False):
        from PIL import Image, ImageDraw
        im = Image.new("L", (1400, self.image_h), 215)
        d = ImageDraw.Draw(im)
        words = []

        def word(x, y, w, h, t):
            d.rectangle([x, y, x + w, y + h], fill=40)
            words.append((x, y, w, h, t))

        def body(col, y0, y1=1900):
            # each line's words start at a different offset, as real type's
            # do: word gaps lined up down the page read as gutters
            for k, y in enumerate(range(y0, y1, self.BODY_STEP)):
                x = col[0]
                first = 20 + (k * 17) % 37
                word(x, y, first, self.BODY_H, f"body{k}a")
                x += first + 8
                while x + 50 < col[1]:
                    word(x, y, 50, self.BODY_H, f"body{k}x{x}")
                    x += 58
                if x + 8 < col[1]:
                    word(x, y, col[1] - x, self.BODY_H, f"body{k}z")

        for x in range(120, 1180, 120):                      # the dateline row
            word(x, self.DATELINE_Y, 80, self.BODY_H, f"dateline{x}")
        if banner:
            for k, x in enumerate(range(110, 1190, 270)):
                word(x, 140, 240, 44, f"BANNER{k}")
            for col in (self.A, self.B, self.C):
                body(col, 210)
        else:
            word(110, 140, 300, 40, "DIRECT")
            word(110, 190, 300, 40, "CABLE")
            word(130, 250, 260, 20, "Communication")
            body(self.A, self.A_BODY)
            word(490, 140, 300, 40, "FIFTY")
            body(self.B, self.B_BODY)
            body(self.C, 140)
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


def spread(page, box):
    c = page.coords()
    inside = [w for w in c["words"] if box[0] <= w[0] + w[2] / 2 < box[0] + box[2]
              and box[1] <= w[1] + w[3] / 2 < box[1] + box[3]]
    return clips._headline_spread(rules.PageInk(page), c, box, inside, 60, 1)


class HeadlineSpread(unittest.TestCase):
    HEAD = (110, 140, 300, 90)          # column A's two headline lines

    def test_two_columns_the_headlines_and_its_neighbour(self):
        x, y, w, h = spread(SpreadPage(), self.HEAD)
        self.assertLess(x, SpreadPage.A[0] + 5)
        self.assertGreater(x + w, SpreadPage.B[1] - 40)
        self.assertLess(x + w, SpreadPage.C[0], "the third column is not taken")

    def test_the_dateline_row_is_taken_on_a_front_page(self):
        _, y, _, _ = spread(SpreadPage(), self.HEAD)
        self.assertLessEqual(y, SpreadPage.DATELINE_Y)

    def test_the_bottom_is_into_the_story_that_starts_lowest(self):
        _, y, _, h = spread(SpreadPage(), self.HEAD)
        bottom = y + h
        lines_in = (bottom - SpreadPage.A_BODY) / float(SpreadPage.BODY_STEP)
        self.assertGreaterEqual(lines_in, clips.SPREAD_BODY_LINES - 1)
        self.assertLess(lines_in, clips.SPREAD_BODY_LINES + 4)

    def test_a_banner_takes_its_whole_span_and_no_neighbour_is_needed(self):
        x, y, w, h = spread(SpreadPage(banner=True), (110, 140, 1080, 44))
        self.assertLess(x, SpreadPage.A[0] + 5)
        self.assertGreater(x + w, SpreadPage.C[1] - 40)

    def test_a_crop_never_passes_the_depth_cap(self):
        page = SpreadPage()
        for box in (self.HEAD, (490, 140, 300, 40)):
            _, y, _, h = spread(page, box)
            self.assertLessEqual(h, clips.SPREAD_MAX_FRAC * page.image_h)


class NoCut(unittest.TestCase):
    MIN_H = 13                          # SPREAD_BODY_H x a 10-px text height

    def test_a_display_word_across_the_bottom_carries_it_down(self):
        rect = clips._no_cut((0, 0, 500, 300), [(100, 280, 200, 40, "HEAD")], self.MIN_H)
        self.assertEqual(rect[3], 321)

    def test_past_the_cap_the_bottom_backs_off_above_it(self):
        rect = clips._no_cut((0, 0, 500, 300), [(100, 280, 200, 40, "HEAD")], self.MIN_H, max_y1=310)
        self.assertEqual(rect[3], 279)

    def test_body_type_across_the_bottom_is_cut_like_his_crops(self):
        rect = clips._no_cut((0, 0, 500, 300), [(100, 295, 50, 10, "body")], self.MIN_H)
        self.assertEqual(rect[3], 300)

    def test_a_display_word_across_a_side_widens_it(self):
        rect = clips._no_cut((0, 0, 500, 300), [(450, 100, 200, 40, "BANNER")], self.MIN_H)
        self.assertEqual(rect[2], 650)

    def test_a_stack_is_not_ended_between_its_lines(self):
        stack = [(100, 240, 200, 40, "DAYTON"), (100, 290, 200, 40, "CRITICAL")]
        rect = clips._no_cut((0, 0, 500, 282), stack, self.MIN_H)
        self.assertEqual(rect[3], 331)


class InkStrip:
    """A PageInk stand-in whose rows are ink or paper by a list of runs."""
    def __init__(self, runs, h=600):
        self.h, self.w = h, 400
        self.ink = set()
        for t, e in runs:
            self.ink.update(range(t, e + 1))

    def row_share(self, y, a, b):
        return 0.5 if y in self.ink else 0.0


class SettleBottom(unittest.TestCase):
    TEXT_H = 10

    def settle(self, runs, y1, cap=590):
        return clips._settle_bottom(InkStrip(runs), 0, 400, y1, self.TEXT_H, cap, 400)

    def test_a_line_the_bottom_runs_through_is_taken_whole(self):
        self.assertEqual(self.settle([(200, 210)], 205), 211)

    def test_a_headline_is_not_ended_between_its_lines(self):
        # "JEWISH DRIVE IS / CONTINUED UNTIL / NEXT SATURDAY": three display
        # lines 20 tall, 8 apart, with the bottom left after the first
        self.assertEqual(self.settle([(200, 219), (228, 247), (256, 275)], 222), 276)

    def test_body_lines_below_a_finished_line_do_not_carry_it(self):
        self.assertEqual(self.settle([(200, 209), (216, 225)], 212), 212)

    def test_past_the_cap_a_line_is_left_out_and_the_cap_holds(self):
        # the bottom backs off above the line and cannot be pushed back down
        self.assertEqual(self.settle([(200, 230)], 210, cap=220), 195)

    def test_a_picture_is_not_a_line(self):
        tall = clips.SPREAD_PICTURE * self.TEXT_H + 20
        self.assertEqual(self.settle([(100, 100 + tall)], 150), 150)


class DropFurniture(unittest.TestCase):
    META = {"title": "Griffin Daily News"}

    def test_a_dateline_item_is_dropped_and_the_headlines_stay(self):
        text = ("GRIFFIN, GA., TUESDAY, MAY 18, 1926. BRILLIANT EXERCISES FOR GRIFFIN "
                "SCHOOLS. Work Starts Tomorrow On $75,000 Theatre.")
        self.assertEqual(clips._drop_furniture(text, self.META),
                         "BRILLIANT EXERCISES FOR GRIFFIN SCHOOLS. Work Starts Tomorrow On $75,000 Theatre.")

    def test_the_papers_own_name_is_dropped(self):
        text = "THE GRIFFIN DAILY NEWS. BIG DELEGATION OF ELKS GOING TO STATE MEET."
        self.assertEqual(clips._drop_furniture(text, self.META),
                         "BIG DELEGATION OF ELKS GOING TO STATE MEET.")

    def test_one_word_of_the_title_in_a_headline_is_not_furniture(self):
        text = "WHAT IS THE POPULATION OF GRIFFIN?"
        self.assertEqual(clips._drop_furniture(text, self.META), text)

    def test_nothing_left_is_empty(self):
        self.assertEqual(clips._drop_furniture("GRIFFIN, GA., TUESDAY, MAY 18, 1926.", self.META), "")


class SpreadBlocks(unittest.TestCase):
    """transcribe.blocks_of(): the spread's reply read a block to an item."""

    def test_printed_lines_of_one_item_are_one_item(self):
        import transcribe
        reply = ("DIRECT\nCABLE NOW\n\nCommunication Has Been Es-\ntablished Between Wash-\n"
                 "ington and Guantanamo.\n\nTROOPS ARRIVED.")
        self.assertEqual(transcribe.blocks_of(reply), [
            "DIRECT CABLE NOW",
            "Communication Has Been Established Between Washington and Guantanamo.",
            "TROOPS ARRIVED."])

    def test_a_soft_hyphen_is_a_broken_word(self):
        import transcribe
        self.assertEqual(transcribe.blocks_of("Still Suffer\u00ad\ning From Injuries\n\nBULLETINS"),
                         ["Still Suffering From Injuries", "BULLETINS"])

    def test_a_reply_with_no_blank_line_is_a_line_to_an_item(self):
        import transcribe
        self.assertEqual(transcribe.blocks_of("FIFTY PEOPLE WERE DROWNED\nCAUSED A TIDAL WAVE"),
                         ["FIFTY PEOPLE WERE DROWNED", "CAUSED A TIDAL WAVE"])

    def test_a_capital_after_a_hyphen_is_not_a_broken_word(self):
        import transcribe
        self.assertEqual(transcribe.blocks_of("Anti-\nSaloon League Meets\n\nTROOPS ARRIVED."),
                         ["Anti- Saloon League Meets", "TROOPS ARRIVED."])


if __name__ == "__main__":
    unittest.main()
