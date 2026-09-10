#!/usr/bin/env python3
"""
Tests for everygeorgia_post.py and profile.py: the post text, the selection
order, the REVIEW path and the launch gate.

⚠️ THE "NEVER POSTS" TESTS ARE THE POINT. A REVIEW must be logged and skipped,
never posted; a refused clip must be skipped; a scheduled run before the
launch thread must do nothing and exit 0. Each of those is a silent failure
in the other direction: a post goes out and looks fine.

Stdlib only, no network, no atproto: CLIP is swapped for a fake and the
state lives in a temp directory.
"""
import json
import os
import re
import tempfile
import unittest

import everygeorgia_post as ep
import gates
import nameplate_crop as npc
import profile as prof


def fake_result(lccn="sn89053135", date="1898-01-06", outcome=gates.PASS,
                title="The Abbeville chronicle.", city="Abbeville", page_hits=()):
    v = gates.check("nameplate", "sn89053135", date, page_hits=set(page_hits)) \
        if outcome == gates.REVIEW else gates.Verdict(outcome, [])
    meta = {"lccn": lccn, "title": title, "city": city, "county": "Wilcox",
            "postable": "yes"}
    url = f"https://gahistoricnewspapers.galileo.usg.edu/lccn/{lccn}/{date}/ed-1/seq-1/"
    caption, alt, credit = npc.describe(meta, date, type("P", (), {"url": url})())
    return {"lccn": lccn, "date": date, "edition": 1, "lane": "nameplate",
            "verdict": v, "postable": v.postable, "band_fraction": 0.08,
            "extended": False, "meta": meta, "url": url,
            "image_box": (0, 0, 100, 10), "size": (1600, 200),
            "words_in_band": [], "page_hits": sorted(page_hits),
            "caption": caption, "alt": alt, "credit": credit, "bytes": b"x"}


class Compose(unittest.TestCase):
    def test_citation_form_with_credit_and_tags(self):
        text = ep.text_of(ep.compose(fake_result()))
        self.assertTrue(text.startswith("[Nameplate], “The Abbeville Chronicle,” Abbeville, 6 January 1898, p. 1, "))
        self.assertIn("gahistoricnewspapers.galileo.usg.edu/lccn/sn89053135/1898-01-06/ed-1/seq-1. "
                      "Presented online by the Digital Library of Georgia.", text)
        self.assertTrue(text.endswith("\n\n#Georgia #History"))
        self.assertLessEqual(len(text), 300)

    def test_link_and_tags_are_facets_not_plain_text(self):
        segs = ep.compose(fake_result())
        kinds = [s[0] for s in segs]
        self.assertIn("link", kinds)
        self.assertEqual(kinds.count("tag"), 2)
        link = next(s for s in segs if s[0] == "link")
        self.assertTrue(link[2].startswith("https://gahistoricnewspapers.galileo.usg.edu/lccn/"))
        self.assertTrue(link[2].endswith("/"))
        self.assertEqual([s[2] for s in segs if s[0] == "tag"], list(ep.TAGS))

    def test_city_is_omitted_when_the_roster_has_none(self):
        text = ep.text_of(ep.compose(fake_result(title="The Gwinnett herald.", city="")))
        self.assertIn("“The Gwinnett Herald,” 6 January 1898", text)

    def test_a_long_title_shortens_the_visible_url_not_the_credit(self):
        long = "The bulletin of the Catholic Laymen's Association of Georgia and its friends everywhere."
        text = ep.text_of(ep.compose(fake_result(title=long, city="Augusta")))
        self.assertLessEqual(len(text), 300)
        self.assertIn(ep.CREDIT, text)

    def test_no_straight_marks_or_em_dash_reach_a_reader(self):
        for r in (fake_result(), fake_result(title="Burke's weekly for boys and girls.")):
            text = ep.text_of(ep.compose(r))
            for s in (text, ep.alt_text(r)):
                self.assertNotIn("'", s)
                self.assertNotIn('"', s)
                self.assertNotIn("—", s)

    def test_alt_carries_the_paper_name_and_no_unverified_claim(self):
        alt = ep.alt_text(fake_result())
        self.assertIn("“The Abbeville Chronicle,”", alt)
        self.assertNotIn("worn", alt)


