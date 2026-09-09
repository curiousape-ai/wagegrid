#!/usr/bin/env python3
"""Build the WageGrid static site from catalogs and the OEWS seed."""

from __future__ import annotations

import html
import json
import os
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog"
DATA = ROOT / "data"
SRC_STATIC = ROOT / "src" / "static"
DIST = ROOT / "dist"

SITE_NAME = "WageGrid"
SITE_URL = os.environ.get("WAGEGRID_SITE_URL", "https://wagegrid.pages.dev").rstrip("/")
PERIOD = "May 2025"
CITATION = (
    "U.S. Bureau of Labor Statistics, Occupational Employment and Wage Statistics, May 2025."
)
BLS_OES = "https://www.bls.gov/oes/"
BLS_TABLES = "https://www.bls.gov/oes/tables.htm"
KILL_RULE = (
    "14 days after the first indexable deploy: if Search Console shows no impressions "
    "and there is no money signal (AdSense / affiliate / lead), take the project down. "
    "Do not keep a dead slice online out of habit."
)

RELATED_GROUPS = (
    ("15-1252", "15-2051", "15-1254"),
    ("29-1141", "29-1292", "29-1123", "31-9092"),
    ("47-2111", "47-2152", "49-9021", "47-2031", "47-2061"),
    ("13-2011", "13-2051", "13-1111", "11-2021"),
    ("35-1011", "35-3011", "41-1011"),
    ("33-3051", "21-1021", "25-2021"),
    ("17-2051",),
    ("53-3032",),
    ("27-1024",),
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def money_hour(value: float | int | None) -> str:
    if value is None:
        return '<span class="blank" title="Not published by BLS">—</span>'
    return f"${value:,.2f}"


def money_year(value: float | int | None) -> str:
    if value is None:
        return '<span class="blank" title="Not published by BLS">—</span>'
    return f"${int(round(value)):,}"


def count(value: float | int | None) -> str:
    if value is None:
        return '<span class="blank" title="Not published by BLS">—</span>'
    return f"{int(round(value)):,}"


def ratio(value: float | int | None) -> str:
    if value is None:
        return '<span class="blank" title="Not published by BLS">—</span>'
    return f"{float(value):.2f}"


def plain_hour(value: float | int | None) -> str:
    return "not published" if value is None else f"${value:,.2f}"


def plain_year(value: float | int | None) -> str:
    return "not published" if value is None else f"${int(round(value)):,}"


def annual_only(occ: dict, row: dict) -> bool:
    if occ.get("annual_only"):
        return True
    hourly_missing = row.get("hourly_mean") is None and row.get("hourly_median") is None
    annual_present = row.get("annual_mean") is not None or row.get("annual_median") is not None
    return hourly_missing and annual_present


def median_compare_parts(this_median: float | int, others: list[tuple[dict, dict]]) -> list[str]:
    parts = []
    for metro, obs in others:
        other = obs.get("annual_median")
        if other is None:
            parts.append(f"{metro['short_name']} has no published annual median")
            continue
        diff = int(round(this_median)) - int(round(other))
        if diff == 0:
            parts.append(f"the same as {metro['short_name']} ({plain_year(other)})")
        elif diff > 0:
            parts.append(f"{plain_year(diff)} higher than {metro['short_name']} ({plain_year(other)})")
        else:
            parts.append(f"{plain_year(abs(diff))} lower than {metro['short_name']} ({plain_year(other)})")
    return parts


def pair_faqs(metro: dict, occ: dict, obs: dict, only_annual: bool, other_rows: list[tuple[dict, dict]]) -> list[dict]:
    faqs: list[dict] = []
    if obs.get("annual_median") is not None:
        faqs.append(
            {
                "q": f"What is the median annual wage for {occ['short_title']} in {metro['short_name']}?",
                "a": (
                    f"The OEWS {PERIOD} annual median for {occ['title']} in {metro['name']} "
                    f"is {plain_year(obs['annual_median'])}."
                ),
            }
        )
    else:
        faqs.append(
            {
                "q": f"Is an annual median published for {occ['short_title']} in {metro['short_name']}?",
                "a": (
                    f"BLS did not publish an annual median for {occ['title']} in {metro['name']} "
                    f"in OEWS {PERIOD}."
                ),
            }
        )
    if only_annual:
        faqs.append(
            {
                "q": f"Does OEWS publish an hourly wage for {occ['short_title']} in {metro['short_name']}?",
                "a": (
                    f"No. OEWS {PERIOD} does not publish hourly mean or median for {occ['title']} "
                    f"in {metro['name']}. WageGrid shows annual wages only and does not convert annual to hourly."
                ),
            }
        )
    elif obs.get("hourly_median") is not None:
        faqs.append(
            {
                "q": f"What is the hourly median for {occ['short_title']} in {metro['short_name']}?",
                "a": (
                    f"The OEWS {PERIOD} hourly median for {occ['title']} in {metro['name']} "
                    f"is {plain_hour(obs['hourly_median'])}."
                ),
            }
        )
    if obs.get("employment") is not None:
        faqs.append(
            {
                "q": f"How many {occ['short_title']} work in {metro['short_name']}?",
                "a": (
                    f"OEWS {PERIOD} estimates {int(round(obs['employment'])):,} wage-and-salary "
                    f"{occ['title']} in {metro['name']}. Self-employed workers are excluded."
                ),
            }
        )
    else:
        faqs.append(
            {
                "q": f"How many {occ['short_title']} work in {metro['short_name']}?",
                "a": f"Employment for {occ['title']} in {metro['name']} is suppressed in OEWS {PERIOD}.",
            }
        )
    if obs.get("location_quotient") is not None:
        faqs.append(
            {
                "q": f"What is the location quotient for {occ['short_title']} in {metro['short_name']}?",
                "a": (
                    f"The OEWS {PERIOD} location quotient is {float(obs['location_quotient']):.2f}. "
                    f"Values above 1.00 mean {occ['title']} are more concentrated in {metro['name']} "
                    f"than in the national occupational mix."
                ),
            }
        )
    if obs.get("annual_mean") is not None:
        faqs.append(
            {
                "q": f"What is the mean annual wage for {occ['short_title']} in {metro['short_name']}?",
                "a": (
                    f"The OEWS {PERIOD} annual mean for {occ['title']} in {metro['name']} "
                    f"is {plain_year(obs['annual_mean'])}."
                ),
            }
        )
    this_median = obs.get("annual_median")
    if this_median is not None and other_rows:
        parts = median_compare_parts(this_median, other_rows)
        if parts:
            faqs.append(
                {
                    "q": (
                        f"How does {metro['short_name']}'s {occ['short_title']} median "
                        f"compare to the other WageGrid metros?"
                    ),
                    "a": (
                        f"{metro['short_name']}'s published OEWS {PERIOD} annual median "
                        f"({plain_year(this_median)}) is " + " and ".join(parts) + ". "
                        "These are published medians minus published medians. "
                        "WageGrid does not adjust for cost of living."
                    ),
                }
            )
    faqs.append(
        {
            "q": "Does this wage include self-employed workers?",
            "a": (
                "No. OEWS estimates cover wage-and-salary workers and exclude the self-employed. "
                "WageGrid does not add a self-employment figure."
            ),
        }
    )
    faqs.append(
        {
            "q": "Why is a wage cell blank?",
            "a": "BLS withholds some OEWS estimates for quality or confidentiality. WageGrid does not fill those cells.",
        }
    )
    return faqs


def occupation_faqs(occ: dict, scored: list[tuple[object, dict, dict]]) -> list[dict]:
    faqs: list[dict] = []
    published = [(metro, obs) for _score, metro, obs in scored if obs.get("annual_median") is not None]
    if published:
        ranked = sorted(published, key=lambda item: item[1]["annual_median"], reverse=True)
        best_metro, best_obs = ranked[0]
        listing = ", ".join(f"{m['short_name']} {plain_year(o['annual_median'])}" for m, o in ranked)
        faqs.append(
            {
                "q": f"Which WageGrid metro has the highest {occ['short_title']} annual median?",
                "a": (
                    f"{best_metro['name']} has the highest published OEWS {PERIOD} annual median "
                    f"for {occ['title']} ({plain_year(best_obs['annual_median'])}). "
                    f"Among metros with a published median: {listing}. "
                    "WageGrid does not rank suppressed cells or invent a missing wage."
                ),
            }
        )
    else:
        faqs.append(
            {
                "q": f"Which WageGrid metro has the highest {occ['short_title']} annual median?",
                "a": (
                    f"OEWS {PERIOD} does not publish enough annual medians to rank {occ['title']} "
                    "across Austin, Chicago, and Seattle."
                ),
            }
        )
    employed = [(metro, obs) for _score, metro, obs in scored if obs.get("employment") is not None]
    if employed:
        ranked = sorted(employed, key=lambda item: item[1]["employment"], reverse=True)
        top_metro, top_obs = ranked[0]
        listing = ", ".join(f"{m['short_name']} {int(round(o['employment'])):,}" for m, o in ranked)
        faqs.append(
            {
                "q": f"Which WageGrid metro employs the most {occ['short_title']}?",
                "a": (
                    f"{top_metro['name']} has the highest published OEWS {PERIOD} employment "
                    f"for {occ['title']} ({int(round(top_obs['employment'])):,} wage-and-salary workers). "
                    f"Published employment: {listing}. Self-employed workers are excluded."
                ),
            }
        )
    lqs = [(metro, obs) for _score, metro, obs in scored if obs.get("location_quotient") is not None]
    if lqs:
        ranked = sorted(lqs, key=lambda item: item[1]["location_quotient"], reverse=True)
        top_metro, top_obs = ranked[0]
        listing = ", ".join(f"{m['short_name']} {float(o['location_quotient']):.2f}" for m, o in ranked)
        faqs.append(
            {
                "q": f"Where are {occ['short_title']} most concentrated relative to the national mix?",
                "a": (
                    f"{top_metro['short_name']} has the highest published location quotient "
                    f"({float(top_obs['location_quotient']):.2f}). Published LQs: {listing}."
                ),
            }
        )
    hourly_rows = [(metro, obs) for _score, metro, obs in scored if obs.get("hourly_median") is not None]
    if not hourly_rows:
        faqs.append(
            {
                "q": f"Does OEWS publish hourly pay for {occ['short_title']}?",
                "a": (
                    f"Not in this slice. OEWS {PERIOD} does not publish hourly mean or median for "
                    f"{occ['title']} in Austin, Chicago, or Seattle. WageGrid does not convert annual wages to hourly."
                ),
            }
        )
    else:
        bits = []
        for _score, metro, obs in scored:
            if obs.get("hourly_median") is not None:
                bits.append(f"{metro['short_name']} {plain_hour(obs['hourly_median'])}")
            else:
                bits.append(f"{metro['short_name']} not published")
        faqs.append(
            {
                "q": f"What is the hourly median for {occ['short_title']} in each metro?",
                "a": (
                    f"OEWS {PERIOD} hourly medians: " + "; ".join(bits) + ". "
                    "Blank means BLS withheld the estimate."
                ),
            }
        )
    faqs.append(
        {
            "q": "Does this comparison include self-employed workers?",
            "a": (
                "No. OEWS covers wage-and-salary workers and excludes the self-employed. "
                "WageGrid does not add a self-employment estimate."
            ),
        }
    )
    return faqs


def faq_section(faqs: list[dict]) -> str:
    if not faqs:
        return ""
    items = "".join(
        f"<details><summary>{e(item['q'])}</summary><p>{e(item['a'])}</p></details>" for item in faqs
    )
    return f'<section class="section faq"><h2>Questions</h2>{items}</section>'


class Site:
    def __init__(self) -> None:
        self.metros = load_json(CATALOG / "metros.json")["metros"]
        self.occupations = load_json(CATALOG / "occupations.json")["occupations"]
        seed = load_json(DATA / "oews-may2025-seed.json")
        self.source = seed["source"]
        self.rows = {(r["area_code"], r["soc"]): r for r in seed["observations"]}
        self.metro_by_slug = {m["slug"]: m for m in self.metros}
        self.occ_by_slug = {o["slug"]: o for o in self.occupations}
        self.pages: list[str] = []
        self.today = date.today().isoformat()

    def row(self, metro: dict, occ: dict) -> dict:
        return self.rows[(metro["area_code"], occ["soc"])]

    def related_occs(self, occ: dict) -> list[dict]:
        group = next((g for g in RELATED_GROUPS if occ["soc"] in g), ())
        others = [code for code in group if code != occ["soc"]]
        if not others:
            others = [o["soc"] for o in self.occupations if o["soc"] != occ["soc"]][:4]
        found = [o for o in self.occupations if o["soc"] in others]
        return found[:4]

    def write(self, rel: str, content: str) -> None:
        path = DIST / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if rel.endswith(".html"):
            url = "/" if rel == "index.html" else "/" + rel.replace("index.html", "")
            self.pages.append(url)

    def page(
        self,
        title: str,
        body: str,
        description: str,
        path: str,
        canonical: str,
        current: str | None = None,
        json_ld: list[dict] | None = None,
    ) -> None:
        crumbs_current = current or ""
        nav = []
        for href, label, key in (
            ("/", "Home", "home"),
            ("/metros/", "Metros", "metros"),
            ("/occupations/", "Occupations", "occupations"),
            ("/about/", "About", "about"),
        ):
            cur = ' aria-current="page"' if crumbs_current == key else ""
            nav.append(f'<a href="{href}"{cur}>{label}</a>')
        scripts = ""
        if json_ld:
            payload = json.dumps(json_ld, indent=2)
            scripts = f'<script type="application/ld+json">\n{payload}\n</script>'
        doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)}</title>
  <meta name="description" content="{e(description)}">
  <link rel="canonical" href="{e(canonical)}">
  <link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,560;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/styles.css">
  {scripts}
