"""Rebuild and validate the travel eSIM coverage dataset.

    uv run scripts/build.py           # fetch the live catalogue, rebuild data/, docs/index.html and the README stats
    uv run scripts/build.py --source plans.json   # rebuild from a saved copy of the feed
    uv run scripts/build.py --check   # validate what is committed (CI): schema, CSV = JSON, page lists every country

Source: eSIMology's public plans feed (https://esimology.com/plans.json). Only coverage facts are kept:
country, operator names and network types. Prices and plan details are left out.
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
FEED = "https://esimology.com/plans.json"
SITE = "https://esimology.com"
PAGES = "https://behoss.github.io/esim-coverage/"
REPO = "https://github.com/behoss/esim-coverage"
JSON_OUT = ROOT / "data" / "coverage.json"
CSV_OUT = ROOT / "data" / "coverage.csv"
HTML_OUT = ROOT / "docs" / "index.html"
SCHEMA = ROOT / "schema" / "coverage.schema.json"
README = ROOT / "README.md"
CSV_COLUMNS = ["iso2", "country", "operator", "network_types", "best_network", "esim_url"]
GEN = {"3G": 3, "4G": 4, "5G": 5}
# Codes the catalogue covers only through regional plans, so the feed carries no country name for them.
NAMES = {"AN": "Netherlands Antilles", "GL": "Greenland", "TL": "Timor-Leste", "TW": "Taiwan"}


def fetch(source: str | None) -> dict:
    if source:
        return json.loads(Path(source).read_text())
    req = urllib.request.Request(
        FEED, headers={"User-Agent": "esim-coverage-build/1.0 (+https://github.com/behoss/esim-coverage)"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def build(feed: dict) -> dict:
    names: dict[str, str] = dict(NAMES)
    pages: dict[str, str] = {}
    ops: dict[str, dict[str, dict]] = {}
    regions: dict[str, dict[str, str]] = {}
    for d in feed["destinations"]:
        if d["scope"] == "country" and len(d["countries"]) == 1:
            names[d["countries"][0]] = d["name"]
            pages[d["countries"][0]] = d["url"]
        for cc in d["countries"]:
            cc = cc.upper()
            if d["scope"] != "country":
                regions.setdefault(cc, {})[d["name"]] = d["url"]
            for o in d["networks"].get(cc, []):
                name = o["name"].strip()
                if not name:
                    continue
                slot = ops.setdefault(cc, {}).setdefault(name.lower(), {"name": name, "network_types": set()})
                slot["network_types"].update(t for t in o["types"] if t in GEN)
    # A single-country plan named after a region (Greenland) is its country page.
    for d in feed["destinations"]:
        if len(d["countries"]) == 1 and d["countries"][0] not in pages and d["name"] == names.get(d["countries"][0]):
            pages[d["countries"][0]] = d["url"]
            regions.get(d["countries"][0], {}).pop(d["name"], None)
    countries = []
    for cc in sorted(ops, key=lambda c: names.get(c, c)):
        operators = [
            {"name": o["name"], "network_types": sorted(o["network_types"], key=GEN.get)}
            for o in sorted(ops[cc].values(), key=lambda o: o["name"].lower())
            if o["network_types"]
        ]
        if not operators:
            continue
        countries.append(
            {
                "iso2": cc,
                "country": names.get(cc, cc),
                "best_network": max((t for o in operators for t in o["network_types"]), key=GEN.get),
                "operators": operators,
                "esim_url": pages.get(cc),
                "regional_plans": [{"name": n, "url": u} for n, u in sorted(regions.get(cc, {}).items())],
            }
        )
    return {
        "name": "Travel eSIM coverage by country",
        "updated": date.today().isoformat(),
        "licence": "CC-BY-4.0",
        "url": PAGES,
        "countries": countries,
    }


def to_csv(data: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for c in data["countries"]:
        for o in c["operators"]:
            w.writerow([c["iso2"], c["country"], o["name"], "/".join(o["network_types"]), c["best_network"], c["esim_url"] or ""])
    return buf.getvalue()


def stats(data: dict) -> dict:
    cs = data["countries"]
    return {
        "countries": len(cs),
        "operators": len({o["name"].lower() for c in cs for o in c["operators"]}),
        "rows": sum(len(c["operators"]) for c in cs),
        "five_g": sum(1 for c in cs if c["best_network"] == "5G"),
    }


def page(data: dict) -> str:
    s = stats(data)
    e = html.escape
    rows = []
    for c in data["countries"]:
        nets = "".join(
            f'<li>{e(o["name"])} <span class="t">{e(" / ".join(o["network_types"]))}</span></li>' for o in c["operators"]
        )
        link = (
            f'<a href="{e(c["esim_url"])}">{e(c["country"])} eSIM</a>'
            if c["esim_url"]
            else (
                f'<a href="{e(c["regional_plans"][0]["url"])}">{e(c["regional_plans"][0]["name"])} eSIM</a>'
                if c["regional_plans"]
                else ""
            )
        )
        rows.append(
            f'<tr data-g="{c["best_network"]}"><td><span class="cc">{c["iso2"]}</span> {e(c["country"])}</td>'
            f'<td><ul>{nets}</ul></td><td><span class="g g{c["best_network"][0]}">{c["best_network"]}</span></td><td>{link}</td></tr>'
        )
    ld = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": "Travel eSIM coverage by country",
        "description": (
            f"Which mobile networks a travel eSIM connects to in {s['countries']} countries and territories, "
            "with the network type (3G, 4G or 5G) for each operator. JSON and CSV, free to reuse."
        ),
        "url": PAGES,
        "sameAs": REPO,
        "keywords": ["travel eSIM", "eSIM coverage", "mobile networks by country", "5G coverage", "roaming", "open data"],
        "creator": {"@type": "Person", "name": "Bez", "url": "https://behoss.github.io"},
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "isAccessibleForFree": True,
        "dateModified": data["updated"],
        "spatialCoverage": "Worldwide",
        "variableMeasured": ["country ISO code", "country", "mobile network operator", "network type"],
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{PAGES}coverage.json"},
            {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"{PAGES}coverage.csv"},
        ],
    }
    title = f"Travel eSIM coverage by country: networks and 5G in {s['countries']} countries"
    desc = (
        f"Which mobile networks a travel eSIM uses in {s['countries']} countries, with 4G and 5G per operator. "
        "Free open data in CSV and JSON."
    )
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{PAGES}">
<meta name="color-scheme" content="light">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{PAGES}">
<meta property="og:type" content="website">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>
:root{{--ink:#0f172a;--mute:#475569;--line:#e2e8f0;--bg:#f8fafc;--brand:#0f766e;--brand2:#115e59;--soft:#ccfbf1}}
*{{box-sizing:border-box}}html{{color-scheme:light}}
body{{margin:0;font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:#fff}}
.w{{max-width:1200px;margin:0 auto;padding:0 20px}}
header{{background:linear-gradient(180deg,#f0fdfa,#fff);border-bottom:1px solid var(--line)}}
.top{{display:flex;justify-content:space-between;align-items:center;padding:16px 0;font-size:15px}}
.top a{{color:var(--mute);text-decoration:none}}.top a:hover{{color:var(--brand)}}
.hero{{padding:28px 0 36px}}
h1{{font-size:clamp(28px,4.4vw,46px);line-height:1.12;margin:0 0 14px;letter-spacing:-.02em}}
.lead{{font-size:19px;color:var(--mute);max-width:760px;margin:0 0 22px}}
.stats{{display:flex;flex-wrap:wrap;gap:12px;margin:0 0 24px;padding:0;list-style:none}}
.stats li{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 16px;min-width:150px}}
.stats b{{display:block;font-size:26px;line-height:1.1}}
.stats span{{color:var(--mute);font-size:14px}}
.cta{{display:flex;flex-wrap:wrap;gap:12px;align-items:center}}
.btn{{display:inline-block;background:var(--brand);color:#fff;text-decoration:none;font-weight:600;padding:13px 22px;border-radius:10px}}
.btn:hover{{background:var(--brand2)}}
.btn2{{display:inline-block;color:var(--brand);border:1px solid var(--brand);text-decoration:none;font-weight:600;padding:12px 20px;border-radius:10px}}
.btn2:hover{{background:var(--soft)}}
main{{padding:28px 0 40px}}
.bar{{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-bottom:14px}}
input[type=search]{{flex:1 1 280px;font:inherit;padding:12px 14px;border:1px solid #cbd5e1;border-radius:10px}}
input[type=search]:focus{{outline:2px solid var(--brand);border-color:var(--brand)}}
label.f{{display:flex;gap:8px;align-items:center;color:var(--mute)}}
#n{{color:var(--mute);font-size:14px}}
table{{width:100%;border-collapse:collapse;font-size:15px}}
th{{text-align:left;font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--mute);border-bottom:2px solid var(--line);padding:10px 8px}}
td{{border-bottom:1px solid var(--line);padding:10px 8px;vertical-align:top}}
tr:hover td{{background:var(--bg)}}
td ul{{margin:0;padding:0;list-style:none}}
.t{{color:var(--mute);font-size:13px}}
.cc{{display:inline-block;font:12px/1 ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--bg);border:1px solid var(--line);border-radius:5px;padding:3px 5px;margin-right:4px}}
.g{{font-weight:700;font-size:13px;padding:3px 8px;border-radius:999px}}.g5{{background:var(--soft);color:var(--brand2)}}.g4{{background:#e0e7ff;color:#3730a3}}.g3{{background:#f1f5f9;color:#475569}}
td a{{color:var(--brand);font-weight:600}}
section.about{{background:var(--bg);border-top:1px solid var(--line);padding:32px 0}}
section.about h2{{font-size:22px;margin:0 0 10px}}
section.about p,section.about li{{color:#334155;max-width:820px}}
code{{font:14px ui-monospace,SFMono-Regular,Menlo,monospace;background:#fff;border:1px solid var(--line);border-radius:5px;padding:1px 5px}}
footer{{padding:22px 0;color:var(--mute);font-size:14px;border-top:1px solid var(--line)}}
footer a{{color:var(--mute)}}
@media (max-width:640px){{
 .lead{{font-size:17px}} .stats li{{min-width:calc(50% - 6px);flex:1}} .stats b{{font-size:21px;white-space:nowrap}} .top{{font-size:14px;gap:12px}} .top span{{white-space:nowrap}}
 thead{{display:none}} table,tbody,tr,td{{display:block;width:100%}}
 tr{{border-bottom:1px solid var(--line);padding:10px 0}} td{{border:0;padding:3px 0}}
}}
</style>
</head>
<body>
<header>
<div class="w">
<nav class="top"><strong>eSIM coverage data</strong><span><a href="{REPO}">GitHub</a> · <a href="{SITE}">eSIMology</a></span></nav>
<div class="hero">
<h1>Travel eSIM coverage by country</h1>
<p class="lead">See which mobile networks a travel eSIM connects to in {s["countries"]} countries, and whether you get 4G or 5G. Search any country below, or download the full dataset in CSV or JSON.</p>
<ul class="stats">
<li><b>{s["countries"]}</b><span>countries and territories</span></li>
<li><b>{s["operators"]}</b><span>mobile networks</span></li>
<li><b>{s["five_g"]}</b><span>countries with 5G</span></li>
<li><b>{data["updated"]}</b><span>last updated</span></li>
</ul>
<div class="cta">
<a class="btn" href="{SITE}">Get a travel eSIM for 200+ countries from £3.99</a>
<a class="btn2" href="coverage.csv">Download CSV</a>
<a class="btn2" href="coverage.json">Download JSON</a>
</div>
</div>
</div>
</header>
<main class="w">
<div class="bar">
<input type="search" id="q" placeholder="Search a country or network, e.g. Japan, Vodafone" aria-label="Search countries and networks">
<label class="f"><input type="checkbox" id="g5"> 5G only</label>
<span id="n">{s["countries"]} countries</span>
</div>
<table>
<thead><tr><th>Country</th><th>Mobile networks</th><th>Best</th><th>Travel eSIM</th></tr></thead>
<tbody id="rows">
{chr(10).join(rows)}
</tbody>
</table>
</main>
<section class="about">
<div class="w">
<h2>About this data</h2>
<p>Each row is a country a travel eSIM covers, with every mobile network (operator) the eSIM can connect to there and the network types each one offers. The data comes from the live catalogue at <a href="{SITE}">eSIMology</a>, where every travel eSIM is delivered by email in about a minute.</p>
<ul>
<li><b>Files:</b> <a href="coverage.json">coverage.json</a> (one object per country) and <a href="coverage.csv">coverage.csv</a> (one row per country and network).</li>
<li><b>Columns:</b> <code>iso2</code>, <code>country</code>, <code>operator</code>, <code>network_types</code>, <code>best_network</code>, <code>esim_url</code>.</li>
<li><b>Licence:</b> data under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>; credit "eSIM coverage data by Bez, <a href="{SITE}">eSIMology</a>". Code under MIT.</li>
<li><b>Source code and schema:</b> <a href="{REPO}">github.com/behoss/esim-coverage</a>.</li>
</ul>
</div>
</section>
<footer><div class="w">Travel eSIM coverage data by <a href="https://behoss.github.io">Bez</a> · updated {data["updated"]} · <a href="{SITE}">eSIMology travel eSIMs</a></div></footer>
<script>
(function(){{var q=document.getElementById('q'),g=document.getElementById('g5'),n=document.getElementById('n'),rs=[].slice.call(document.querySelectorAll('#rows tr'));
var tx=rs.map(function(r){{return r.textContent.toLowerCase()}});
function f(){{var v=q.value.trim().toLowerCase(),o=g.checked,k=0;rs.forEach(function(r,i){{var s=(!v||tx[i].indexOf(v)>-1)&&(!o||r.dataset.g==='5G');r.hidden=!s;if(s)k++}});n.textContent=k+(k===1?' country':' countries')}}
q.addEventListener('input',f);g.addEventListener('change',f)}})();
</script>
</body>
</html>
"""


