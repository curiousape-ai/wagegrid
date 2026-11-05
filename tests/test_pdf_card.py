"""Wage-card PDF uses seed figures and leaves suppressed cells blank."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pdf_card

ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT / "data" / "oews-may2025-seed.json").read_text(encoding="utf-8"))
METROS = json.loads((ROOT / "catalog" / "metros.json").read_text(encoding="utf-8"))["metros"]
OCCS = json.loads((ROOT / "catalog" / "occupations.json").read_text(encoding="utf-8"))["occupations"]


def _pair(area: str, soc: str) -> tuple[dict, dict, dict]:
    metro = next(item for item in METROS if item["area_code"] == area)
    occ = next(item for item in OCCS if item["soc"] == soc)
    obs = next(row for row in SEED["observations"] if row["area_code"] == area and row["soc"] == soc)
    return metro, occ, obs


def _text(pdf: bytes) -> str:
    return pdf.decode("latin-1").replace(",", "").replace("$", "")


class WageCardPdfTests(unittest.TestCase):
    def test_austin_software_developers_uses_exact_seed_figures(self) -> None:
        metro, occ, obs = _pair("12420", "15-1252")
        pdf = pdf_card.render_wage_card(metro, occ, obs)
        text = _text(pdf)
        for key in (
            "employment",
            "hourly_mean",
            "hourly_median",
            "annual_mean",
            "annual_median",
            "employment_per_1000",
            "location_quotient",
        ):
            self.assertIsNotNone(obs[key], key)
            self.assertIn(pdf_card.plain_exact(obs[key]), text, key)
        self.assertIn(b"%PDF-1.4", pdf)
        self.assertEqual(pdf.count(b"/Type /Pages"), 1)
        self.assertEqual(pdf.count(b"/Type /Page "), 1)
        self.assertIn(b"May 2025 OEWS", pdf)
        self.assertIn(pdf_card.CITATION.encode("ascii"), pdf)
        self.assertIn(b"These figures are estimates.", pdf)
        self.assertIn(b"BLS prevails.", pdf)
        self.assertIn(b"not career, legal, or pay-setting advice.", pdf)
        self.assertIn(b"not affiliated with BLS or the U.S. Department of Labor.", pdf)
        self.assertNotIn(b"buy.stripe.com", pdf)
        self.assertNotIn(b"checkout.stripe.com", pdf)
        self.assertNotIn(b"{{", pdf)
        self.assertNotIn(b"10th percentile", pdf)
        self.assertEqual(pdf.count(b"/Count 1"), 1)

    def test_suppressed_hourly_cells_stay_blank(self) -> None:
        metro, occ, obs = _pair("12420", "25-2021")
        self.assertIn("hourly_mean", obs["suppressed"])
        self.assertIn("hourly_median", obs["suppressed"])
        pdf = pdf_card.render_wage_card(metro, occ, obs)
        self.assertIn(b"Hourly mean: not published", pdf)
        self.assertIn(b"Hourly median: not published", pdf)
        text = _text(pdf)
        self.assertIn(pdf_card.plain_exact(obs["annual_mean"]), text)
        self.assertIn(pdf_card.plain_exact(obs["annual_median"]), text)
        self.assertNotIn(b"None", pdf)
        self.assertNotIn(b"null", pdf)
        self.assertNotIn(b"$0", pdf)

    def test_every_seed_pair_keeps_published_figures_and_omits_checkout(self) -> None:
        rows = {(row["area_code"], row["soc"]): row for row in SEED["observations"]}
        self.assertEqual(len(rows), 75)
        for metro in METROS:
            for occ in OCCS:
                obs = rows[(metro["area_code"], occ["soc"])]
                pdf = pdf_card.render_wage_card(metro, occ, obs)
                text = _text(pdf)
                for key, value in obs.items():
                    if key in ("area_code", "soc", "suppressed") or value is None:
                        continue
                    if key in (obs.get("suppressed") or []):
                        continue
                    self.assertIn(pdf_card.plain_exact(value), text, f"{metro['slug']} {occ['slug']} {key}")
                self.assertNotIn(b"buy.stripe.com", pdf)
                self.assertNotIn(b"checkout.stripe.com", pdf)
                self.assertNotIn(b"{{", pdf)

    def test_percentile_row_uses_seed_value_and_blank_suppression(self) -> None:
        metro, occ, obs = _pair("12420", "15-1252")
        extra = dict(obs)
        extra["hourly_pct10"] = None
        extra["hourly_pct25"] = 70.5
        extra["suppressed"] = ["hourly_pct10"]
        pdf = pdf_card.render_wage_card(metro, occ, extra)
        self.assertIn(b"Hourly 10th percentile: not published", pdf)
        self.assertIn(b"Hourly 25th percentile: $70.5", pdf)
        self.assertNotIn(b"Hourly 75th percentile", pdf)


if __name__ == "__main__":
    unittest.main()