</head>
<body>
  <a class="skip" href="#content">Skip to content</a>
  <header class="site-header">
    <div class="site-header__bar">
      <a class="wordmark" href="/">
        <img class="wordmark__mark" src="/static/favicon.svg" alt="">
        <span>{SITE_NAME}</span>
      </a>
      <nav class="nav" aria-label="Primary">{"".join(nav)}</nav>
    </div>
  </header>
  <main id="content">
    {body}
  </main>
  <footer class="site-footer">
    <div class="site-footer__inner">
      <p class="cite">{e(CITATION)} WageGrid is not affiliated with BLS. Blank cells are BLS suppressions, not estimates.</p>
      <p><a href="/about/">Methodology</a> · <a href="/llms.txt">llms.txt</a></p>
    </div>
  </footer>
</body>
</html>
"""
        self.write(path, doc)

    def ad_slot(self) -> str:
        return """
<aside class="ad-slot" aria-label="Advertisement">
  <p class="ad-slot__label">Advertisement</p>
  <div class="ad-slot__box" data-ad="adsense-stub"></div>
</aside>
"""

    def crumbs(self, items: list[tuple[str, str]]) -> tuple[str, dict]:
        parts = []
        crumb_ld = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [],
        }
        for i, (href, label) in enumerate(items, start=1):
            parts.append(f'<a href="{e(href)}">{e(label)}</a>' if href else e(label))
            crumb_ld["itemListElement"].append(
                {
                    "@type": "ListItem",
                    "position": i,
                    "name": label,
                    "item": SITE_URL + (href or items[-1][0]),
                }
            )
        return '<nav class="crumbs" aria-label="Breadcrumb">' + " / ".join(parts) + "</nav>", crumb_ld

    def build_home(self) -> None:
        metro_cards = "".join(
            f"""<a class="card" href="/metros/{e(m['slug'])}/">
              <h2>{e(m['short_name'])}</h2>
              <p>{e(m['name'])}</p>
              <p>OEWS area {e(m['area_code'])}</p>
            </a>"""
            for m in self.metros
        )
        occ_items = "".join(
            f'<li><a href="/occupations/{e(o["slug"])}/">{e(o["short_title"])}</a><span class="soc">{e(o["soc"])}</span></li>'
            for o in self.occupations
        )
        body = f"""
