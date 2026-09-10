# everygeorgia — where things stand, 11 September 2026

A Bluesky account posting clippings from **Georgia Historic Newspapers**, run by
the Digital Library of Georgia at UGA. Read `README.md` for the technical
findings and `PROFILE.md` for the account text and the reasoning behind every
line of it.

## ✅ Permission arrived on 10 September 2026, and the poster is built

Donnie Summerlin, Digital Projects Archivist at UGA Libraries, replied to the
21 August request on 10 September (T. Rashaun Ellis copied): "Yes, please do.
We only ask that you credit the Digital Library of Georgia." On the rights
question: "You can feel free to use the materials that are no longer under
copyright however you choose. Permission from us is not necessary." On the
citation form: "Feel free to cite in whatever form you prefer. Those are
merely suggestions." On traffic: he forwarded the rate-limit question to their
developers weeks ago, they never replied, and he is chasing it, so **no rate
limit or User-Agent has been asked for**; ours identifies the account anyway
(`ghn_api.UA`). On content: "It is up to your discretion to select what you
post, but a cautious approach is certainly warranted." The mail is in the
Inbox; `permission_followup.py --resolved` was run the same day and the
reminder is silent.

**What was built on 11 September 2026:**

| | |
| --- | --- |
| `everygeorgia_post.py` | the poster: selection, the citation post, the six-post launch thread, `--setup-profile` |
| `profile.py` | the bio and thread as data, curled once, tested against the limits |
| gate 4, the ink edge | in `nameplate_crop.py`; see below, it is most of the day |
| `test_everygeorgia_post.py` | 25 tests; `test_nameplate.py` is now 67 |
| `com.chrisstanford.everygeorgia` | loaded from `~/Library/LaunchAgents`, 09:10 and 23:10 KST, exits 0 in one line until the thread is posted (verified by `kickstart`) |

⛔ **What is NOT done, and cannot be done by a script: the account does not
exist.** Chris creates `georgianewspapers.bsky.social` and puts an app password
in this Mac's Keychain, in a GUI session:

```bash
security add-generic-password -a "georgianewspapers.bsky.social" -s "everygeorgia-bluesky" -w
```

Then, in order: `everygeorgia_post.py --setup-profile` (name, bio, avatar),
`--launch` (the thread, post 1 pinned), and the daily job takes over by itself.
After launch, add the bot to `bot_health_check.py`, `bot_alt_check.py`,
`bot_variety_check.py` and `bot_scout_collect.py`, which was deliberately not
done ahead: a health check on an account that does not exist alerts every
morning.

## The poster, in five decisions

1. **One issue per title, titles in a fixed shuffled order** (`SHUFFLE_SEED`,
   appended never reshuffled), so all 836 titles with a pre-1931 NoC-US issue
   post once before any posts twice. Without it the Atlanta Georgian's 14,185
   issues would be one post in fifteen. Within a title the date is a seeded
   shuffle keyed on the pass number, so pass 2 shows a different year.
2. **The post is the GHN FAQ citation**, as promised on 21 August, with a
   bracketed description in the article slot and the sequence number as the
   page: `[Nameplate], “The Independent Press,” Eatonton, 13 January 1855,
   p. 1, gahistoricnewspapers.galileo.usg.edu/lccn/…/seq-1. Presented online
   by the Digital Library of Georgia.` then `#Georgia #History` as tag facets.
   The URL is a link facet; a title so long the post would pass 300 shortens
   the visible URL, never the credit. Dates are UK order, house style, and
   **post 5 of the thread moved from "Feb. 23, 1875" to "23 February 1875"**
   to match. Titles come through `display_title()`: the roster's catalogue
   case ("The Abbeville chronicle.") becomes "The Abbeville Chronicle".
3. **REVIEW is logged to `data/review.jsonl` and the run moves on** to the next
   date of the same title. For a nameplate a REVIEW costs a change of date,
   not a picture. Nothing REVIEW is posted by the script; the file is Chris's
   to read. REFUSE is skipped and named in the log.
4. **Bounded**: `TITLES_PER_RUN` 8 × `TRIES_PER_TITLE` 5 (8 was 4 until the
   dozen-post sample: three runs in twelve came up empty, because failures
   correlate within a title and many titles hold one or two issues). A candidate page costs
   manifest + coordinates + one image (the probe of the top 22% is cut locally
   into the crop, so there is no second image call). A normal run is about 10
   calls, a bad one about 60, all cached.
