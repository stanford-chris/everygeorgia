# georgianewspapers — Bluesky profile

Everything needed to set the account up.

> ⛔ **The account does not exist and must not be created yet.** A permission
> email went to UGA on 21 August 2026 and has not been answered. See `README.md`.

## Handle and name

| | |
| --- | --- |
| Handle | `georgianewspapers.bsky.social` |
| Display name | **Georgia Newspaper Clippings** (27 of 64) |
| Avatar | `avatar/avatar_G_dark_72.png` (1024×1024, 248 KB) |

All four candidates were free when checked on 21 August 2026:
`georgianewspapers`, `everygeorgianews`, `everygeorgiapaper`, `gahistoricnews`.

⚠️ **"Every Georgia Newspaper" was rejected, and the reason matters.** It would
have matched the everylibrary/everycarnegie family, but those rosters aim at
completeness and this corpus cannot: GHN covers 157 of 159 counties, holdings
begin mid-run (0 of 14 sampled titles has a genuine first issue), and the
*Atlanta Constitution* holds 474 issues across 18 years. "Every" would be an
overclaim in the account's own name.

⚠️ **"Georgia Historic Newspapers" is DLG's project name and must not be used.**
Neither may anything else that implies endorsement. "Clippings" does the work of
distinguishing us from the archive, and it is the word DLG themselves used
("Here's a clip of the front page…").

⚠️ **No hyphen in the handle, deliberately.** Bluesky clients linkify bios by
running a URL detector over the text, and a hyphen in the domain kills it.

## Description

233 of 256 characters.

```
Clippings from Georgia's newspapers before 1931: nameplates, advertisements, headlines, market reports.

From Georgia Historic Newspapers, presented online by the Digital Library of Georgia. Unofficial. Run by @stanfordc.bsky.social.
```

⚠️ **A bio cannot carry a link.** `app.bsky.actor.profile` has no description
facets; clients auto-detect bare domains and nothing else. That is why the links
live in the pinned thread and not here.

⚠️ **"Alt text on every image." was cut on 21 August 2026, and should stay cut.**
Two reasons, and the second is the real one. Bluesky's official app puts an ALT
badge on images that carry alt text, so a sighted reader already gets the fact
per-post. More importantly it was the *generic* form of a claim post 4 makes
properly — "alt text carries the actual words of the clip, not a description of
it" is distinctive; "alt text on every image" is what any careful account says.
The 25 characters bought back "presented **online** by", which is DLG's own
credit phrasing and worth more while their permission is outstanding.

The counter-argument is on the record because it is not a bad one: the ALT badge
is a *visual* affordance, and the reader for whom this is a decisive question
cannot see it. If the bio ever needs the reassurance back, use the distinctive
form — "Alt text is the clip's own words." — not the generic one.

## The 1931 cutoff

The bio and post 1 both say **before 1931**, and post 3 says "pre-1931 pages".
That agreement is the point: two different years in one thread invites the reader
to ask which one governs.

⚠️ **It is our rule, never a statement about where the archive ends, and it must
never replace the rights join.** README's warning stands — rights are not a date
rule, NoC-US runs to 1928 while In Copyright begins in 1924, and any invented
cutoff would override DLG's item-level determination. This does not override it.
Both gates apply, DLG's is still the operative one, and a date gate can only ever
narrow, so it cannot over-claim. That is the opposite failure mode from the one
the warning guards against.

Why 1931 rather than 1930, which was recommended first:

- **Post 3's ~118,000 "lynched" figure was counted over pages before 1931.**
  Restating it as "pre-1930" would quote a measured number over a denominator it
  was not measured on. The number keeps its own denominator; post 1 moved to meet
  it.
- **The maintenance objection to 1931 was wrong.** It was rejected initially for
  tracking the moving public domain line and so needing an annual edit. It only
  needs that if it is meant to track. As a fixed cutoff it never needs touching,
  and as the PD line advances past it the number becomes *more* conservative. No
  future makes "before 1931" an over-claim.
- **It costs no known material.** 1931 sits well above the observed 1928 NoC-US
  ceiling, as 1930 did.

⚠️ **Do not quote an exact range in place of this.** An earlier draft said
"1763–1928" and neither number was defensible: 1763 is the archive's overall
start rather than the span of what is publishable, and 1928 came from a year
facet that returns only its top 100 values. `sort=year_asc` is untrustworthy too:
it reports 1889 as the earliest NoC-US record while a 1767 record was directly
observed in the same filtered set. A real span waits on `rights_join.py`; the
cutoff does not.

## Pinned thread

Five posts, all inside 300 characters. Post 1 is the pinned one; the rest thread
beneath it.

