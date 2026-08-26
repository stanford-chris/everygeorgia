#!/usr/bin/env python3
"""
ghn_api.py -- shared client for Georgia Historic Newspapers (Open ONI) and the
UGA IIIF image server. Read-only: it fetches, caches and computes geometry.
Nothing here posts, and nothing here should ever learn how.

Three endpoints, and only these:

  manifest      /lccn/<lccn>/<date>/ed-<n>.json   -- IIIF Presentation manifest.
                One canvas per page, carrying that page's pixel size and the
                IIIF Image API service for it.
  coordinates   /lccn/.../seq-<n>/coordinates/    -- word-level OCR boxes.
  IIIF image    iiif-ha.galib.uga.edu/iiif/2/...  -- arbitrary region crops.

⚠️⚠️ THE OCR COORDINATE SPACE IS NOT THE IMAGE SPACE, and this is the trap that
will produce a plausible wrong crop rather than an error. The coordinates
endpoint reports its own `width`/`height` -- 796 x 1190 on the page measured
21 August 2026 -- while the same page's image is 3080 x 4607, a factor of
3.869. Feeding an OCR box straight to IIIF as a region crops a postage stamp
from the top-left corner and returns it with HTTP 200. Always scale through
`Page.to_image()`.

⚠️ THE MANIFEST LIES ABOUT THE IIIF PROFILE. Each canvas's inline
`service.profile` reads `level0`, which would mean no arbitrary regions at all.
The server's own `info.json` reports **level2** with `regionByPct`,
`sizeByConfinedWh` and the rest, and an arbitrary region crop demonstrably
works (verified 26 August 2026 against sn89053135, 1898-01-06). Trust
info.json; do not "fix" this code to respect the manifest's claim.

⚠️ Carry identifiers through; never reconstruct them. The IIIF service id
embeds a batch path (`batch_gu_abbevillechronicle01_ver01/data/.../0001.jp2`)
that cannot be derived from the LCCN and date. Read it off the canvas. Guessing
identifiers has already put two wrong links into this project's sample posts.

⚠️ A curl 200 is not arrival. Turnstile serves its challenge with status 200,
so every response is checked for being actual JSON/JPEG and the effective URL
is compared against the requested host.

⚠️ Requests are cached under data/cache/ and paced. GHN is a public archive run
by the institution this project has an unanswered permission request with; it
is not a service to hammer. See [[reference_curl_200_is_not_arrival]].
"""
import json
import os
import re
import subprocess
import time
from urllib.parse import quote, unquote, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "cache")
BASE = "https://gahistoricnewspapers.galileo.usg.edu"
IIIF_HOST = "iiif-ha.galib.uga.edu"
UA = ("everygeorgia/0.1 (crop research, unpublished; "
      "contact stanfordc+claude@mac.com)")
PAUSE = 0.4
TIMEOUT = 60

LCCN_RE = re.compile(r"^[a-z]{2}\d{8,10}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FetchError(RuntimeError):
    """A request that could not be completed or could not be trusted."""


def _slug(url):
    return re.sub(r"[^A-Za-z0-9]+", "_", url)[-160:]


def _curl(url, binary=False, tries=4):
    """One fetch, with backoff. Returns bytes.

    ⚠️ Checks `url_effective`: a redirect to another host means a challenge or
    an error page, and those arrive with status 200."""
    last = None
    for i in range(tries):
        try:
            r = subprocess.run(
                ["curl", "-sS", "--compressed", "-A", UA, "-L",
                 "--max-time", str(TIMEOUT),
                 "-w", "\n%{http_code} %{url_effective}", url],
                check=True, capture_output=True)
            body, _, tail = r.stdout.rpartition(b"\n")
            code, _, eff = tail.decode("utf-8", "replace").partition(" ")
            if code != "200":
                raise FetchError(f"HTTP {code} for {url}")
            if urlsplit(eff).netloc != urlsplit(url).netloc:
                raise FetchError(f"redirected off-host to {eff!r} (challenge?)")
            if not binary and b"currently unavailable" in body[:200]:
                raise FetchError("service reports itself unavailable")
            return body
        except (subprocess.CalledProcessError, FetchError) as e:
            last = e
            if i < tries - 1:
                time.sleep(min(30, 3 * (2 ** i)))
    raise FetchError(f"{url}: {last}")


def fetch(url, binary=False):
    """Cached fetch. JSON is parsed; binary is returned as bytes."""
    path = os.path.join(CACHE, _slug(url) + (".bin" if binary else ".json"))
    if os.path.exists(path):
        with open(path, "rb") as f:
            body = f.read()
        if not binary:
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                pass                      # fall through and refetch
        else:
            return body
    body = _curl(url, binary=binary)
    if not binary:
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            raise FetchError(f"{url}: not JSON ({e})") from e
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "wb") as f:
        f.write(body)
    time.sleep(PAUSE)
    return body if binary else data


