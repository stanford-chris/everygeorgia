#!/usr/bin/env python3
"""
georgia_roster.py — build the roster of Georgia newspaper titles from Georgia
Historic Newspapers, for a bot that posts one paper's nameplate at a time.

GHN carries 1,164 titles across 157 of Georgia's 159 counties. `newspapers.json`
lists all of them but gives only a label and an LCCN, so this fills in the town,
county, years, frequency and publisher that a post needs, and records which
issues may lawfully be published.

  titles    /newspapers.json, one request, the authoritative list of what exists.
  detail    One page-search per title (`rows=1&lccn=...`) rather than the title
            JSON, because the search document carries place_of_publication,
            county, city, start_year, end_year, frequency and publisher in a
            single response, where the IIIF title JSON carries only a label and
            the issue manifests.
  rights    Batched against the Digital Library of Georgia API, which assigns a
            rightsstatements.org URI per issue. GHN's own API has no rights data
            at all.

Three things about this are load-bearing:

  ⚠️ Rights are NOT a date rule, and must not be turned into one. Measured
  21 Aug 2026: "No Copyright - United States" runs to 1928 while "In Copyright"
  begins in 1924, so the 1920s overlap and are decided title by title. Any
  cutoff year invented here would be a guess overriding DLG's own item-level
  determination.

  ⚠️ DLG does not hold every issue. It has 371,998 GHN records against 518,801
  issues in GHN itself, so roughly 28% carry no rights statement. Those are
  recorded as `unknown`, never as safe. A title whose sampled issues are all
  unknown gets `rights_status=unknown` and must stay out of any automatic lane.

  ⚠️ The DLG record id is `dlg_ghn_<lccn>-<date>-ed-<n>` and is built here from
  GHN's own ids, never typed by hand. Guessing identifiers put two wrong links
  into sample posts on 21 Aug 2026.

Responses are cached under data/titles/, so re-running costs no requests.

Usage:
    python3 georgia_roster.py                 # build and write the csv
    python3 georgia_roster.py --refetch       # ignore the cache
    python3 georgia_roster.py --stdout        # report only, write nothing
    python3 georgia_roster.py --limit=50      # first N titles, for a dry run
"""
import csv, json, os, subprocess, sys, time

BASE = "https://gahistoricnewspapers.galileo.usg.edu"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "titles")
OUT = os.path.join(HERE, "data", "georgia_roster.csv")
UA = ("everygeorgia-roster/0.1 (one-off roster build; "
      "contact stanfordc+claude@mac.com)")
PAUSE = 0.35            # polite spacing; the whole run is ~1,200 requests

FIELDS = ["lccn", "title", "city", "county", "place_of_publication",
          "start_year", "end_year", "frequency", "publisher", "language"]


def fetch(url, tries=3):
    """GET JSON with retries. The GHN API returns intermittent 500s."""
    last = None
    for i in range(tries):
        try:
            r = subprocess.run(
                ["curl", "-sS", "--compressed", "-A", UA, "-L",
                 "--max-time", "90", url],
                check=True, capture_output=True)
            return json.loads(r.stdout)
        except Exception as e:                      # noqa: BLE001
            last = e
            if i < tries - 1:
                time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{url[:110]} -> {type(last).__name__}")


def cached(name, url, refetch=False):
    path = os.path.join(CACHE, name)
    if not refetch and os.path.exists(path):
        try:
            return json.load(open(path))
        except json.JSONDecodeError:
            pass
    d = fetch(url)
    os.makedirs(CACHE, exist_ok=True)
    json.dump(d, open(path, "w"))
    time.sleep(PAUSE)
    return d


def titles(refetch=False):
    d = cached("_newspapers.json", f"{BASE}/newspapers.json", refetch)
    out = []
    for c in d.get("collections", []):
        lccn = c["@id"].rstrip(".json").rsplit("/", 1)[-1]
        out.append((lccn, c.get("label", "")))
    return out


def detail(lccn, refetch=False):
    """One page-search carries every descriptive field the roster needs."""
    url = (f"{BASE}/search/pages/results/?format=json&rows=1&andtext="
           f"&lccn={lccn}")
    d = cached(f"{lccn}.json", url, refetch)
    items = d.get("items") or []
    if not items:
        return None
    it = items[0]
    first = lambda k: (it.get(k) or [""])[0] if isinstance(it.get(k), list) else (it.get(k) or "")
    return dict(
        lccn=lccn,
        title=it.get("title", ""),
        city=first("city"),
        county=first("county"),
        place_of_publication=it.get("place_of_publication", ""),
        start_year=it.get("start_year", ""),
        end_year=it.get("end_year", ""),
        frequency=it.get("frequency", ""),
        publisher=it.get("publisher", ""),
        language=first("language"),
    )


def main():
    args = sys.argv[1:]
    refetch = "--refetch" in args
    stdout = "--stdout" in args
    limit = next((int(a.split("=", 1)[1]) for a in args if a.startswith("--limit=")), None)
    for a in args:
        if a not in ("--refetch", "--stdout") and not a.startswith("--limit="):
            sys.exit(f"unknown argument: {a}")

    ts = titles(refetch)
    if limit:
        ts = ts[:limit]
    print(f"titles listed: {len(ts)}", file=sys.stderr)

    rows, failed = [], []
    for i, (lccn, label) in enumerate(ts, 1):
        try:
            d = detail(lccn, refetch)
        except RuntimeError as e:
            failed.append((lccn, label, str(e)[:60])); continue
        if not d:
            failed.append((lccn, label, "no pages indexed")); continue
        if not d["title"]:
            d["title"] = label
        rows.append(d)
        if i % 100 == 0:
            print(f"  {i}/{len(ts)}  ok={len(rows)} failed={len(failed)}", file=sys.stderr)

    print(f"\nresolved {len(rows)} of {len(ts)}; {len(failed)} unresolved", file=sys.stderr)
    for lccn, label, why in failed[:15]:
        print(f"   {lccn:14} {label[:40]:42} {why}", file=sys.stderr)

    if stdout:
        w = csv.DictWriter(sys.stdout, fieldnames=FIELDS)
        w.writeheader(); w.writerows(rows)
        return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader(); w.writerows(rows)
    print(f"wrote {OUT} ({len(rows)} rows)", file=sys.stderr)


if __name__ == "__main__":
    main()
