# WageGrid

US occupational wages by metro, from BLS OEWS May 2025.

v1 slice: Austin, Chicago, Seattle × ~25 occupations.

This repo is the GitHub home for the Nuttall #2 experiment. Generator and pages land in follow-up commits.

## Next

- Build: `python3 scripts/fetch_oews.py && python3 scripts/build.py`
- Deploy: Cloudflare Pages on `dist/` (`wrangler pages deploy dist --project-name wagegrid`)
- Kill: 14 days after first indexable deploy if no GSC impressions and no money signal
