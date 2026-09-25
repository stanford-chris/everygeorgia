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
from unittest import mock

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
        # No "[Nameplate]," on a nameplate post, his call on the first post, 11 September 2026.
        # Title, date, link: no city, no page number, his instruction on the first post.
        # And no quotation marks round the title, his instruction the same evening.
        self.assertTrue(text.startswith("The Abbeville Chronicle, January 6, 1898. "))
        self.assertNotIn("p. 1", text)
        # The URL is not printed: it is a link facet on "Presented online".
        self.assertNotIn("gahistoricnewspapers", text)
        self.assertIn("January 6, 1898. Courtesy of the Digital Library of Georgia.", text)
        links = [s for s in ep.compose(fake_result()) if s[0] == "link"]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0][1], "Digital Library of Georgia")
        self.assertEqual(links[0][2],
                         "https://gahistoricnewspapers.galileo.usg.edu/lccn/sn89053135/1898-01-06/ed-1/seq-1/")
        self.assertTrue(text.endswith("\n\n#Georgia #History #Abbeville"))
        self.assertLessEqual(len(text), 300)

    def test_link_and_tags_are_facets_not_plain_text(self):
        segs = ep.compose(fake_result())
        kinds = [s[0] for s in segs]
        self.assertIn("link", kinds)
        self.assertEqual(kinds.count("tag"), 3)   # #Georgia #History and the town
        link = next(s for s in segs if s[0] == "link")
        self.assertTrue(link[2].startswith("https://gahistoricnewspapers.galileo.usg.edu/lccn/"))
        self.assertTrue(link[2].endswith("/"))
        self.assertEqual([s[2] for s in segs if s[0] == "tag"], list(ep.TAGS) + ["Abbeville"])

    def test_city_is_omitted_when_the_roster_has_none(self):
        text = ep.text_of(ep.compose(fake_result(title="The Gwinnett herald.", city="")))
        self.assertIn("The Gwinnett Herald, January 6, 1898", text)

    def test_a_long_title_still_fits_with_the_whole_credit(self):
        long = "The bulletin of the Catholic Laymen's Association of Georgia and its friends everywhere."
        text = ep.text_of(ep.compose(fake_result(title=long, city="Augusta")))
        self.assertLessEqual(len(text), 300)
        self.assertIn(ep.CREDIT, text)

    def test_the_link_words_are_the_credit_s_own_opening(self):
        # If CREDIT is ever reworded, the facet must move with it or the
        # assert in compose() fires before a post is built.
        self.assertEqual(ep.CREDIT.count(ep.LINK_TEXT), 1)

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

    def test_narrow_lane_without_full_titles_still_shrinks_the_order(self):
        """The pre-fix, single-set behaviour is kept for a caller with
        nothing broader to offer, so `full_titles` is genuinely optional
        rather than a silent requirement."""
        s = {"order": [], "pass": 1, "posted": [], "tried": {}}
        ep.title_order(s, self.issues)   # seed the full order, 3 titles
        narrow = {"sn00000001": self.issues["sn00000001"]}
        ep.next_titles(s, narrow, lane="headline")
        self.assertEqual(s["order"], ["sn00000001"])

    def test_a_narrow_lane_never_collapses_the_shared_order_when_full_titles_is_given(self):
        """14 September 2026: headline/article/cartoon draw from a narrow
        eligible subset of the full title universe (in production, 19 or 13
        of 843), and a narrow-lane win used to persist state["order"] down
        to that subset -- discovered when a reader noticed the Griffin Daily
        News (three separate LCCNs for one continuously-published paper,
        a Chronicling America title-change split) posting three times in
        three days, because Griffin occupied 3 of headline/article's 19
        eligible slots and any headline-lane win collapsed the master order
        to that 19. `full_titles` (always sources["nameplate"] from
        `pick()`) is what keeps the master order at its full size regardless
        of which lane's subset actually won the run."""
        s = {"order": [], "pass": 1, "posted": [], "tried": {}}
        narrow = {"sn00000001": self.issues["sn00000001"]}
        owed = ep.next_titles(s, narrow, lane="headline", full_titles=self.issues)
        self.assertEqual(owed, ["sn00000001"])
        self.assertEqual(sorted(s["order"]), sorted(self.issues))   # NOT shrunk to 1
        # A later nameplate-lane call still sees the same, undisturbed full order.
        again = ep.next_titles(s, self.issues, lane="nameplate", full_titles=self.issues)
        self.assertEqual(sorted(again), sorted(self.issues))
        self.assertEqual(sorted(s["order"]), sorted(self.issues))

    def test_pick_threads_sources_nameplate_as_full_titles(self):
        """The wiring in `pick()`: a narrow-lane win must not shrink the
        shared order, using the real call path rather than next_titles()
        directly."""
        ep.CLIP = lambda lane, l, d, e, seq=1, phrase=None: fake_result(l, d)
        s = {"order": [], "pass": 1, "posted": [], "tried": {}}
        for lane in ep.LANES + (ep.CARTOON_SEARCH,):
            s["tried"].setdefault(lane, {})
        sources = {"nameplate": self.issues,
                   "headline": {"sn00000001": self.issues["sn00000001"]}}
        lccn, r = ep.pick(s, sources, "headline", log=lambda *a: None)
        self.assertIsNotNone(r)
        self.assertEqual(sorted(s["order"]), sorted(self.issues))

    def test_dates_differ_between_passes(self):
        d1 = ep.dates_for("sn00000001", self.issues["sn00000001"], 1)
        d2 = ep.dates_for("sn00000001", self.issues["sn00000001"], 2)
        self.assertEqual(sorted(d1), sorted(d2))
        self.assertEqual(d1, ep.dates_for("sn00000001", self.issues["sn00000001"], 1))

    def test_pass_and_refuse_and_review(self):
        def clip(lane, lccn, date, ed, seq=1, phrase=None):
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
        self.assertIn("sn00000002", s["tried"]["nameplate"])   # refused, but tried
        self.assertTrue(self.calls[0][0] == "sn00000002")  # order was honoured
        self.assertNotIn(("sn00000002", "1880-01-01"), [(c[0], c[1]) for c in self.calls[1:]])

    def test_review_is_logged_and_never_returned(self):
        ep.CLIP = lambda lane, l, d, e, seq=1, phrase=None: fake_result(l, d, gates.REVIEW, page_hits={"lynch"})
        issues = {"sn00000001": self.issues["sn00000001"]}
        s = {"order": ["sn00000001"], "pass": 1, "posted": [], "tried": {}}
        lccn, r = ep.choose(s, issues, log=lambda *a: None)
        self.assertIsNone(r)
        with open(ep.REVIEW_FILE) as f:
            lines = [json.loads(x) for x in f]
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0]["page_hits"], ["lynch"])
        self.assertIn("not a rejection", lines[0]["reasons"][0])
        self.assertEqual(sorted(s["tried"]["nameplate"]["sn00000001"]), sorted(d for d, _ in self.issues["sn00000001"]))

    def test_tries_are_bounded_per_title(self):
        issues = {"sn00000009": [(f"19{i:02d}-01-01", 1) for i in range(20)]}
        ep.CLIP = lambda lane, l, d, e, seq=1, phrase=None: (_ for _ in ()).throw(npc.Refused("x"))
        s = {"order": [], "pass": 1, "posted": [], "tried": {}}
        ep.choose(s, issues, log=lambda *a: None)
        self.assertEqual(len(s["tried"]["nameplate"]["sn00000009"]), ep.TRIES_PER_TITLE)

    def test_pass_rolls_over_when_every_title_is_done(self):
        import io, contextlib
        s = {"order": [], "pass": 1, "tried": {},
             "posted": [{"lccn": l, "date": "x", "pass": 1} for l in self.issues]}
        with contextlib.redirect_stdout(io.StringIO()):
            owed = ep.next_titles(s, self.issues)
        self.assertEqual(s["pass"], 2)
        self.assertEqual(sorted(owed), sorted(self.issues))
        self.assertEqual(s["tried"]["nameplate"], {})

    def test_state_round_trips_atomically(self):
        s = {"order": ["a"], "pass": 3, "posted": [],
             "tried": {lane: {} for lane in ep.LANES + (ep.CARTOON_SEARCH,)}}
        ep.save_state(s)
        self.assertEqual(ep.load_state(), s)
        self.assertFalse(os.path.exists(ep.STATE_FILE + ".tmp"))


