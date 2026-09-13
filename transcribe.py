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
TIMEOUT = 300            # ⚠️ Not 120. Measured 11 September 2026, afternoon: the
                         # harness reading the image and answering a trivial
                         # prompt is 10 s, but a real transcription is 60-98 s
                         # (98 s for the Dalton Argus band at 1600px, 71 s at
                         # 1000px, so the size is not the cost). At 120 s the
                         # twelve-sample dry run timed out 14 times, 28 minutes
                         # of nothing, and each timeout also spends a candidate.
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

# ⚠️ The model's own commentary, shipped as the page's words. Found on the
# evening of 11 September 2026 in a dry run of the FIRST post: the Dawson
# Journal's band came back "The image doesn't allow further zoom via this
# tool, but the visible text is clear enough to transcribe. Vol. II. DAWSON,
# GA., ..." and clean() has no eye for it, so it would have gone out as alt
# text at 09:10 the next morning. Under --tools Read the model tries to
# enlarge the image, cannot, and says so before answering. The prompt already
# says "no commentary, no preamble" three ways; a prompt rule is not a fix
# (CLAUDE.md, the alt-text verification pass). So a reply that reads as
# commentary is REJECTED, the call is made once more naming the fault, and a
# second such reply refuses the clip (None), which costs a candidate and not
# a reader. The markers are tool talk and first-person apology, deliberately
# NOT "let me" or "I'll", which an 1860s editorial can open with.
# ⚠️⚠️ And the SECOND shape, which shipped on the FIRST POST at 18:23 KST on
# 11 September 2026 with the first guard in place: not tool talk but
# DESCRIPTION of the page's elements, "The masthead line ”DAWSON, GA., …” is
# clearly the large display dateline, with ”Vol. II.” and ”No. 21.” flanking
# it in bold. The advertisement ”HOYL & SIMMONS,” is in bold display type."
# No first person, no tool, so the first markers slept through it. The
# markers below name that register: a sentence ABOUT a line of type rather
# than the line itself. And for BAND_PROMPT (display type only) there is a
# second, structural test in `looks_described()`: a band transcription is
# mostly capitals and Title Case, while a description is mostly lowercase
# prose; the bad Dawson reply is 60 percent lowercase words against 17 for
# the good one. That test is NOT applied to the full PROMPT, where a prose
# advertisement is legitimately lowercase.
COMMENTARY = re.compile(
    r"\bthis tool\b|\bzoom\b|\bas an ai\b"
    r"|\bi(?:'|’)?m (?:unable|not able|sorry)\b|\bi am (?:unable|not able|sorry)\b"
    r"|\bi (?:can(?:no|'|’)t|cannot|could not|couldn(?:'|’)t) "
    r"(?:zoom|read|make out|see|access|open|view)\b"
    r"|\bthe (?:image|file|clipping|scan) (?:is|does|doesn(?:'|’)?t|appears|shows|contains)\b"
    r"|\bhere(?:'|’)?s? (?:is |are )?(?:the |my |a )?transcription\b|\btranscription:"
    r"|\bvisible text\b"
    # description of type rather than the type itself
    r"|\bis clearly\b|\bin bold(?: display)? type\b|\bin (?:large|small|bold) (?:display )?type\b"
    r"|\bflanking\b|\bappears to (?:read|be|say)\b|\breads as follows\b"
    r"|\bthe (?:masthead|dateline|nameplate|headline|banner) (?:line|text|reads|is|appears)\b"
    r"|\bthe (?:large|small|main|bold) (?:display |body )?(?:text|type|headline|dateline)\b"
    r"|\bset in (?:large|small|bold|display|body)\b",
    re.IGNORECASE)
LOWERCASE_SHARE_MAX = 0.45


def looks_described(text):
    """For a display-type reply only: true when most words are lowercase,
    which is prose about the page rather than the page's display type."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'’]*", text) if len(w) > 1]
    if len(words) < 6:
        return False
    lower = sum(1 for w in words if w[0].islower())
    return lower / len(words) > LOWERCASE_SHARE_MAX
COMMENTARY_REMINDER = (
    " Your previous reply began with commentary about the image or your tools "
    "rather than the printed words. Reply with the printed words only."
)


def is_commentary(text):
    """True when the reply talks about the image or the model instead of
    quoting the page."""
    return bool(COMMENTARY.search(text))


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


# ⚠️ The band's items are separated by PERIODS, his call on 12 September 2026,
# on reading the Americus Times-Recorder alt: "GERMANS ATTACK SOMME FRONTS
# FAILING TO GAIN WEATHER MAY ALLOW VISITORS TO SHOW" is nine headlines as one
# clause, because the prompt asked for a single space between lines and a
# screen reader gets no pause. The model is asked only WHERE the boundaries
# are (one item per line); the punctuation is ours, so it is the same every
# time, and a period buys a longer pause than a comma. The paper did separate
# these items, by rules and white space, so this is nearer what was printed,
# not further from it.
TERMINAL = ".!?…"


def items_of(text):
    """The reply's lines, each cleaned as clean() cleans, empties dropped."""
    text = re.sub(r"^```[a-z]*\n?|\n?```$", "", text.strip()).strip()
    out = []
    for line in text.splitlines():
        line = " ".join(line.split()).strip().strip('"').strip()
        if line:
            out.append(line)
    return out


