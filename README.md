# WageGrid

US occupational wages by metro, from BLS OEWS May 2025.

v1 slice: Austin, Chicago, Seattle × 25 occupations.

This repo is the GitHub home for the Nuttall #2 experiment.

## Slice

| Metro | OEWS area |
| --- | --- |
| Austin-Round Rock-San Marcos, TX | `12420` |
| Chicago-Naperville-Elgin, IL-IN | `16980` |
| Seattle-Tacoma-Bellevue, WA | `42660` |

Occupations (2018 SOC): software developers, registered nurses, accountants and auditors, electricians, plumbers, heavy truck drivers, retail supervisors, marketing managers, data scientists, civil engineers, elementary teachers, police officers, chefs, bartenders, construction laborers, HVAC, dental hygienists, physical therapists, web developers, financial and investment analysts, management analysts, graphic designers, child/family/school social workers, carpenters, medical assistants.

Every wage is an official OEWS estimate. Suppressed cells stay blank. Teachers are annual-only when OEWS withholds hourly. Cite BLS on every page. Ads are an empty AdSense stub.

## Regenerate

```bash
python3 scripts/fetch_oews.py
python3 scripts/build.py
```

`fetch_oews.py` tries the BLS metropolitan workbook (`oesm25ma.zip`), then falls back to the BLS Public Data API. Raw zip/xlsx land in `data/raw/` and are gitignored. The committed slice is `data/oews-may2025-seed.json` plus `data/SOURCE.md`.

Optional:

```bash
WAGEGRID_SITE_URL=https://your.domain python3 scripts/build.py
python3 scripts/fetch_oews.py --api-key "$BLS_API_KEY"
```

Build writes `dist/`: home, about, metro indexes, occupation comparisons, 75 metro × occupation pages, sitemap, `robots.txt` (`Allow: /`), `llms.txt`, FAQ JSON-LD, related links, and Cloudflare `_redirects` for slug aliases.

## Deploy

```bash
wrangler pages deploy dist --project-name wagegrid
```

Then in Google Search Console, add the Pages hostname (or custom domain), verify, and submit `https://<host>/sitemap.xml`.

## Kill

14 days after the first indexable deploy: if Search Console shows no impressions and there is no money signal (AdSense / affiliate / lead), take the project down. Do not keep a dead slice online out of habit.

## Layout

```
catalog/                 metros + occupations
scripts/fetch_oews.py    BLS workbook or API → seed
scripts/build.py         seed → dist/
data/oews-may2025-seed.json
src/static/              styles + favicon
dist/                    static site
```
