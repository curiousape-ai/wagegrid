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

`WAGEGRID_SITE_URL` defaults to `https://wagegrid.pages.dev` when it is unset.

Build writes `dist/`: home, about, metro indexes, occupation comparisons, 75 metro × occupation pages, the PDF export page, one free sample PDF, sitemap, `robots.txt` (`Allow: /`), `llms.txt`, FAQ JSON-LD, related links, and Cloudflare `_redirects` for slug aliases.

Tests:

```bash
python3 -m unittest discover -s tests -v
```

## Paid PDF

Each metro × occupation page offers a one-off print-ready wage card for US$19.99. The HTML page stays free. Figures are the official OEWS May 2025 estimates in `data/oews-may2025-seed.json` (mean and median in this slice; a percentile row is printed only when that key is present). Suppressed cells stay blank.

Checkout is omitted until `STRIPE_PAYMENT_LINK` is an `https://buy.stripe.com/…` or `https://checkout.stripe.com/…` URL with a path. If the variable is unset, blank, or still an unsubstituted template token, the buy control is left out and the page says "PDF unlock pending Stripe". Any other value fails the build.

The free sample is Austin × software developers at `dist/samples/austin-software-developers-oews-may2025.pdf`. It contains no checkout URL. Write any card for Stripe file delivery with:

```bash
python3 scripts/pdf_card.py \
  --metro austin-round-rock-san-marcos-tx \
  --occupation software-developers \
  --out card.pdf
```

Paid cards are not published under `dist/`. This static site cannot tell that a visitor paid.

## Deploy

```bash
wrangler pages deploy dist --project-name wagegrid
```

Then in Google Search Console, add the Pages hostname (or custom domain), verify, and submit `https://<host>/sitemap.xml`.

## Kill

14 days after the first indexable deploy: if Search Console shows no impressions and there is no money signal (AdSense / affiliate / lead), take the project down.

Paid PDFs: 14 days after the first indexable public offer (checkout live on the public site), the deciding number is at least one paid PDF. An unpublished draft does not start that clock. Do not keep a dead slice online out of habit.

## Layout

```
catalog/                 metros + occupations
scripts/fetch_oews.py    BLS workbook or API → seed
scripts/build.py         seed → dist/
scripts/pdf_card.py      one OEWS wage-card PDF
scripts/stripe_link.py   Payment Link gate
scripts/offer.py         price, pending note, buy control
tests/                   Stripe hide rules and seed figures
data/oews-may2025-seed.json
src/static/              styles + favicon
dist/                    static site
```