def join_items(items):
    """One string, each item ending in a period unless it already ends in
    terminal punctuation, so "A. B! C." and never "A.. B"."""
    parts = []
    for it in items:
        it = it.strip()
        if not it:
            continue
        parts.append(it if it[-1] in TERMINAL else it + ".")
    return " ".join(parts)


# The band under a nameplate: display type only. ⚠️ Asked for every word, an
# 1839 front page's band is a wall of body text, thousands of characters, and
# the call ran past 240 s twice per candidate on 11 September 2026 (eight
# minutes to learn nothing, and the candidate spent). Body text is what the
# archive's OCR reads well and the page gate already screens; the band is
# transcribed for the display type the OCR cannot read, so that is all it
# asks for.
BAND_PROMPT = (
    "The file {name} in this directory is a clipping from a Georgia newspaper "
    "printed in {year}. Transcribe only the words set in large or bold display "
    "type: headlines, titles, slogans, datelines and the like. Ignore body "
    "text set in small type entirely, even if there is a lot of it. Transcribe "
    "exactly as printed, in reading order. Put each headline, title, slogan or "
    "dateline on a line of its own, however many printed lines it occupies, "
    "with a single space between the printed lines of one item. "
    "Keep the original spelling and capitalisation. Write [illegible] for any "
    "word you cannot read. Reply with the transcription and nothing else: no "
    "description, no summary, no commentary, no quotation marks around it, no "
    "preamble. If there is no display type at all, reply with the single word "
    "NONE."
)

# The headline lane's crop: a headline and whatever decks sit under it, all
# display type, so the same one-item-per-line rule as the band (his call,
# 12 September 2026, "Do the same for the headline lane"): a deck otherwise
# runs straight on from its headline in the alt. ⚠️ looks_described() is NOT
# applied here: a deck set in sentence case is legitimately lowercase prose.
# The full PROMPT stays for articles and advertisements, whose lines wrap
# mid-sentence and where a period per line would be wrong.
HEADLINE_PROMPT = (
    "The file {name} in this directory is a clipping from a Georgia newspaper "
    "printed in {year}: a headline, with any decks or subheadings beneath it. "
    "Transcribe the words printed in it, exactly as printed, in reading order. "
    "Put the headline and each deck or subheading on a line of its own, however "
    "many printed lines it occupies, with a single space between the printed "
    "lines of one item. Keep the original spelling and capitalisation. Write "
    "[illegible] for any word you cannot read. Reply with the transcription and "
    "nothing else: no description, no summary, no commentary, no quotation marks "
    "around it, no preamble. If the image is unreadable reply exactly CANNOT_READ."
)
# the prompts whose reply is one item per line, joined by join_items()
ITEM_PROMPTS = (BAND_PROMPT, HEADLINE_PROMPT)


def _strip_fences(text):
    return re.sub(r"^```[a-z]*\n?|\n?```$", "", (text or "").strip()).strip()


