#!/usr/bin/env python3
"""Print-ready one-page OEWS wage card from the committed seed.

Figures come only from the observation dict. Missing and suppressed cells
are printed as "not published". Percentile rows appear only when the seed
object actually has those keys. The PDF never includes a checkout URL.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog"
DATA = ROOT / "data"
SEED_PATH = DATA / "oews-may2025-seed.json"

PERIOD = "May 2025"
CITATION = (
    "U.S. Bureau of Labor Statistics, Occupational Employment and Wage Statistics, May 2025."
)

CORE_FIELDS = (
    ("employment", "Employment", "count"),
    ("hourly_mean", "Hourly mean", "hour"),
    ("hourly_median", "Hourly median", "hour"),
    ("annual_mean", "Annual mean", "year"),
    ("annual_median", "Annual median", "year"),
    ("employment_per_1000", "Employment per 1,000 jobs", "number"),
    ("location_quotient", "Location quotient", "number"),
)

# Printed only when the key exists on the observation. This seed slice has
# mean and median, not percentiles; do not invent the missing cells.
PERCENTILE_FIELDS = (
    ("hourly_pct10", "Hourly 10th percentile", "hour"),
    ("hourly_pct25", "Hourly 25th percentile", "hour"),
    ("hourly_pct75", "Hourly 75th percentile", "hour"),
    ("hourly_pct90", "Hourly 90th percentile", "hour"),
    ("annual_pct10", "Annual 10th percentile", "year"),
    ("annual_pct25", "Annual 25th percentile", "year"),
    ("annual_pct75", "Annual 75th percentile", "year"),
    ("annual_pct90", "Annual 90th percentile", "year"),
    ("h_pct10", "Hourly 10th percentile", "hour"),
    ("h_pct25", "Hourly 25th percentile", "hour"),
    ("h_pct75", "Hourly 75th percentile", "hour"),
    ("h_pct90", "Hourly 90th percentile", "hour"),
    ("a_pct10", "Annual 10th percentile", "year"),
    ("a_pct25", "Annual 25th percentile", "year"),
    ("a_pct75", "Annual 75th percentile", "year"),
    ("a_pct90", "Annual 90th percentile", "year"),
)

BLANK = "not published"
MAX_LINES = 46


def plain_exact(value: int | float) -> str:
    """Shortest plain decimal for a seed number, without grouping."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"wage value must be numeric, got {type(value).__name__}")
    if isinstance(value, float):
        if not value.is_integer():
            return format(value, ".12f").rstrip("0").rstrip(".")
        value = int(value)
    return str(value)


def grouped(value: int | float) -> str:
    text = plain_exact(value)
    if "." in text:
        return text
    sign = ""
    digits = text
    if digits.startswith("-"):
        sign = "-"
        digits = digits[1:]
    chunks: list[str] = []
    while digits:
        chunks.append(digits[-3:])
        digits = digits[:-3]
    return sign + ",".join(reversed(chunks))


def display_cell(obs: dict, key: str, kind: str) -> str:
    suppressed = set(obs.get("suppressed") or [])
    value = obs.get(key)
    if value is None or key in suppressed:
        return BLANK
    exact = plain_exact(value)
    if kind == "hour":
        return f"${exact}"
    if kind == "year":
        return f"${grouped(value)}"
    if kind == "count":
        return grouped(value)
    return exact


def iter_fields(obs: dict):
    yield from CORE_FIELDS
    seen: set[str] = set()
    for key, label, kind in PERCENTILE_FIELDS:
        if key not in obs or label in seen:
            continue
        seen.add(label)
        yield key, label, kind


def card_lines(metro: dict, occ: dict, obs: dict) -> list[str]:
    lines = [
        "WageGrid wage card",
        str(occ["title"]),
        str(metro["name"]),
        f"SOC {occ['soc']}  |  OEWS area {metro['area_code']}",
        f"Date: {PERIOD} OEWS",
        "",
    ]
    for key, label, kind in iter_fields(obs):
        lines.append(f"{label}: {display_cell(obs, key, kind)}")
    lines.extend(
        [
            "",
            "Percentile cells are printed only when the OEWS seed includes them.",
            "Suppressed cells are left blank. They are not estimates.",
            "",
            "Source:",
            CITATION,
            f"Date: {PERIOD} OEWS.",
            "These figures are estimates. If this card and BLS disagree, BLS prevails.",
            "This is not career, legal, or pay-setting advice.",
            "WageGrid is not affiliated with BLS or the U.S. Department of Labor.",
            "https://www.bls.gov/oes/",
        ]
    )
    return lines


def wrap(text: str, width: int = 88) -> list[str]:
    if text == "":
        return [""]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if len(trial) <= width:
            current = trial
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines or [""]


def _pdf_escape(text: str) -> str:
    if not text.isascii():
        raise ValueError("wage card text must stay ASCII")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_document(lines: list[str]) -> bytes:
    if len(lines) > MAX_LINES:
        raise RuntimeError(f"wage card is {len(lines)} lines; keep it to one page")
    ops = [
        "0.6 w",
        "54 736 m",
        "558 736 l",
        "S",
        "BT",
        "/F1 16 Tf",
        "18 TL",
        "54 710 Td",
        f"({_pdf_escape(lines[0])}) Tj",
        "/F1 11 Tf",
        "14 TL",
    ]
    for line in lines[1:]:
        ops.append("T*")
        ops.append(f"({_pdf_escape(line)}) Tj")
    ops.append("ET")
    stream = "\n".join(ops).encode("ascii")
    return _assemble(stream)


def _assemble(stream: bytes) -> bytes:
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    parts = [header]
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in parts))
        parts.append(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref_at = sum(len(part) for part in parts)
    xref_lines = [f"xref\n0 {len(objects) + 1}\n", "0000000000 65535 f \n"]
    xref_lines.extend(f"{offset:010d} 00000 n \n" for offset in offsets)
    parts.append("".join(xref_lines).encode("ascii"))
    parts.append(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n"
        ).encode("ascii")
    )
    return b"".join(parts)


def render_wage_card(metro: dict, occ: dict, obs: dict) -> bytes:
    wrapped: list[str] = []
    for line in card_lines(metro, occ, obs):
        wrapped.extend(wrap(line))
    return pdf_document(wrapped)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def lookup_pair(metro_slug: str, occ_slug: str) -> tuple[dict, dict, dict]:
    metros = load_json(CATALOG / "metros.json")["metros"]
    occupations = load_json(CATALOG / "occupations.json")["occupations"]
    seed = load_json(SEED_PATH)
    metro = next((item for item in metros if item["slug"] == metro_slug), None)
    occ = next((item for item in occupations if item["slug"] == occ_slug), None)
    if metro is None or occ is None:
        raise SystemExit("unknown metro or occupation slug")
    obs = next(
        (
            row
            for row in seed["observations"]
            if row["area_code"] == metro["area_code"] and row["soc"] == occ["soc"]
        ),
        None,
    )
    if obs is None:
        raise SystemExit("seed has no observation for that metro and occupation")
    return metro, occ, obs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write one OEWS wage-card PDF from the seed")
    parser.add_argument("--metro", required=True, help="metro slug")
    parser.add_argument("--occupation", required=True, help="occupation slug")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    metro, occ, obs = lookup_pair(args.metro, args.occupation)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(render_wage_card(metro, occ, obs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
