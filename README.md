# everygeorgia

A proposed Bluesky account posting clippings from **Georgia Historic Newspapers**,
run by the Digital Library of Georgia at UGA.

> ⛔ **NOTHING IS PUBLISHED, AND NOTHING SHOULD BE.**
> A permission email went to `dlgnwp@uga.edu` and `gnp@uga.edu` on 21 August 2026.
> No reply yet. The ask is specifically *permission to publish*, which is DLG's own
> term of art: their [Using DLG Materials](https://dlg.usg.edu/teach/using-materials)
> page grants educational and scholarly use freely but requires written permission
> from the institution holding the physical item for publication. A public account
> is publication. Do not post until they answer.

## Why this project exists

Chris is a Georgia native and a UGA Grady College graduate whose first newspaper job
was at *The Augusta Chronicle*; his grandfather was an advertising executive at the
*Atlanta Journal-Constitution*. The DLG's own Twitter account used to post exactly
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

**The corpus is not neutral, and a random draw is not viable.** In pre-1931 pages,
~118,000 contain "lynched" and 8,600 "negro for sale". Sampling real daily front
pages 1885–1908, a keyword blocklist rejected **15 of 24**. The filter removes the
era, not an occasional problem.

**The blocklist silences the Black press.** It rejected the front pages of *The
Colored American* (Augusta, 6 Jan 1866) and *The Colored Tribune* (Savannah), because
they share vocabulary with slave-sale advertisements. This is why the judgment stays
with a person, and it is named in the email.

**Search finds shape, never genre.** "Salutatory" in Georgia papers overwhelmingly
means a commencement address; "prospectus" is one-in-seven the newspaper sense;
"the editor regrets" returned a poem about a rejection slip. Selectors that work do
so because the phrase is genre-specific ("sarsaparilla" only appears in advertising).

**Carry identifiers through; never reconstruct them.** Guessing LCCNs put two wrong
links into sample posts and killed a lookup outright.

**A curl 200 is not arrival.** Turnstile returns its challenge page with status 200,
so every "verified" link check was passing on a challenge. Check `url_effective`.

## The editorial test for difficult material

A caption does not travel with a screenshot. The question is not "can I frame this?"
but **"is the image defensible with no words attached?"** A Georgia bishop's headline
calling the Klan un-American passes. A 1920 paper printing the Klan founder's denial
as news fails, because the image alone is Klan publicity whatever the caption says.
