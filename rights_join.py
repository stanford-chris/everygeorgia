#!/usr/bin/env python3
"""
rights_join.py — join the GHN title roster against the Digital Library of
Georgia's per-issue rights statements, to find which titles have an issue that
may lawfully be published.

GHN's own API carries no rights data at all. DLG's does: every GHN issue it
holds gets a rightsstatements.org URI. Of 371,998 GHN records in DLG,
271,937 are "No Copyright - United States" (NoC-US), and those are the only
ones this project will draw on.

  paginate  DLG's search API, filtered to the GHN collection and NoC-US, 250
            records a page (its ceiling), 1,088 pages. Deep pagination was
            verified to page 1,088 before this was written.
  parse     Record ids are `dlg_ghn_<lccn>-<YYYY-MM-DD>-ed-<n>`, so the id
            alone yields the title, the issue date and the edition. No second
            request is needed to learn which paper a record belongs to.
  join      Aggregate per LCCN, then match against georgia_roster.csv.

Three things are load-bearing:

  ⚠️ A title absent from the NoC-US set is recorded as `none`, never as
  `unknown`, and the two are different. DLG holds 371,998 records against
  518,801 issues in GHN, so roughly 28% of issues have no rights statement at
  all. A title can therefore have issues in GHN, no NoC-US record here, and
  still be perfectly publishable — we simply do not know. Neither state may be
  treated as permission.

  ⚠️ Rights are not a date rule. NoC-US runs to 1928 while "In Copyright"
  begins in 1924, so the 1920s overlap and are decided title by title. Do not
  replace this join with a cutoff year.

  ⚠️ Pages are cached under data/rights/. Deleting that directory costs another
  1,088 requests against a public archive, so delete it deliberately.

Usage:
    python3 rights_join.py                 # paginate, join, write the csv
    python3 rights_join.py --stdout        # report only, write nothing
    python3 rights_join.py --pages=20      # first N pages, for a dry run
"""
import csv, json, os, re, subprocess, sys, time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "rights")
ROSTER = os.path.join(HERE, "data", "georgia_roster.csv")
OUT = os.path.join(HERE, "data", "georgia_rights.csv")
UA = ("everygeorgia-roster/0.1 (one-off rights join; "
      "contact stanfordc+claude@mac.com)")
NOC = "http%3A%2F%2Frightsstatements.org%2Fvocab%2FNoC-US%2F1.0%2F"
GHN = "Georgia+Historic+Newspapers"
URL = ("https://dlg.usg.edu/records.json?per_page=250&page={p}"
       "&f%5Bcollection_titles_sms%5D%5B%5D=" + GHN +
       "&f%5Brights_facet%5D%5B%5D=" + NOC)
ID_RE = re.compile(r"^dlg_ghn_(.+?)-(\d{4}-\d{2}-\d{2})-ed-(\d+)$")
PAUSE = 0.25


def fetch(url, tries=6):
    """⚠️ DLG returns a plain-text 503 ("currently unavailable") under load,
    not JSON and not an HTTP error curl will flag. Observed repeatedly on
    21 Aug 2026. Back off generously rather than treating it as a hard failure:
    a 1,088-page run will meet it more than once."""
    last = None
    for i in range(tries):
        try:
            r = subprocess.run(["curl", "-sS", "--compressed", "-A", UA, "-L",
                                "--max-time", "150", url],
                               check=True, capture_output=True)
            body = r.stdout
            if b"currently unavailable" in body[:200]:
                raise RuntimeError("503 unavailable")
            return json.loads(body)
        except Exception as e:                       # noqa: BLE001
            last = e
            if i < tries - 1:
                time.sleep(min(60, 5 * (2 ** i)))
    raise RuntimeError(f"page fetch failed: {type(last).__name__}")


def page(p):
    path = os.path.join(CACHE, f"p{p:05d}.json")
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except json.JSONDecodeError:
            pass
    d = fetch(URL.format(p=p))
    os.makedirs(CACHE, exist_ok=True)
    json.dump(d, open(path, "w"))
    time.sleep(PAUSE)
    return d


def main():
    args = sys.argv[1:]
    stdout = "--stdout" in args
    cap = next((int(a.split("=", 1)[1]) for a in args if a.startswith("--pages=")), None)
    for a in args:
        if a != "--stdout" and not a.startswith("--pages="):
            sys.exit(f"unknown argument: {a}")

    # ⚠️ Do not grind against a struggling service. On 21 Aug 2026 DLG was
    # returning 503 on roughly three requests in four, and this job makes 1,088
    # of them. Probe first, and refuse to start rather than add to the load --
    # the whole point of the permission email was that we would not be part of
    # that problem. Cached pages mean a later run resumes for free.
    bad = 0
    for _ in range(6):
        try:
            page(1); break
        except RuntimeError:
            bad += 1
    if bad >= 6:
        sys.exit("DLG is refusing requests (503). Nothing fetched; re-run later "
                 "-- cached pages make a resumed run free.")
    first = page(1)
    total = first["response"]["pages"]["total_count"]
    npages = (total + 249) // 250
    if cap:
        npages = min(npages, cap)
    print(f"NoC-US GHN records: {total} across {npages} pages", file=sys.stderr)

    per = defaultdict(list)
    unparsed = 0
    for p in range(1, npages + 1):
        try:
            d = page(p)
        except RuntimeError as e:
            print(f"  page {p}: {e}", file=sys.stderr); continue
        for doc in d["response"]["docs"]:
            m = ID_RE.match(doc["id"])
            if not m:
                unparsed += 1; continue
            lccn, date, ed = m.groups()
            per[lccn].append((date, int(ed)))
        if p % 100 == 0:
            print(f"  {p}/{npages} pages, {len(per)} titles so far", file=sys.stderr)

    print(f"\ntitles with NoC-US issues: {len(per)}   unparsed ids: {unparsed}",
          file=sys.stderr)

    roster = {r["lccn"]: r for r in csv.DictReader(open(ROSTER))}
    rows = []
    for lccn, r in roster.items():
        iss = sorted(per.get(lccn, []))
        rows.append(dict(
            lccn=lccn, title=r["title"], city=r["city"], county=r["county"],
            start_year=r["start_year"], end_year=r["end_year"],
            noc_issues=len(iss),
            noc_first=iss[0][0] if iss else "",
            noc_last=iss[-1][0] if iss else "",
            postable="yes" if iss else "no",
        ))
    orphans = set(per) - set(roster)

    ok = sum(1 for r in rows if r["postable"] == "yes")
    print(f"roster titles: {len(rows)}   postable: {ok}   "
          f"no NoC-US record: {len(rows)-ok}", file=sys.stderr)
    print(f"NoC-US LCCNs not in the roster: {len(orphans)}", file=sys.stderr)

    flds = list(rows[0].keys())
    if stdout:
        w = csv.DictWriter(sys.stdout, fieldnames=flds); w.writeheader(); w.writerows(rows)
        return
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=flds); w.writeheader(); w.writerows(rows)
    print(f"wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
