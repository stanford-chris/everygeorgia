# everygeorgia — where things stand, 26 August 2026

A Bluesky account posting clippings from **Georgia Historic Newspapers**, run by
the Digital Library of Georgia at UGA. Read `README.md` for the technical
findings and `PROFILE.md` for the account text and the reasoning behind every
line of it.

## ⛔ The one rule

**Nothing is published, the account does not exist, and neither should change
until UGA replies.** A permission email went to `dlgnwp@uga.edu` and
`gnp@uga.edu` on 21 August 2026. DLG's terms grant educational use freely but
require written permission from the holding institution to *publish*, and a
public account is publication. Silence is not permission; set a date to follow
up rather than letting it drift into a tacit yes.

✅ **That follow-up date now exists, and until 26 August 2026 it did not.** The
instruction above was written on the 21st and never carried out: a grep of this
repo, the memory file and the observation log found no date, no reminder and no
job anywhere. The only thing standing between the project and death by drift was
somebody happening to ask. `permission_followup.py` now mails Chris if UGA has
not replied, first on **4 September 2026** (two weeks after the email) and every
14 days after that, under `com.chrisstanford.everygeorgiafollowup` (weekly
check, Fridays 09:30, `~/Library/LaunchAgents`).

⛔ **It sends nothing to UGA and must never learn how.** It prompts Chris; the
decision to write again is his. Silence it with
`permission_followup.py --resolved "what happened"` once they reply.

⛔ **Do not send a second email yet.** Decided 21 August: wait to hear back
before writing again, including about the API trouble below.

## Done

| | |
| --- | --- |
| Roster | `data/georgia_roster.csv` — 1,158 of 1,164 titles, 158 counties |
| Avatar | `avatar/avatar_G_dark_72.png` — blackletter G, Macon, 23 Feb 1875 |
| Profile text | **Settled.** Bio at 233/256 and six pinned posts, all verified |
| Corpus measurement | Frequency table in `README.md`, measured not estimated |
| Picture detector | Works; see README. Finds pictures, not specifically cartoons |
| Permission email | Sent |
| Rights join | **Completed 22 August**, 1,159 rows. 843 titles postable |
| Nameplate lane | **Built 26 August**: detector, crop pipeline, 37 tests |
| Crop-level measure | **Done 26 August.** Step 5 below is discharged |
| Follow-up reminder | **Set 26 August**, first fires 4 September |

The thread runs 264, 272, 204, 113, 288, 252 characters. Post 1 is pinned; 2–6
thread beneath. Only post 5 needs a link facet. Both handles in post 6 resolved
when checked on 21 August — **re-check at posting time rather than trusting
that line.**

Commits: `ad04b79`, `4bdc5a7`, `463b2e6`, `5609c0b`, `1b8bc89`, then the evening
run `f725ed9` → `53f27c4`.

## What changed on the evening of 21 August

- **A 1931 cutoff.** The bio and post 1 both say "before 1931". It is *our* rule,
  never a claim about where the archive ends, and it does **not** replace the
  rights join — both gates apply and a date gate can only narrow. See
  `PROFILE.md`, which also records why 1930 lost.
- **Post 3 was reframed, and this is the most substantive change.** It said "This
  archive is not a neutral record". It now says "These posts are not
  representative of the archive". The archive is faithful — it preserves what was
  printed, and lynching and slavery were part of what was printed. What is not a
  fair sample is *this account's feed*. That is the harder admission and it
  describes our own output rather than characterising DLG's holdings.
- **Alt text was split from the biography**, taking the thread from five posts to
  six. Welded together with a written-out profile URL they came to 355
  characters. The thread now ends on the biography, because "Corrections
  welcome" is the line someone replies to.
- **The subject frequencies were measured** rather than asserted. One pre-1931
  front page in five carries slavery, lynching or Klan vocabulary before "negro"
  is counted at all; 47% mention it. Table and three cautions in `README.md`.

## No longer blocked on DLG

⚠️ **This section said "Blocked, on DLG" until 26 August 2026 and had been
wrong for four days.** The health gate it worried might never fire fired at
21:25 on 21 August, and `data/georgia_rights.csv` was written at 11:45 on the
22nd. Read `data/await_dlg.log`; do not trust a status line in a file nobody
has re-read.

**The join, and the number that decides the shape of this project:**

