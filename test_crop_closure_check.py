#!/usr/bin/env python3
"""
Tests for crop_closure_check.py. No network: the network-touching half
(check_post) is a thin wrapper around ghn_api/clips calls already covered
by test_clips.py's ClosureMargins and AdHeadingGap/AdTailGap classes, so
what is pinned here is the part unique to this script -- state-file
reading, date filtering, the URL builder, and the pure classification
flag_from_margins() applies to an already-computed margins dict.
"""
import unittest
from datetime import datetime, timezone

import crop_closure_check as ccc


class RecentAdPosts(unittest.TestCase):
    NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)

    def test_only_the_ad_lane_is_kept(self):
        state = {"posted": [
            {"lane": "ad", "at": "2026-09-14T14:10:22+00:00"},
            {"lane": "market", "at": "2026-09-14T14:10:22+00:00"},
            {"lane": "cartoon", "at": "2026-09-14T14:10:22+00:00"},
        ]}
        out = ccc.recent_ad_posts(state, 7, now=self.NOW)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["lane"], "ad")

    def test_only_within_the_window_is_kept(self):
        state = {"posted": [
            {"lane": "ad", "at": "2026-09-14T14:10:22+00:00"},   # 1 day ago
            {"lane": "ad", "at": "2026-08-01T00:00:00+00:00"},   # weeks ago
        ]}
        out = ccc.recent_ad_posts(state, 7, now=self.NOW)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["at"], "2026-09-14T14:10:22+00:00")

    def test_a_missing_or_unparseable_timestamp_is_skipped_not_crashed_on(self):
        state = {"posted": [
            {"lane": "ad"},                                 # no 'at' at all
            {"lane": "ad", "at": "not-a-date"},
            {"lane": "ad", "at": "2026-09-14T14:10:22+00:00"},
        ]}
        out = ccc.recent_ad_posts(state, 7, now=self.NOW)
        self.assertEqual(len(out), 1)

    def test_an_empty_posted_list_returns_nothing(self):
        self.assertEqual(ccc.recent_ad_posts({"posted": []}, 7, now=self.NOW), [])
        self.assertEqual(ccc.recent_ad_posts({}, 7, now=self.NOW), [])


class PhraseFor(unittest.TestCase):
    def test_the_phrase_is_looked_up_by_lccn_date_seq(self):
        state = {"tried": {"ad": {"sn87090234:1872-10-01:3": "clothing and hats"}}}
        post = {"lccn": "sn87090234", "date": "1872-10-01", "seq": 3}
        self.assertEqual(ccc.phrase_for(state, post), "clothing and hats")

    def test_a_post_with_no_tried_record_returns_none(self):
        state = {"tried": {"ad": {}}}
        post = {"lccn": "sn00000000", "date": "1900-01-01", "seq": 1}
        self.assertIsNone(ccc.phrase_for(state, post))

    def test_a_missing_tried_section_entirely_returns_none_not_a_crash(self):
        post = {"lccn": "sn00000000", "date": "1900-01-01", "seq": 1}
        self.assertIsNone(ccc.phrase_for({}, post))


class FlagFromMargins(unittest.TestCase):
    def test_a_rule_stop_is_never_flagged(self):
        margins = {"top": {"reason": "rule", "ratio": None, "text": "x"}, "bottom": None}
        self.assertEqual(ccc.flag_from_margins(margins), [])

    def test_a_cap_stop_is_never_flagged(self):
        margins = {"top": None,
                  "bottom": {"reason": "display-excluded-by-cap", "ratio": None, "text": "x"}}
        self.assertEqual(ccc.flag_from_margins(margins), [])

    def test_no_neighbor_is_never_flagged(self):
        self.assertEqual(ccc.flag_from_margins({"top": None, "bottom": None}), [])

    def test_a_healthy_gap_ratio_is_not_flagged(self):
        margins = {"top": {"reason": "gap", "ratio": 0.95, "text": "x"}, "bottom": None}
        self.assertEqual(ccc.flag_from_margins(margins, floor=0.15), [])

    def test_a_near_miss_gap_ratio_is_flagged(self):
        margins = {"top": {"reason": "gap", "ratio": 0.02, "text": "x"}, "bottom": None}
        found = ccc.flag_from_margins(margins, floor=0.15)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["side"], "top")

    def test_a_negative_ratio_is_flagged(self):
        margins = {"top": {"reason": "gap", "ratio": -0.5, "text": "x"}, "bottom": None}
        self.assertEqual(len(ccc.flag_from_margins(margins, floor=0.15)), 1)

    def test_should_have_been_included_is_always_flagged(self):
        margins = {"top": None,
                  "bottom": {"reason": "should-have-been-included", "ratio": 0.0, "text": "x"}}
        found = ccc.flag_from_margins(margins, floor=0.15)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["side"], "bottom")

    def test_both_sides_can_be_flagged_independently(self):
        margins = {
            "top": {"reason": "gap", "ratio": 0.01, "text": "a"},
            "bottom": {"reason": "gap", "ratio": 0.9, "text": "b"},
        }
        found = ccc.flag_from_margins(margins, floor=0.15)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["side"], "top")

    def test_an_empty_margins_dict_flags_nothing(self):
        self.assertEqual(ccc.flag_from_margins({}), [])
        self.assertEqual(ccc.flag_from_margins(None), [])


class PostUrl(unittest.TestCase):
    def test_the_rkey_is_taken_from_the_end_of_the_uri(self):
        post = {"uri": "at://did:plc:4yw7vlj3rwihz2ophxlemh36/app.bsky.feed.post/3mvibzeeibr2x"}
        self.assertEqual(
            ccc.post_url(post),
            "https://bsky.app/profile/georgianewspapers.bsky.social/post/3mvibzeeibr2x")

    def test_a_missing_uri_does_not_crash(self):
        self.assertTrue(ccc.post_url({}).endswith("/post/"))


class LoadState(unittest.TestCase):
    def test_a_missing_file_returns_none_not_a_crash(self):
        self.assertIsNone(ccc.load_state("/nonexistent/path/post_state.json"))


if __name__ == "__main__":
    unittest.main()