<div class="wrap">
  <header class="hero">
    <p class="kicker">BLS OEWS · {PERIOD}</p>
    <h1>Austin, Chicago, and Seattle occupational wages.</h1>
    <p class="lede">WageGrid publishes official Occupational Employment and Wage Statistics for 25 occupations in three metros. No invented wages. Suppressed BLS cells stay blank. OEWS covers wage-and-salary workers and excludes the self-employed.</p>
  </header>
  <section class="section">
    <h2>Metros</h2>
    <div class="metro-cards">{metro_cards}</div>
  </section>
  <section class="section">
    <h2>Occupations</h2>
    <ul class="occ-list">{occ_items}</ul>
  </section>
  <section class="section">
    <h2>How to read a page</h2>
    <p>Each metro × occupation page shows employment, mean and median wages, and the location quotient from OEWS {PERIOD}. Hourly figures are omitted when BLS publishes the occupation annual-only (common for teachers). Compare the same job across the three metros, or switch occupations inside one metro.</p>
    {self.ad_slot()}
  </section>
</div>
"""
        self.page(
            f"{SITE_NAME} — Austin, Chicago, Seattle occupational wages (OEWS {PERIOD})",
            body,
            f"Official BLS OEWS {PERIOD} wages for 25 occupations in Austin, Chicago, and Seattle. Wage-and-salary workers only; suppressed cells stay blank.",
            "index.html",
            f"{SITE_URL}/",
            current="home",
        )

    def build_about(self) -> None:
        retrieved = self.source.get("retrieved", "")
        method = self.source.get("method", "BLS OEWS")
        body = f"""
