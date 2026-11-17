"""DOI verification pass for the manuscript bibliography -- run BEFORE a reference is cited.

For every entry: does the DOI resolve at doi.org, and do Crossref and OpenAlex both
return a record whose title, authors and year match what we claim? Anything that does
not verify is flagged, never silently accepted.

Input: a BibTeX file (.bib) or a CSV with columns key,doi,title,authors,year
(authors separated by ' and ', each "Family, Given" or "Given Family").

    python -m src.verify_refs refs.bib
    python -m src.verify_refs refs.csv --out results/refcheck.csv

Exit status 1 if any entry FAILs, so it can gate a build.

Privacy: requests carry a generic User-Agent and no personal details. Crossref's
"polite pool" asks for a contact address; set CROSSREF_MAILTO yourself if you want
that -- nothing is filled in by default.

Verdicts:
  VERIFIED  resolves; both sources agree on title, first author and year
  WARN      verifies, but something needs a human look (near-miss title, year differs
            only between online and print dates, one source unreachable, author list
            partially matched)
  FAIL      does not resolve, unknown to Crossref, title/first-author/year mismatch,
            retracted, duplicate DOI, or no DOI given
"""
import argparse
import csv
import difflib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

UA = "reference-verifier/1.0 (python-urllib)"
if os.environ.get("CROSSREF_MAILTO"):
    UA += f" (mailto:{os.environ['CROSSREF_MAILTO']})"
TITLE_OK, TITLE_WARN = 0.95, 0.85


# ---------------------------------------------------------------- input parsing
def parse_bib(text):
    out = []
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        if m.group(1).lower() in ("comment", "string", "preamble"):
            continue
        i, depth = m.end(), 1
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        body = text[m.end():i - 1]
        fields = {}
        for fm in re.finditer(r"(\w+)\s*=\s*", body):
            j = fm.end()
            if j < len(body) and body[j] == "{":
                d, k = 1, j + 1
                while k < len(body) and d:
                    d += {"{": 1, "}": -1}.get(body[k], 0)
                    k += 1
                val = body[j + 1:k - 1]
            elif j < len(body) and body[j] == '"':
                k = body.index('"', j + 1)
                val = body[j + 1:k]
            else:
                val = re.match(r"[^,\n]*", body[j:]).group(0)
            fields.setdefault(fm.group(1).lower(), val.strip())
        out.append(dict(key=m.group(2), doi=fields.get("doi", ""), title=fields.get("title", ""),
                        authors=fields.get("author", ""), year=fields.get("year", "")))
    return out


def load(path):
    if path.lower().endswith(".bib"):
        return parse_bib(open(path, encoding="utf-8").read())
    return [dict(key=r.get("key", ""), doi=r.get("doi", ""), title=r.get("title", ""),
                 authors=r.get("authors", ""), year=r.get("year", ""))
            for r in csv.DictReader(open(path, newline="", encoding="utf-8"))]


# ---------------------------------------------------------------- normalisation
def clean_doi(d):
    d = d.strip()
    d = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", d, flags=re.I)
    return d.lower()


def norm(s):
    s = re.sub(r"\\[`'^\"~=.]", "", s or "")               # LaTeX accents: \` \' \^ \" ...
    s = re.sub(r"\\[uvHcdbtk](?=[\s{])\s*", "", s)          # letter accents: \v{c}, \c c
    s = re.sub(r"\\(ss|ae|oe|aa|o|l)\b", r"\1", s, flags=re.I)  # \ss \o \l -> ss o l
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s)                    # any other command
    s = unicodedata.normalize("NFKD", s.replace("{", "").replace("}", ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"<[^>]+>", " ", s)                          # JATS tags in Crossref titles
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def families(authors):
    fam = []
    for a in re.split(r"\s+and\s+", authors or ""):
        a = a.strip()
        if not a or a.lower() in ("others", "et al", "et al."):
            continue
        fam.append(norm(a.split(",")[0] if "," in a else a.split()[-1]))
    return fam


def family_of(display_name):
    toks = norm(display_name).split()
    return toks[-1] if toks else ""


# ---------------------------------------------------------------- network
def fetch(url, method="GET", tries=3, timeout=30):
    last = None
    for k in range(tries):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            opener = urllib.request.build_opener(NoRedirect) if method == "HEAD" else \
                urllib.request.build_opener()
            with opener.open(req, timeout=timeout) as r:
                return r.status, (r.read() if method == "GET" else b"")
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308, 404, 410):
                return e.code, b""
            last = f"HTTP {e.code}"
        except Exception as e:                                 # timeouts, DNS, resets
            last = type(e).__name__
        time.sleep(1.5 * (k + 1))
    return None, last


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def crossref(doi):
    st, body = fetch("https://api.crossref.org/works/" + urllib.parse.quote(doi))
    if st != 200:
        return None, st if st else body
    m = json.loads(body)["message"]
    years = {}
    for k in ("issued", "published-print", "published-online", "published"):
        dp = (m.get(k) or {}).get("date-parts") or [[None]]
        if dp[0] and dp[0][0]:
            years[k] = int(dp[0][0])
    return dict(title=(m.get("title") or [""])[0],
                fams=[norm(a.get("family", a.get("name", ""))) for a in m.get("author", [])],
                years=years, venue=(m.get("container-title") or [""])[0],
                type=m.get("type", ""),
                retraction=any(u.get("type") in ("retraction", "removal")
                               for u in m.get("updated-by", []) or [])), None