**1 — what this is (269)**
```
What this is: clippings from Georgia's newspapers before 1931 — a nameplate, a headline, an ad, a market report — with the name of the paper, the date and a link to the full issue.

Everything comes from Georgia Historic Newspapers: gahistoricnewspapers.galileo.usg.edu
```
Three edits on 21 August 2026. "a clipping a few times a day" became
"clippings", dropping a cadence claim that has not been decided. "with the paper"
became "with the name of the paper", because the first could be read as the paper
itself. And the four lanes were reordered to follow the page — nameplate at the
top, headline beneath it, ads and market reports inside — where the old order was
arbitrary.

**2 — how things are chosen (262)**
```
How things are chosen: Only from issues the Digital Library of Georgia marks "No Copyright – United States" and only from a handful of categories I've picked deliberately.

Anything touching slavery, the Ku Klux Klan or racial violence I select and frame myself.
```
"the Klan" was spelled out to **Ku Klux Klan** — better on a first mention, and
it does not assume the reader's shorthand. "Never at random." was cut here; post
3 still carries the idea ("so this one doesn't draw at random").

**3 — why (246)**
```
This archive is not a neutral record: Roughly 118,000 of its pre-1931 pages mention lynching, and a bot drawing at random would eventually post something indefensible. This one doesn't draw at random.

Unofficial, and not affiliated with the DLG.
```
⚠️ **"mention lynching", not 'contain the word "lynched"'.** The ONI index stems:
`lynch`, `lynched`, `lynching` and `lynchings` all return 118,518. The old
wording named a specific word the number does not measure, and this is the post
that has to be exactly right.

⚠️ **"pre-1931" stays, and is not redundant with post 1.** The subject of the
sentence is the archive, and the archive is not pre-1931 — 161,368 of its
4,564,007 pages mention lynching. Drop the qualifier and the figure is attached
to a denominator it was not measured on. Post 3 is also the most likely of the
five to be screenshotted, being the difficult one, and a caption does not travel
with a screenshot.

**4 — alt text and who runs it (249)**
```
Alt text carries the actual words of the clip, not a description of it, so a screen reader gets what the page says.

Run by @stanfordc.bsky.social — Georgia native, Grady College, first job at The Augusta Chronicle. Corrections welcome and acted on.
```

**5 — the avatar (277, link as a facet)**
```
The avatar is a clipping too: an ornate blackletter capital G from the nameplate of the Georgia Weekly Telegraph and Georgia Journal & Messenger, Macon, Feb. 23, 1875. The white pitting in the strokes is the microfilm, not a filter.

gahistoricnewspapers.galileo.usg.edu/lccn/…
```
→ facet target: `https://gahistoricnewspapers.galileo.usg.edu/lccn/sn85034222/1875-02-23/ed-1/seq-1/`

⚠️ **Post 5 needs the link as a facet.** With the URL written out it is 309
characters. A facet stores the URI outside the text, so the visible form costs
45 characters rather than 75. Verified against live posts: the full URL does not
appear in `record.text` at all.

⚠️ **Keep post 3.** It is the least comfortable of the five and the one that
makes the account defensible, because it says the difficult thing before anyone
has to ask.

## The avatar

A blackletter capital **G** from the nameplate of the *Georgia Weekly Telegraph
and Georgia Journal & Messenger*, Macon, Bibb County, 23 February 1875. Source
image kept beside it as `avatar/source_G_1875_macon.jpg`.

It was found by accident: the picture detector built for editorial cartoons kept
flagging blackletter capitals, because ornate gothic type is dense enough to read
as art and the OCR cannot read it. A false positive there, a gift here.

Two things were measured rather than guessed:

- **Everything is judged at 56px**, the size Bluesky renders in a feed. Word
  crops fail ("ONI", "SSENG" are noise). Real newsprint texture inside a state
  silhouette fails. Column rules and a masthead band fail *worse*, because any
  internal division breaks a silhouette rather than decorating it.
- **The letterform must not be cleaned by connected-component isolation.**
  Taking the largest connected dark region stripped the G to its outer contour
  and discarded every interior stroke: blackletter capitals are built from
  separate strokes. Use a soft alpha ramp and a median filter instead.

A Georgia state silhouette, built from GHN's own `counties_map.json`, was the
runner-up and is a fine fallback. It reads instantly at 56px but says only
"Georgia" where the G says "Georgia" and "old newspaper" at once.

## Still to decide

- **Whether any of this is A.I.-written.** everycarnegie discloses that its image
  descriptions are generated. Here, alt text for nameplates, advertisements and
  market notes can come straight from the page's own OCR, and captions can be
  templated from metadata — so the account may need no disclosure at all, which
  is worth saying out loud if true. But the headline lane cannot use OCR (display
  type OCRs worst of anything on the page), so those descriptions are written by
  hand or by a model. Decide before launch, not after.
- **The `website` field**, and whether the pinned thread can ever say anything
  warmer than "not affiliated" — both wait on UGA's reply.