5. **Two a day, 09:10 and 23:10 KST** (8:10 p.m. and 10:10 a.m. US Eastern),
   the everycarnegie reasoning: the audience is American. Ten minutes off
   everycarnegie's slots so two bots are not logging in at once. Not decided
   by Chris; change the plist if he wants otherwise.

⚠️ **The alt text lost a sentence.** It ended "Scanned from microfilm; the page
is worn and the ink uneven", which was true of the one crop it was written
beside and unverified for every other. It now says only what the archive holds
exactly, plus what the detector guarantees (display type at the top of the
front page).

## Gate 4, the ink edge: the crops were read, and a fifth of them were wrong

HANDOFF said "read the crops; do not read only the summary line". Done, on
11 September, on eleven pages: **two shipped a headline as furniture, one cut
an engraved title in half, one cut a corner box, one cut its own letters'
feet.** Every one passed every gate. The cause is one thing: the band is built
from OCR word boxes, and display type is what the OCR reads worst, so the band
ends where the OCR words end rather than where the ink ends.

`refine_band()` now reads the pixels. It fetches the top 22% of the page once
at the final width, and for every row measures **continuing ink**: the share
of columns dark at that row and again nine rows down. A rule reads near zero
(it stops); a glyph or a box side reads high (it continues); a torn, taped,
foxed page reads near zero too, which a plain darkness count did not (the
Middle Georgia Argus read 5-7% dark at a perfectly clean edge, indistinguishable
from a cut box). Then, in order:

- **One tall body of ink in the band, or refuse.** Bodies are runs of non-clear
  rows parted by a gap of paper; tall is 0.9% of the page; a body must hold
  some rows of large ink or it is a smear (the Crawfordville Democrat's torn
  top edge is 23 rows of faint ink). The film edge and its soft tail are
  stripped from the front. **This is the rule that catches the Banner-Herald**:
  the OCR read the "LARRY GANTT'S COLUMN" box beside the banner headline and
  nothing of the headline, so the geometry took the headline row as a sparse
  dateline and, worse, called the box the masthead cluster, so no rule
  anchored on the cluster could see it.
- **If the band's edge cuts ink, walk down to the first gap** (0.4% of the page
  of clear rows) and end there plus the measure's nine-row blind zone (without
  that the Independent Press came back with its letters' feet cut). The walk
  refuses rather than cross large ink unless the edge is already in large ink
  that is contiguous with the cluster (a blackletter the OCR read the top of),
  and it may not reach display type the OCR did read, nor body text, nor 22%.
- **After extending, one tall body again.** A light-face headline the walk
  crossed without meeting large ink would otherwise arrive as furniture.

Measured on twenty-three pages (the eleven, plus the dozen sample posts drawn
for Chris the same day): twenty pass or REVIEW and every crop was read by eye
and is whole; the Banner-Herald, the Georgian and the Sunny South are refused,
the first two for an unread headline and the third because its engraved title
runs past 22% of the page. Two more rules came out of the dozen: **the ink
threshold is relative to the page's own contrast** (the washed-out Pembroke
Journal of 1928 had its whole title read as paper at a fixed step below the
paper median, and shipped cut), and **the dark top of a torn frame is stripped
whole after a true film edge**, or it counts as a body of its own. **No page in the
sample that should have been refused now passes, and no crop that passes is
cut.** The cost is the dateline under some titles, which the walk stops above
when the gap between them is narrow.

⚠️ **Every threshold in that gate was set against these eleven pages and no
others.** `InkEdge` in `test_nameplate.py` pins each rule on a synthetic
profile, and the pages are named in the code beside the constant they set.
Re-run `nameplate_crop.py <lccn> <date> --out x.jpg` and LOOK before moving
one. `crop_frequency.py` has not been re-run under the new gate, so its PASS
rates are the old gate's.

## Done