def check_ident(lccn, date):
    """⚠️ Refuse a malformed identifier rather than requesting it. A bad LCCN
    returns GHN's own 404 page, and a bad date silently returns nothing
    useful."""
    if not LCCN_RE.match(lccn or ""):
        raise ValueError(f"not an LCCN: {lccn!r}")
    if not DATE_RE.match(date or ""):
        raise ValueError(f"not an ISO date: {date!r}")


class Page:
    """One page of one issue: its image geometry and its OCR geometry.

    `scale` converts OCR coordinate space to image pixel space. It is derived
    from the two reported widths, never assumed to be 1 and never hardcoded."""

    def __init__(self, lccn, date, ed, seq, image_w, image_h, service):
        self.lccn, self.date, self.ed, self.seq = lccn, date, ed, seq
        self.image_w, self.image_h = image_w, image_h
        self.service = service
        self._coords = None

    def __repr__(self):
        return f"<Page {self.lccn} {self.date} ed-{self.ed} seq-{self.seq}>"

    @property
    def url(self):
        return f"{BASE}/lccn/{self.lccn}/{self.date}/ed-{self.ed}/seq-{self.seq}/"

    def coords(self):
        """{'width', 'height', 'words': [(x, y, w, h, text), ...]} in OCR space.

        ⚠️ Word keys are not unique positions: one key carries every occurrence
        of that word on the page, so the boxes must be flattened out."""
        if self._coords is None:
            d = fetch(f"{BASE}/lccn/{self.lccn}/{self.date}/"
                      f"ed-{self.ed}/seq-{self.seq}/coordinates/")
            words = []
            for text, boxes in (d.get("coords") or {}).items():
                for b in boxes:
                    try:
                        x, y, w, h = (int(v) for v in b[:4])
                    except (TypeError, ValueError):
                        continue
                    words.append((x, y, w, h, text))
            self._coords = {
                "width": int(d.get("width") or 0),
                "height": int(d.get("height") or 0),
                "words": words,
            }
        return self._coords

    @property
    def scale(self):
        """image pixels per OCR unit. Raises rather than guessing."""
        cw = self.coords()["width"]
        if not cw or not self.image_w:
            raise FetchError(f"{self!r}: cannot scale, widths {cw}/{self.image_w}")
        return self.image_w / cw

    def to_image(self, box):
        """An (x, y, w, h) box in OCR space -> the same box in image pixels,
        clamped to the page. This is the only sanctioned way to build a crop."""
        s = self.scale
        x, y, w, h = box
        x0 = max(0, int(round(x * s)))
        y0 = max(0, int(round(y * s)))
        x1 = min(self.image_w, int(round((x + w) * s)))
        y1 = min(self.image_h, int(round((y + h) * s)))
        if x1 <= x0 or y1 <= y0:
            raise ValueError(f"empty box after scaling: {box}")
        return (x0, y0, x1 - x0, y1 - y0)

    def crop_url(self, image_box, width=1200, fmt="jpg"):
        """IIIF region URL. `image_box` must already be in IMAGE space -- pass
        it through to_image() first."""
        x, y, w, h = image_box
        return (f"https://{IIIF_HOST}/iiif/2/{quote(self.service_path, safe='')}"
                f"/{x},{y},{w},{h}/{width},/0/default.{fmt}")

    @property
    def service_path(self):
        """The identifier portion of the IIIF service id, un-escaped once so it
        can be re-quoted safely."""
        marker = "/iiif/2/"
        i = self.service.find(marker)
        if i < 0:
            raise FetchError(f"{self!r}: unrecognised IIIF service {self.service!r}")
        return unquote(self.service[i + len(marker):])

    def fetch_crop(self, image_box, width=1200):
        return fetch(self.crop_url(image_box, width), binary=True)


def issue_pages(lccn, date, ed=1):
    """Every page of one issue, as Page objects, read from its IIIF manifest.

    ⚠️ "Issue" and "edition" are different units. DLG marks rights on ISSUES;
    an edition sits inside one. `ed` defaults to 1 because nearly every title
    here printed once a day, but it is a parameter, not an assumption."""
    check_ident(lccn, date)
    m = fetch(f"{BASE}/lccn/{lccn}/{date}/ed-{ed}.json")
    try:
        canvases = m["sequences"][0]["canvases"]
    except (KeyError, IndexError) as e:
        raise FetchError(f"{lccn} {date}: no canvases in manifest") from e
    pages = []
    for i, c in enumerate(canvases, start=1):
        try:
            service = c["images"][0]["resource"]["service"]["@id"]
        except (KeyError, IndexError):
            continue
        pages.append(Page(lccn, date, ed, i,
                          int(c["width"]), int(c["height"]), service))
    if not pages:
        raise FetchError(f"{lccn} {date}: manifest carried no usable pages")
    return pages


def front_page(lccn, date, ed=1):
    """seq-1. `sequence=1` is what the search API calls a front page too."""
    return issue_pages(lccn, date, ed)[0]
