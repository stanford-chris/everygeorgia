"""The commentary guard in transcribe.py. Stdlib only; `claude -p` is a mock."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcribe  # noqa: E402

DAWSON = ("The image doesn’t allow further zoom via this tool, but the visible text is "
          "clear enough to transcribe. Vol. II. DAWSON, GA., FRIDAY, JUNE 14, 1867. No. 21.")
CLEAN = "Vol. II. DAWSON, GA., FRIDAY, JUNE 14, 1867. No. 21. The Peddler’s Story."
# What the FIRST POST shipped, 18:23 KST 11 September 2026: description, not tool talk.
DESCRIBED = ("The masthead line ”DAWSON, GA., FRIDAY, JUNE 14, 1867.” is clearly the large "
             "display dateline, with ”Vol. II.” and ”No. 21.” flanking it in bold. The "
             "advertisement ”HOYL & SIMMONS,” is in bold display type. DAWSON, GA., FRIDAY, "
             "JUNE 14, 1867. Vol. II. No. 21. HOYL &")
GOOD_BAND = ("Vol. II. DAWSON, GA., FRIDAY, JUNE 14, 1867. No. 21. Rates of Advertising. Job Work "
             "The Peddler’s Story. HOYL & SIMMONS, ATTORNEYS AT LAW, DAWSON, GEORGIA. Young America "
             "at the Wheel. Muscular Development of Women. Remedy for Bud Worm. Power of Scent in a")
PROSE_AD = ("Read what one of the GREATEST NEWSPAPERS IN AMERICA has to say on this subject: The "
            "manufacturers of Castoria have been compelled to spend hundreds of thousands of dollars "
            "to familiarize the public with the signature of Chas. H. Fletcher.")


def _proc(stdout, rc=0):
    m = mock.Mock()
    m.returncode = rc
    m.stdout = stdout
    m.stderr = ""
    return m


class Commentary(unittest.TestCase):
    def test_the_dawson_reply_is_commentary(self):
        self.assertTrue(transcribe.is_commentary(DAWSON))

    def test_the_page_words_are_not(self):
        self.assertFalse(transcribe.is_commentary(CLEAN))

    def test_apology_forms(self):
        for t in ("I'm unable to read this clipping.", "I am sorry, the file is blank.",
                  "Here is the transcription: HOYL & SIMMONS", "I cannot make out the words."):
            self.assertTrue(transcribe.is_commentary(t), t)

    def test_the_first_post_s_described_reply_is_caught_both_ways(self):
        self.assertTrue(transcribe.is_commentary(DESCRIBED))
        self.assertTrue(transcribe.looks_described(DESCRIBED))

    def test_a_real_band_and_a_prose_ad_are_not_described(self):
        self.assertFalse(transcribe.is_commentary(GOOD_BAND))
        self.assertFalse(transcribe.looks_described(GOOD_BAND))
        self.assertFalse(transcribe.is_commentary(PROSE_AD))

    def test_the_lowercase_test_applies_to_the_band_prompt_only(self):
        # Lowercase prose with no marker: refused as a band, accepted as an ad.
        prose = "the quick brown fox jumps over the lazy dog and keeps on running for a while"
        self.assertTrue(transcribe.looks_described(prose))
        with mock.patch.object(transcribe, "claude_env", return_value={}):
            run = mock.Mock(side_effect=[_proc(prose), _proc(prose)])
            with mock.patch.object(transcribe.subprocess, "run", run):
                self.assertIsNone(transcribe.transcribe(b"j", "1867", log=lambda m: None,
                                                        prompt=transcribe.BAND_PROMPT, max_chars=2000))
            run = mock.Mock(side_effect=[_proc(prose)])
            with mock.patch.object(transcribe.subprocess, "run", run):
                self.assertEqual(transcribe.transcribe(b"j", "1867", log=lambda m: None), prose)

    def test_prose_an_editorial_could_open_with_passes(self):
        for t in ("Let me say at once that the image of our fathers is before us.",
                  "I'll not be answerable for the crops this season.",
                  "DISPLAY TYPE of every description at the JOURNAL office."):
            self.assertFalse(transcribe.is_commentary(t), t)


class Retry(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.object(transcribe, "claude_env", return_value={})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_commentary_is_retried_once_with_the_reminder(self):
        run = mock.Mock(side_effect=[_proc(DAWSON), _proc(CLEAN)])
        with mock.patch.object(transcribe.subprocess, "run", run):
            out = transcribe.transcribe(b"jpg", "1867", log=lambda m: None)
        self.assertEqual(out, CLEAN)
        self.assertEqual(run.call_count, 2)
        first, second = (c.args[0][-1] for c in run.call_args_list)
        self.assertNotIn("previous reply", first)
        self.assertIn("previous reply", second)

    def test_commentary_twice_refuses_the_clip(self):
        run = mock.Mock(side_effect=[_proc(DAWSON), _proc(DAWSON)])
        with mock.patch.object(transcribe.subprocess, "run", run):
            out = transcribe.transcribe(b"jpg", "1867", log=lambda m: None)
        self.assertIsNone(out)
        self.assertEqual(run.call_count, 2)

    def test_a_clean_reply_is_one_call_and_no_reminder(self):
        run = mock.Mock(side_effect=[_proc(CLEAN)])
        with mock.patch.object(transcribe.subprocess, "run", run):
            out = transcribe.transcribe(b"jpg", "1867", log=lambda m: None)
        self.assertEqual(out, CLEAN)
        self.assertEqual(run.call_count, 1)
        self.assertNotIn("previous reply", run.call_args.args[0][-1])


class Periods(unittest.TestCase):
    """The band's items are joined with periods, his call on 12 September
    2026: one item per line from the model, the punctuation ours."""
    AMERICUS = ("GERMANS ATTACK SOMME FRONTS FAILING TO GAIN\n"
                "WEATHER MAY ALLOW VISITORS TO SHOW\n\n"
                "ITALY SAYS PEACE TO COME TOGETHER\n"
                "OLDEST AND YOUNGEST SHAKE WITH WILSON.\n"
                "WHERE IS THE MONEY?\n")

    def test_each_item_ends_in_a_period_and_none_is_doubled(self):
        out = transcribe.join_items(transcribe.items_of(self.AMERICUS))
        self.assertEqual(out, "GERMANS ATTACK SOMME FRONTS FAILING TO GAIN. "
                              "WEATHER MAY ALLOW VISITORS TO SHOW. "
                              "ITALY SAYS PEACE TO COME TOGETHER. "
                              "OLDEST AND YOUNGEST SHAKE WITH WILSON. "
                              "WHERE IS THE MONEY?")
        self.assertNotIn("..", out)

    def test_a_wrapped_item_stays_one_item(self):
        # printed over two lines, returned on one: no period inside it
        out = transcribe.join_items(transcribe.items_of("THE NEWS, Established 1871.\nBlakely   &  Ellis"))
        self.assertEqual(out, "THE NEWS, Established 1871. Blakely & Ellis.")

    def test_the_prompt_asks_for_one_item_per_line_and_not_a_single_space_between_lines(self):
        self.assertIn("on a line of its own", transcribe.BAND_PROMPT)
        self.assertNotIn("single space between lines", transcribe.BAND_PROMPT)
        # the full prompt (headline, article, ad) is deliberately unchanged
        self.assertIn("single space between lines", transcribe.PROMPT)

    def test_the_band_reply_reaches_the_caller_with_periods(self):
        with mock.patch.object(transcribe, "claude_env", return_value={}):
            run = mock.Mock(side_effect=[_proc(self.AMERICUS)])
            with mock.patch.object(transcribe.subprocess, "run", run):
                out = transcribe.transcribe(b"j", "1916", log=lambda m: None,
                                            prompt=transcribe.BAND_PROMPT, max_chars=8000)
        self.assertTrue(out.startswith("GERMANS ATTACK SOMME FRONTS FAILING TO GAIN. WEATHER"))
        self.assertTrue(out.endswith("WHERE IS THE MONEY?"))

    def test_none_and_the_other_prompts_are_untouched(self):
        with mock.patch.object(transcribe, "claude_env", return_value={}):
            run = mock.Mock(side_effect=[_proc("NONE\n")])
            with mock.patch.object(transcribe.subprocess, "run", run):
                self.assertEqual(transcribe.transcribe(b"j", "1916", log=lambda m: None,
                                                       prompt=transcribe.BAND_PROMPT), "")
            run = mock.Mock(side_effect=[_proc("REESE IS\nON THE RACK")])
            with mock.patch.object(transcribe.subprocess, "run", run):
                self.assertEqual(transcribe.transcribe(b"j", "1916", log=lambda m: None),
                                 "REESE IS ON THE RACK")

    def test_a_multi_line_reply_is_still_screened_for_commentary(self):
        with mock.patch.object(transcribe, "claude_env", return_value={}):
            run = mock.Mock(side_effect=[_proc(DAWSON.replace(". ", ".\n")), _proc(self.AMERICUS)])
            with mock.patch.object(transcribe.subprocess, "run", run):
                out = transcribe.transcribe(b"j", "1867", log=lambda m: None,
                                            prompt=transcribe.BAND_PROMPT, max_chars=8000)
        self.assertEqual(run.call_count, 2)
        self.assertTrue(out.startswith("GERMANS"))


if __name__ == "__main__":
    unittest.main()
