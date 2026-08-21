# everygeorgia — where things stand, 21 August 2026

A Bluesky account posting clippings from **Georgia Historic Newspapers**, run by
the Digital Library of Georgia at UGA. Read `README.md` for the technical
findings and `PROFILE.md` for the account text.

## ⛔ The one rule

**Nothing is published, the account does not exist, and neither should change
until UGA replies.** A permission email went to `dlgnwp@uga.edu` and
`gnp@uga.edu` on 21 August 2026. DLG's terms grant educational use freely but
require written permission from the holding institution to *publish*, and a
public account is publication. Silence is not permission; set a date to follow
up rather than letting it drift into a tacit yes.

## Done

| | |
| --- | --- |
| Roster | `data/georgia_roster.csv` — 1,158 of 1,164 titles, 158 counties |
| Avatar | `avatar/avatar_G_dark_72.png` — blackletter G, Macon, 23 Feb 1875 |
| Profile text | `PROFILE.md` — handle, name, bio, six pinned posts |
| Picture detector | Works; see README. Finds pictures, not specifically cartoons |
| Permission email | Sent |

Commits: `ad04b79`, `4bdc5a7`, `463b2e6`, `5609c0b`.

## Blocked, and on what

**The rights join, on DLG's servers.** `data/georgia_rights.csv` does not exist
yet. DLG has been returning 503 on most requests since roughly 16:00 on
21 August (7 of 8 probes at worst). `com.chrisstanford.everygeorgiarights` fires
`rights_join_tick.sh` every 15 minutes, probes three times, and starts the join
only on a clean 3/3. It has been correctly declining ever since. Nothing is
cached yet, so the eventual run starts from scratch — about 1,088 pages.

**The bio's date range, on that join.** `PROFILE.md`'s description deliberately
has no years. An earlier draft said "1763–1928" and neither number was
defensible. `sort=year_asc` is also untrustworthy: it reports 1889 as the
earliest NoC-US record while a 1767 record was directly observed in the same
filtered set. Do not quote a range until the join produces one.

**Everything else, on UGA.**

## Open questions for Chris

1. ~~**Does post 4 keep "Corrections welcome and acted on"?**~~ **Resolved
   21 August 2026: cut.** It now reads "Corrections welcome." in post 6. "Acted
   on" promises future behaviour nothing guarantees; a correction that arrives
   and is not acted on makes the line a lie. Do not restore it. (This session
   twice recommended keeping it, and was twice overruled — the reasoning is in
   `PROFILE.md`.)
2. **Does the account need an A.I. disclosure?** Alt text for nameplates,
   advertisements and market notes can come from the page's own OCR, and
   captions can be templated from metadata — so possibly none is needed, which
   is worth saying out loud if true. But the headline lane cannot use OCR, so
   those descriptions are written by hand or by a model. Decide before launch.
3. **Is "Unofficial, and not affiliated with the DLG" still in the thread?** It
   was cut from post 3 during editing and now lives only in the bio.

## Next moves, in order

1. Wait for the join. When `data/georgia_rights.csv` appears, report: how many of
   the 1,158 titles have a postable issue, and the true earliest/latest NoC-US
   dates. That number decides whether this is a six-month bot or a two-year one.
2. Boot out `com.chrisstanford.everygeorgiarights` once the csv lands, and delete
   its plist — **from outside the job, never from within it**.
3. Build the nameplate lane: pick a NoC-US issue per title, crop the top band,
   compose caption and alt text.
4. Follow up with UGA if there is no reply.

## Things that will bite a fresh session

- **Rights are not a date rule.** NoC-US runs to 1928 while In Copyright begins
  in 1924. Never substitute a cutoff year for the join.
- **A curl 200 is not arrival.** Turnstile serves its challenge with status 200.
  Check `url_effective`, or load the page in a real browser (it clears on the
  *second* navigation).
- **Search finds shape, never genre.** Every failed lane failed this way.
- **Carry identifiers through; never reconstruct them.** This caused two wrong
  links and one whole class of dropped records.
- **DLG returns a plain-text 503**, not an HTTP error curl will flag. Detect the
  body text.