<div class="wrap">
  <header class="page-head">
    <p class="kicker">Methodology</p>
    <h1>About WageGrid: source, suppressions, and kill rule</h1>
    <p class="lede">A static slice of BLS OEWS {PERIOD} for three metros and 25 occupations. Built to be cited, regenerated, and taken down if it does not earn attention.</p>
  </header>
  <section class="section">
    <h2>BLS citation</h2>
    <p>{e(CITATION)}</p>
    <p>Survey home: <a href="{e(BLS_OES)}">bls.gov/oes</a>. Metropolitan tables and series: <a href="{e(BLS_TABLES)}">bls.gov/oes/tables.htm</a>.</p>
    <p>Retrieval method for this build: {e(method)}{f". Seed retrieved {e(retrieved)}." if retrieved else "."} WageGrid does not scrape job boards or invent wages.</p>
    <p>WageGrid is an independent publication. It is not a BLS product and is not endorsed by the U.S. Department of Labor.</p>
  </section>
  <section class="section">
    <h2>Self-employed workers are excluded</h2>
    <p>OEWS estimates wages and employment for <strong>wage-and-salary workers</strong>. The survey excludes self-employed workers, owners of unincorporated businesses, and unpaid family workers. A WageGrid figure is not self-employment earnings and is not a job-posting average.</p>
    <p>Means and medians are survey estimates for the metropolitan statistical area. Location quotient is the metro concentration of the occupation relative to the national occupational mix. Employment per 1,000 jobs is the occupation’s share of metro wage-and-salary employment, as published by BLS.</p>
  </section>
  <section class="section">
    <h2>Suppressions and annual-only occupations</h2>
    <p>BLS suppresses some cells for quality or confidentiality. WageGrid leaves those cells blank. Do not treat a dash as zero, and do not interpolate a missing wage from another metro or from the mean.</p>
    <p>Some occupations, especially teachers, are published annual-only. When hourly mean and median are both unpublished, pages show annual wages only. That is an OEWS publication choice, not a WageGrid conversion from annual to hourly.</p>
  </section>
  <section class="section">
    <h2>Kill criteria</h2>
    <p>{e(KILL_RULE)}</p>
  </section>
  <section class="section">
    <h2>Ads</h2>
    <p>Pages include an empty AdSense slot. No ad script ships until a publisher ID is added. An example affiliate placeholder may appear, labeled as such, with no live partner IDs.</p>
  </section>