| | |
| --- | --- |
| Roster | `data/georgia_roster.csv` — 1,158 of 1,164 titles, 158 counties |
| Avatar | `avatar/avatar_G_dark_72.png` — blackletter G, Macon, 23 Feb 1875 |
| Profile text | **Settled.** Bio at 233/256 and six pinned posts, all verified |
| Corpus measurement | Frequency table in `README.md`, measured not estimated |
| Picture detector | Works; see README. Finds pictures, not specifically cartoons |
| Permission email | Sent; **answered yes, 10 September 2026** |
| Rights join | **Completed 22 August**, 1,159 rows. 843 titles postable |
| Nameplate lane | **Built 26 August**: detector, crop pipeline, 37 tests |
| Crop-level measure | **Done 26 August.** Step 5 below is discharged |
| Follow-up reminder | Fired 4 September; **resolved 11 September** |
| Poster, profile, launch thread, launchd job | **Built 11 September** |

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

## The gates, added 26 August 2026

`gates.py` is the decision layer. ⚠️ **It has THREE outcomes, not two, and that
is the whole design.**

| | |
| --- | --- |
| **PASS** | may be posted automatically |
| **REVIEW** | a person decides. **NOT a refusal, and never counted as one** |
| **REFUSE** | out of bounds: no rights, wrong era, or the crop itself carries it |

The split follows the project's own editorial test. REFUSE is for when the
**image** is indefensible with no words attached. REVIEW is for when the image
is fine and its **context** is not, which is a judgement and stays with a
person.

### ⚠️⚠️ Why the page gate is REVIEW and must never become REFUSE

A binary allow/deny on this vocabulary **erases the Black press.** The README
has recorded since before any of this existed that a keyword blocklist rejected
the front pages of "The Colored American" (Augusta, 6 January 1866) and "The
Colored Tribune" (Savannah), because they share vocabulary with slave-sale
advertisements. Those are the titles this vocabulary appears in most, for the
obvious reason.

**Measured against the real roster: "The Colored Tribune" has THREE postable
issues in the entire corpus, and "Atlanta independent" has one.** A blanket
deny does not reduce those titles, it deletes them. `BlackPressIsNotErased` in
the test suite asserts, against the real csv rather than a synthetic one, that
both come back REVIEW and never REFUSE. If that test ever goes red the gate has
become the thing this project set out not to build.

⚠️ **REVIEW is not an exemption either.** A crop that itself carries the
vocabulary is REFUSED whoever printed it: the rule is about the image, not
about the publisher. That is also pinned.

### The era gate is 1867, and it was measured rather than reasoned

The obvious date is emancipation. The obvious date is wrong. Sampling **196
front pages across 1855-1882**, stratified so no year dominates, the share
carrying a person-term and a sale-term in one block ran:

| | |
| --- | --- |
| 1855-1865 | 43% to 100%, mostly 70-85% |
| 1866 | **42.9%** |
| 1867 onward | 14% to 43%, the false-positive floor |

Publishers carried the standing legal-notice type for a **year after the war**,
so a gate at 1865 would still draw from a pool where two front pages in five
carry it. The floor is `1867-01-01`, on the advertisement lane only.

⚠️ **1861 reads 0.0% in that scan, on five pages.** That is small-sample noise,
not a wartime pause. Do not read the year-by-year figures as a trend.

### What the gates cost

`crop_frequency.py --gates --lane <lane> --sample N`, 80 issues each:

| lane | PASS | REVIEW | REFUSE |
| --- | --- | --- | --- |
| nameplate | 25.0% | 47.5% | 23.8% |
| advertisement | 21.2% | 27.5% | 47.5% |

⚠️ **A PASS share is not a supply figure.** 25% of 218,505 is still about
55,000 auto-postable issues. And for the nameplate lane a REVIEW costs almost
nothing in practice: a masthead is the same every week, so it is the same
picture on a different date.

⚠️ **The report names the titles most often sent to REVIEW, deliberately.** The
effect on any particular paper must be visible rather than silent, which is the
only way anyone would notice the Black-press problem returning by a different
route.

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
6. ~~Wait for UGA.~~ **Answered 10 September: yes, credit DLG.**
7. ~~Read the reply for conditions.~~ **One condition, the credit line, and
   every post carries it.** Open question 2 is settled for the nameplate lane,
   which is the only lane shipping: nothing is generated, nothing to disclose.
8. **Chris creates the account and stores the app password**, then
   `--setup-profile`, `--launch`, and the audits gain a bot each.

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