| | |
| --- | --- |
| Roster titles | 1,158 |
| Postable (≥1 NoC-US issue) | **843** |
| No NoC-US record | 315 (`unknown`, never `none`, and never permission) |
| Total NoC-US issues | **224,097** |
| Pre-1931 NoC-US issues | **218,505**, across 840 titles |
| Date span | 1763-04-07 to 2021-02-25 |

That answers "six-month bot or two-year one": supply is not the constraint at
any cadence, and it never will be. Selection is
([[reference_bot_variety_is_selection_not_supply]]).

⚠️ **910 of 1,088 DLG pages are cached, not all of them**, so these are floors.
Fourteen page fetches failed during the join and are logged in
`data/rights_join.log`.

⛔ `com.chrisstanford.everygeorgiarights` was **booted out and both copies of
its plist deleted on 26 August 2026**, per step 3 below. It had run 431 times,
the last 400-odd of them exiting immediately because the csv existed. Nothing
schedules it now and nothing should.

## The nameplate lane is built, and the crop-level measure is done

Step 5 said: sample N NoC-US issues per lane and score the actual crops, before
the advertisement and headline lanes open. Done 26 August 2026.

| | measured on the same pages, by the same method |
| --- | --- |
| slavery / lynching / Klan | page **27.0%** → nameplate crop **0.0%** |
| "negro" | page **54.8%** → nameplate crop **0.0%** |

Sample of 120 pre-1931 NoC-US issues (seed 20260826): 115 front pages read, 84
nameplates detected, 31 refused. Held out on a second draw the thresholds had
never seen (seed 424242, 60 issues): 38 detected of 57, **0.0% on both measures
again**. Twelve crops from that held-out draw were read by eye and all twelve
are clean nameplates.

✅ **And the exact measure, which needs no sampling at all: none of the 843
postable titles carries slavery, lynching or Klan vocabulary in its own name.**
`crop_frequency.py --titles` scores the roster strings rather than OCR, so that
one is definitive rather than an estimate.

⚠️ **Both crop figures are upper bounds that are additionally DEPRESSED by
OCR.** Display type is the worst-recognised text on a page, so a nameplate crop
under-reports by construction. That is exactly why the title pass exists beside
it; neither measure is trusted alone.

**Files:**

- `ghn_api.py` — ONI manifests, OCR coordinates, IIIF region crops. Read-only.
- `nameplate.py` — the detector. Geometry, never text.
- `nameplate_crop.py` — one clipping: image, caption, alt text. Four gates.
- `crop_frequency.py` — the measurement above.
- `test_nameplate.py` — **37 tests, stdlib only, no network.** Verified by
  mutation: six deliberate breakages were each confirmed to fail the suite and
  pass again on restore.

⚠️⚠️ **THE THREE FAILURES THAT SHAPED IT ARE THE PART WORTH KEEPING.** Each was
a plausible-looking crop, not a crash, and each is now a named regression test:

1. **Macon Telegraph, 8 June 1901.** A headline set at 0.52 of the masthead
   height chained into the cluster and the crop came out reading **"SHERIFF OF
   CARROLL FIRES ON THE MOB"**. Fixed by requiring a joining row to be ≥0.65 of
   the first row's height. Legitimate second lines measure 0.74 and above.
2. **Athens Banner, 29 December 1908.** The blackletter masthead produced *no*
   display boxes at all, so the detector locked onto the first thing that did:
   the headline deck 10.4% down, cropping **"YOUNG NEGRO GIRL KILLED BENEATH
   SEABOARD ENGINE"** as a nameplate. Fixed by tightening the top bound from
   25% of the page to 9% — measured, not chosen: across 98 detections the
   cluster top ran median 5.2%, p90 9.9%. Savannah Morning News, 20 October
   1877, failed the same way at 9.7%.
3. **Griffin Daily News, 3 June 1916.** A 23-row chain down the page produced a
   band 30% deep. It was a baseball score, and on another day it would not be.

⚠️ **Both of the crops that reached a human were caught BY EYE, not by an
assertion.** The vocabulary gate flagged them, which is the belt working, but
the geometry should never have offered them. Read the crops; do not read only
the summary line.

⚠️ **The detector refuses roughly a quarter to a third of pages, and refusal is
the design.** A page whose masthead did not OCR is not a page with a small
nameplate: it is a page the detector cannot read, and a band drawn from the only
thing it *can* see is a guess dressed as a measurement. There are 218,505
issues; skipping a third costs nothing.

