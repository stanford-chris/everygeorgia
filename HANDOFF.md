# everygeorgia — where things stand, 21 August 2026 (evening)

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

## Blocked, and on what

**The rights join, on DLG — but not for the reason previously recorded here.**
`data/georgia_rights.csv` still does not exist and nothing is cached, so the
eventual run starts from scratch at about 1,088 pages.

⚠️ **DLG is not down. It is shedding load and serving browsers first.** Measured
21 August: a Safari user-agent returned 200 on four of four attempts across the
evening while our own identifying UA returned 503, 200, 503 on the same URL
seconds apart. The 503 is DLG's own application response — `text/plain`,
`retry-after: 60`, no Cloudflare headers, no `cf-ray` — so it is **not** a bot
challenge, and loading a page by hand in a browser establishes no session the
scripts could reuse. This corrects the earlier entry, which read the failing
health probe as an outage.

⛔ **Do not spoof a browser user-agent.** Ours names the project and carries the
same address that emailed UGA. If DLG is serving humans before bots under load,
that is the correct priority.

⚠️ **The 3/3 health gate may therefore never fire.** It was calibrated for "is
DLG up?" when the real condition is "will DLG talk to *us* right now?" Do not
loosen it to fire 1,088 requests into a load-shedding host. If it persists, the
fix is to ask UGA — but see the one rule above: not until they reply.

`com.chrisstanford.everygeorgiarights` is **left running deliberately**. Three
requests every 900 seconds is about 12 an hour, light enough not to matter, and
it is the only thing that will notice recovery unattended. Watch
`data/await_dlg.log` for a line reading `health 3/3`.

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

1. **Wait.** For UGA, and for `data/await_dlg.log` to report `health 3/3`.
2. When `data/georgia_rights.csv` appears, report how many of the 1,158 titles
   have a postable issue and the true earliest/latest NoC-US dates. That number
   decides whether this is a six-month bot or a two-year one.
3. Boot out `com.chrisstanford.everygeorgiarights` once the csv lands and delete
   its plist — **from outside the job, never from within it.**
4. Build the nameplate lane first. It is the safest by a distance: a nameplate is
   the top band of a page, so the page-level frequencies barely touch it.
5. Before the advertisement and headline lanes open, measure at the **crop**
   level — sample N NoC-US issues per lane and score the actual crops. The
   nameplate lane does not need this.

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