</div>
"""
        self.page(
            f"About WageGrid: OEWS source, suppressions, and kill rule — {SITE_NAME}",
            body,
            f"How WageGrid cites BLS OEWS {PERIOD}, excludes the self-employed, leaves suppressions blank, and when the slice is killed.",
            "about/index.html",
            f"{SITE_URL}/about/",
            current="about",
        )

    def build_metro_index(self) -> None:
        cards = "".join(
            f"""<a class="card" href="/metros/{e(m['slug'])}/">
              <h2>{e(m['name'])}</h2>
              <p>Area code {e(m['area_code'])} · {len(self.occupations)} occupations</p>
            </a>"""
            for m in self.metros
        )
        crumbs, crumb_ld = self.crumbs([("/", "Home"), ("/metros/", "Metros")])
        body = f"""
<div class="wrap">
  <header class="page-head">
    {crumbs}
    <p class="kicker">{PERIOD}</p>
    <h1>Occupational wages by metro</h1>
    <p class="lede">Austin, Chicago, and Seattle as published in OEWS metropolitan statistical area estimates.</p>
  </header>
  <div class="metro-cards">{cards}</div>
</div>
"""
        self.page(
            f"Occupational wages by metro — {SITE_NAME}",
            body,
            f"Browse BLS OEWS {PERIOD} wage tables for Austin, Chicago, and Seattle.",
            "metros/index.html",
            f"{SITE_URL}/metros/",
            current="metros",
            json_ld=[crumb_ld],
        )

    def build_occ_index(self) -> None:
        items = "".join(
            f'<li><a href="/occupations/{e(o["slug"])}/">{e(o["title"])}</a><span class="soc">{e(o["soc"])}</span></li>'
            for o in self.occupations
        )
        crumbs, crumb_ld = self.crumbs([("/", "Home"), ("/occupations/", "Occupations")])
        body = f"""
<div class="wrap">
  <header class="page-head">
    {crumbs}
    <p class="kicker">2018 SOC · {PERIOD}</p>
    <h1>Occupation salaries across three metros</h1>
    <p class="lede">Compare each detailed occupation’s OEWS wages in Austin, Chicago, and Seattle.</p>
  </header>
  <ul class="occ-list">{items}</ul>
</div>
"""
        self.page(
            f"Occupation salaries: Austin vs Chicago vs Seattle — {SITE_NAME}",
            body,
            f"25 OEWS {PERIOD} occupations compared across Austin, Chicago, and Seattle.",
            "occupations/index.html",
            f"{SITE_URL}/occupations/",
            current="occupations",
            json_ld=[crumb_ld],
        )

    def metro_table(self, metro: dict) -> str:
        rows = []
        for occ in self.occupations:
            obs = self.row(metro, occ)
            href = f"/metros/{metro['slug']}/{occ['slug']}/"
            rows.append(
                f"""<tr>
                  <td><a href="{e(href)}">{e(occ['short_title'])}</a></td>
                  <td class="num">{count(obs.get('employment'))}</td>
                  <td class="num">{money_hour(obs.get('hourly_median'))}</td>
                  <td class="num">{money_year(obs.get('annual_median'))}</td>
                  <td class="num">{money_year(obs.get('annual_mean'))}</td>
                </tr>"""
            )
        return f"""
<table>
  <thead>
    <tr>
      <th>Occupation</th>
      <th class="num">Employment</th>
      <th class="num">Hourly median</th>
      <th class="num">Annual median</th>
      <th class="num">Annual mean</th>
    </tr>
  </thead>
  <tbody>{"".join(rows)}</tbody>