✅ **This lane needs no model, and that is a real contribution to open question
2.** The crop is chosen by arithmetic and the caption and alt text are built
from the title, city and date the archive already holds exactly. Nothing about
a nameplate post is generated, so there is nothing to disclose. **That settles
the disclosure question for this lane only** — the headline lane still cannot
be done without a model, and the question stays open for it.

⛔ **Nothing here can post.** No `atproto` import, no credential, no account.
`nameplate_crop.py` additionally writes nothing without `--out`, which is the
reverse of the scheduled bots in this estate and deliberate: see
[[reference_seoul_index_dry_run_flag]], where `--help` published a live card.

## The advertisement and headline lanes, measured 26 August 2026

⚠️⚠️ **NEITHER LANE HAS BEEN DESIGNED, so these measure a provisional geometry
and not a specification.** They are drawn generously, to find more candidate
crops rather than fewer. If a real design lands, re-run `crop_frequency.py`
rather than quoting these.

Sample of 120 pre-1931 NoC-US issues (seed 20260826), held out on 60 more at an
unseen seed. "Crops" is the share of individual crops carrying slavery,
lynching, Klan or "negro" vocabulary; "pages" is the share of front pages
yielding at least one such crop.

| lane | crops | pages | held out |
| --- | --- | --- | --- |
| nameplate | **0.0%** | **0.0%** | 0.0% |
| headline | 5.6% | 7.0% | 5.7% |
| display advertisement | 1.1% | 1.7% | 4.1% |
| any text block (the bound) | 5.5% | **62.6%** | — |

⚠️⚠️ **THE MOST IMPORTANT NUMBER HERE IS NOT IN THAT TABLE, AND IT IS NOT GOOD
NEWS.** On the pages whose body text already carries slavery/lynching/Klan
vocabulary, a headline crop carries it only **16.3% of the time**, and a display
ad crop **3.1%**. A low crop figure is therefore **NOT a safety finding**: it
means the crop is blind to what the page around it is about. **These lanes
cannot screen themselves on the crop alone**, which is exactly the property that
made the nameplate lane safe. Any headline or advertisement lane must gate on
the WHOLE PAGE, not on its own crop.

⚠️ **Both figures are floors, and the headline one especially.** A headline is
display type, which is the worst-recognised text on a page, so scoring a
headline crop's OCR under-reports by construction. The nameplate lane had an
exact second measure to sit beside it (the roster titles); these have none.

### The advertisement lane before 1865 is a different problem entirely

`crop_frequency.py --lane block --slave-ads` looks for a person-term and a
sale-term inside one crop-sized block, which is the shape of a slave-sale
notice. Front pages carrying at least one:

| | |
| --- | --- |
| whole sample | 25 of 115 (**21.7%**) |
| **before 1865** | 55 of 80 (**68.8%**) |
| 1865 onward | 13 of 79 (16.5%) |

⚠️⚠️ **AND THE ANTEBELLUM HITS ARE NOT ADVERTISEMENTS. THEY ARE THE PAPER'S OWN
STANDING RATE CARD**, read by eye on four of them. The wording, from the
Milledgeville paper of 24 August 1850:

> "Sales of Negroes by Administators, Executors or Guardians, must be at Public
> Auction, on the first Tuesday in the month, between the legal hours of sale,
> before the Court House..."

That is boilerplate legal-notice furniture, printed on the front page of
essentially every antebellum Georgia issue, not an advertisement somebody
placed. **So the exposure is not a matter of which ad you pick.** It is on the
page, in the same fixed position, every week, for decades. A lane that crops
antebellum front-page text at random is not occasionally unlucky: it is drawing
from a pool where roughly two pages in three carry this.

✅ **It also sits close to the nameplate**, which is worth knowing before anyone
loosens that band: these blocks were found 13% to 30% down the page. The
nameplate band runs 3.9% to 13.5% and measured 0.0% across 180 issues, so it is
clear today, and the margin is thinner than it looks.

⛔ **The slave-sale scan is a SHAPE, not a subject classifier.** It catches
runaway notices, hiring advertisements and ordinary estate sales alongside what
it is looking for, and one of the four read by eye was a plain advertising rate
card with no slave content at all. That is the right direction to err for a
gate, and the wrong direction for a statistic: read 21.7% and 68.8% as "carries
this shape", never as "is a slave-sale advertisement".

### What this says about sequencing

