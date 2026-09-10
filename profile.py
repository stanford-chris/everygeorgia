#!/usr/bin/env python3
"""
profile.py -- the account text, as data. PROFILE.md holds the reasoning behind
every line; this file holds the lines. everygeorgia_post.py reads them for
--setup-profile and --launch, and the tests check them against Bluesky's
limits, so the text you read here is the text that goes out.

⚠️ Change PROFILE.md and this file together. The markdown is the record of
why; this is the record of what. They were one thing until 11 September 2026,
when the account went from proposed to being built and the text needed a
form a script could post.

⚠️ Post 5's date reads "23 February 1875" here and read "Feb. 23, 1875" in
PROFILE.md until 11 September 2026. Every daily post carries its date in UK
order (house style, and nameplate_crop.uk_date()), so an AP-style date in the
one pinned post that carries one would read as an error beside them. Changed
here and in PROFILE.md the same day; 290 characters.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

HANDLE = "georgianewspapers.bsky.social"
DISPLAY_NAME = "Georgia Newspaper Clippings"
AVATAR = os.path.join(HERE, "avatar", "avatar_G_dark_72.png")
GHN = "https://gahistoricnewspapers.galileo.usg.edu"

BIO = (
    # ⚠️ Chris's wording, set live on Bluesky on 11 September 2026 and read
    # back from the API here, so --setup-profile re-writes what he wrote.
    "A 🤖 posting clippings from Georgia's newspapers before 1931: Nameplates, "
    "advertisements, headlines, market reports. 🗞️\n\n"
    "From Georgia Historic Newspapers, presented online by the Digital Library "
    "of Georgia. Unofficial. Run by @stanfordc.bsky.social."
)

# Each post: text, plus the facets it needs. `links` are (visible text, url);
# `mentions` are handles, resolved to DIDs at post time and never stored,
# because a handle is an identifier and this project has already put two
# reconstructed LCCNs into sample posts. Post 1 is pinned; 2-6 thread under it.
THREAD = [
    {
        "text": (
            "What this is: Clippings from Georgia's newspapers before 1931 — "
            "nameplates, headlines, ads, market reports — with the name of the "
            "paper, the date and a link to the full issue.\n\n"
            "Everything comes from Georgia Historic Newspapers: "
            "gahistoricnewspapers.galileo.usg.edu"
        ),
        "links": [("gahistoricnewspapers.galileo.usg.edu", GHN + "/")],
        "mentions": [],
    },
    {
        "text": (
            "How things are chosen: Only from issues that the Digital Library of "
            "Georgia marks “No Copyright – United States” and only "
            "from a handful of categories that I've picked deliberately.\n\n"
            "Anything touching slavery, the Ku Klux Klan or racial violence I "
            "select and frame myself."
        ),
        "links": [],
        "mentions": [],
    },
    {
        "text": (
            "These posts are not representative of the archive: Roughly 160,000 "
            "of its pages mention lynching, and a bot drawing at random would "
            "eventually post something indefensible. This one doesn't draw at "
            "random."
        ),
        "links": [],
        "mentions": [],
    },
    {
        "text": (
            "Alt text: It carries the actual words of the clip, not a "
            "description, so a screen reader gets what the page says."
        ),
        "links": [],
        "mentions": [],
    },
    {
        "text": (
            "This account's avatar is a clipping too: An ornate blackletter "
            "capital G from the nameplate of the Georgia Weekly Telegraph and "
            "Georgia Journal & Messenger, Macon, 23 February 1875. The white "
            "pitting in the strokes is the microfilm, not a filter.\n\n"
            "gahistoricnewspapers.galileo.usg.edu/lccn/…"
        ),
        "links": [("gahistoricnewspapers.galileo.usg.edu/lccn/…",
                   GHN + "/lccn/sn85034222/1875-02-23/ed-1/seq-1/")],
        "mentions": [],
    },
    {
        "text": (
            "Run by @stanfordc.bsky.social, not the Digital Library of Georgia. "
            "Born in Atlanta, I'm a graduate of the journalism school at UGA "
            "(@ugagrady.bsky.social) and started my newspaper career at The Augusta "
            "Chronicle. Corrections welcome."
        ),
        "links": [],
        "mentions": ["stanfordc.bsky.social", "ugagrady.bsky.social"],
    },
]


def curly(s):
    """Straight marks to house style. The thread text above is typed with
    straight apostrophes for readability in source; it is curled once, here,
    and the test suite checks that nothing straight reaches the feed."""
    s = s.replace("’", "'")            # normalise, then curl once
    out = []
    for i, ch in enumerate(s):
        if ch == "'":
            prev = s[i - 1] if i else " "
            out.append("’" if prev.isalnum() or prev in ".,!?" else "‘")
        elif ch == '"':
            prev = s[i - 1] if i else " "
            out.append("”" if prev.isalnum() or prev in ".,!?" else "“")
        else:
            out.append(ch)
    return "".join(out)


def thread():
    """The six posts with their text curled, in order."""
    return [dict(p, text=curly(p["text"])) for p in THREAD]


def bio():
    return curly(BIO)


if __name__ == "__main__":
    b = bio()
    print(f"bio [{len(b)}/256]\n{b}\n")
    for i, p in enumerate(thread(), 1):
        print(f"--- {i}/{len(THREAD)}  [{len(p['text'])}/300]"
              f"{'  ⚠️ OVER' if len(p['text']) > 300 else ''}")
        print(p["text"] + "\n")