</table>
"""

    def build_metro(self, metro: dict) -> None:
        others = "".join(
            f'<li><a class="card" href="/metros/{e(m["slug"])}/"><h3>{e(m["short_name"])}</h3><p>{e(m["name"])}</p></a></li>'
            for m in self.metros
            if m["slug"] != metro["slug"]
        )
        crumbs, crumb_ld = self.crumbs(
            [("/", "Home"), ("/metros/", "Metros"), (f"/metros/{metro['slug']}/", metro["short_name"])]
        )
        body = f"""
<div class="wrap">
  <header class="page-head">
    {crumbs}
    <p class="kicker">OEWS area {e(metro['area_code'])} · {PERIOD}</p>
    <h1>Occupational wages in {e(metro['short_name'])}</h1>
    <p class="lede">{PERIOD} occupational employment and wage estimates for {e(metro['name'])}. Wage-and-salary workers only.</p>
  </header>
  <section class="section">
    {self.metro_table(metro)}
    {self.ad_slot()}
  </section>
  <section class="section">
    <h2>Other metros</h2>
    <ul class="related">{others}</ul>
  </section>
</div>
"""
        self.page(
            f"Occupational wages in {metro['short_name']} — OEWS {PERIOD} — {SITE_NAME}",
            body,
            f"BLS OEWS {PERIOD} wages for {metro['name']} across 25 occupations. Self-employed workers are excluded.",
            f"metros/{metro['slug']}/index.html",
            f"{SITE_URL}/metros/{metro['slug']}/",
            current="metros",
            json_ld=[crumb_ld],
        )

    def occ_compare_table(self, occ: dict) -> tuple[str, dict | None]:
        scored = []
        for metro in self.metros:
            obs = self.row(metro, occ)
            score = obs.get("annual_median")
            if score is None:
                score = obs.get("annual_mean")
            scored.append((score, metro, obs))
        published = [s for s in scored if s[0] is not None]
        best = max(published, key=lambda item: item[0])[1]["area_code"] if published else None
        rows = []
        for score, metro, obs in scored:
            klass = ' class="winner"' if metro["area_code"] == best else ""
            href = f"/metros/{metro['slug']}/{occ['slug']}/"
            rows.append(
                f"""<tr{klass}>
                  <td><a href="{e(href)}">{e(metro['short_name'])}</a><div class="muted">{e(metro['name'])}</div></td>
                  <td class="num">{count(obs.get('employment'))}</td>
                  <td class="num">{money_hour(obs.get('hourly_median'))}</td>
                  <td class="num">{money_year(obs.get('annual_median'))}</td>
                  <td class="num">{money_year(obs.get('annual_mean'))}</td>
                  <td class="num">{ratio(obs.get('location_quotient'))}</td>
                </tr>"""
            )
        table = f"""
<table>
  <thead>
    <tr>
      <th>Metro</th>
      <th class="num">Employment</th>
      <th class="num">Hourly median</th>
      <th class="num">Annual median</th>
      <th class="num">Annual mean</th>
      <th class="num">LQ</th>
    </tr>
  </thead>
  <tbody>{"".join(rows)}</tbody>
</table>
"""
        winner = next((m for m in self.metros if m["area_code"] == best), None)
        return table, winner, scored

    def build_occupation(self, occ: dict) -> None:
        table, winner, scored = self.occ_compare_table(occ)
        related = "".join(
            f'<li><a class="card" href="/occupations/{e(o["slug"])}/"><h3>{e(o["short_title"])}</h3><p>{e(o["soc"])}</p></a></li>'
            for o in self.related_occs(occ)
        )
        crumbs, crumb_ld = self.crumbs(
            [("/", "Home"), ("/occupations/", "Occupations"), (f"/occupations/{occ['slug']}/", occ["short_title"])]
        )
        win_line = (
            f"<p>{e(winner['short_name'])} has the highest published annual median among the three metros.</p>"
            if winner
            else "<p>No metro in this slice has a published annual wage for ranking.</p>"
        )
        faqs = occupation_faqs(occ, scored)
        body = f"""
<div class="wrap">
  <header class="page-head">
    {crumbs}
    <p class="kicker">SOC {e(occ['soc'])} · {PERIOD}</p>
    <h1>{e(occ['short_title'])} salary: Austin vs Chicago vs Seattle</h1>
    <p class="lede">{PERIOD} OEWS comparison for {e(occ['title'])} in Austin-Round Rock-San Marcos, TX; Chicago-Naperville-Elgin, IL-IN; and Seattle-Tacoma-Bellevue, WA.</p>
  </header>
  <section class="section">
    {table}
    <div class="note">{win_line}<p>Highlighted row is the highest published annual median (annual mean if median is suppressed).</p></div>
    {self.ad_slot()}
  </section>
  <section class="section">
    <h2>Related occupations</h2>
    <ul class="related">{related}</ul>
  </section>
  {faq_section(faqs)}
