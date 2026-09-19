# everygeorgia — where things stand, 12 September 2026

A Bluesky account posting clippings from **Georgia Historic Newspapers**, run by
the Digital Library of Georgia at UGA. Read `README.md` for the technical
findings and `PROFILE.md` for the account text and the reasoning behind every
line of it.

## ✅ Permission arrived on 10 September 2026, and the poster is built

UGA Libraries replied to the 21 August request on 10 September: yes, with one
condition, credit the Digital Library of Georgia. On rights: material no longer
under copyright may be used freely and needs no permission from them. On the
citation form: theirs is a suggestion, any form will do. On traffic: the
rate-limit question had gone to their developers and had no answer yet, so
**no rate limit or User-Agent has been asked for**; ours identifies the account
anyway (`ghn_api.UA`). On content: selection is at our discretion, and a
cautious approach is warranted. The mail is in the Inbox;
`permission_followup.py --resolved` was run the same day and the reminder is
silent.

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

## ✅ Launch scheduled: 08:40 KST, Saturday 12 September 2026

`com.chrisstanford.everygeorgia-launch` (in `~/Library/LaunchAgents`, no mirror) runs
`everygeorgia_launch.sh` once: `--launch` posts the six-post thread and pins post 1,
then the script deletes its own plist and boots itself out, last, the everycarnegie
shape. On failure it leaves the job in place as the signal and the poster refuses a
second `--launch` once `data/post_state.json` records the thread. His call on the
evening of the 11th: "post it tomorrow morning, so I can catch it if something goes
wrong." The daily job then posts the first clipping, the Dawson Journal of 14 June
1867 (a dry run from the empty state picks it), at 09:10. Verified: `plutil -lint`
clean, `bash everygeorgia_launch.sh --dry-run` prints the six posts and removes
nothing, `launchctl print` shows the job loaded from `~/Library/LaunchAgents`.
✅ **Resolved 16:03 KST: he created a new app password and stored it himself; `login_client()`
logs in.** For the record, what happened: **the stored app password stopped working on the
afternoon of 11 September 2026, found at 15:57 KST by a read-only login test.** `createSession` answers 401 "Invalid
identifier or password" by handle and by DID, for the 19-character item in the Keychain
(`-a georgianewspapers.bsky.social -s everygeorgia-bluesky`, created 08:25 KST, never
modified). The same item logged in for `--setup-profile` at 08:25 and again at 11:38
and 11:40 (api_calls.jsonl), so it was revoked or replaced server-side after that. Until
a working app password was stored (his job, in a GUI session:
`security add-generic-password -a georgianewspapers.bsky.social -s everygeorgia-bluesky -U -w`)
the 08:40 launch would have failed at login, left its job loaded and notified. **The test
that found it, to re-run before relying on the job**:
`python3 -c 'import sys; sys.argv=["x"]; import everygeorgia_post as ep; print(ep.login_client(retries=1).me.handle)'`.
✅ **A Keychain read from a launchd job is verified too** (16:05 KST): a throwaway
RunAtLoad agent ran `security find-generic-password ... -w | wc -c` and got 20 bytes back at
exit 0, then was booted out and its plist deleted. Nothing about the launch is untested now
except the post itself. If the log at `~/Library/Logs/everygeorgia-launch.log` shows a
Keychain refusal, run `python3 everygeorgia_post.py --launch` by hand in a terminal
and remove the plist. **After it posts**: add the bot to `bot_health_check.py`,
`bot_alt_check.py`, `bot_variety_check.py` and `bot_scout_collect.py`.

The final thread text is in `profile.py` (post 3 at 299, post 4 at 218, both his
edits of the 11th; see PROFILE.md).

## The four lanes, built the evening of 11 September 2026

