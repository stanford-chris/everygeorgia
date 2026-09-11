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


if __name__ == "__main__":
    unittest.main()