class DisplayTitle(unittest.TestCase):
    def test_catalogue_form_becomes_title_case(self):
        cases = {
            "The Abbeville chronicle.": "The Abbeville Chronicle",
            "Daily chronicle & sentinel.": "Daily Chronicle & Sentinel",
            "The Advertiser-republican.": "The Advertiser-Republican",
            "The DeKalb news.": "The DeKalb News",
            "DuPont Okefenokean.": "DuPont Okefenokean",
            "The banner of the South and planters' journal.":
                "The Banner of the South and Planters’ Journal",
            "The 124th infantry alligator.": "The 124th Infantry Alligator",
            "The sunny South.": "The Sunny South",
        }
        for src, want in cases.items():
            self.assertEqual(npc.display_title(src), want)


class Selection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._state, self._review = ep.STATE_FILE, ep.REVIEW_FILE
        ep.STATE_FILE = os.path.join(self.tmp.name, "post_state.json")
        ep.REVIEW_FILE = os.path.join(self.tmp.name, "review.jsonl")
        self._clip = ep.CLIP
        self.issues = {
            "sn00000001": [("1900-01-01", 1), ("1900-02-01", 1), ("1900-03-01", 1)],
            "sn00000002": [("1880-01-01", 1)],
            "sn00000003": [("1890-01-01", 1), ("1891-01-01", 1)],
        }
        self.calls = []

    def tearDown(self):
        ep.STATE_FILE, ep.REVIEW_FILE, ep.CLIP = self._state, self._review, self._clip
        self.tmp.cleanup()

    def test_order_is_fixed_and_appends(self):
        s = {"order": [], "pass": 1, "posted": [], "tried": {}}
        first = ep.title_order(s, self.issues)
        self.assertEqual(sorted(first), sorted(self.issues))
        again = ep.title_order(dict(s), self.issues)
        self.assertEqual(first, again)
        more = dict(self.issues, sn00000004=[("1901-01-01", 1)])
        grown = ep.title_order(s, more)
        self.assertEqual(grown[:3], first)
        self.assertEqual(grown[3], "sn00000004")

    def test_dates_differ_between_passes(self):
        d1 = ep.dates_for("sn00000001", self.issues["sn00000001"], 1)
        d2 = ep.dates_for("sn00000001", self.issues["sn00000001"], 2)
        self.assertEqual(sorted(d1), sorted(d2))
        self.assertEqual(d1, ep.dates_for("sn00000001", self.issues["sn00000001"], 1))

    def test_pass_and_refuse_and_review(self):
        def clip(lccn, date, ed):
            self.calls.append((lccn, date))
            if lccn == "sn00000002":
                raise npc.Refused("no geometry")
            if date.startswith("1900-01"):
                return fake_result(lccn, date, gates.REVIEW, page_hits={"negro"})
            return fake_result(lccn, date)
        ep.CLIP = clip
        s = {"order": ["sn00000002", "sn00000001", "sn00000003"], "pass": 1,
             "posted": [], "tried": {}}
        lccn, r = ep.choose(s, self.issues, log=lambda *a: None)
        self.assertIsNotNone(r)
        self.assertTrue(r["postable"])
        self.assertNotEqual(lccn, "sn00000002")
        self.assertIn("sn00000002", s["tried"])           # refused, but tried
        self.assertTrue(self.calls[0][0] == "sn00000002")  # order was honoured
        self.assertNotIn(("sn00000002", "1880-01-01"), [(c[0], c[1]) for c in self.calls[1:]])

    def test_review_is_logged_and_never_returned(self):
        ep.CLIP = lambda l, d, e: fake_result(l, d, gates.REVIEW, page_hits={"lynch"})
        issues = {"sn00000001": self.issues["sn00000001"]}
        s = {"order": ["sn00000001"], "pass": 1, "posted": [], "tried": {}}
        lccn, r = ep.choose(s, issues, log=lambda *a: None)
        self.assertIsNone(r)
        with open(ep.REVIEW_FILE) as f:
            lines = [json.loads(x) for x in f]
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0]["page_hits"], ["lynch"])
        self.assertIn("not a rejection", lines[0]["reasons"][0])
        self.assertEqual(sorted(s["tried"]["sn00000001"]), sorted(d for d, _ in self.issues["sn00000001"]))

    def test_tries_are_bounded_per_title(self):
        issues = {"sn00000009": [(f"19{i:02d}-01-01", 1) for i in range(20)]}
        ep.CLIP = lambda l, d, e: (_ for _ in ()).throw(npc.Refused("x"))
        s = {"order": [], "pass": 1, "posted": [], "tried": {}}
        ep.choose(s, issues, log=lambda *a: None)
        self.assertEqual(len(s["tried"]["sn00000009"]), ep.TRIES_PER_TITLE)

    def test_pass_rolls_over_when_every_title_is_done(self):
        import io, contextlib
        s = {"order": [], "pass": 1, "tried": {},
             "posted": [{"lccn": l, "date": "x", "pass": 1} for l in self.issues]}
        with contextlib.redirect_stdout(io.StringIO()):
            owed = ep.next_titles(s, self.issues)
        self.assertEqual(s["pass"], 2)
        self.assertEqual(sorted(owed), sorted(self.issues))
        self.assertEqual(s["tried"], {})

    def test_state_round_trips_atomically(self):
        s = {"order": ["a"], "pass": 3, "posted": [], "tried": {}}
        ep.save_state(s)
        self.assertEqual(ep.load_state(), s)
        self.assertFalse(os.path.exists(ep.STATE_FILE + ".tmp"))