Chris: "I want everything. The profile can wait." So the advertisement,
headline, article (his follow-up: "a headline and first graf") and market-report
lanes were built the same day, on top of the
nameplate lane, and the poster cycles the four (`LANES` in
`everygeorgia_post.py`, one lane per run, a lane that comes up empty handing
its slot to the next). ⚠️ **The launch still waits**, and two profile edits
wait with it: the bio and post 1 say "before 1931", which is no longer a
rule (below), and the headline lane's alt text is model-written, so the bio
needs a disclosure line (everycarnegie's "Image descriptions are
A.I.-written", in this account's words).

**The 1931 cutoff is gone** (`gates.CUTOFF = None`), at his request: DLG
marks 8,628 issues from 1931 on as No Copyright (the Savannah Tribune to
1960, the Brantley Enterprise to 1973) and the 21 August email told UGA
their determination would be used, not ours.

| lane | source | crop | words a reader gets |
| --- | --- | --- | --- |
| nameplate | title order, front pages | `nameplate_crop.py` | the title, from the roster |
| headline | title order, **dailies only** (38 titles, 78,766 issues; `DAILY_PER_YEAR`) | topmost display item below the nameplate with its deck, `items.py` + `rules.py` | **model transcription**, `transcribe.py`, alt prefixed `A.I.-transcribed` |
| article | as headline | the headline item plus its first paragraph: everything down to the first run of three tight lines, then that run to the next indented line or ten lines (`clip_article`) | model transcription, whole |
| ad | search on genre phrases (`AD_PHRASES`: sarsaparilla, castoria, "for sale by all druggists"…), any page | the column block of set text around the phrase, `clips.block_around()` | OCR when legible, else the model |
| market | search on `MARKET_PHRASES`, any page | the block under the phrase, capped at ten rows and 15% of the page | OCR only; refused when illegible |

Every lane runs gates.py's crop and page passes, and the two model lanes run
the vocabulary prefixes over the transcription as well, since for display
type the OCR is the text it cannot read. Every lane's post is the same
citation with its label in the bracketed slot: `[Headline]`,
`[Advertisement]`, `[Market report]`.

### What the day taught, in the order it bit

- **lanes.py's geometries were measurement tools and said so.** Drawn on real
  pages, headline boxes chained across every column and ads cut their own
  borders. What separates items on a page is its RULES and GUTTERS, which are
  ink, so `rules.py` reads them from one 1,400px fetch of the page.
- **Gutters, not rules**: the Macon Telegraph has seven columns and no
  printed rules. **Page-level gutters, not the item's own rows**: measured
  over a few lines of an advertisement its own white space read as gutters
  and three of three crops were cut through their lettering. **An interior
  column dark down the page is a rule, not film edge**: treated as film,
  an eight-column Savannah page had no boundaries and a block spanned it.
- **`crop_frequency.norm()` returns ONE token.** Fed a transcription it
  returned one word, so every ad had no advertising words and a headline
  transcription carrying "negro" reached REVIEW instead of REFUSE. Pinned
  in `test_clips.py`.
- **Decks and paragraphs are told apart by spacing, not size.** On the Macon
  Telegraph the decks are bold body-height lines two ems apart and the
  paragraph is the same height set tight; a height rule ended the article
  crop inside the decks. And `rows_of()` puts a wrapped word in a row of
  its own, so `_lines()` folds those back before spacing is read.
- **Weeklies have no headlines.** The topmost display item on a small-town
  front page came back "COUNTY DIRECTORY", an office address, a brand name.
  The headline lane draws from dailies only, and refuses a transcription
  under three words or reading as an advertisement.
- **Display-ad OCR cannot say what a display ad is** ('ANDY GArtlACTlC'), and
  a boxed-on-four-sides test found nothing on microfilm, where every rule is
  broken. So ads are found by SEARCH on phrases with no other life in a
  newspaper, as reference_ghn_lane_findings said in August, and the block
  of set text around the phrase is the crop.
- **The search stems even as `phrasetext`**: "market report" answers with
  "market reports" and "Local Markets", so `find_phrase()` matches on
  prefix.
- **A market report is figures in prose**, not a table: "Bacon.—clear rib
  sides 10 cts" with the figures OCR'd as "16@17c". The test is a share of
  tokens carrying a digit, and the block ends at the paragraph after the
  heading, or ten rows.

- **A banner headline is cut at the first gutter, and its second line is
  left behind (found 11 September 2026, afternoon, in the twelve-sample dry
  run before launch).** The Cordele Dispatch of 10 October 1919 shipped
  "U. S. TO" out of "U. S. TO ADD 15 MILLIONS FOR GREAT WORLD AIR ROUTES",
  three faults deep. The gutter split judged clearance over the item box
  with its deck, which reaches into the column tier beneath where every
  gutter is clear; judged on the row itself, a word space over a gutter is
  white top to bottom too ("TO ADD" and "FRENCH DESTROY | MEMORIAL" both
  measure 0.000 dark). What separates them is **ink across a gutter**:
  banners measured 9, 10 and 21 gutters straddled against 5, 4 and 8 clear,
  the column tier 3 against 6, so a row straddling more than it clears is
  one banner (`items.gutter_counts`). Then the deck loop judged same-size
  per WORD, and seven of the second banner's eight words fell under 0.85 of
  the head; it steps one line at a time now, judged by the line's tallest
  word, and a line that is a tier (gap-split, or clearing at least as many
  gutters as it straddles) ends the item. And `_check_transcription` refuses
  a headline with any `[illegible]`; the half rule stays for articles.
  Measured before and after on all 129 cached front pages: 109 unchanged,
  20 changed, 10 of them dailies and every one 1860-1877, where the deck now
  stops earlier on standing heads and ads (a letter-spaced "Noon Telegrams"
  line reads as a tier). ⚠️ The article lane REFUSES a banner page ("no
  paragraph of body text under the headline"), since its paragraph search
  runs under the whole span; that is the right failure, and inner pages are
  where a banner's story would be found.

- **`claude -p` is an agent, and unconfined it will go anywhere (11 September
  2026, afternoon).** The dry runs crawled: 14 transcriptions timed out at
  120 s, then 5 more at 300 s. The transcripts under `~/.claude/projects`
  said why. A bare image-and-answer call is 10 s and an easy band 35 s; on a
  hard band the model cropped and enlarged the image with sips and Python
  through a dozen Bash calls; and on the Georgia Pioneer of 22 March 1839
  it ran `find ~ -iname clips.py`, read this project, ran `clip_nameplate`
  on three pages itself and returned "Ran cleanly. Results: ..." as the
  band's words. `transcribe.py` now runs `--restricted --tools Read` (20 s,
  two turns, on the same band), and the band asks for **display type only**
  (`BAND_PROMPT`): the strip's body text is the OCR's to read and the page
  gate's to screen, and asked for every word an 1839 band is thousands of
  characters. ⚠️ **The other bots' describers make the same unconfined
  call** (old-seoul and sherlock-quotes `image_alt.py`, everylibrary's and
  everycarnegie's describers); not touched here.

- **A skyline headline above the masthead defeats the nameplate band, and
  the headline lane then took the nameplate as a second line (11 September
  2026, twelve-sample run, Americus Times-Recorder of 9 June 1915).** "BRYAN
  QUITS CABINET" sits ABOVE the title on that page, so the OCR band (the top
  12.5 percent) held the skyline and not the nameplate; the nameplate lane's
  ink-edge gate refused it, correctly. But the headline lane's first
  candidate beneath that band was "COUNTRY SOLID IN SUPPORT OF WILSON", and
  the nameplate under it (973 units against a 699 head) passed the same-size
  test, so the crop carried the paper's title and the alt read it out. A
  continuation line is now at most `SAME_MAX` (1.25) times the head, taller
  ends the item, and `_refuse_own_title` refuses a headline or article whose
  words carry the roster title, the belt on the words a reader is given.
- **A scan can cut the nameplate, and the crop is then right and the picture
  wrong.** The Cordele Dispatch and Daily Sentinel of 24 September 1925 is
  filmed with the top of its title off the frame; the crop begins at the
  page's top edge as it should. Not gated: ink in the top rows is film edge
  on many good scans (the Dawson Journal's black border), so "ink at row 0"
  is not a test. Left as a known shape; a reader sees a title with its top
  sliced.
- **The Atlanta Daily New Era of 12 April 1871 has a tear through "NEW ERA"**
  and reads "NEW  RA." in the crop. The crop is right. Same class as above:
  the film, not the bot, and not gated.

### Yields, measured on the samples that set every constant

| lane | tries | passed or REVIEW | what the refusals were |
| --- | --- | --- | --- |
| headline (dailies) | 22 | 7 | antebellum dailies have no headlines; two ads caught by the transcription test |
| ad (search) | 23 | 10 | phrase stemmed away; block would not close |
| market (search) | 50 | 3 | prose around the phrase; illegible OCR |

⚠️ **The market lane is thin and the advertisement crops are uneven.** A
market run looks at `SEARCH_TRIES` (8) candidates and will often post
nothing, handing the slot on. Ad crops are columns of set text, sometimes
walls of it, occasionally a neighbour's heading at the foot. **Both lanes
ship because he asked for everything; hold either by removing it from
`LANES`.** ⏸ **The ARTICLE lane is held that way since the evening of
11 September 2026, his call ("Hold the article lane until the ad test
exists"): both article picks in the twelve-sample dry run were grocers'
advertisements passing as prose (Americus Times-Recorder, 13 July 1904; Griffin
Daily News, 9 March 1888). `LANES` is four; `test_the_article_lane_is_held_on_his_instruction`
pins it. Restore it between headline and ad once `clips.py` can tell an ad
from an article; the dateline test below is the one to try.** The crops were read by eye, as this file requires: the good ones
are the J. D. & T. F. Smith card (Atlanta, 1884), the Marietta market report
(1878) and "AIRPLANE RAID BY 20 OVER LONDON" (Augusta Herald, 1917).

⚠️ **Cost per run rose.** A headline costs a model call (10-40 s, and one
timed out at 120 s twice); an ad costs one when its OCR is under 72 percent
word-like. The model is `claude-sonnet-5` through `claude -p` with the
Keychain setup-token, as the photograph bots do, and a spent quota is waited
out once per run through `limit_guard`.

Tests: `test_clips.py` (12, synthetic page with columns, gutters and a
rule), `test_everygeorgia_post.py` (30, lanes and rotation), `test_nameplate.py`
(69). All stdlib plus Pillow, no network, no model.

## ✅ Vocabulary in the crop is REVIEW, not REFUSE (his call, evening of 11 September 2026)

"I don't think I want clippings refused outright. I'd like to look at them." Until that
evening a hit in the crop's OWN words was the one vocabulary condition that refused with
no person seeing it: `gates.check` on the OCR inside the crop, `clip_nameplate` on the
model's reading of the band, `_check_transcription` on a headline or article, the ad
lane on a transcribed ad. All four now hand the crop to the review queue instead
(`_review()` in clips.py; `gates.check` collects the reason and downgrades to REVIEW
unless rights, era or geometry already refuse, which still refuse outright).
**Nothing REVIEW is ever posted, so the feed is unchanged; the queue gains the crops.**
`log_review` now records `lane`, `words` and `image_box` so a line can be judged from
the file. Verified on two of the afternoon's pages: the Americus article of 30 July 1917
("NEGRO SOLDIERS IN SERIOUS CLASH") returns REVIEW with all three reasons named, and
the Savannah Daily Herald nameplate of 3 July 1865 returns REVIEW on its page hits.
Tests: `test_vocabulary_in_the_crop_is_REVIEW_since_11_September_2026`,
`test_rights_and_era_still_refuse_outright`, and the Black-press test now asserts
"never postable" rather than "refused".

⚠️ **Found doing it: `transcribe.py` inherited the caller's stdin, and `claude -p` reads
stdin as prompt.** A hand test run as `python3 - <<'EOF'` handed the model the rest of the
heredoc; with Bash it ran the script (the 1839 "Ran cleanly. Results:" incident above was
THAT, not the model wandering on its own), and under `--restricted` it came back as a
"prompt-injection note" in the words field. `stdin=subprocess.DEVNULL` now; launchd gives
/dev/null anyway, so no scheduled run was ever affected.

## ⏳ Next lane to build: notice, from weeklies' front pages (his call, 11 September 2026)

"I'm not opposed to featuring clips of ads and notices." The headline lane finds the
topmost display item below the nameplate and, on a weekly, throws it away as not a
headline: the attorneys' card, the county directory, the paper's own rate card, a
sheriff's sale. Those are the clip. The ad lane reaches weeklies only by search on a
phrase, which finds shape and never genre, so this is a sixth lane, not a widening
of that one.

**Build it after a week or two of real posts**, once the five lanes' real balance is
visible, and not before: the launch was scheduled and verified as it stood.
- The headline lane's machinery (`items.snapped`, `_headline_item`) with its
  advertisement REFUSAL inverted: a transcription reading as an ad or a notice is
  the pass, a news headline the refusal. Draw from the non-dailies.
- Transcribed by the model, gated on the vocabulary prefixes like every lane, alt
  prefixed `A.I.-transcribed`, label `[Notice]` or `[Advertisement]` by what the
  transcription reads as.
- ⚠️ **The era floor is the ad lane's, 1867, and is not negotiable**: before 1865 the
  standing legal-notice block on a weekly's front page is a slave-sale rate card,
  measured at 68.8 percent of front pages (README, "The advertisement lane before
  1865"). The notice lane starts where the ad lane does.
- Measure on twenty weekly front pages by eye before it ships, as every lane was,
  and add it to `LANES` last.

## ✅ The cartoon lane, 12 September 2026 ("Build the cartoon lane, strips included")

`pictures.py`, the sixth lane in `LANES`, drawing from the dailies like the
headline lane. Read its docstring first; the short form:

- **A cartoon is found by the hole it leaves in the OCR, not by its ink.** The
  three August attempts measured ink and failed because line art is neither
  text-textured nor continuous-toned. Re-measured on the Atlanta Georgian of
  15 January 1919, page 10: the strip is 0.18 ink against 0.15 for a text
  column, and no rule separates them; OCR-box coverage is 0.22 against 0.51.
  So the page is cut into cells (1/40 by 1/50), a cell is picture-like when
  under `COVER_MAX` (0.30) coverage and not film-black, a closing pass folds
  the lettered balloons back in, and a connected block big enough is a
  candidate. The ink floor is on the COMPONENT'S mean (0.06), never the cell:
  the first pass floored each cell and threw away the white inside the drawing.
- **Two cheap passes before any image.** Coordinates alone say whether a page
  has a hole worth the 1400px fetch; the ink pass confirms it; candidates are
  ranked ACROSS THE ISSUE (advertisement words in the framed crop last, then
  by size) before `MODEL_CALLS_PER_ISSUE` (3) are spent. Page by page, the
  1919 front page's unread headline cluster and a shoe advertisement's
  engraving would have spent the budget before the strip on page 10.
- **The frame** snaps only to a gutter within 3 percent of the picture's own
  edge (`rules.column_bounds` took the next uncrossed gutter and the whole
  column of type between, since the strip's border reads as crossing its
  own); trims at an absolute paper gap (`PAPER_ABS` 0.02) in the outer 30
  percent of the component, which is what cut off the unread headline tier
  the component had grown into (a rule test cannot: the dark-suited figures
  read 0.45-0.72, as a rule does); and takes up to three real-text OCR lines
  above (display allowed: a strip's title) and below (body height only: a
  caption, never the next item's headline).
- **The model sorts the kind** (`PICTURE_PROMPT`, through `transcribe.ask()`,
  a confined call whose reply keeps its lines): editorial-cartoon,
  comic-strip, sports-cartoon and humorous-drawing post; photograph,
  engraving, advertisement, map, diagram, ornament, text-only and other are
  refused and named in the log. It also transcribes the title and the printed
  words (balloons separated by bars, joined with periods as the band is) and
  describes the drawing in a sentence or two, and answers a separate
  CARICATURE line: a yes is REVIEW. Vocabulary in anything it read is REVIEW.
  The page gate applies as everywhere. Measured on the strip: 22 s, parsed
  clean, kind comic-strip, caricature no.
- **The alt is the one on this account that is a description**: "A.I.-described
  comic strip from “Atlanta Georgian,” Atlanta, Georgia, January 15, 1919,
  page 10. Five men sit around a card table… A.I.-transcribed, the words
  read: “HA! HA!! …”". Both labels are load-bearing: `bot_alt_check.py`'s
  marker for this account is the second. Quotes are curled by position
  (`pictures.curl`), not by `clips._curl`, which closed an opening one.
- **Era floor 1900, measured on the corpus's credit lines** (the table is in
  gates.py): no syndicate line on any page before 1905, "cartoonist" rare
  before 1900, and the first dry run at 1880 spent 35 model calls on 1886-1904
  dailies for engravings, advertisements and photographs. Local cartoons
  before 1900 are unmeasured.
- **A lane draws only from issues past its floor** (`eligible()` in the
  poster): four of the first run's eight titles were 1828-1878 and cost five
  skips each before a page was looked at.

⚠️ **The detector finds PICTURES; only the model's KIND line stands between an
advertisement's engraving and the feed**, and its first miss was in that
direction: a serial-story illustration signed Parker (Augusta Daily Herald,
24 January 1914) came back comic-strip and would have posted. The prompt
gained an "illustration" kind and the cartoon kinds now say what makes one
(exaggeration, panels, balloons, a joke or a comment); re-read, it is
illustration and the strip is still comic-strip. `test_pictures.py` (26) pins
that gate, the caricature REVIEW, the vocabulary REVIEW, both alt labels, the
detector on a synthetic page, the neck split, the trim, the thin-rule test
and the clear-row share.

**Yield, measured 12 September 2026, and the honest reading is that it is
thin.** A hand sample of one random issue from each of seven eligible dailies
plus the known Georgian page: **one PASS** (the Georgian's strip), **one
REVIEW** (a Dorman H. Smith editorial cartoon, "Give Him Time!", Banner-Herald
of 22 January 1925, page 4: the page gate, since the editorial beside it is
headed "The Negro and the South"), six refused with every picture named:
photographs, advertisements, unread type, one illustration. The two dry runs
through the poster, 25 issues of 1886-1911 dailies, found no cartoon at all
and spent about 60 model calls saying so, which is what moved the floor to
1900 and put the clear-row share ahead of size in the ranking. **Expect the
lane to hand its slot on more often than it posts** until the title order
reaches the Georgian (14,118 issues, 1913-1920, the one title where strips
are routine); the two eligible-issue fixes bound what an empty run costs at
about eight titles' worth of model calls. Three frames were read by eye and
are whole: the strip with its copyright line, the Parker illustration with
its caption, the Banner-Herald cartoon with its title and a sliver of the
column beside it.

### The credit-line search seed, 12 September 2026, evening ("Build the credit-line search seed")

The cartoon lane now draws two ways (`pick()` in the poster): first from search
hits on the syndicate credit lines a strip carries in set type
(`clips.CARTOON_PHRASES`: "International Feature Service", "Newspaper Feature
Service", "Registered U. S. Patent Office"; `clips.cartoon_candidates()`, from
1900), then, when nothing passes, from the title order as before. The search
half keeps its own tried map under `CARTOON_SEARCH` and posts as "cartoon".

**Measured before wiring.** 255 candidate pages on postable issues from one
search page per phrase per decade: **185 are the Atlanta Georgian's** (a Hearst
paper), 34 the Augusta Herald, 13 Americus, 11 the Brunswick News, 7 the
Banner-Herald, 2 each Griffin and The Red and Black, 1 the Athens Banner; by
year they run 1914-1922 with a tail to 1930. That share is why
`CARTOON_RECENT_WINDOW` is 3, not the ad lane's 30: the Georgian may post one
cartoon in four rather than none after its first. The lane was then run on
eight hits spread across titles: two PASS at once (a Brunswick News editorial
cartoon, "'Twas Loaded", and a Griffin Daily News sports panel by Laufer, both
1930), one illustration refused, one id the client refuses (The Red and Black's
`gua1179162`, now dropped at the search), and four "no hole" that were **the
detector's faults, not the pages'**. Fixing them took the evening and every
constant below was set on eight named pages, so re-run
`pictures.clip_cartoon(lccn, date, seq=n)` on them and LOOK before moving one:
the Georgian 1919-01-15 p10, Banner-Herald 1925-01-22 p4 and 1930-10-24 p9,
Americus 1920-02-09 p7, Brunswick 1930-06-11 p4, Griffin 1930-02-19 p2, Augusta
Herald 1922-08-20 p13, Augusta Daily Herald 1914-01-24 p5 (the illustration).
Final regression on all eight: seven PASS or REVIEW with whole crops, the
illustration refused twice over.

**The geometry as settled, in `pictures.py`, each rule with the page that set it:**
- the coordinates-only pass has no area ceiling (a comic page is half hole);
- a component is cut at NECKS on columns and rows, a neck being three or more
  consecutive cell rows or columns picture-like in under 30 percent of the
  other extent, and EVERY piece is a candidate (the masthead block beside the
  Banner-Herald cartoon; the portrait chain in the Brunswick column; two rows
  of lettering inside "'Twas Loaded" are two thick and are not a neck);
- rows in the running head or nameplate band are CLIPPED off a piece, never
  the piece dropped (the Americus strips reach row 0 through the page banner);
- each piece is parted into BANDS at paper gaps three rows deep across the
  span (film edge and the outer 5 percent of the span excluded, since a black
  stripe or a column rule keeps every row off paper), a paper row with ink at
  both edges of the span being inside a BOX and no gap; adjacent tall bands
  under 1.2 percent apart rejoin, a short band between (a title line) parts
  them; each band is neck-cut on columns again and keeps the band's own rows
  (the black monument in the Griffin panel is not a picture-like cell);
- the ink ceiling is 0.90 (dense hatching passed 0.70 and fragmented "Side
  Glances"), the fill floor 0.35, the clear-row share ranks and cuts at 0.25.

⚠️ **Two cleverer rules were measured and dropped, and should not come back
without a new measurement**: refusing a rejoin when the lower band opens with
display type (hand lettering in a cartoon is taller than any title, and it
halved "'Twas Loaded"), and parting bands at printed rules as well as paper
(fires on rows inside drawings; halved three of six).

⚠️ **Residual, known and accepted**: strips stacked inside a page-wide box (the
Americus comic page) come through as one band, since the box test that keeps a
cartoon whole across its sky also keeps them together; the model still calls
it a comic strip and the crop is several strips, legible at 1200 wide. Not a
slice and not a wrong kind.

## ⏳ Inside pages for headlines and articles: wanted, not yet possible

Chris, 11 September 2026: "I'd eventually like to include inside pages."
The capability exists (`clips.choose_page()`, a seeded draw with the
running head skipped; `--seq` for a hand-picked page) and `INNER_SHARE` is
0.0 because the measurement said so: 25 tries on pages 2, 3 and 5 of six
dailies gave one news story, a poem, two advertisements and a masthead. The
five crops are in the session record.

**What it needs before it can be turned on**: a test for an advertisement
that is not its vocabulary. The Pearline soap copy sells nothing by name
until its last line; a poem has no markers at all. The signals worth trying,
in order: the illustration (an inner-page item with a picture in it is an
ad far more often than not), a rule box around the item, and a story's own
shape (a dateline like "London.—" or "WASHINGTON, Dec. 8.—" opening the
first paragraph, which the Crippen and Wilson stories both have and no
advertisement does). The dateline test is cheap and probably the one to
build first. Raise `INNER_SHARE` only with a measured yield behind it.

## The poster, in five decisions

1. **One issue per title, titles in a fixed shuffled order** (`SHUFFLE_SEED`,
   appended never reshuffled), so all 836 titles with a pre-1931 NoC-US issue
   post once before any posts twice. Without it the Atlanta Georgian's 14,185
   issues would be one post in fifteen. Within a title the date is a seeded
   shuffle keyed on the pass number, so pass 2 shows a different year.
   ⚠️➡️✅ **This promise was broken for headline/article/cartoon from launch
   until 14 September 2026 — see "The shared title order could collapse to a
   lane's own subset" below, now fixed.**
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

## ✅ The shared title order could collapse to a lane's own subset — fixed 14 September 2026

The "OPEN FINDING" left in `~/Scripts/CLAUDE.md` on the night of 11 September
(the title order not being as fixed as `title_order()` promises) is now
**fixed**, not just diagnosed. It surfaced again on 14 September when Chris
noticed the Griffin Daily News — one continuously-published paper split by
Chronicling America into three LCCNs across its own title changes (1881-89,
1889-1924, 1924-present) — posting three times in three days.

**The mechanism, confirmed this time rather than guessed at.** `title_order()`
maintains ONE shared `state["order"]` ledger, but headline/article/cartoon
draw from their own narrow eligible-title subsets (19/19/13 of the full 843
postable titles), and `title_order()`'s first line drops anything from the
existing order that is not in whatever `titles` set it was just called with.
A win by one of those narrow lanes therefore persisted the shared order down
to that lane's tiny pool — measured live at exactly 19 on 14 September, right
after a headline-lane post the evening before. Griffin occupies 3 of those 19
slots, so once the order was stuck there Griffin had a genuine ~16% chance of
being the next headline-lane post. Not a shuffle coincidence: a structural
bias, and it would recur for any other town whose paper Chronicling America
split the same way.

**The fix.** `pick()` now always threads `sources["nameplate"]` (the
unfiltered 843-title universe) through `choose()`/`next_titles()` as a
separate `full_titles` argument, so `title_order()` is never called with
anything narrower than the full set. Each lane still only WALKS its own
eligible subset when picking a title to try; it just no longer prunes the
shared ledger to it. Verified the fix self-heals the already-stuck state
file (19 → 843) on the very next call, with no manual state edit needed, and
mutation-tested the new regression tests against a scratch copy of the whole
repo by reverting just the `pick()` wiring — confirmed to fail without the
fix and pass with it. Commit `6b69564`; `test_everygeorgia_post.py` gained
three tests pinning this shape (`Selection.test_a_narrow_lane_never_collapses_
the_shared_order_when_full_titles_is_given` and its two neighbours).

⚠️ **The alt text lost a sentence.** It ended "Scanned from microfilm; the page
is worn and the ink uneven", which was true of the one crop it was written
beside and unverified for every other. It now says only what the archive holds
exactly, plus what the detector guarantees (display type at the top of the
front page).

## ✅ Griffin's own frequency skew, not just the collapse — fixed 19 September 2026

Chris flagged a specific post ("georgia in print bot continues to seem to
favor griffin paper," linking the 18 September nameplate post of *Griffin
daily news.*, sn83009936) five days after the 14 September fix above. That
fix was real but narrower than it read: it stopped the shared order
collapsing to a lane's subset, and said outright, in its own words, that the
underlying skew "would recur for any other town whose paper Chronicling
America split the same way." It was never a claim that Griffin would stop
getting extra turns — only that a lane win would stop deleting 824 other
titles from the ledger.

**Measured on the live account (26 posts since launch):** 4 of 26 (15%) were
Griffin, under one of its three LCCNs — 3 of 12 nameplate posts, 1 of 5
headline posts. Two distinct mechanisms, confirmed rather than assumed:
- **Headline/cartoon's own narrow "dailies" pools.** Unchanged since
  14 September: Griffin occupies 3 of headline's 19 eligible titles and 2 of
  cartoon's 13 (`eligible(dailies(issues), lane)`, run live). That pool
  completes a full pass roughly monthly, so Griffin was always going to
  recur there at ~3x a normal daily's rate, forever, not as a passing
  artefact.
- **A shuffle coincidence in the nameplate lane**, not previously diagnosed:
  `SHUFFLE_SEED` is fixed for reproducibility, and it happened to place all
  three Griffin LCCNs at positions 5, 8 and 10 of the 843-title order.
  Nameplate walks the full, unfiltered order from position 0 and — at its
  own ~0.4 posts/day — needs roughly six years to complete one pass, so it
  hit all three in its first two weeks purely because they sit near the
  front. This half fades on its own; it was left alone.

A grep for "same city, several dailies" (the naive fix) would have been
wrong: Savannah alone holds 12 daily titles that are genuinely distinct,
competing papers (Savannah Morning News, Savannah Daily Republican, Savannah
Georgian...), not one renamed masthead. Each candidate family was instead
checked against its members' ACTUAL held issue dates (`issues_by_title()`,
not the roster's declared, sometimes open-ended year range) for a gapless,
non-overlapping handoff — a real continuation, not two papers sharing a
city. Four passed: **Griffin daily news** (1881-89 → 1889-1924 →
1924-present, no gap at all — the transition dates are literally
day-to-day), **Cordele dispatch** (1916 → 1920-06-02 → 1926-04-08, also
day-to-day), **Augusta herald** (1909-1914-03-03 → 1914-03-18, 15-day gap)
and **Macon telegraph and messenger** (1871-1873-08-30 → 1873-10-09, 40-day
gap). Left OUT, each for a real reason rather than caution alone: Columbus's
gapless Daily Sun → Sun and Enquirer → Daily Times → Columbus Daily Times
chain changes name too completely ("Sun" to "Times") to call a simple
rename, and Columbus Enquirer-Sun picks up four years after that chain
ends; Atlanta Georgian and News → Atlanta Georgian has a 14-month gap
(and Atlanta Georgian alone already dominates its pool at 14,118 issues, so
merging it would change nothing); Macon News arrives the year after
Telegraph and Messenger folded under a name with no relation to it at all.

**The fix is scoped to turn-taking only.** `TITLE_FAMILIES`/`family()` in
`everygeorgia_post.py` never touch `issues_by_title()`, `dailies()` or
`eligible()` — a family's real per-LCCN issue lists and density/era-floor
math are untouched, so nothing about which titles qualify as "daily" or
"postable" changes. Only `title_order()`, `next_titles()`,
`posted_this_pass()`, `choose()` and (for the search lanes) `recent_titles()`
now compare through `family()`, so a split paper occupies exactly one slot
in the order and one turn per pass per lane, while `choose()` still combines
dates from every real member present and calls `CLIP()` with whichever real
LCCN actually published that date — the returned lccn, and everything in
`state["posted"]`, is always the real member, never a synthetic family id.
Verified the fix self-heals the live state file the same way the
14 September one did: on a deep copy of the real `post_state.json`,
`title_order()` collapsed 843 entries to 837 on the very first call (Griffin
3→1, Cordele 3→1, Augusta 2→1, Macon 2→1), with no manual edit. Also ran the
real `pick()`/`sources` wiring end to end against the full 843-title,
19/13-eligible production data (CLIP stubbed to refuse everything, so no
network fetch and no write to the real state or review files) and confirmed
it completes without error across all five lanes.

⚠️ **Mutation-tested, not just green:** reverting `posted_this_pass()` to
compare raw lccn instead of `family()` was confirmed to let a family-mate
take a second turn in the same pass/lane — the exact shape of the original
finding — and the new tests catch it. `test_everygeorgia_post.py` gained a
`TitleFamilies` class (8 tests, a synthetic three-LCCN family isolated from
the real `TITLE_FAMILIES` tuple) covering: family resolution, order
collapsing to one slot, self-healing a state that still holds raw members,
`next_titles()` owing a family only one turn, `choose()` returning the real
member (not the family id), one turn per pass per lane regardless of which
member is posted, `TRIES_PER_TITLE` bounding the whole family rather than
each member separately, and `recent_titles()`/`choose_search()` treating a
family as one title for search-lane variety. All 39 pre-existing tests in
the file pass unchanged, confirming no non-family title's selection
behaviour moved. The other four suites in this repo (`test_clips.py`,
`test_nameplate.py`, `test_pictures.py`, `test_transcribe.py`) were also
re-run and are unaffected, as expected — nothing here touches their code.

⚠️ **Not addressed, on purpose:** the roster almost certainly holds other
split-title families beyond these four (51 exact name+city duplicates
turned up in an unrelated scan of the whole roster, most of them genuinely
distinct competing papers rather than renames — see Savannah above). Only
the four already confirmed, gapless, non-overlapping continuations were
merged; anything else needs the same by-hand date-range read before being
added to `TITLE_FAMILIES`, not a rule that infers it from a shared city.

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

## ✅ Fixed 19 September 2026: the headline crop dropped its own headline

Reported live: the headline post for the Atlanta Georgian of 27 September 1918
shipped "IS SMASHING; BULGARIA STAGGERING" -- HAIG cut off the front, and
"VICTORIES EVERYWHERE!", the actual banner headline above it, entirely absent.
Two independent, real bugs in `items.py`, both from real word geometry on this
page, both fixed with tests that fail on the old code:

1. **`nameplate.rows_of()`'s tolerance is scaled by the LARGER of the two
   heights compared**, so a tiny, unrelated word can bridge into a giant
   banner's row purely because the banner's own height makes the tolerance
   window huge -- even when the two never share any y-range. The nameplate
   area's small slogan word "Homes" (top 1814, height 317) sat, by x, inside
   the span of "VICTORIES" (top 2679, height 2367) with a 548-unit y-gap
   between them; `rows_of()` merged them anyway, and "Homes" then split
   "VICTORIES" away from "EVERYWHERE" at the x-gap step in `display_rows()`.
   Worse, the merged row's reported top (1814, from "Homes") read as inside
   the nameplate, so the whole banner was filtered out of headline candidacy
   before transcription ever ran. `items._y_overlap_groups()` now re-splits a
   `rows_of()` row wherever two words' vertical spans do not actually
   overlap, before the existing x-gap split runs -- it can only refine a
   false merge, never introduce one, since real same-line words always
   overlap in y however different their sizes.

2. **`rules.snap()`'s paper-mode vertical walk can climb above a headline
   candidate's own raw top**, even though `box_with_deck()`'s own docstring
   already promises "a headline item's own top is the seed row itself, never
   walked" -- that promise only held inside `box_with_deck`'s own loop.
   Snapping "VICTORIES EVERYWHERE!" (raw top 2613) walked upward looking for
   a rule or a clear gap and never found one: this page's masthead furniture
   (the dateline credit line -- "VOL. XVII ... ATLANTA, GA., FRIDAY,
   SEPTEMBER 27, 1918 ... Issued daily..." -- and the eagle emblem above it)
   fills the whole width densely all the way up to the masthead lettering
   itself, with no band of consecutive-enough clear rows anywhere in
   between. The walk stopped only once it hit that lettering as a "rule", at
   OCR y 1375: inside the nameplate's own 0-1828 band, and still above the
   dateline row it had just swept in too. Unclamped, that either disqualified
   the (now-correct) candidate at `clips._headline_item`'s own floor check,
   or would have posted a crop carrying the paper's own masthead furniture
   above the real headline. `items.snapped()` now holds the snap to the raw
   candidate's own top for the headline lane, exactly as `box_with_deck`
   already holds itself -- clamping to the raw top rather than to the
   nameplate's own detected bottom, because on this page that bottom (1828)
   sits short of the furniture (the dateline row runs to about 2443) it
   should cover, and clamping there would have swept the dateline row into
   the crop instead.

Both fixed in `items.py`; regression tests `DisplayRowsYOverlap` and
`SnapNeverWalksAboveTheRawTop` in `test_clips.py`, both confirmed to fail
against the pre-fix code. Full suite: 288/288. Verified against the real page
(`sn89053729`, 1918-09-27, ed 5, seq 1): `clips._headline_item()` now returns
exactly `["VICIORIES", "EVERYWHERE"]` as the head, cleanly, with nothing above
or beside it.

⚠️⚠️ **OPEN FINDING, not fixed: the same page's deck line is dropped by a
THIRD, harder problem, and this one was deliberately left alone.**
`items.is_tier()` calls `gutter_counts()` on the row "HAIG IS SMASHING;
BULGARIA STAGGERING" and reads it as a tier of several column items (3 of 4
page-level gutters inside its span are "clear" -- not crossed by ink -- on
this row, and only 1 is "straddled"), so `box_with_deck()` refuses it as the
head's deck line entirely, and `split_at_gutters()` separately cuts "HAIG"
off the front of it as its own one-word item. Both are the SAME underlying
false positive: this row's word-spacing (a perfectly ordinary headline, five
words, normal gaps) happens to put 3 of this page's 4 nearby column gutters
inside its own natural word-gaps, purely by coincidence of where the page's
real column grid (measured over the WHOLE page height, for the body text
several thousand units further down) falls under this one banner line. The
calibration this heuristic was built on (`gutter_counts`'s own docstring:
banners measured 9, 10, 21 straddled against 5, 4, 8 clear; a genuine tier 3
against 6) all had 9-29 total gutters in span; this row has only 4, so one
coincidental alignment flips the ratio with no statistical room to absorb
it. **Not fixed here**: a coverage-based guard (requiring the gutters to span
a meaningful fraction of the row's own width) was tried and rejected --
it demonstrably breaks the existing, deliberately-calibrated tier fixture in
`test_clips.py` (`test_a_row_straddling_the_gutters_is_a_banner_and_is_not_split`),
whose own tier case has similarly few gutters in span. Fixing this properly
needs either a `rule`-vs-`paper` distinction carried through `pi.gutters()`'s
own return value (currently discarded) or validation against the wider
historical corpus this heuristic was calibrated on, neither of which this
session had in hand. Consequence, with both fixes above applied: the headline
lane now correctly posts "VICTORIES EVERYWHERE!" alone for this page, with
nothing above or beside it and nothing wrong in it, but without its deck line.

⚠️ **OPEN FINDING, not fixed: `_check_transcription`'s 3-token floor refuses a
genuine two-word headline outright.** With both fixes above, `clip_headline()`
correctly transcribes this page's real headline as "VICTORIES EVERYWHERE!" --
and then `_check_transcription` raises `Refused("transcription too short or
too broken")`, because `len(plain) < 3` (only "victories" and "everywhere")
regardless of both words being long, legible, and non-noise (the OTHER half
of that same check, `>= 3 tokens of length >= 4`, would pass at 2 of 2 were
the token-count floor not there first). This floor is shared across every
lane (`clips._check_transcription`, headline/article/ad/market alike) and
was not touched here: loosening it risks admitting genuine noise on other
lanes, and validating a change against the historical corpus this file was
calibrated on is out of scope for what this session verified. Consequence:
this page's headline lane now REFUSES (skips) rather than posts something
wrong -- correct and safe, but it means a real, punchy, two-word headline
like this one currently cannot post via the headline lane at all.
