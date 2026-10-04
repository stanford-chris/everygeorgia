# everygeorgia

**Georgia in Print**, [@georgianewspapers.bsky.social](https://bsky.app/profile/georgianewspapers.bsky.social):
a Bluesky account posting clippings from **Georgia Historic Newspapers**, the
archive run by the Digital Library of Georgia at UGA. Unofficial.

UGA Libraries gave permission to publish on 10 September 2026, with one
condition: credit the Digital Library of Georgia. Every post ends "Courtesy of
the Digital Library of Georgia.", with the link to the page on those words.

## Why this project exists

I'm a Georgia native and a UGA Grady College graduate whose first newspaper job
was at "The Augusta Chronicle". The DLG's own Twitter account used to post exactly
this kind of clipping and stopped in December 2024.

## Two APIs, and they are complementary

| | |
| --- | --- |
| **Open ONI** at `gahistoricnewspapers.galileo.usg.edu` | Page images, word-level OCR coordinates, full page text in `ocr_eng` on every search result, and a level-2 IIIF image server at `iiif-ha.galib.uga.edu` allowing arbitrary region crops. The only source of pages, text and images. |
| **DLG** at `dlg.usg.edu/about/api` | 1,084,812 records across all of DLG; GHN is its largest collection at 371,998, issue-level, no OCR, no IIIF. Its value is **machine-readable rights statements**. |

## What it posts

Two runs a day, one clipping each. The lanes take turns in this order
(`LANES` in `everygeorgia_post.py`); a lane that comes up empty hands its slot
to the next, and the rotation continues from the lane that last posted.

| Lane | Source | From | Text in the alt |
| --- | --- | --- | --- |
| nameplate | front page, title order | any date | the band under the masthead, model-transcribed |
| headline | front page of a daily, title order | 1880 | headline and decks, model-transcribed |
| article | front page of a daily, title order | 1880 | headline and first paragraph, one column; must carry a dateline or wire credit |
| ad | search on advertising phrases | 1867 | OCR if legible, else model-transcribed; a boxed ad is cropped to its printed border |
| market | search on market-report phrases | 1867 | OCR; the whole headed section |
| classified | search on want-ad phrases | 1867 | OCR; a run of items in one column |
| cartoon | syndicate credit-line search, then title order (dailies) | 1900 | a model description plus the printed words |

`HELD_LANES` is where a lane waits before joining the rotation (`--lane <x>`
runs it by hand). It is currently empty.

Selection is one issue per **title**, titles in a fixed shuffled order, so every
paper posts once before any posts twice. Only issues DLG marks "No Copyright -
United States" are used; there is no year cutoff of our own. Model-written words
are labelled `A.I.-transcribed` (cartoon descriptions `A.I.-described`) wherever
they reach a reader. Post text is the paper's name and date, the credit, and
`#Georgia #History` plus a tag for the paper's town (`#FortValley`) when the
roster knows it.

## Review

`gates.py` returns PASS, REVIEW or REFUSE. REVIEW means the crop or the page it
links to carries slavery, lynching or Klan vocabulary: a person decides. A
REVIEW item is never posted by the ordinary path and never blocks the run.

1. The item is appended to `data/review.jsonl` with its crop saved under
   `data/review/`, and the run moves on.
2. After each live run, new items are mailed with their crops embedded (through
   the estate's `estate_mail.py`, outside this repo). Dry runs are logged but
   not mailed.
3. A person decides:
   ```bash
   python3 everygeorgia_post.py --approve LCCN:DATE[:LANE]
   python3 everygeorgia_post.py --reject LCCN:DATE[:LANE]
   ```
   Decisions go to `data/review_decisions.jsonl`; the latest per item wins.
4. Approved items post in their lane's turn, alternating with ordinary picks
   and never back to back from one title family. Each is re-cut first: it is
   dropped if the re-cut is refused (rights, era, geometry) or lands on a
   different crop, and the alt uses the words the reviewer read. Approval
   lifts the vocabulary hold and nothing else.

## Running it

```bash
python3 everygeorgia_post.py                 # post one, live
python3 everygeorgia_post.py --dry-run       # choose and print, post nothing
python3 everygeorgia_post.py --lane cartoon  # one lane instead of the rotation
python3 everygeorgia_post.py --status
```

A bare run posts; unknown flags are rejected. The Bluesky app password is read
from the Keychain (service `everygeorgia-bluesky`).

## Files

- `everygeorgia_post.py`: the poster, the rotation, the review queue and mail,
  `--launch` (pinned thread), `--setup-profile`.
- `profile.py`: the bio and the six-post pinned thread as data.
- `gates.py`: PASS / REVIEW / REFUSE, with each lane's era floor. The ad lane's
  1867 floor is measured: publishers carried the standing slave-sale rate card
  for a year after the war.
- `clips.py`: one clipping from any lane, the search candidate lists, the block
  and column builders.
- `nameplate.py`, `nameplate_crop.py`: the nameplate detector (by geometry,
  never by text) and the nameplate clipping. Gate 4 reads the pixels, because
  the OCR reads display type worst.
- `rules.py`: the page's grid from its pixels: gutters, rules, film edge and the
  printed border of a boxed ad.
- `items.py`: display rows split at column gaps, boxed with their decks.
- `pictures.py`: the cartoon lane. A drawing is found by the hole it leaves in
  the OCR, not by its ink, and the model sorts it by kind.
- `transcribe.py`: words in a clipping, by `claude -p` vision.
- `ghn_api.py`: Open ONI manifests, OCR coordinates and IIIF crops. Read-only,
  cached, cannot post. The OCR coordinate space is not the image space and
  varies by page: always scale through `Page.to_image()`. The manifest claims
  IIIF `level0`; the server's `info.json` says `level2`, which is right.
- `georgia_roster.py` -> `data/georgia_roster.csv`: 1,158 of 1,164 titles across
  158 counties.
- `rights_join.py` -> `data/georgia_rights.csv`: the roster joined to DLG's
  per-issue rights. Run once (22 August 2026): 843 of 1,158 titles postable.
- `crop_frequency.py`, `lanes.py`: the crop-level vocabulary measurement below.
- `crop_closure_check.py`: weekly read-only check that each lane's crop closed
  with room to spare.
- `permission_followup.py`: the permission reminder, now resolved and silent.
- `test_*.py`: stdlib tests, run by path.
- `avatar/avatar_G_dark_72.png`: a blackletter G from the "Georgia Weekly
  Telegraph and Georgia Journal & Messenger", Macon, 23 February 1875, with its
  source image.

## Things learned the hard way

**Rights are not a date rule.** "No Copyright - United States" runs to 1928 while
"In Copyright" begins in 1924, so the 1920s overlap and are decided title by
title, and DLG marks thousands of later issues No Copyright too. Any cutoff year
invented here would override DLG's own item-level determination.

**DLG does not hold every issue.** 371,998 records against 518,801 issues in GHN,
so roughly 28% carry no rights statement. That state is `unknown`, not `none`,
and neither is permission.

**The corpus is not neutral, and a random draw is not viable.** Measured 21 August
2026 against 2,272,709 pre-1931 pages, of which 353,576 are front pages:

| term | all pages | front pages |
| --- | --- | --- |
| `slave` (stems `slaves`) | 197,981: 8.7% | 39,818: **11.3%** |
| `lynch*` | 118,518: 5.2% | 27,283: **7.7%** |
| `ku klux` | 17,000: 0.7% | 4,886: 1.4% |
| `negro for sale` | 8,673: 0.4% | 1,950: 0.6% |
| any of those three subjects | 318,881: 14.0% | 68,315: **19.3%** |
| `negro` alone | 719,394: 31.7% | 166,982: **47.2%** |

Roughly one pre-1931 front page in five carries slavery, lynching or Klan
vocabulary. Three cautions:

- **It counts vocabulary, not subject.** "Slave" catches classical allusion;
  "negro" spans neutral news and the Black press writing about itself. Every
  figure is an upper bound on subject.
- **It is page-level, and the lanes are crops.** Measured at crop level
  (`crop_frequency.py`): the nameplate crop carries 0.0% against 27.0% at page
  level, and none of the 843 postable titles carries the vocabulary in its name.
  Headline crops run 5.6% and display ads 1.1%, but a crop is blind to the page
  around it, so every lane also gates on the whole page.
- **The index stems.** `lynch`, `lynched` and `lynching` all return 118,518. Never
  quote a figure as the count of one literal word.

**`date1`/`date2` take ISO dates, and a wrong format is silently ignored.**
`date1=1763&date2=1930&dateFilterType=yearRange` returns the whole corpus with an
HTTP 200. Use `date1=1763-01-01&date2=1930-12-31&dateFilterType=range&searchType=advanced`.
`sequence=1` restricts to front pages.

**A blocklist silences the Black press.** It rejected front pages of "The Colored
American" (Augusta, 1866) and "The Colored Tribune" (Savannah), which share
vocabulary with slave-sale advertisements. That is why REVIEW goes to a person
rather than being a refusal.

**Search finds shape, never genre.** "Salutatory" in Georgia papers mostly means a
commencement address; "the editor regrets" returned a poem. Selectors work when
the phrase is genre-specific ("sarsaparilla" only appears in advertising).

**Rights are issue-level, not edition-level.** Identifiers are
`/lccn/<lccn>/<date>/ed-1/seq-<n>/`; DLG marks issues, so "an issue per title"
means `ed-1` unless a title genuinely printed more than once a day.

**Carry identifiers through; never reconstruct them.** Guessed LCCNs produced
wrong links.

**A curl 200 is not arrival.** Turnstile returns its challenge page with status
200. Check `url_effective`.

**DLG sheds load and serves browsers first.** During the rights join its API
returned 503 on most requests from our identifying User-Agent while a browser UA
got through. The join probed for health before starting, cached every page so
it could resume, and never spoofed a browser UA: under load, humans should come
first.

## The editorial test for difficult material

A caption does not travel with a screenshot. The question is not "can I frame this?"
but **"is the image defensible with no words attached?"** A Georgia bishop's headline
calling the Klan un-American passes. A 1920 paper printing the Klan founder's denial
as news fails, because the image alone is Klan publicity whatever the caption says.