- **The nameplate lane stands alone as safe**, and for a structural reason no
  other lane has: a paper's own name cannot be about a lynching.
- **A headline lane needs a page-level gate**, because its crop cannot see what
  it is part of. That gate already exists in the page-level figures.
- **An advertisement lane needs an era gate before anything else.** Post-1865 it
  is a normal editorial problem; pre-1865 the front page carries slave-sale
  boilerplate as standing furniture.
- ⛔ **None of this is a recommendation to open either lane.** It is the
  measurement step 5 asked for, so that the decision is made on numbers.

**Everything else, on UGA.**

## Open questions for Chris

1. ~~Does post 4 keep "Corrections welcome and acted on"?~~ **Resolved: cut.**
   "Acted on" promises future behaviour nothing guarantees. Do not restore it.
   This session recommended keeping it twice and was overruled twice; both the
   argument and its rebuttal are in `PROFILE.md` so it is not restored by someone
   reading only the first half.
2. **Does the account need an A.I. disclosure?** Still open, and it cannot be
   settled yet. It turns on one thing only: whether any published text comes from
   a model. Nameplates, ads and market reports can take alt text from the page's
   own OCR and captions from metadata — no model, nothing to disclose, which is
   worth saying out loud if true. The headline lane cannot: display type OCRs
   worse than anything else on a page. **So this is a decision about which lanes
   ship, not a decision about wording.** UGA's answer does not settle it either —
   permission and disclosure serve different audiences — though a yes could
   arrive with conditions, so read their reply for that specifically.
3. ~~Is the affiliation line still in the thread?~~ **Resolved.** It moved out of
   post 3, where it was stranded, into post 6: "Run by @stanfordc.bsky.social,
   not the Digital Library of Georgia". "Unofficial" now appears once, in the
   bio. `PROFILE.md` records that posts 1–3 carrying no disclaimer was weighed
   and accepted, and that the fix if that looks wrong is to trim post 1, **not**
   to put the line back in post 3.

## Next moves, in order

1. ~~Wait for `data/await_dlg.log` to report `health 3/3`.~~ **Done 21 August.**
2. ~~Report how many titles have a postable issue.~~ **Done: 843, and 218,505
   pre-1931 issues.**
3. ~~Boot out `com.chrisstanford.everygeorgiarights` and delete its plist.~~
   **Done 26 August**, from outside the job.
4. ~~Build the nameplate lane.~~ **Done 26 August.**
5. ~~Measure at the crop level before the advertisement and headline lanes
   open.~~ **Done 26 August for the nameplate lane.** ⚠️ Still owed for the
   **advertisement** and **headline** lanes before either opens: the figures
   above are the nameplate band's, and say nothing about a crop taken from the
   middle of a page.
6. **Wait for UGA**, and answer the reminder when it arrives on 4 September.
7. When permission lands, read the reply for conditions before building
   anything else. A yes with conditions changes which lanes ship, which is what
   open question 2 turns on.

`rights_join_tick.sh` is spent but kept: it documents how the join was gated,
and it exits 0 in silence the moment the csv exists.

## Things that will bite a fresh session

- **Rights are not a date rule.** NoC-US runs to 1928 while In Copyright begins
  in 1924. The 1931 cutoff is an additional narrowing, never a substitute.
- **A figure and its denominator move together.** Post 3 quotes 160,000 against
  the whole archive of 4,564,007 pages; the pre-1931 subset is a different
  number, 118,518 of 2,272,709. Never move one without the other.
- **The ONI index stems.** `lynch`, `lynched`, `lynching`, `lynchings` all return
  one total; `slave` and `slaves` likewise. No count here names a literal word.
- **`date1`/`date2` take ISO dates, and a wrong format is silently ignored** —
  `yearRange` with bare years returns the whole corpus with a 200.
- **"Issue" and "edition" are different units.** An edition sits inside an issue;
  DLG marks rights on issues. Post 2 must say "issues".
- **The bio's lane list and post 1's differ on purpose.** Do not reconcile them.
- **A curl 200 is not arrival** on the ONI side — Turnstile serves its challenge
  with status 200; check `url_effective`. DLG's failure is the opposite shape: a
  plain-text 503 with a real message, which is not a challenge at all.
- **Search finds shape, never genre.** Every failed lane failed this way.
- **Carry identifiers through; never reconstruct them.** This caused two wrong
  links and one whole class of dropped records.