def openalex(doi):
    st, body = fetch("https://api.openalex.org/works/doi:" + urllib.parse.quote(doi))
    if st != 200:
        return None, st if st else body
    m = json.loads(body)
    return dict(title=m.get("title") or "",
                fams=[family_of(a["author"]["display_name"]) for a in m.get("authorships", [])],
                year=m.get("publication_year"), retracted=bool(m.get("is_retracted"))), None


# ---------------------------------------------------------------- the check
def check(ref, seen):
    flags, fails = [], []
    doi = clean_doi(ref["doi"])
    if not doi:
        return "FAIL", ["no DOI given -- cannot be verified by this pass"], {}
    if doi in seen:
        fails.append(f"duplicate DOI (also {seen[doi]})")
    seen.setdefault(doi, ref["key"])

    st, _ = fetch("https://doi.org/" + urllib.parse.quote(doi), method="HEAD")
    if st in (301, 302, 303, 307, 308):
        pass
    elif st in (404, 410):
        fails.append(f"doi.org: DOI does not resolve (HTTP {st})")
    else:
        flags.append(f"doi.org unreachable ({st or _})")

    cr, cr_err = crossref(doi)
    oa, oa_err = openalex(doi)
    if cr is None:
        (fails if cr_err == 404 else flags).append(
            "Crossref: DOI unknown (404)" if cr_err == 404 else f"Crossref unreachable ({cr_err})")
    if oa is None:
        flags.append("OpenAlex: DOI unknown (404)" if oa_err == 404 else
                     f"OpenAlex unreachable ({oa_err})")
    if cr is None and oa is None:
        fails.append("neither Crossref nor OpenAlex returned a record")
        return "FAIL", fails + flags, {}

    given_t, given_f, given_y = norm(ref["title"]), families(ref["authors"]), ref["year"].strip()
    got = {}
    for src, rec in (("Crossref", cr), ("OpenAlex", oa)):
        if rec is None:
            continue
        r = difflib.SequenceMatcher(None, given_t, norm(rec["title"])).ratio() if given_t else 0
        got[f"{src}_title"] = rec["title"]
        got[f"{src}_title_ratio"] = f"{r:.3f}"
        if not given_t:
            flags.append("no title given to compare")
        elif r < TITLE_WARN:
            fails.append(f"{src} title mismatch ({r:.2f}): \"{rec['title']}\"")
        elif r < TITLE_OK:
            flags.append(f"{src} title near-miss ({r:.2f}): \"{rec['title']}\"")
        if given_f and rec["fams"]:
            if given_f[0] != rec["fams"][0]:
                fails.append(f"{src} first author is '{rec['fams'][0]}', given '{given_f[0]}'")
            missing = [f for f in given_f if f not in rec["fams"]]
            if missing:
                flags.append(f"{src}: given authors not found: {', '.join(missing)}")
            if len(given_f) < len(rec["fams"]) and "others" not in ref["authors"].lower():
                flags.append(f"{src} lists {len(rec['fams'])} authors, {len(given_f)} given")
        elif not given_f:
            flags.append("no authors given to compare")

    if given_y:
        y = int(given_y)
        cr_years = set(cr["years"].values()) if cr else set()
        oa_year = oa["year"] if oa else None
        if cr:
            got["Crossref_years"] = cr["years"]
        if oa_year:
            got["OpenAlex_year"] = oa_year
        if y not in cr_years and y != oa_year:
            fails.append(f"year {y} matches no source: Crossref {cr['years'] if cr else 'n/a'}, "
                         f"OpenAlex {oa_year}")
        else:
            if cr and y != cr["years"].get("issued"):
                flags.append(f"year {y} is not Crossref's 'issued' year {cr['years']}"
                             + (f"; it matches OpenAlex ({oa_year}), typically the online-first "
                                f"year -- IEEE style cites the issue year" if y == oa_year else ""))
            if oa_year and y != oa_year:
                flags.append(f"OpenAlex year {oa_year}, given {y} (sources disagree; "
                             f"usually online-first vs print)")
    else:
        flags.append("no year given to compare")

    if (cr and cr["retraction"]) or (oa and oa["retracted"]):
        fails.append("RETRACTED according to " +
                     " and ".join(s for s, f in (("Crossref", cr and cr["retraction"]),
                                                 ("OpenAlex", oa and oa["retracted"])) if f))
    if cr:
        got["venue"], got["type"] = cr["venue"], cr["type"]
    return ("FAIL" if fails else "WARN" if flags else "VERIFIED"), fails + flags, got


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("refs")
    ap.add_argument("--out", help="CSV report path")
    a = ap.parse_args()
    refs = load(a.refs)
    seen, rows = {}, []
    for ref in refs:
        verdict, notes, got = check(ref, seen)
        rows.append(dict(key=ref["key"], doi=ref["doi"], verdict=verdict,
                         notes=" | ".join(notes), **{k: str(v) for k, v in got.items()}))
        print(f"{verdict:9s} {ref['key']}  {ref['doi']}")
        for n in notes:
            print(f"          - {n}")
        time.sleep(0.2)
    n = {v: sum(r["verdict"] == v for r in rows) for v in ("VERIFIED", "WARN", "FAIL")}
    print(f"\n{len(rows)} references: {n['VERIFIED']} verified, {n['WARN']} warn, {n['FAIL']} FAIL")
    if a.out:
        cols = sorted({k for r in rows for k in r}, key=lambda k: (k not in
                      ("key", "doi", "verdict", "notes"), k))
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"report: {a.out}")
    return 1 if n["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
