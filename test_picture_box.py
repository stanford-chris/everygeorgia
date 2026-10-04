#!/usr/bin/env python3
"""
test_picture_box.py -- clips._picture_box(), the headline lane's crop for a
headline that titles a picture inside a printed box (5 October 2026, his
call on the Atlanta Georgian and News of 23 November 1910, "New Jewish
Alliance Building"), on a synthetic page carrying that page's shape:

  - the page's own dateline rule across the full width, which the box
    hangs from (it has no top border of its own);
  - a box whose left side is a double line that ENDS at the box's bottom
    rule, and whose right side is a column rule that runs on down the page;
  - inside it, the display title, a halftone the OCR read nothing on, a
    caption, a full-width rule under the caption that both sides cross,
    and a section of body type;
  - variants: the same box with type where the picture was, the same box
    with both sides running on, and a headline with paper either side.

Stdlib and PIL only, no network. Run by path or by discovery.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import clips        # noqa: E402
import rules        # noqa: E402


class PicturePage:
    """1400 wide so OCR space and small-image space coincide (scale 1.0),
    as test_border_box.BoxedPage relies on."""
    lccn, date, ed, seq = "sn00000004", "1910-11-23", 1, 1
    image_w, image_h = 1400, 2000
    url = "https://example/lccn/sn00000004/1910-11-23/ed-1/seq-1/"
    BODY_H = 10

    LEFT = (403, 407)          # outer and inner stroke of the double line
    RIGHT = 1100               # the column rule that runs on
    TOP_RULE = 100             # the page's dateline rule
    CAPTION_RULE = 640         # interior: both sides cross it
    BOTTOM = 900               # the box's bottom rule (the left side ends here)
    TITLE = (500, 120, 500, 32)

    def __init__(self, picture=True, sides_run_on=False, sides=True):
        from PIL import Image, ImageDraw
        im = Image.new("L", (1400, self.image_h), 215)
        d = ImageDraw.Draw(im)
        words = []

        def word_row(x0, x1, y, h=self.BODY_H, prefix="type"):
            x, i = x0, 0
            while x + 60 < x1:
                d.rectangle([x, y, x + 60, y + h], fill=40)
                words.append((x, y, 60, h, f"{prefix}{i}word"))
                x += 90; i += 1

        d.rectangle([0, self.TOP_RULE, 1399, self.TOP_RULE + 3], fill=20)
        # a column of type left of the box, under the dateline rule
        for y in range(130, 1980, 20):
            word_row(30, 380, y)
        lo, li = self.LEFT
        left_end = 1990 if sides_run_on else self.BOTTOM
        if sides:
            d.rectangle([lo, self.TOP_RULE, lo + 1, left_end], fill=20)
            d.rectangle([li, self.TOP_RULE, li + 1, left_end], fill=20)
            d.rectangle([self.RIGHT, self.TOP_RULE, self.RIGHT + 2, 1990], fill=20)
            d.rectangle([lo, self.BOTTOM - 3, self.RIGHT + 2, self.BOTTOM], fill=20)
            d.rectangle([li + 2, self.CAPTION_RULE, self.RIGHT - 2, self.CAPTION_RULE + 2], fill=20)
        tx, ty, tw, th = self.TITLE
        for k, tok in enumerate(("New", "Jewish", "Alliance", "Building")):
            x = tx + k * 125
            d.rectangle([x, ty, x + 100, ty + th], fill=30)
            words.append((x, ty, 100, th, tok))
        if picture:
            # a halftone: dark everywhere, a light speck every few pixels,
            # and no OCR word on it
            d.rectangle([420, 180, 1090, 600], fill=60)
            for y in range(180, 600, 5):
                for x in range(420, 1090, 7):
                    im.putpixel((x, y), 200)
        else:
            for y in range(180, 600, 16):
                word_row(420, 1090, y)
        for y in (610, 622):
            word_row(420, 1090, y, prefix="caption")
        for y in range(660, 880, 16):
            word_row(420, 1090, y, prefix="growth")
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


def find(page):
    return clips._picture_box(rules.PageInk(page), page.coords(), PicturePage.TITLE)


class PictureBox(unittest.TestCase):
    def test_the_box_is_found_from_the_dateline_rule_to_where_the_left_side_ends(self):
        box = find(PicturePage())
        self.assertIsNotNone(box)
        x, y, w, h = box
        for got, want in ((x, PicturePage.LEFT[0]), (y, PicturePage.TOP_RULE),
                          (x + w, PicturePage.RIGHT + 3), (y + h, PicturePage.BOTTOM + 1)):
            self.assertLessEqual(abs(got - want), 4, (box, got, want))

    def test_the_rule_under_the_caption_is_walked_past(self):
        x, y, w, h = find(PicturePage())
        self.assertGreater(y + h, PicturePage.CAPTION_RULE + 100)

    def test_type_where_the_picture_was_is_not_a_picture_box(self):
        self.assertIsNone(find(PicturePage(picture=False)))

    def test_sides_that_run_on_past_every_rule_close_nothing(self):
        self.assertIsNone(find(PicturePage(sides_run_on=True)))

    def test_a_headline_with_paper_either_side_is_not_in_a_box(self):
        self.assertIsNone(find(PicturePage(sides=False)))


class PictureBoxDescription(unittest.TestCase):
    REPLY = ("PICTURE: An architect's drawing of a two-story building with arched "
             "windows and a columned entrance, a flag flying from its roof, trees either side.\n"
             "CAPTION: It is being erected in Capitol-ave. Picture from architect's plans.")

    def test_both_lines_are_read(self):
        r = clips.parse_picbox(self.REPLY)
        self.assertTrue(r["picture"].startswith("An architect's drawing"))
        self.assertTrue(r["caption"].startswith("It is being erected"))

    def test_no_caption_is_an_empty_caption_not_a_failure(self):
        r = clips.parse_picbox("PICTURE: A drawing of a building.\nCAPTION: NONE")
        self.assertEqual(r["caption"], "")

    def test_no_description_is_a_failure(self):
        self.assertIsNone(clips.parse_picbox("CAPTION: Something printed."))
        self.assertIsNone(clips.parse_picbox("CANNOT_READ"))

    def test_the_alt_labels_the_description_and_the_caption_separately(self):
        tail = clips.picture_alt_tail({"picture": "A drawing of a building.",
                                       "caption": "It is being erected in Capitol-ave."})
        self.assertIn("A.I.-described, the picture beneath it: A drawing of a building.", tail)
        self.assertIn("A.I.-transcribed, the caption reads: “It is being erected in Capitol-ave.”", tail)

    def test_no_caption_leaves_no_caption_sentence(self):
        tail = clips.picture_alt_tail({"picture": "A drawing.", "caption": ""})
        self.assertNotIn("caption", tail)

    def test_the_posted_alt_carries_the_tail(self):
        import everygeorgia_post as P
        r = {"lane": "headline", "words": "New Jewish Alliance Building.", "generated": True,
             "meta": {"title": "Atlanta Georgian and News", "city": "Atlanta"},
             "url": "https://example/lccn/sn89053728/1910-11-23/ed-1/seq-1/", "date": "1910-11-23",
             "picture_box": {"picture": "A drawing of a building.", "caption": ""}}
        alt = P.alt_text(r)
        self.assertTrue(alt.startswith("A.I.-transcribed headline"))
        self.assertTrue(alt.endswith("A.I.-described, the picture beneath it: A drawing of a building."))


if __name__ == "__main__":
    unittest.main()