def _call_model(image_bytes, year, prompt, *, env, model, timeout, log,
                 unavailable_label, failed_label, on_success=None):
    """One confined `claude -p --restricted --tools Read` call over the image
    alone in its own cwd -- shared by ask() and transcribe(), whose bodies
    were near-identical copies of exactly this: build the temp dir, write
    the image, run the call, catch `TimeoutExpired`/`OSError`, wait out a
    spent quota once per run through `limit_guard`. Up to two attempts: a
    transient exception or a hard failure spends one, a successful quota
    wait does not (`tries -= 1`), matching both callers' original loops.

    ⚠️⚠️ --restricted --tools Read, and the reason is on the record
    (11 September 2026). Unconfined, `claude -p` is an agent with Bash: on
    an easy band it read the file once (35 s); on a hard one it cropped and
    enlarged the image with sips and Python through a dozen tool calls
    (60-280 s, the timeouts); and on the Georgia Pioneer of 22 March 1839 it
    ran `find ~ -iname clips.py`, read THIS project's code, ran
    clip_nameplate itself on three pages and returned "Ran cleanly.
    Results: ..." as the transcription. Confined to reading the one file it
    answers in 20 s in two turns.

    `on_success(raw_stdout)` sees a successful reply and returns either
    `("return", value)` to stop here and hand back `value`, or
    `("retry", new_prompt)` to spend the second attempt on a reformulated
    prompt (transcribe()'s commentary reminder, appended to the *template*
    so it survives the `.format()` below). With no `on_success`, a
    successful reply is returned as raw stdout (ask()'s case).
    `unavailable_label` and `failed_label` are the only wording difference
    between the two callers' log lines. The subprocess invocation itself --
    flags, env, cwd, timeout, stdin -- must stay exactly as it is."""
    global _limit_waited
    tries = 0
    while tries < 2:
        tries += 1
        try:
            with tempfile.TemporaryDirectory() as td:
                name = "clip.jpg"
                with open(os.path.join(td, name), "wb") as f:
                    f.write(image_bytes)
                r = subprocess.run(["claude", "-p", "--restricted", "--tools", "Read",
                                    "--model", model, prompt.format(name=name, year=year)],
                                   capture_output=True, text=True, env=env,
                                   cwd=td, timeout=timeout,
                                   # ⚠️ stdin closed. claude -p reads whatever
                                   # stdin holds as more prompt, and a caller
                                   # run as `python3 - <<EOF` hands it the rest
                                   # of that script: on 11 September 2026 the
                                   # model was given a timing harness that way,
                                   # ran it (it had Bash then), and returned
                                   # the harness's output as a "transcription".
                                   stdin=subprocess.DEVNULL)
        except (subprocess.TimeoutExpired, OSError) as exc:
            log(f"  ({unavailable_label} unavailable: {exc.__class__.__name__})")
            continue
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()[:200] or "(no output)"
            if not _limit_waited and limit_guard.is_usage_limit(err):
                _limit_waited = True
                if limit_guard.wait_for_reset(err, budget_s=LIMIT_BUDGET_S,
                                              log=lambda m: log(f"  {m}")):
                    tries -= 1
                    continue
            log(f"  ({failed_label} failed, exit {r.returncode}: {err})")
            return None
        if on_success is None:
            return r.stdout
        action, value = on_success(r.stdout)
        if action == "retry":
            prompt = value
            continue
        return value
    return None


def ask(image_bytes, year, prompt, *, env=None, model=MODEL, timeout=TIMEOUT, log=print):
    """One confined call with the image alone in its cwd, the reply's lines
    kept (a prompt whose answer is labelled lines needs them), or None on a
    failure. The pictures lane's reading of a drawing goes through here:
    transcribe() applies the commentary guards, which a DESCRIPTION of a
    picture legitimately trips ("the drawing shows"), so that lane reads its
    reply through its own parser. Same flags, same stdin, same quota wait;
    the confinement is not to be relaxed here either."""
    env = env or claude_env()
    raw = _call_model(image_bytes, year, prompt, env=env, model=model, timeout=timeout,
                      log=log, unavailable_label="model", failed_label="model call")
    return None if raw is None else _strip_fences(raw)


def transcribe(image_bytes, year, *, env=None, model=MODEL, timeout=TIMEOUT, log=print,
               max_chars=MAX_CHARS, prompt=PROMPT):
    """The printed words, or None. `max_chars` is the cap on the reply: a
    headline's is MAX_CHARS, the band under a nameplate is allowed more,
    since there its only job is the vocabulary check."""
    env = env or claude_env()

    def on_success(raw_stdout):
        text = clean(raw_stdout)
        if is_commentary(text) or (prompt is BAND_PROMPT and looks_described(text)):
            log(f"  (transcription rejected: reads as the model's commentary, not the page: "
                f"{text[:80]!r})")
            return "retry", prompt + COMMENTARY_REMINDER
        if prompt is BAND_PROMPT and text.strip() == "NONE":
            return "return", ""
        if "CANNOT_READ" in text:
            log("  (transcription: model could not read the clip)")
            return "return", None
        if any(prompt is p for p in ITEM_PROMPTS):
            # the guards above read the flattened reply; the reader gets the
            # items with a period between them (see join_items)
            text = join_items(items_of(raw_stdout))
        if not (MIN_CHARS <= len(text) <= max_chars):
            log(f"  (transcription rejected: {len(text)} chars)")
            return "return", None
        return "return", text

    return _call_model(image_bytes, year, prompt, env=env, model=model, timeout=timeout,
                       log=log, unavailable_label="transcription", failed_label="transcription",
                       on_success=on_success)
