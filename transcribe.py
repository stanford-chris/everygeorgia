#!/usr/bin/env python3
"""
transcribe.py -- the words printed in a clipping, read by claude -p's vision.

Why a model at all. The account's promise, in the 21 August 2026 email and in
post 4 of the pinned thread, is alt text carrying "the actual words of the
clip". For body type the OCR supplies them. For display type it does not:
"THE ABBEVILLE CHRONICLE." OCRs as 't mraLE mK', and a headline is display
type by definition. Nothing else on this account is generated, and the
nameplate lane needs no model, so this is the ONE place model-written text
reaches a reader, and it is labelled where it lands: every alt built from
this carries PREFIX at its head, for the reason image_alt.py in old-seoul
gives at length (alt text travels without the bio; the reader who most needs
to know is the one least likely to have seen it).

⚠️ It transcribes. It does not describe, summarise or interpret, and the
prompt says so three ways, because a model asked about a headline will
happily explain it. What comes back is the words or nothing.

⚠️ The transcription is ALSO the vocabulary gate for display type. The crop
gate in gates.py reads the OCR, which for a headline is the text it cannot
read. On 11 September 2026 two banner headlines were shipped as nameplate
furniture for exactly that reason. So clips.py runs the vocabulary prefixes
over the transcription too, and a transcription that carries them REFUSES
the crop.

⚠️ Failure returns None and the caller refuses the clip. No fallback to a
citation here, unlike the photograph bots: an alt saying only "a headline
from the Augusta Herald" breaks the promise post 4 makes, and a clip whose
words nobody could read is not one to post.

Same invocation shape as image_alt.py: the image sits alone in a temp
directory that is the model's cwd, the Keychain setup-token goes in as
CLAUDE_CODE_OAUTH_TOKEN so a launchd run does not depend on the interactive
login (scan_filer.py's lesson, 16 August 2026), and a spent quota is waited
out once per run through limit_guard.
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
# ⚠️ ~/Scripts by name, not this file's parent: this directory lives in
# ~/Projects and is reached from ~/Scripts through a symlink, so the parent
# of the real path is not ~/Scripts (the trap that broke everycarnegie's
# describer on 30 August 2026).
sys.path.insert(0, os.path.join(os.path.expanduser("~"), "Scripts"))
import limit_guard  # noqa: E402

MODEL = "claude-sonnet-5"
TIMEOUT = 120
LIMIT_BUDGET_S = 1800
PREFIX = "A.I.-transcribed"
CLAUDE_TOKEN_ACCOUNT = "seoulbot"
CLAUDE_TOKEN_SERVICE = "claude-oauth-token"
MAX_CHARS = 1200
MIN_CHARS = 3

PROMPT = (
    "The file {name} in this directory is a clipping from a Georgia newspaper "
    "printed in {year}. Transcribe the words printed in it, exactly as printed, "
    "in reading order, with a single space between lines. Keep the original "
    "spelling and capitalisation. Write [illegible] for any word you cannot "
    "read. Reply with the transcription and nothing else: no description, no "
    "summary, no commentary, no quotation marks around it, no preamble. If the "
    "image is unreadable reply exactly CANNOT_READ."
)

_limit_waited = False


def claude_env():
    env = os.environ.copy()
    r = subprocess.run(["security", "find-generic-password", "-a", CLAUDE_TOKEN_ACCOUNT,
                        "-s", CLAUDE_TOKEN_SERVICE, "-w"], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        env["CLAUDE_CODE_OAUTH_TOKEN"] = r.stdout.strip()
    return env


def clean(text):
    text = re.sub(r"^```[a-z]*\n?|\n?```$", "", text.strip()).strip()
    text = " ".join(text.split()).strip().strip('"').strip()
    return text


def transcribe(image_bytes, year, *, env=None, model=MODEL, timeout=TIMEOUT, log=print,
               max_chars=MAX_CHARS):
    """The printed words, or None. `max_chars` is the cap on the reply: a
    headline's is MAX_CHARS, the band under a nameplate is allowed more,
    since there its only job is the vocabulary check."""
    global _limit_waited
    env = env or claude_env()
    tries = 0
    while tries < 2:
        tries += 1
        try:
            with tempfile.TemporaryDirectory() as td:
                name = "clip.jpg"
                with open(os.path.join(td, name), "wb") as f:
                    f.write(image_bytes)
                r = subprocess.run(["claude", "-p", "--model", model,
                                    PROMPT.format(name=name, year=year)],
                                   capture_output=True, text=True, env=env,
                                   cwd=td, timeout=timeout)
        except (subprocess.TimeoutExpired, OSError) as exc:
            log(f"  (transcription unavailable: {exc.__class__.__name__})")
            continue
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()[:200] or "(no output)"
            if not _limit_waited and limit_guard.is_usage_limit(err):
                _limit_waited = True
                if limit_guard.wait_for_reset(err, budget_s=LIMIT_BUDGET_S,
                                              log=lambda m: log(f"  {m}")):
                    tries -= 1
                    continue
            log(f"  (transcription failed, exit {r.returncode}: {err})")
            return None
        text = clean(r.stdout)
        if "CANNOT_READ" in text:
            log("  (transcription: model could not read the clip)")
            return None
        if not (MIN_CHARS <= len(text) <= max_chars):
            log(f"  (transcription rejected: {len(text)} chars)")
            return None
        return text
    return None