def validate(data: dict, csv_text: str, page_text: str) -> list[str]:
    errs = [
        f"{'/'.join(map(str, e.path))}: {e.message}"
        for e in Draft202012Validator(json.loads(SCHEMA.read_text()), format_checker=FormatChecker()).iter_errors(data)
    ]
    isos = [c["iso2"] for c in data.get("countries", [])]
    if len(isos) != len(set(isos)):
        errs.append("duplicate iso2 codes")
    if csv_text != to_csv(data):
        errs.append("data/coverage.csv does not match data/coverage.json (run scripts/build.py)")
    for c in data.get("countries", []):
        if f'<span class="cc">{c["iso2"]}</span>' not in page_text:
            errs.append(f"docs/index.html is missing {c['iso2']}")
    return errs


def write_readme(data: dict) -> None:
    s = stats(data)
    text = README.read_text()
    text = re.sub(
        r"<!-- stats -->.*?<!-- /stats -->",
        f"<!-- stats -->{s['countries']} countries and territories, {s['operators']} mobile networks, {s['rows']} country-network rows. Last updated: {data['updated']}.<!-- /stats -->",
        text,
        flags=re.DOTALL,
    )
    README.write_text(text)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="validate the committed files only")
    ap.add_argument("--source", help="read the feed from a local file instead of the live site")
    a = ap.parse_args()
    if a.check:
        data = json.loads(JSON_OUT.read_text())
        errs = validate(data, CSV_OUT.read_text(), HTML_OUT.read_text())
        if (ROOT / "docs" / "coverage.json").read_text() != JSON_OUT.read_text() or (
            ROOT / "docs" / "coverage.csv"
        ).read_text() != CSV_OUT.read_text():
            errs.append("docs/ copies differ from data/ (run scripts/build.py)")
    else:
        data = build(fetch(a.source))
        csv_text, page_text = to_csv(data), page(data)
        errs = validate(data, csv_text, page_text)
        if not errs:
            JSON_OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
            CSV_OUT.write_text(csv_text)
            HTML_OUT.write_text(page_text)
            (ROOT / "docs" / "coverage.json").write_text(JSON_OUT.read_text())
            (ROOT / "docs" / "coverage.csv").write_text(csv_text)
            write_readme(data)
    if errs:
        print(f"FAIL: {len(errs)} problem(s)", *errs[:20], sep="\n  ")
        return 1
    s = stats(data)
    print(
        f"OK: {s['countries']} countries, {s['operators']} networks, {s['rows']} rows, {s['five_g']} with 5G, updated {data['updated']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
