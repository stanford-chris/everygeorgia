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

255 of 256 characters.

```
Clippings from Georgia's historic newspapers: nameplates, advertisements, headlines, market reports. Alt text on every image.

From Georgia Historic Newspapers, presented online by the Digital Library of Georgia. Unofficial. Run by @stanfordc.bsky.social.
```

⚠️ **A bio cannot carry a link.** `app.bsky.actor.profile` has no description
facets; clients auto-detect bare domains and nothing else. That is why the links
live in the pinned thread and not here.

**No date range, on purpose.** An earlier draft said "1763–1928" and neither
number was defensible: 1763 is the archive's overall start rather than the span
of what is publishable, and 1928 came from a year facet that returns only its
top 100 values. Add the real span once `rights_join.py` reports it.

## Pinned thread

Five posts, all inside 300 characters. Post 1 is the pinned one; the rest thread
beneath it.

**1 — what this is (275)**
```
What this is: a clipping a few times a day from Georgia's newspapers — a nameplate, an advertisement, a headline, a market report — with the paper, the date and a link to the full issue.

Everything comes from Georgia Historic Newspapers: gahistoricnewspapers.galileo.usg.edu
```

**2 — how things are chosen (272)**
```
How things are chosen. Never at random. Only from issues the Digital Library of Georgia marks "No Copyright – United States," and only from a handful of categories I've picked deliberately.

Anything touching slavery, the Klan or racial violence I select and frame myself.
```

**3 — why (256)**
```
This archive is not a neutral record. In its pre-1931 pages, roughly 118,000 contain the word "lynched." A bot drawing at random would eventually post something indefensible, so this one doesn't draw at random.

Unofficial, and not affiliated with the DLG.
```

**4 — alt text and who runs it (241)**
```
Alt text carries the actual words of the clip, not a description of it, so a screen reader gets what the page says.

Run by @stanfordc.bsky.social — Georgia native, Grady College, first job at The Augusta Chronicle. Corrections welcome and acted on.
```

**5 — the avatar (279, link as a facet)**
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
