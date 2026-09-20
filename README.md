# everygeorgia

**Georgia in Print**, [@georgianewspapers.bsky.social](https://bsky.app/profile/georgianewspapers.bsky.social):
a Bluesky account posting clippings from **Georgia Historic Newspapers**, the
archive run by the Digital Library of Georgia at UGA. Unofficial.

> ✅ **Permission to publish arrived on 10 September 2026** from UGA Libraries,
> with one condition: credit the Digital Library of Georgia. Every post ends
> "Presented online by the Digital Library of Georgia." The poster was built on
> 11 September; the account was created by hand the same day. See `HANDOFF.md`.

## Why this project exists

I'm a Georgia native and a UGA Grady College graduate whose first newspaper job
was at *The Augusta Chronicle*. The DLG's own Twitter account used to post exactly
this kind of clipping and stopped in December 2024.

## Two APIs, and they are complementary

| | |
| --- | --- |
| **Open ONI** at `gahistoricnewspapers.galileo.usg.edu` | Page images, word-level OCR coordinates, full page text in `ocr_eng` on every search result, and a level-2 IIIF image server at `iiif-ha.galib.uga.edu` allowing arbitrary region crops. The only source of pages, text and images. |
| **DLG** at `dlg.usg.edu/about/api` | 1,084,812 records across all of DLG; GHN is its largest collection at 371,998, issue-level, no OCR, no IIIF. Its value is **machine-readable rights statements**. |

## Files

- `georgia_roster.py` → `data/georgia_roster.csv`. 1,158 of 1,164 titles across 158
  counties. Six unresolved, listed in the build log.
- `rights_join.py` → `data/georgia_rights.csv`. Joins the roster against DLG's
  per-issue rights. **Not yet run to completion:** DLG was returning 503 on roughly
  three requests in four on 21 August. The script now probes first and refuses to
  start rather than grind against a struggling service.
- `ghn_api.py` — Open ONI manifests, word-level OCR coordinates and IIIF region
  crops. Read-only, cached, and it cannot post. ⚠️ **The OCR coordinate space is
  not the image space** and is not consistent between pages: measured from
  796x1190 to 22839x31677 against images of 3080x4607 and 4879x6435, so it is
  both smaller and larger than the image depending on the page. Always scale
  through `Page.to_image()`. ⚠️ The manifest's inline IIIF profile claims
  `level0`; the server's own `info.json` says **level2** and arbitrary region
  crops demonstrably work. Trust `info.json`.
- `nameplate.py` — the nameplate detector, by geometry and never by text.
- `gates.py` — the decision layer: PASS / REVIEW / REFUSE. ⚠️ **REVIEW is not a
  refusal.** The page-level vocabulary gate returns REVIEW precisely so that a
  blanket deny does not erase the Black press, which has three postable issues
  of "The Colored Tribune" to lose. The advertisement lane's era floor is
  1867, measured: publishers carried the standing slave-sale rate card for a
  year after the war.
- `lanes.py` — provisional crop geometries for the headline and advertisement
  lanes, plus the text-block bound. ⚠️ Neither lane is designed, so these
  measure an assumption; they are drawn generously on purpose.
- `nameplate_crop.py` — one clipping: image, caption and alt text, six gates.
  ⚠️ **Gate 4 reads the pixels**, because the OCR band ends where the OCR words
  end and display type is what the OCR reads worst: two unread headlines shipped
  as furniture and three crops were cut before it existed. See HANDOFF.md.
- `everygeorgia_post.py` — the poster. One issue per title in a fixed shuffled
  order; the GHN FAQ citation as the post; REVIEW logged to `data/review.jsonl`
  and skipped; `--launch` for the pinned thread; `--setup-profile`.
- `profile.py` — the bio and the six-post thread as data.
- `rules.py` — the page's grid from its pixels: gutters, rules, film edge, and
  the snapping of an OCR box to its cell. ⚠️ Gutters over the whole page, never
  over an item's own rows; interior dark columns are rules, not film.
- `items.py` — display rows split at column gaps, boxed with their decks.
- `clips.py` — one clipping from any lane; the block-of-text builder for the
  search-driven lanes; the search candidate lists. ✅ Also the **classified lane**
  (`clip_classified`, built and released 20 September 2026): a run of want-ad
  items around a search phrase, in a column read from the pixels at the image's own
  resolution (`local_column`: a want-ad department is set at its own measure inside a
  border, on no page-level gutter, and its gutter is 20px with a dotted rule that reads
  as grain at 1400px), items cut at rules, gaps and headings (`classified_block`), the
  20th-century `LEAD—` form and the 19th-century heading-over-paragraph form both
  recognised, wanted-notice vocabulary REVIEW. HANDOFF.md has the traps.
- `transcribe.py` — the words in a clipping, by `claude -p` vision, prefixed
  `A.I.-transcribed` wherever they reach a reader.
- `pictures.py` — the cartoon lane: a drawing found by the hole it leaves in the
  OCR (line art cannot be told from type by its ink; it can by its OCR-box
  coverage, 0.22 against 0.51), framed by the page's grid, sorted by kind by the
  model, described and transcribed by it. The one lane whose alt is a
  description, labelled `A.I.-described`. See HANDOFF.md.
- `crop_frequency.py` — the crop-level measurement above, plus `--titles`.
- `permission_followup.py` — the UGA reminder. ⛔ Mails Chris, never UGA.
- `test_nameplate.py` — 67 tests, stdlib only. `test_everygeorgia_post.py` — 25.
- `avatar/avatar_G_dark_72.png` — a blackletter G from the *Georgia Weekly Telegraph
  and Georgia Journal & Messenger*, Macon, 23 February 1875. Source image kept
  alongside it so the provenance travels with the asset.

## Things learned the hard way

**Rights are not a date rule.** "No Copyright – United States" runs to 1928 while
"In Copyright" begins in 1924, so the 1920s overlap and are decided title by title.
Any cutoff year invented here would override DLG's own item-level determination.

**DLG does not hold every issue.** 371,998 records against 518,801 issues in GHN, so
roughly 28% carry no rights statement. That state is `unknown`, and it is not the
same as `none`. Neither may be treated as permission.

**The corpus is not neutral, and a random draw is not viable.** Measured 21 August
2026 against 2,272,709 pre-1931 pages, of which 353,576 are front pages:

| term | all pages | front pages |
| --- | --- | --- |
| `slave` (stems `slaves`) | 197,981 — 8.7% | 39,818 — **11.3%** |
| `lynch*` | 118,518 — 5.2% | 27,283 — **7.7%** |
| `ku klux` | 17,000 — 0.7% | 4,886 — 1.4% |
| `negro for sale` | 8,673 — 0.4% | 1,950 — 0.6% |
| any of those three subjects | 318,881 — 14.0% | 68,315 — **19.3%** |
| `negro` alone | 719,394 — 31.7% | 166,982 — **47.2%** |

Roughly **one pre-1931 front page in five** carries slavery, lynching or Klan
vocabulary before "negro" is counted at all, and nearly half mention it. Sampling
real daily front pages 1885–1908, a keyword blocklist rejected **15 of 24** — a
result these proportions predict rather than contradict. The filter removes the
era, not an occasional problem.

Three cautions travel with the table, and none of them are pedantry:

- **It counts vocabulary, not subject.** Same rule as everywhere else here:
  search finds shape, never genre. "Slave" catches classical allusion and
  temperance rhetoric; "negro" spans neutral news, church notices and the Black
  press writing about itself. Every figure is an **upper bound** on subject.
- **It is page-level, and the lanes are crops.** A nameplate is the top band of a
  page. A page mentioning lynching almost never mentions it in the masthead, so
  the nameplate lane's real exposure is far below 7.7%. That is why it is the
  lane to launch with. ✅ **The crop-level measure has now been made**
  (26 August 2026): on the same pages and by the same method, slavery/lynching/
  Klan vocabulary runs **27.0% at page level and 0.0% in the nameplate crop**,
  and "negro" **54.8% against 0.0%**. Held out on a second sample the
  thresholds had never seen, both stayed 0.0%. And exactly, with no sampling:
  **none of the 843 postable titles carries that vocabulary in its own name.**
  Run it with `crop_frequency.py`. ✅ **The advertisement and headline lanes were
  measured on 26 August 2026 too**, and they are a different picture: headline
  crops 5.6%, display-ad crops 1.1%, any text block 5.5% of crops but **62.6%
  of pages**. ⚠️ **A low crop figure there is not safety.** On pages whose body
  text already carries the vocabulary, a headline crop carries it only 16.3% of
  the time: the crop is blind to the page around it, so those lanes cannot
  screen themselves and must gate on the whole page. And before 1865, **68.8%
  of front pages carry a slave-sale-shaped block** which turns out to be the
  paper's own standing legal-notice rate card, not an advertisement. See
  HANDOFF.md.
- **⚠️ The index stems, so no count here names a single word.** `lynch`,
  `lynched`, `lynching` and `lynchings` all return 118,518; `slave` and `slaves`
  both return 197,981. `slavery` is separate at 91,544. Never quote one of these
  figures as the count of a literal word — post 3 did, and was corrected.

⚠️ **`date1`/`date2` take ISO dates, and a wrong format is silently ignored.**
`date1=1763&date2=1930&dateFilterType=yearRange` returns the **whole corpus**
with an HTTP 200 and no warning — 4,564,007 pages read as a plausible answer. Use
`date1=1763-01-01&date2=1930-12-31&dateFilterType=range&searchType=advanced`, and
sanity-check any new filter against a range you can predict. `sequence=1`
restricts to front pages.

**The blocklist silences the Black press.** It rejected the front pages of *The
Colored American* (Augusta, 6 Jan 1866) and *The Colored Tribune* (Savannah), because
they share vocabulary with slave-sale advertisements. This is why the judgment stays
with a person, and it is named in the email.

**Search finds shape, never genre.** "Salutatory" in Georgia papers overwhelmingly
means a commencement address; "prospectus" is one-in-seven the newspaper sense;
"the editor regrets" returned a poem about a rejection slip. Selectors that work do
so because the phrase is genre-specific ("sarsaparilla" only appears in advertising).

**"Issue" and "edition" are different units, and only one of them is what DLG
marks.** An edition sits *inside* an issue: every identifier is
`/lccn/<lccn>/<date>/ed-1/seq-<n>/`, and on a sampled record the `edition` field
comes back `None` with an empty `edition_label`, because nearly every paper here
printed once a day. A morning and an evening printing would be two editions of
one issue. **DLG's rights statements are issue-level** — 371,998 records against
518,801 issues — so any sentence about what is postable has to say "issues".
"Editions" was proposed for post 2 on 21 August 2026 as the more natural word and
rejected for exactly this: it would name a unit DLG does not mark, in the one
sentence where the account stakes its permission claim. It is also the unit to
get right when building the lanes — picking "an issue per title" means picking
`ed-1` unless a title genuinely has more.

**Carry identifiers through; never reconstruct them.** Guessing LCCNs put two wrong
links into sample posts and killed a lookup outright.

**A curl 200 is not arrival.** Turnstile returns its challenge page with status 200,
so every "verified" link check was passing on a challenge. Check `url_effective`.

## The editorial test for difficult material

A caption does not travel with a screenshot. The question is not "can I frame this?"
but **"is the image defensible with no words attached?"** A Georgia bishop's headline
calling the Klan un-American passes. A 1920 paper printing the Klan founder's denial
as news fails, because the image alone is Klan publicity whatever the caption says.

## The rights join is done

✅ **Completed 11:45 on 22 August 2026**, from 910 of 1,088 DLG pages: 843 of
1,158 titles postable, **218,505 pre-1931 NoC-US issues** across 840 titles.
`com.chrisstanford.everygeorgiarights` was booted out and both copies of its
plist deleted on 26 August. The section below is kept because the reasoning in
it outlives the job.

## How the rights join ran itself

`com.chrisstanford.everygeorgiarights` fires `rights_join_tick.sh` **every 15
minutes**, and that job is the only thing that needs to happen for
`data/georgia_rights.csv` to appear.

⚠️ **It is a timer, not a resident watcher, and that is the point.** launchd
re-fires a `StartInterval` job after the machine wakes; a long-lived process
polling in a loop does not survive sleep. The first attempt at this was a
`nohup` loop, which would have died at the first lid-close.

⚠️ **It probes before it works.** DLG was returning 503 on 7 of 8 requests on
21 August 2026, and the join makes 1,088 of them. Only a clean 3/3 health check
starts it; anything less logs a line and exits. Starting into a degraded service
would mean thousands of retries against a host already shedding load, days after
we emailed UGA promising to be a light touch.

⚠️ **Every partial attempt is progress.** Pages are cached under `data/rights/`,
so a run interrupted at page 900 resumes there. The script exits immediately and
silently once the csv exists, so the job costs nothing after it succeeds.

⚠️ **DLG is not down; it is shedding load, and it serves browsers first.**
Measured 21 August 2026. The 503 is DLG's own application response — `text/plain`,
`retry-after: 60`, body "The Digital Library of Georgia is currently unavailable
- please try again shortly", **no Cloudflare headers and no `cf-ray`** — so it is
not a bot challenge and there is no cookie or session a browser visit could
establish for us to reuse. Loading a page by hand in Safari does nothing for the
scripts. Across three spaced rounds a Safari user-agent returned 200 every time
(4 of 4 across all tests that evening) while our own identifying UA returned 503,
200, 503, on the same URL seconds apart.

⛔ **Do not spoof a browser user-agent to get through.** Our UA names the project
and carries the same address that emailed UGA asking permission. If DLG is under
load and serving humans before bots, that is the right priority, and working
around it would take capacity from a struggling service while our request sits
unanswered in their inbox.

⚠️ **This may mean the 3/3 gate never fires.** The probe was calibrated for "is
DLG up?", but the real condition is "is DLG willing to talk to *us* right now?"
If our UA succeeds around one time in three while browsers are served cleanly,
three consecutive clean probes may effectively never occur, and the job will
decline forever against a service that would answer slowly. Do not loosen it to
fire 1,088 requests into a host that is shedding load. If it persists beyond a
day or two, raise it with UGA alongside the permission chase — they run the API
and may have a bulk route or be willing to let a known client through.

The plist lives in `~/Library/LaunchAgents`; the copy here is a **mirror, not the
loaded file**. A job bootstrapped from `~/Scripts` does not survive a reboot.
Verify which is live before trusting either:

```bash
launchctl print gui/$UID/com.chrisstanford.everygeorgiarights | grep 'path ='
tail -5 ~/Scripts/everygeorgia/data/await_dlg.log
```

Once the csv lands, this job can be booted out and its plist deleted — but do it
from outside the job, never from within it.
