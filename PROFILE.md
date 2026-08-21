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
Clippings from Georgia's newspapers before 1931: Nameplates, advertisements, headlines, market reports.

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

Six posts, all inside 300 characters. Post 1 is the pinned one; the rest thread
beneath it.

Every post opens with a label or a claim and then a colon, which is what makes
the thread read as a set of cards rather than six paragraphs.

⚠️ **Capitalise after that colon in every case, including where a fragment
follows, and do not "correct" it.** This is a deliberate departure, decided
21 August 2026. The house rule elsewhere is to capitalise after a mid-sentence
colon only when a full sentence follows, and by that rule posts 1, 2 and 5 and
the bio should all read lowercase. They do not, because here the colon is
functioning as a card heading rather than as punctuation inside a sentence, and a
thread where three cards start capital and three start lowercase looks like an
error rather than a rule. Consistency of shape beat consistency with the grammar,
knowingly.

⚠️ **The exception is post 1's second colon**, which introduces a URL. That one
stays as it is; capitalising a domain breaks it.

**1 — what this is (264)**
```
What this is: Clippings from Georgia's newspapers before 1931 — nameplates, headlines, ads, market reports — with the name of the paper, the date and a link to the full issue.

Everything comes from Georgia Historic Newspapers: gahistoricnewspapers.galileo.usg.edu
```
Two edits on 21 August 2026. "a clipping a few times a day" became "clippings",
dropping a cadence claim that has not been decided. "with the paper" became "with
the name of the paper", because the first could be read as the paper itself.

⚠️ **The lane list here differs from the bio's on purpose. Do not reconcile
them.** This post reads **nameplates, headlines, ads, market reports**; the bio
reads **Nameplates, advertisements, headlines, market reports**. Two differences,
both deliberate:

- **Order.** This post follows the page — nameplate at the top, headline beneath
  it, ads and market reports inside. The bio is a plain listing with no sentence
  around it, so it has no page to follow.
- **"ads" against "advertisements".** This post is a sentence in the account's
  own voice and takes the conversational word. The bio is the formal description.

