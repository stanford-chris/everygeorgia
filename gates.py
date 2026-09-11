#!/usr/bin/env python3
"""
gates.py -- the decision layer: may this crop be posted automatically, must a
person look at it first, or is it out of bounds entirely.

⚠️⚠️ THERE ARE THREE OUTCOMES, NOT TWO, AND THAT IS THE WHOLE POINT OF THIS
FILE. A binary allow/deny would silence the Black press, and the README has
said so since before any of this was built: a keyword blocklist rejected the
front pages of "The Colored American" (Augusta, 6 January 1866) and "The
Colored Tribune" (Savannah) because they share vocabulary with slave-sale
advertisements. Those are the very titles this vocabulary appears in most, for
the obvious reason. The Colored Tribune has exactly THREE postable issues in
the whole corpus; a blanket deny erases it.

  PASS    may be posted automatically
  REVIEW  a person decides. NOT a refusal, and never counted as one.
  REFUSE  out of bounds: no rights, wrong era, or the crop itself carries it

The split follows the project's own editorial test. REFUSE is for when the
IMAGE is indefensible with no words attached. REVIEW is for when the image is
fine and its CONTEXT is not, which is a judgement and stays with a person.

⚠️ The page gate exists because the crops cannot see the page. Measured
26 August 2026: on pages whose body text already carries slavery/lynching/Klan
vocabulary, a headline crop carries it only 16.3% of the time and a display-ad
crop 3.1%. So a clean crop is NOT evidence of a clean page, and a lane that
screened only its own crop would post the headline above a lynching story
having checked nothing that could have told it.

⚠️ For the nameplate lane the page gate costs almost nothing, which is why it
is on. A masthead is the same every week, so a page sent to REVIEW is not a
lost picture: it is the same picture on a different date. What it buys is that
the credit line, which publishes the page's own URL, does not send a reader
uninvited to a front page about a lynching.
"""
import csv
import os
from datetime import date

PASS, REVIEW, REFUSE = "PASS", "REVIEW", "REFUSE"
HERE = os.path.dirname(os.path.abspath(__file__))
RIGHTS_CSV = os.path.join(HERE, "data", "georgia_rights.csv")
CUTOFF = None                  # ⚠️ Was "1931-01-01" until 11 September 2026. The
                               # line was the project's own narrowing on top of
                               # DLG's per-issue rights, never a rights rule, and
                               # was lifted at Chris's request: DLG marks 8,628
                               # issues from 1931 on as No Copyright (2,500 from
                               # the 1930s, 3,000 from the 1940s, the Savannah
                               # Tribune to 1960), and the 21 August email told
                               # UGA their determination would be used rather
                               # than ours. None means no cutoff; a date string
                               # restores one. The bio and post 1 still say
                               # "before 1931" until the profile is rewritten.


class Policy:
    def __init__(self, min_date=None, page_gate=True, why=""):
        self.min_date = min_date
        self.page_gate = page_gate
        self.why = why


# ⚠️ The advertisement lane's era floor is MEASURED, not reasoned from
# emancipation. Sampling 196 front pages across 1855-1882, the share carrying a
# person-term and a sale-term in one block ran 70-85% through 1865, fell to
# 42.9% in 1866 and to 14.3% in 1867, where it settles into the false-positive
# floor. Publishers carried the standing legal-notice type -- "Sales of Negroes
# by Administators, Executors or Guardians, must be at Public Auction" -- for a
# year after the war, so a gate at 1865 would still be drawing from a pool
# where two front pages in five carry it.
# ⚠️ 1861 reads 0.0% in that scan on FIVE pages. That is small-sample noise,
# not a wartime pause. Do not read the year-by-year figures as a trend.
POLICIES = {
    "nameplate": Policy(
        min_date=None, page_gate=True,
        why="measured 0.0% at crop level over 180 issues; the page gate is "
            "for the credit link, and costs only a change of date"),
    "headline": Policy(
        min_date=None, page_gate=True,
        why="the crop is blind to its page: 16.3% on already-flagged pages"),
    "article": Policy(
        min_date=None, page_gate=True,
        why="a headline with its first paragraph; same blindness, same gate"),
    "ad": Policy(
        min_date="1867-01-01", page_gate=True,
        why="68.8% of pre-1865 front pages carry the standing slave-sale rate "
            "card; the shape does not fall to its floor until 1867"),
    "market": Policy(
        min_date="1867-01-01", page_gate=True,
        why="a market report is a column of set text, the same shape as the "
            "rate card the ad lane's floor exists for; same floor"),
}


class Verdict:
    def __init__(self, outcome, reasons=None):
        self.outcome = outcome
        self.reasons = list(reasons or [])

    @property
    def postable(self):
        return self.outcome == PASS

    def __repr__(self):
        return f"<{self.outcome}: {'; '.join(self.reasons) or 'clean'}>"


_roster = None


def roster():
    global _roster
    if _roster is None:
        with open(RIGHTS_CSV) as f:
            _roster = {r["lccn"]: r for r in csv.DictReader(f)}
    return _roster


def check(lane, lccn, issue_date, crop_hits=None, page_hits=None,
          have_geometry=True):
    """Decide one candidate.

    `crop_hits` / `page_hits` are truthy when the sensitive vocabulary was
    found in the crop / anywhere on the page. They are passed in rather than
    computed here so this module stays free of the scoring rules and can be
    tested without a page.

    ⚠️ Every failing condition is collected, not just the first. A crop refused
    for three reasons should say three, or fixing one looks like progress."""
    if lane not in POLICIES:
        raise ValueError(f"no policy for lane {lane!r}")
    pol = POLICIES[lane]
    reasons, outcome = [], PASS

    meta = roster().get(lccn)
    if meta is None:
        return Verdict(REFUSE, [f"{lccn} is not in the roster"])
    if meta.get("postable") != "yes":
        reasons.append(f"{lccn} has no NoC-US issue recorded"); outcome = REFUSE
    if not issue_date or (CUTOFF and issue_date >= CUTOFF):
        reasons.append(f"{issue_date} is on or after the {CUTOFF[:4]} cutoff"
                       if issue_date else "no issue date")
        outcome = REFUSE
    if pol.min_date and issue_date and issue_date < pol.min_date:
        reasons.append(f"era gate: {lane} starts at {pol.min_date} "
                       f"({pol.why})")
        outcome = REFUSE
    if not have_geometry:
        reasons.append("no confident crop geometry"); outcome = REFUSE
    if crop_hits:
        reasons.append(f"the crop itself carries {sorted(crop_hits)}")
        outcome = REFUSE
    if pol.page_gate and page_hits and outcome != REFUSE:
        # ⚠️ REVIEW, never REFUSE. See the header: this is the condition that
        # would silence the Black press if it denied outright.
        reasons.append(f"the page carries {sorted(page_hits)}; "
                       "a person decides, this is not a rejection")
        outcome = REVIEW
    return Verdict(outcome, reasons)


def earliest(lane):
    """The first date a lane may draw from, as a plain string, or None."""
    return POLICIES[lane].min_date


def describe_policies():
    out = []
    for lane, p in POLICIES.items():
        out.append(f"{lane:<10} from {p.min_date or 'any date'} to {CUTOFF or 'any date'}, "
                   f"page gate {'on' if p.page_gate else 'OFF'}")
        out.append(f"           {p.why}")
    return "\n".join(out)


if __name__ == "__main__":
    print(describe_policies())