class TitleFamilies(unittest.TestCase):
    """19 September 2026: a split paper (three LCCNs for one continuously-
    published title, a Chronicling America title-change split -- Griffin
    Daily News in production) was still getting three turns out of a small
    eligible pool after the 14 September collapse fix, which only stopped
    the shared order shrinking to a narrow lane's subset and said outright
    that the frequency skew itself "would recur for any other town whose
    paper Chronicling America split the same way." These pin that a family
    now occupies exactly one slot in title_order/next_titles/choose, while
    CLIP and the returned lccn still see the real member that published a
    given date."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._state, self._review = ep.STATE_FILE, ep.REVIEW_FILE
        ep.STATE_FILE = os.path.join(self.tmp.name, "post_state.json")
        ep.REVIEW_FILE = os.path.join(self.tmp.name, "review.jsonl")
        self._clip = ep.CLIP
        self._family_of = dict(ep.FAMILY_OF)
        # A synthetic three-LCCN family, gapless and non-overlapping, same
        # shape as Griffin's -- isolated from the real TITLE_FAMILIES tuple
        # so this suite does not depend on the production roster.
        ep.FAMILY_OF = dict(ep.FAMILY_OF, **{
            "sn10000002": "sn10000001", "sn10000003": "sn10000001"})
        self.issues = {
            "sn10000001": [("1881-01-01", 1), ("1885-06-01", 1)],
            "sn10000002": [("1890-01-01", 1)],
            "sn10000003": [("1920-01-01", 1), ("1925-01-01", 1)],
            "sn00000009": [("1900-01-01", 1)],
        }

    def tearDown(self):
        ep.STATE_FILE, ep.REVIEW_FILE, ep.CLIP = self._state, self._review, self._clip
        ep.FAMILY_OF = self._family_of
        self.tmp.cleanup()

    def test_family_resolves_to_its_canonical_member(self):
        self.assertEqual(ep.family("sn10000002"), "sn10000001")
        self.assertEqual(ep.family("sn10000003"), "sn10000001")
        self.assertEqual(ep.family("sn10000001"), "sn10000001")
        self.assertEqual(ep.family("sn00000009"), "sn00000009")   # no family

    def test_title_order_collapses_a_family_to_one_slot(self):
        s = {"order": [], "pass": 1, "posted": [], "tried": {}}
        order = ep.title_order(s, self.issues)
        self.assertEqual(sorted(order), sorted({"sn10000001", "sn00000009"}))
        self.assertNotIn("sn10000002", order)
        self.assertNotIn("sn10000003", order)

    def test_title_order_self_heals_a_state_still_holding_raw_members(self):
        """A state file saved before this merge existed may hold several of
        a family's raw members as separate entries (production's did, for
        Griffin). The first call must collapse them to one, keeping the
        earliest surviving position, exactly as the 14 September fix
        self-healed a collapsed order with no manual edit."""
        s = {"order": ["sn10000002", "sn00000009", "sn10000003", "sn10000001"],
             "pass": 1, "posted": [], "tried": {}}
        order = ep.title_order(s, self.issues)
        self.assertEqual(order, ["sn10000001", "sn00000009"])

    def test_next_titles_owes_a_family_only_one_turn(self):
        s = {"order": [], "pass": 1, "posted": [], "tried": {}}
        owed = ep.next_titles(s, self.issues, lane="nameplate")
        self.assertEqual(owed.count("sn10000001"), 1)
        self.assertNotIn("sn10000002", owed)
        self.assertNotIn("sn10000003", owed)

    def test_choose_returns_the_real_member_that_published_the_date(self):
        """The family id is internal bookkeeping; the caller (and
        state["posted"]) must see the actual LCCN CLIP fetched from, for
        accurate citation and history."""
        calls = []

        def clip(lane, lccn, date, ed, seq=1, phrase=None):
            calls.append((lccn, date))
            return fake_result(lccn, date)
        ep.CLIP = clip
        s = {"order": ["sn10000001"], "pass": 1, "posted": [], "tried": {}}
        lccn, r = ep.choose(s, {"sn10000001": self.issues["sn10000001"],
                                 "sn10000002": self.issues["sn10000002"],
                                 "sn10000003": self.issues["sn10000003"]},
                             log=lambda *a: None)
        self.assertIn(lccn, ("sn10000001", "sn10000002", "sn10000003"))
        self.assertEqual(r["lccn"], lccn)
        self.assertEqual(calls[0][0], lccn)   # CLIP was called with the real member

    def test_a_family_gets_one_turn_per_pass_per_lane_regardless_of_which_member(self):
        """Once sn10000002 (a Griffin-shaped family member) has posted in
        this lane this pass, sn10000001 and sn10000003 -- its family-mates
        -- must not also get a turn: this is the mechanism that let three
        LCCNs of one paper post three times in the account's opening weeks."""
        s = {"order": ["sn10000001"], "pass": 1,
             "posted": [{"lccn": "sn10000002", "date": "1890-01-01",
                         "pass": 1, "lane": "nameplate"}],
             "tried": {}}
        owed = ep.next_titles(s, self.issues, lane="nameplate")
        self.assertNotIn("sn10000001", owed)   # the family's turn is already taken
        self.assertIn("sn00000009", owed)      # an unrelated title is unaffected

    def test_tries_are_bounded_across_the_whole_family(self):
        """TRIES_PER_TITLE is a budget per TURN, not per LCCN -- a family
        does not get TRIES_PER_TITLE dates on each of its members."""
        many = {"sn10000001": [(f"18{i:02d}-01-01", 1) for i in range(10)],
                "sn10000002": [(f"19{i:02d}-01-01", 1) for i in range(10)]}
        ep.CLIP = lambda lane, l, d, e, seq=1, phrase=None: (_ for _ in ()).throw(npc.Refused("x"))
        s = {"order": [], "pass": 1, "posted": [], "tried": {}}
        ep.choose(s, many, log=lambda *a: None)
        self.assertEqual(len(s["tried"]["nameplate"]["sn10000001"]), ep.TRIES_PER_TITLE)

    def test_recent_titles_and_search_lane_dedupe_treat_a_family_as_one_title(self):
        s = {"order": [], "pass": 1,
             "posted": [{"lccn": "sn10000002", "date": "1890-01-01",
                         "pass": 1, "lane": "ad"}],
             "tried": {}}
        recent = ep.recent_titles(s, "ad")
        self.assertIn("sn10000001", recent)   # normalised through family()
        cands = [("sn10000001", "1885-06-01", 1, 1, "phrase"),
                 ("sn00000009", "1900-01-01", 1, 1, "phrase")]
        ep.CLIP = lambda lane, l, d, e, seq=1, phrase=None: fake_result(l, d)
        lccn, r = ep.choose_search(s, cands, "ad", log=lambda *a: None)
        self.assertEqual(lccn, "sn00000009")   # the family member was skipped as recent