</div>
"""
        self.page(
            f"{occ['short_title']} salary: Austin vs Chicago vs Seattle — {SITE_NAME}",
            body,
            f"Compare official OEWS {PERIOD} {occ['title']} wages in Austin, Chicago, and Seattle. No invented numbers.",
            f"occupations/{occ['slug']}/index.html",
            f"{SITE_URL}/occupations/{occ['slug']}/",
            current="occupations",
            json_ld=[crumb_ld, faq_ld(faqs)],
        )

    def build_pair(self, metro: dict, occ: dict) -> None:
        obs = self.row(metro, occ)
        only_annual = annual_only(occ, obs)
        crumbs, crumb_ld = self.crumbs(
            [
                ("/", "Home"),
                (f"/metros/{metro['slug']}/", metro["short_name"]),
                (f"/metros/{metro['slug']}/{occ['slug']}/", occ["short_title"]),
            ]
        )
        stats = [
            ("Employment", count(obs.get("employment"))),
            ("Annual median", money_year(obs.get("annual_median"))),
            ("Annual mean", money_year(obs.get("annual_mean"))),
            ("Location quotient", ratio(obs.get("location_quotient"))),
        ]
        if not only_annual:
            stats.insert(1, ("Hourly median", money_hour(obs.get("hourly_median"))))
            stats.insert(2, ("Hourly mean", money_hour(obs.get("hourly_mean"))))
        stat_html = "".join(
            f'<div class="stat"><p class="stat-label">{e(label)}</p><p class="stat-value">{value}</p></div>'
            for label, value in stats
        )
        compare_rows = []
        for other in self.metros:
            other_obs = self.row(other, occ)
            href = f"/metros/{other['slug']}/{occ['slug']}/"
            current = other["slug"] == metro["slug"]
            label = f"{other['short_name']}" + (" (this metro)" if current else "")
            link = e(label) if current else f'<a href="{e(href)}">{e(label)}</a>'
            compare_rows.append(
                f"""<tr>
                  <td>{link}</td>
                  <td class="num">{money_year(other_obs.get('annual_median'))}</td>
                  <td class="num">{money_year(other_obs.get('annual_mean'))}</td>
                  <td class="num">{count(other_obs.get('employment'))}</td>
                </tr>"""
            )
        related = "".join(
            f'<li><a class="card" href="/metros/{e(metro["slug"])}/{e(o["slug"])}/"><h3>{e(o["short_title"])}</h3><p>In {e(metro["short_name"])}</p></a></li>'
            for o in self.related_occs(occ)
        )
        other_metros = "".join(
            f'<li><a class="card" href="/metros/{e(m["slug"])}/{e(occ["slug"])}/"><h3>{e(m["short_name"])}</h3><p>{e(occ["short_title"])}</p></a></li>'
            for m in self.metros
            if m["slug"] != metro["slug"]
        )
        teacher_note = (
            f"<p>{e(occ['title'])} is shown annual-only because OEWS did not publish hourly wages for this metro × occupation (or the occupation is typically annual-only). WageGrid does not convert annual pay to an hourly rate.</p>"
            if only_annual
            else ""
        )
        other_rows = [(m, self.row(m, occ)) for m in self.metros if m["slug"] != metro["slug"]]
        faqs = pair_faqs(metro, occ, obs, only_annual, other_rows)
        body = f"""
<div class="wrap">
  <header class="page-head">
    {crumbs}
    <p class="kicker">{e(metro['name'])} · SOC {e(occ['soc'])} · {PERIOD}</p>
    <h1>{e(occ['short_title'])} salary in {e(metro['short_name'])}</h1>
    <p class="lede">Official OEWS {PERIOD} estimates for {e(occ['title'])} in {e(metro['name'])}. Wage-and-salary workers only; blank cells are BLS suppressions.</p>
  </header>
  <section class="section">
    <div class="stat-row">{stat_html}</div>
    <div class="note">
      <p>{e(CITATION)} Employment per 1,000 jobs: {ratio(obs.get('employment_per_1000'))}.</p>
      {teacher_note}
    </div>
    {self.ad_slot()}
  </section>
  <section class="section">
    <h2>Same occupation, other metros</h2>
    <table>
      <thead>
        <tr>
          <th>Metro</th>
          <th class="num">Annual median</th>
          <th class="num">Annual mean</th>
          <th class="num">Employment</th>
        </tr>
      </thead>
      <tbody>{"".join(compare_rows)}</tbody>
    </table>
    <ul class="related related--after">{other_metros}</ul>
  </section>
  <section class="section">
    <h2>Related occupations in {e(metro['short_name'])}</h2>
    <ul class="related">{related}</ul>
    <p><a href="/metros/{e(metro['slug'])}/">All occupations in {e(metro['short_name'])}</a> · <a href="/occupations/{e(occ['slug'])}/">All metros for {e(occ['short_title'])}</a></p>
  </section>
  {faq_section(faqs)}