They were forcibly matched on 21 August 2026 and unmatched the same evening. The
matching looked like tidiness and was not asked for: the instruction naming
"nameplates, advertisements, headlines, market reports" was about the **bio**.
Both lists are plural and unarticled, which is the one thing they do share — an
earlier draft here wrote them singular with articles ("a nameplate, an
advertisement…"), disagreeing in number with the "clippings" it expands. An intermediate draft reordered this post to follow the
page — nameplate at the top, headline beneath it, ads and market reports inside —
and shortened "advertisement" to "ad"; it was a better sentence in isolation and
was dropped because it made the two lists disagree.

**2 — how things are chosen (272)**
```
How things are chosen: Only from issues that the Digital Library of Georgia marks "No Copyright – United States" and only from a handful of categories that I've picked deliberately.

Anything touching slavery, the Ku Klux Klan or racial violence I select and frame myself.
```
"the Klan" was spelled out to **Ku Klux Klan** — better on a first mention, and
it does not assume the reader's shorthand. "Never at random." was cut here; post
3 still carries the idea ("so this one doesn't draw at random"). The capital
"Only" is deliberate: see the note at the head of this section.

⚠️ **"issues", never "editions".** DLG marks rights on issues; an edition is a
sub-unit inside one. See `README.md`. Considered and rejected 21 August 2026.

⚠️ **The second sentence is proportionate, and it was measured.** Roughly one
pre-1931 front page in five carries slavery, lynching or Klan vocabulary before
"negro" is counted at all, and 47% mention it. The full table and its three
cautions are in `README.md`. This is not a rare problem being dressed up as a
common one.

**3 — why (204)**
```
These posts are not representative of the archive: Roughly 160,000 of its pages mention lynching, and a bot drawing at random would eventually post something indefensible. This one doesn't draw at random.
```
⚠️ **"representative", not "neutral", and the claim is about the feed rather than
the archive.** This post said "This archive is not a neutral record" until
21 August 2026. Two problems, and the second is the substantive one.

"Neutral" was doing two jobs: it can mean *unbiased*, or it can mean *a fair
sample*. Only the second is the claim worth making, and "representative" says it
without the ambiguity.

More importantly the accusation was pointed the wrong way. The archive is
faithful — it preserves what was printed, and lynching and slavery were part of
what was printed. The thing that is **not** a fair sample is this account's feed:
nameplates, ads and market reports are a gentler nineteenth-century Georgia than
the archive actually holds. That is the harder admission and the more honest one,
and it describes our own output rather than characterising DLG's holdings, which
matters while their permission is outstanding.

⚠️ **Do not "restore" a claim that the papers were unbiased.** Many were not —
Klan notices ran as community news and slave sales as ordinary classifieds. The
post avoids the question entirely, which is why it must stay on "representative".

⚠️ **"These posts", not "Posts".** Same reason post 5 says "This account's
avatar": the post has to say whose in a screenshot.
⚠️ **Posts 1 to 3 carry no disclaimer, and that was decided rather than
overlooked.** After the move, "Unofficial" appears only in the bio and post 6 is
the thread's only disclaimer — so a screenshot of the first three posts, which is
the most plausible way for someone to mistake this for DLG's own account, has
nothing explicit on it. Considered and accepted on 21 August 2026. Post 1 cannot
hold the line without going over 300, and the alternative was trimming post 1 to
make room. Post 2 names the Digital Library of Georgia as an outside authority
this account defers to for rights, which reads as unaffiliated by implication.
**If that judgment ever looks wrong, the fix is to trim post 1, not to put the
line back into post 3, where it did not belong.**

⚠️ **The affiliation disclaimer left this post on 21 August 2026 and belongs in
post 6.** It read "Not affiliated with the Digital Library of Georgia" and was a
statement about the account's provenance stranded at the end of a post about the
corpus. Post 6 is the post about who runs the account, so it says it there. Post
1 was the other candidate and cannot take it: both drafts ran past 300.
⚠️ **"mention lynching", not 'contain the word "lynched"'.** The ONI index stems:
`lynch`, `lynched`, `lynching` and `lynchings` all return the same total. The old
wording named a specific word the number does not measure, and this is the post
that has to be exactly right.

⚠️ **The figure and the denominator must move together, and they have moved
twice.** The sentence's subject is the archive, so the number has to be the
archive's: **161,368** of GHN's 4,564,007 pages mention lynching, quoted as
"roughly 160,000". The pre-1931 subset is a different number — 118,518 of
2,272,709 — and an earlier draft paired that figure with the unqualified word
"pages", which reads as a claim about the whole archive and understates it. If
this sentence ever regains "pre-1931", the figure goes back to 118,000 in the
same edit. Never move one without the other.

⚠️ **Post 3 is the most likely of the six to be screenshotted**, being the
difficult one, and a caption does not travel with a screenshot. It has to be true
standing alone, with no thread around it — which is the whole reason the
denominator matters here more than anywhere else.

**4 — alt text (113)**
```
Alt text: It carries the actual words of the clip, not a description, so a screen reader gets what the page says.
```

**5 — the avatar (288, link as a facet)**
```
This account's avatar is a clipping too: An ornate blackletter capital G from the nameplate of the Georgia Weekly Telegraph and Georgia Journal & Messenger, Macon, Feb. 23, 1875. The white pitting in the strokes is the microfilm, not a filter.

gahistoricnewspapers.galileo.usg.edu/lccn/…
```
→ facet target: `https://gahistoricnewspapers.galileo.usg.edu/lccn/sn85034222/1875-02-23/ed-1/seq-1/`

⚠️ **This post needs the link as a facet.** With the URL written out it is 309
characters. A facet stores the URI outside the text, so the visible form costs
45 characters rather than 75. Verified against live posts: the full URL does not
appear in `record.text` at all.

**6 — who runs it (269)**
```
Run by @stanfordc.bsky.social, not the Digital Library of Georgia: Born in Atlanta, I'm a graduate of the journalism school at UGA (@ugagrady.bsky.social). I've had a 30-year career in newspapers, starting at The Augusta Chronicle. Corrections are welcome and acted on.
```
✅ **Both handles were verified to resolve on 21 August 2026** via
`app.bsky.actor.getProfile`: `stanfordc.bsky.social` ("Chris Stanford") and
`ugagrady.bsky.social` ("UGA Grady College of Journalism and Mass
Communication"). Check again before posting rather than trusting this line — a
handle is an identifier, and this project has already put two reconstructed
LCCNs into sample posts.

⚠️ **Use the bare handle, never the profile URL.** The draft carried
`https://bsky.app/profile/ugagrady.bsky.social`, which pushed the post to 355 and
renders as a raw link. The handle costs 24 characters less, reaches the same
place and renders as a real mention.

⚠️ **Alt text and the biography were one post until 21 August 2026, and splitting
them is what made the rest fit.** Welded together they were 355 characters and
every version that fit required cutting the biography to a CV line. They are also
unrelated claims, and the alt text commitment was the weaker for sitting on top
of a résumé.

⚠️ **The thread ends here on purpose.** The last post is where the reader is
left, and "corrections are welcome and acted on" is the line someone replies to.
The alternative considered was ending on the avatar, whose facet link points back
into the archive and keeps the emphasis off the author — a real argument for an
account whose posture is deference to the archive, and rejected only because post
1 already hands the reader that link.

⚠️ **Keep post 3.** It is the least comfortable of the six and the one that
makes the account defensible, because it says the difficult thing before anyone
has to ask.

⚠️ **Six posts is longer than anyone reads.** What has to land — what this is,
how things are chosen, and why — is in the first three. Anything added later goes
at the tail, never in front of those.

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