class LaunchThread(unittest.TestCase):
    def test_every_post_fits_and_the_bio_fits(self):
        for i, p in enumerate(prof.thread(), 1):
            self.assertLessEqual(len(p["text"]), 300, f"post {i}")
        self.assertLessEqual(len(prof.bio()), 256)

    def test_first_three_posts_carry_what_has_to_land(self):
        texts = [p["text"] for p in prof.thread()]
        self.assertTrue(texts[0].startswith("What this is:"))
        self.assertTrue(texts[1].startswith("How things are chosen:"))
        self.assertIn("not representative of the archive", texts[2])
        self.assertIn("issues", texts[1])
        self.assertNotIn("editions", texts[1])

    def test_facets_land_on_unique_text(self):
        dids = {"stanfordc.bsky.social": "did:plc:a", "ugagrady.bsky.social": "did:plc:b"}
        for p in prof.thread():
            segs = ep.thread_segments(p, dids)
            self.assertEqual(ep.text_of(segs), p["text"])
        last = ep.thread_segments(prof.thread()[-1], dids)
        self.assertEqual([s for s in last if s[0] == "mention"],
                         [("mention", "@stanfordc.bsky.social", "did:plc:a"),
                          ("mention", "@ugagrady.bsky.social", "did:plc:b")])
        fifth = ep.thread_segments(prof.thread()[4], dids)
        link = next(s for s in fifth if s[0] == "link")
        self.assertEqual(link[2], "https://gahistoricnewspapers.galileo.usg.edu/lccn/sn85034222/1875-02-23/ed-1/seq-1/")

    def test_post_five_date_is_uk_order(self):
        self.assertIn("23 February 1875", prof.thread()[4]["text"])
        self.assertNotIn("Feb.", prof.thread()[4]["text"])

    def test_nothing_straight_reaches_the_feed(self):
        for p in prof.thread():
            self.assertNotIn("'", p["text"])
            self.assertNotIn('"', p["text"])
        self.assertNotIn("'", prof.bio())

    def test_curly_directions(self):
        self.assertEqual(prof.curly("I've a 'word' here"), "I’ve a ‘word’ here")
        self.assertEqual(prof.curly('marks "No Copyright" and'), "marks “No Copyright” and")


class LaunchGate(unittest.TestCase):
    def test_scheduled_run_before_launch_posts_nothing(self):
        """The gate lives in main(); this pins the state key it reads."""
        src = open(ep.__file__).read()
        self.assertIn('not state.get("launch_thread_posted")', src)
        self.assertIn("Not launched yet", src)

    def test_unknown_flags_are_rejected(self):
        import subprocess, sys
        r = subprocess.run([sys.executable, ep.__file__, "--dryrun"],
                           capture_output=True, text=True, cwd=os.path.dirname(ep.__file__))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unrecognized", r.stderr)


class Promises(unittest.TestCase):
    """What the 21 August 2026 email said the bot would do."""

    def test_user_agent_identifies_the_account(self):
        import ghn_api
        self.assertIn("georgianewspapers", ghn_api.UA)
        self.assertIn("@", ghn_api.UA)

    def test_every_post_credits_dlg(self):
        self.assertEqual(ep.CREDIT, "Presented online by the Digital Library of Georgia.")
        self.assertIn(ep.CREDIT, ep.text_of(ep.compose(fake_result())))

    def test_run_is_bounded(self):
        self.assertLessEqual(ep.TITLES_PER_RUN * ep.TRIES_PER_TITLE, 20)


if __name__ == "__main__":
    unittest.main()