</div>
"""
        self.page(
            f"{occ['short_title']} salary in {metro['short_name']} — OEWS {PERIOD} — {SITE_NAME}",
            body,
            f"BLS OEWS {PERIOD} wages for {occ['title']} in {metro['name']}. Official estimates only.",
            f"metros/{metro['slug']}/{occ['slug']}/index.html",
            f"{SITE_URL}/metros/{metro['slug']}/{occ['slug']}/",
            json_ld=[crumb_ld, faq_ld(faqs)],
        )

    def build_robots(self) -> None:
        self.write(
            "robots.txt",
            f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n",
        )

    def build_sitemap(self) -> None:
        urls = []
        for path in self.pages:
            urls.append(
                f"  <url><loc>{e(SITE_URL + path)}</loc><lastmod>{self.today}</lastmod></url>"
            )
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(urls)
            + "\n</urlset>\n"
        )
        self.write("sitemap.xml", xml)

    def build_llms(self) -> None:
        metro_lines = "\n".join(f"- {m['name']} (`{m['area_code']}`): /metros/{m['slug']}/" for m in self.metros)
        occ_lines = "\n".join(f"- {o['title']} (`{o['soc']}`): /occupations/{o['slug']}/" for o in self.occupations)
        text = f"""# {SITE_NAME}

> US occupational wages by metro, from BLS OEWS {PERIOD}.

WageGrid is a static site. Every wage is an official OEWS estimate. Suppressed cells are blank. OEWS covers wage-and-salary workers and excludes the self-employed.

Citation: {CITATION}
Survey: {BLS_OES}

## Metros

{metro_lines}

## Occupations

{occ_lines}

## Pages

- Home: /
- About / methodology (BLS cite, self-employed exclusion, suppressions, kill rule): /about/
- Metro × occupation pages: /metros/{{metro}}/{{occupation}}/

Do not invent wages that are not on these pages. Do not fill suppressed cells.
"""
        self.write("llms.txt", text)

    def build_redirects(self) -> None:
        lines = [
            "# Cloudflare Pages slug aliases",
            "/austin /metros/austin-round-rock-san-marcos-tx/ 301",
            "/austin-tx /metros/austin-round-rock-san-marcos-tx/ 301",
            "/austin-tx/ /metros/austin-round-rock-san-marcos-tx/ 301",
            "/chicago /metros/chicago-naperville-elgin-il-in/ 301",
            "/chicago-il /metros/chicago-naperville-elgin-il-in/ 301",
            "/chicago-il/ /metros/chicago-naperville-elgin-il-in/ 301",
            "/seattle /metros/seattle-tacoma-bellevue-wa/ 301",
            "/seattle-wa /metros/seattle-tacoma-bellevue-wa/ 301",
            "/seattle-wa/ /metros/seattle-tacoma-bellevue-wa/ 301",
        ]
        for metro in self.metros:
            for alias in metro.get("aliases", []):
                lines.append(f"/{alias} /metros/{metro['slug']}/ 301")
                lines.append(f"/{alias}/ /metros/{metro['slug']}/ 301")
                lines.append(f"/{alias}/:occ /metros/{metro['slug']}/:occ 301")
        for occ in self.occupations:
            for alias in occ.get("aliases", []):
                lines.append(f"/occupations/{alias} /occupations/{occ['slug']}/ 301")
                lines.append(f"/occupations/{alias}/ /occupations/{occ['slug']}/ 301")
                for metro in self.metros:
                    lines.append(
                        f"/metros/{metro['slug']}/{alias} /metros/{metro['slug']}/{occ['slug']}/ 301"
                    )
                    lines.append(
                        f"/metros/{metro['slug']}/{alias}/ /metros/{metro['slug']}/{occ['slug']}/ 301"
                    )
        self.write("_redirects", "\n".join(lines) + "\n")

    def copy_static(self) -> None:
        dest = DIST / "static"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(SRC_STATIC, dest)

    def build(self) -> int:
        if DIST.exists():
            shutil.rmtree(DIST)
        DIST.mkdir(parents=True)
        self.copy_static()
        self.build_home()
        self.build_about()
        self.build_metro_index()
        self.build_occ_index()
        for metro in self.metros:
            self.build_metro(metro)
        for occ in self.occupations:
            self.build_occupation(occ)
        for metro in self.metros:
            for occ in self.occupations:
                self.build_pair(metro, occ)
        self.build_robots()
        self.build_llms()
        self.build_redirects()
        self.build_sitemap()
        html_pages = len(self.pages)
        print(f"Built {html_pages} HTML pages into {DIST}")
        return html_pages


def faq_ld(faqs: list[dict]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
            }
            for item in faqs
        ],
    }


def main() -> int:
    site = Site()
    site.build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