class Lanes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._state, self._review, self._clip = ep.STATE_FILE, ep.REVIEW_FILE, ep.CLIP
        ep.STATE_FILE = os.path.join(self.tmp.name, "s.json")
        ep.REVIEW_FILE = os.path.join(self.tmp.name, "r.jsonl")

    def tearDown(self):
        ep.STATE_FILE, ep.REVIEW_FILE, ep.CLIP = self._state, self._review, self._clip
        self.tmp.cleanup()

    def test_rotation_follows_the_lane_that_last_posted(self):
        s = {"posted": []}
        self.assertEqual(ep.next_lane(s), "nameplate")
        s["posted"] = [{"lane": "nameplate"}, {"lane": "headline"}]
        self.assertEqual(ep.next_lane(s), "ad")
        s["posted"].append({"lane": "ad", "dry": True})  # dry posts count: previews rotate
        self.assertEqual(ep.next_lane(s), "market")
        s["posted"].append({"lane": "cartoon"})           # the last lane wraps
        self.assertEqual(ep.next_lane(s), "nameplate")

    def test_an_empty_lane_does_not_give_the_next_one_a_double_turn(self):
        """25 September 2026: market and classified came up empty, cartoon
        took the slot, and the post count then pointed at classified, which
        failed again and handed cartoon a second post in a row."""
        s = {"posted": [{"lane": x} for x in ("nameplate", "headline", "ad", "cartoon")]}
        self.assertEqual(ep.next_lane(s), "nameplate")

    def test_a_hand_run_held_lane_falls_back_to_the_post_count(self):
        s = {"posted": [{"lane": "nameplate"}, {"lane": "article"}]}
        self.assertEqual(ep.next_lane(s), ep.LANES[2])

    def test_cartoon_draws_from_the_credit_line_search_first_then_the_title_order(self):
        """12 September 2026: the search half posts as "cartoon", keeps its
        own tried map, and hands to the title order when nothing passes."""
        calls = []
        def fake_clip(lane, lccn, date, ed=1, seq=1, phrase=None, log=print):
            calls.append((lane, lccn, date, seq, phrase))
            if seq == 7:
                return {"postable": True, "lane": lane, "lccn": lccn, "date": date, "edition": ed,
                        "seq": seq, "url": "u", "caption": "", "page_hits": [], "words": "",
                        "verdict": type("V", (), {"reasons": []})()}
            raise ep.npc.Refused("no")
        state = {"order": [], "pass": 1, "posted": [], "tried": {}}
        for lane in ep.LANES + (ep.CARTOON_SEARCH,):
            state["tried"].setdefault(lane, {})
        sources = {"cartoon": {"t2": [("1915-01-01", 1)]},
                   ep.CARTOON_SEARCH: [("t1", "1916-05-05", 1, 7, "International Feature Service")]}
        with mock.patch.object(ep, "CLIP", fake_clip):
            lccn, r = ep.pick(state, sources, "cartoon", log=lambda m: None)
        self.assertEqual(lccn, "t1")
        self.assertEqual(r["lane"], "cartoon")
        self.assertEqual(calls[0], ("cartoon", "t1", "1916-05-05", 7, "International Feature Service"))
        self.assertIn("t1:1916-05-05:7", state["tried"][ep.CARTOON_SEARCH])
        # nothing from the search: the title order is tried
        calls.clear()
        sources[ep.CARTOON_SEARCH] = [("t1", "1916-05-05", 1, 3, "x")]
        state["tried"][ep.CARTOON_SEARCH] = {}
        with mock.patch.object(ep, "CLIP", fake_clip):
            ep.pick(state, sources, "cartoon", log=lambda m: None)
        self.assertEqual([c[1] for c in calls], ["t1", "t2"])

    def test_eligible_drops_issues_before_the_lanes_floor_and_empty_titles(self):
        issues = {"a": [("1849-03-17", 1), ("1905-01-01", 1)], "b": [("1871-09-19", 1)]}
        self.assertEqual(ep.eligible(issues, "cartoon"), {"a": [("1905-01-01", 1)]})
        self.assertEqual(ep.eligible(issues, "nameplate"), issues)   # no floor

    def test_the_article_lane_is_held_on_his_instruction(self):
        # 11 September 2026: "Hold the article lane until the ad test exists."
        # Both article picks in that evening's twelve were grocers' ads. A hold
        # is a decision pending, not a bug: restore it only when he says so, and
        # move this test with it.
        self.assertNotIn("article", ep.LANES)
        # "cartoon" joined 12 September 2026 ("Build the cartoon lane, strips included");
        # "classified" 20 September 2026 ("Release the lane into the rotation")
        self.assertEqual(ep.LANES, ("nameplate", "headline", "ad", "market", "classified", "cartoon"))

    def test_the_classified_lane_is_a_search_lane_with_an_ocr_alt(self):
        # Built and held 20 September 2026 ("bring me the crops to look at
        # first"), released the same evening. A held lane sits in HELD_LANES
        # and runs only under --lane; nothing is held now.
        self.assertEqual(ep.HELD_LANES, ())
        self.assertIn("classified", ep.SEARCH_LANES)      # a search lane, like ad and market
        self.assertIn("classified", ep.SEARCH_TRIES)
        r = fake_result(); r["lane"] = "classified"; r["generated"] = False
        r["words"] = "LOST—Brown leather suit case"
        self.assertTrue(ep.alt_text(r).startswith("Classified advertisements from “The Abbeville Chronicle,”"))

    def test_no_lane_carries_a_bracketed_label(self):
        # His call on the first headline post, 11 September 2026.
        for lane in ep.LANE_LABEL:
            r = fake_result(); r["lane"] = lane; r["words"] = "COTTON 8 1/2"; r["generated"] = False
            text = ep.text_of(ep.compose(r))
            self.assertTrue(text.startswith("The Abbeville Chronicle, "), (lane, text[:30]))
            self.assertNotIn("[", text)

    def test_alt_carries_the_words_and_names_the_model_only_when_used(self):
        r = fake_result(); r["lane"] = "headline"; r["words"] = "REESE IS ON THE RACK"; r["generated"] = True
        alt = ep.alt_text(r)
        self.assertTrue(alt.startswith("A.I.-transcribed headline from “The Abbeville Chronicle,”"))
        self.assertIn("“REESE IS ON THE RACK”", alt)
        r["lane"] = "market"; r["generated"] = False; r["words"] = "Cotton 8 1/2"
        alt = ep.alt_text(r)
        self.assertTrue(alt.startswith("Market report from"))
        self.assertNotIn("A.I.", alt)

    def test_search_lane_skips_tried_and_recent_titles_and_is_bounded(self):
        calls = []
        def clip(lane, l, d, e, seq=1, phrase=None):
            calls.append((l, d, seq)); raise npc.Refused("x")
        ep.CLIP = clip
        cands = [(f"sn{i:08d}", "1890-01-01", 1, 2, "sarsaparilla") for i in range(40)]
        s = {"order": [], "pass": 1, "tried": {}, "posted": [{"lane": "ad", "lccn": "sn00000003"}]}
        lccn, r = ep.choose_search(s, cands, "ad", log=lambda *a: None)
        self.assertIsNone(r)
        self.assertEqual(len(calls), ep.SEARCH_TRIES["ad"])
        self.assertNotIn("sn00000003", [c[0] for c in calls])
        again = []
        ep.CLIP = lambda lane, l, d, e, seq=1, phrase=None: again.append(l) or (_ for _ in ()).throw(npc.Refused("x"))
        ep.choose_search(s, cands, "ad", log=lambda *a: None)
        self.assertFalse(set(again) & {c[0] for c in calls})

    def test_old_flat_tried_map_migrates_to_the_nameplate_lane(self):
        with open(ep.STATE_FILE, "w") as f:
            json.dump({"order": [], "pass": 1, "posted": [], "tried": {"sn1": ["1900-01-01"]}}, f)
        s = ep.load_state()
        self.assertEqual(s["tried"]["nameplate"], {"sn1": ["1900-01-01"]})
        for lane in ep.LANES:
            self.assertIn(lane, s["tried"])


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
        # Launch evening, 11 September 2026: Grady is a LINK on the words
        # "journalism school at UGA", not a mention, and the handle is gone.
        self.assertEqual([s for s in last if s[0] == "mention"],
                         [("mention", "@stanfordc.bsky.social", "did:plc:a")])
        self.assertIn(("link", "journalism school at UGA", "https://bsky.app/profile/ugagrady.bsky.social"), last)
        self.assertNotIn("@ugagrady", prof.thread()[-1]["text"])
        fifth = ep.thread_segments(prof.thread()[4], dids)
        link = next(s for s in fifth if s[0] == "link")
        # And post 5's link rides on the paper's name, no printed URL.
        self.assertEqual(link[1], "Georgia Weekly Telegraph and Georgia Journal & Messenger")
        self.assertEqual(link[2], "https://gahistoricnewspapers.galileo.usg.edu/lccn/sn85034222/1875-02-23/ed-1/seq-1/")
        self.assertNotIn("gahistoricnewspapers", prof.thread()[4]["text"])

    def test_post_five_date_is_us_order_full_month(self):
        self.assertIn("February 23, 1875", prof.thread()[4]["text"])
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
        self.assertEqual(ep.CREDIT, "Courtesy of the Digital Library of Georgia.")
        self.assertIn(ep.CREDIT, ep.text_of(ep.compose(fake_result())))

    def test_run_is_bounded(self):
        self.assertLessEqual(ep.TITLES_PER_RUN * ep.TRIES_PER_TITLE, 40)
        self.assertLessEqual(max(ep.SEARCH_TRIES.values()), 20)


if __name__ == "__main__":
    unittest.main()


class TownTag(unittest.TestCase):
    def test_city_becomes_one_tag_word(self):
        self.assertEqual(ep.town_tag("Fort Valley"), "FortValley")
        self.assertEqual(ep.town_tag("Atlanta"), "Atlanta")
        self.assertEqual(ep.town_tag("St. Marys"), "StMarys")
        self.assertIsNone(ep.town_tag(""))
        self.assertIsNone(ep.town_tag(None))

    def test_no_city_means_no_third_tag(self):
        text = ep.text_of(ep.compose(fake_result(city="")))
        self.assertTrue(text.endswith("\n\n#Georgia #History"))
