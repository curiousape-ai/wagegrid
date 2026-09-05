# WageGrid data source

All wages on WageGrid come from the U.S. Bureau of Labor Statistics
[Occupational Employment and Wage Statistics (OEWS)](https://www.bls.gov/oes/)
May 2025 estimates. WageGrid is not affiliated with BLS.

## Retrieval

- Period: May 2025 (published 2026)
- Method: BLS Public Data API (OE metro series, May 2025)
- Retrieved: 2026-09-05
- Catalog: `catalog/metros.json` × `catalog/occupations.json`
- Seed: `data/oews-may2025-seed.json`

BLS workbook hosts blocked automated download from this environment, so the seed was built from official OE series IDs (`OEUM` + 7-digit area + `000000` + SOC + data type) for May 2025.

## Suppression

BLS withholds some estimates for quality or confidentiality. WageGrid leaves
those cells blank and lists the missing field names in `suppressed`. Do not
invent or interpolate missing wages.

Teachers and some other occupations are often published annual-only in OEWS
(no hourly mean or median). Show annual figures only when hourly cells are blank.

## License / terms

BLS publications are public-domain U.S. government works. Cite BLS OEWS May 2025
on every page that displays a wage. Re-run `python3 scripts/fetch_oews.py` to
refresh the seed from the current official tables or API.
