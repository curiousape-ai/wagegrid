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
    <h1>US occupational wages, compared by metro.</h1>
    <p class="lede">WageGrid publishes official Occupational Employment and Wage Statistics for Austin, Chicago, and Seattle across 25 occupations. No invented wages. Suppressed BLS cells stay blank.</p>
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
            f"{SITE_NAME} — occupational wages by metro",
            body,
            f"Official BLS OEWS {PERIOD} wages for 25 occupations in Austin, Chicago, and Seattle.",
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
    <h1>Metros</h1>
    <p class="lede">Austin, Chicago, and Seattle as published in OEWS metropolitan area estimates.</p>
  </header>
  <div class="metro-cards">{cards}</div>
</div>
"""
        self.page(
            f"Metros — {SITE_NAME}",
            body,
            "Browse OEWS wage tables for Austin, Chicago, and Seattle.",
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
    <p class="kicker">2018 SOC</p>
    <h1>Occupations</h1>
    <p class="lede">Compare each detailed occupation across the three WageGrid metros.</p>
  </header>
  <ul class="occ-list">{items}</ul>
</div>
"""
        self.page(
            f"Occupations — {SITE_NAME}",
            body,
            "25 OEWS occupations compared across Austin, Chicago, and Seattle.",
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
    <p class="kicker">OEWS area {e(metro['area_code'])}</p>
    <h1>{e(metro['name'])} wages</h1>
    <p class="lede">{PERIOD} occupational employment and wage estimates for {e(metro['short_name'])}.</p>
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
            f"{metro['name']} wages — {SITE_NAME}",
            body,
            f"BLS OEWS {PERIOD} wages for {metro['name']} across 25 occupations.",
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
        return table, winner

    def build_occupation(self, occ: dict) -> None:
        table, winner = self.occ_compare_table(occ)
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
        faqs = [
            {
                "q": f"Which WageGrid metro pays {occ['short_title']} the most?",
                "a": (
                    f"{winner['name']} has the highest published OEWS {PERIOD} annual median for {occ['title']} among Austin, Chicago, and Seattle."
                    if winner
                    else f"OEWS {PERIOD} does not publish enough annual wages to rank {occ['title']} across these metros."
                ),
            },
            {
                "q": f"Does OEWS publish hourly pay for {occ['short_title']}?",
                "a": (
                    f"Often annual-only. WageGrid hides hourly cells when BLS does not publish them for {occ['title']}."
                    if occ.get("annual_only")
                    else f"When BLS publishes hourly mean or median for {occ['title']}, WageGrid shows them. Suppressed cells stay blank."
                ),
            },
        ]
        body = f"""
<div class="wrap">
  <header class="page-head">
    {crumbs}
    <p class="kicker">SOC {e(occ['soc'])}</p>
    <h1>{e(occ['title'])} by metro</h1>
    <p class="lede">{PERIOD} OEWS comparison for {e(occ['short_title'])} in Austin, Chicago, and Seattle.</p>
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
</div>
"""
        self.page(
            f"{occ['title']} wages by metro — {SITE_NAME}",
            body,
            f"Compare {occ['title']} wages in Austin, Chicago, and Seattle using BLS OEWS {PERIOD}.",
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
            f"<p>{e(occ['title'])} is shown annual-only because OEWS did not publish hourly wages for this metro × occupation (or the occupation is typically annual-only).</p>"
            if only_annual
            else ""
        )
        faqs = [
            {
                "q": f"What is the median wage for {occ['short_title']} in {metro['short_name']}?",
                "a": (
                    f"The OEWS {PERIOD} annual median for {occ['title']} in {metro['name']} is {plain_year(obs.get('annual_median'))}."
                    if obs.get("annual_median") is not None
                    else f"BLS did not publish an annual median for {occ['title']} in {metro['name']} in OEWS {PERIOD}."
                ),
            },
            {
                "q": f"How many {occ['short_title']} work in {metro['short_name']}?",
                "a": (
                    f"OEWS {PERIOD} estimates {int(round(obs['employment'])):,} {occ['title']} in {metro['name']}."
                    if obs.get("employment") is not None
                    else f"Employment for {occ['title']} in {metro['name']} is suppressed in OEWS {PERIOD}."
                ),
            },
            {
                "q": "Why is a wage cell blank?",
                "a": "BLS withholds some OEWS estimates for quality or confidentiality. WageGrid does not fill those cells.",
            },
        ]
        body = f"""
<div class="wrap">
  <header class="page-head">
    {crumbs}
    <p class="kicker">{e(metro['name'])} · SOC {e(occ['soc'])}</p>
    <h1>{e(occ['title'])} wages in {e(metro['short_name'])}</h1>
    <p class="lede">Official OEWS {PERIOD} estimates for {e(occ['short_title'])} in {e(metro['name'])}.</p>
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
</div>
"""
        self.page(
            f"{occ['title']} wages in {metro['short_name']} — {SITE_NAME}",
            body,
            f"BLS OEWS {PERIOD} wages for {occ['title']} in {metro['name']}.",
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
