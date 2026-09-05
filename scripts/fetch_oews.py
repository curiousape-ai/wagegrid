#!/usr/bin/env python3
"""Fetch May 2025 OEWS metro wages for the WageGrid catalog.

Prefers the official BLS metropolitan workbook (oesm25ma.zip). When that
download is blocked, falls back to the BLS Public Data API. Writes a compact
seed JSON plus SOURCE.md. Raw zip/xlsx stay in data/raw/ (gitignored).
"""

from __future__ import annotations

import argparse
import io
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog"
DATA = ROOT / "data"
RAW = DATA / "raw"
SEED_PATH = DATA / "oews-may2025-seed.json"
SOURCE_PATH = DATA / "SOURCE.md"

OEWS_ZIP_URLS = (
    "https://www.bls.gov/oes/special.requests/oesm25ma.zip",
    "https://www.bls.gov/oes/special-requests/oesm25ma.zip",
)
BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
USER_AGENT = "WageGrid/1.0 (+https://github.com/curiousape-ai/wagegrid; BLS OEWS May 2025 seed)"

# OEWS data-type codes: https://www.bls.gov/help/hlpforma.htm#OE
DATA_TYPES = {
    "01": "employment",
    "03": "hourly_mean",
    "04": "annual_mean",
    "08": "hourly_median",
    "13": "annual_median",
    "16": "employment_per_1000",
    "17": "location_quotient",
}

NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
NS_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_catalog() -> tuple[list[dict], list[dict]]:
    metros = load_json(CATALOG / "metros.json")["metros"]
    occupations = load_json(CATALOG / "occupations.json")["occupations"]
    return metros, occupations


def ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def http_get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
        return resp.read()


def http_json(url: str, payload: dict, timeout: int = 120) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_number(value: object) -> float | int | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "*", "**", "***", "#", "N/A", "NA", "-", "–", "—"}:
        return None
    text = text.replace(",", "")
    try:
        number = float(text)
    except ValueError:
        return None
    if number.is_integer() and abs(number) >= 1:
        return int(number)
    return number


def empty_observation(area_code: str, soc: str) -> dict:
    row = {
        "area_code": area_code,
        "soc": soc,
        "employment": None,
        "hourly_mean": None,
        "annual_mean": None,
        "hourly_median": None,
        "annual_median": None,
        "employment_per_1000": None,
        "location_quotient": None,
        "suppressed": [],
    }
    return row


def mark_suppressed(row: dict) -> None:
    wage_fields = (
        "employment",
        "hourly_mean",
        "annual_mean",
        "hourly_median",
        "annual_median",
        "employment_per_1000",
        "location_quotient",
    )
    row["suppressed"] = [name for name in wage_fields if row.get(name) is None]


def series_id(bls_area_code: str, soc: str, data_type: str) -> str:
    occ = soc.replace("-", "")
    return f"OEUM{bls_area_code}000000{occ}{data_type}"


def parse_series_id(sid: str) -> tuple[str, str, str] | None:
    match = re.fullmatch(r"OEUM(\d{7})000000(\d{6})(\d{2})", sid)
    if not match:
        return None
    area7, occ6, dtype = match.groups()
    soc = f"{occ6[:2]}-{occ6[2:]}"
    return area7, soc, dtype


# --- workbook path ---------------------------------------------------------


def download_zip(dest: Path) -> Path | None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    for url in OEWS_ZIP_URLS:
        try:
            blob = http_get(url)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"zip download failed ({url}): {exc}", file=sys.stderr)
            continue
        if blob[:2] != b"PK":
            print(f"zip download was not a zip ({url})", file=sys.stderr)
            continue
        dest.write_bytes(blob)
        return dest
    return None


def col_letters_to_index(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def load_shared_strings(zfile: zipfile.ZipFile, path: str | None) -> list[str]:
    if not path:
        return []
    root = ET.fromstring(zfile.read(path))
    strings: list[str] = []
    for item in root.findall(f"{NS_MAIN}si"):
        strings.append("".join(node.text or "" for node in item.iter(f"{NS_MAIN}t")))
    return strings


def iter_xlsx_rows(zfile: zipfile.ZipFile, sheet_path: str, shared: list[str]):
    root = ET.fromstring(zfile.read(sheet_path))
    sheet_data = root.find(f"{NS_MAIN}sheetData")
    if sheet_data is None:
        return
    for row in sheet_data.findall(f"{NS_MAIN}row"):
        values: dict[int, str] = {}
        max_idx = -1
        for cell in row.findall(f"{NS_MAIN}c"):
            ref = cell.get("r")
            if not ref:
                continue
            idx = col_letters_to_index(ref)
            max_idx = max(max_idx, idx)
            cell_type = cell.get("t")
            value_el = cell.find(f"{NS_MAIN}v")
            is_el = cell.find(f"{NS_MAIN}is")
            text = ""
            if cell_type == "inlineStr" and is_el is not None:
                text = "".join(node.text or "" for node in is_el.iter(f"{NS_MAIN}t"))
            elif value_el is not None and value_el.text is not None:
                if cell_type == "s":
                    text = shared[int(value_el.text)]
                else:
                    text = value_el.text
            values[idx] = text
        if max_idx < 0:
            yield []
            continue
        yield [values.get(i, "") for i in range(max_idx + 1)]


def workbook_sheet_paths(zfile: zipfile.ZipFile) -> list[tuple[str, str]]:
    wb = ET.fromstring(zfile.read("xl/workbook.xml"))
    rels = ET.fromstring(zfile.read("xl/_rels/workbook.xml.rels"))
    rel_map = {
        rel.get("Id"): rel.get("Target")
        for rel in rels.findall(f"{NS_REL}Relationship")
    }
    sheets = []
    for sheet in wb.find(f"{NS_MAIN}sheets").findall(f"{NS_MAIN}sheet"):
        name = sheet.get("name") or ""
        rel_id = sheet.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        target = rel_map.get(rel_id, "")
        path = target[3:] if target.startswith("/") else f"xl/{target.lstrip('./')}"
        sheets.append((name, path))
    return sheets


def normalize_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


HEADER_ALIASES = {
    "area": "area_code",
    "area_code": "area_code",
    "area_fips": "area_code",
    "occ_code": "soc",
    "occ_code_": "soc",
    "occupation_code": "soc",
    "tot_emp": "employment",
    "employment": "employment",
    "h_mean": "hourly_mean",
    "a_mean": "annual_mean",
    "h_median": "hourly_median",
    "a_median": "annual_median",
    "jobs_1000": "employment_per_1000",
    "loc_quotient": "location_quotient",
    "locq": "location_quotient",
}


def extract_from_zip(zip_path: Path, metros: list[dict], occupations: list[dict]) -> list[dict]:
    wanted_areas = {m["area_code"] for m in metros}
    wanted_socs = {o["soc"] for o in occupations}
    rows_by_key: dict[tuple[str, str], dict] = {
        (m["area_code"], o["soc"]): empty_observation(m["area_code"], o["soc"])
        for m in metros
        for o in occupations
    }

    with zipfile.ZipFile(zip_path) as zfile:
        xlsx_name = next(
            (n for n in zfile.namelist() if n.lower().endswith(".xlsx")),
            None,
        )
        if not xlsx_name:
            raise RuntimeError("No .xlsx inside OEWS zip")
        xlsx_bytes = zfile.read(xlsx_name)

    with zipfile.ZipFile(io.BytesIO(xlsx_bytes)) as xlsx:
        shared_path = next((n for n in xlsx.namelist() if n.endswith("sharedStrings.xml")), None)
        shared = load_shared_strings(xlsx, shared_path)
        for sheet_name, sheet_path in workbook_sheet_paths(xlsx):
            if "field" in sheet_name.lower() or "note" in sheet_name.lower():
                continue
            iterator = iter_xlsx_rows(xlsx, sheet_path, shared)
            try:
                header_row = next(iterator)
            except StopIteration:
                continue
            headers = [HEADER_ALIASES.get(normalize_header(h), normalize_header(h)) for h in header_row]
            if "area_code" not in headers or "soc" not in headers:
                continue
            for raw in iterator:
                record = {headers[i]: raw[i] if i < len(raw) else "" for i in range(len(headers))}
                area = str(record.get("area_code", "")).strip()
                if area.startswith("00") and len(area) == 7:
                    area = area[2:]
                soc = str(record.get("soc", "")).strip()
                if area not in wanted_areas or soc not in wanted_socs:
                    continue
                row = rows_by_key[(area, soc)]
                for field in (
                    "employment",
                    "hourly_mean",
                    "annual_mean",
                    "hourly_median",
                    "annual_median",
                    "employment_per_1000",
                    "location_quotient",
                ):
                    parsed = parse_number(record.get(field))
                    if parsed is not None:
                        row[field] = parsed

    for row in rows_by_key.values():
        mark_suppressed(row)
    return [rows_by_key[(m["area_code"], o["soc"])] for m in metros for o in occupations]


# --- API path --------------------------------------------------------------


def fetch_via_api(
    metros: list[dict],
    occupations: list[dict],
    batch_size: int = 25,
    pause: float = 0.4,
    api_key: str | None = None,
) -> list[dict]:
    area_by_bls = {m["bls_area_code"]: m["area_code"] for m in metros}
    rows_by_key: dict[tuple[str, str], dict] = {
        (m["area_code"], o["soc"]): empty_observation(m["area_code"], o["soc"])
        for m in metros
        for o in occupations
    }

    series: list[str] = []
    for metro in metros:
        for occ in occupations:
            for dtype in DATA_TYPES:
                series.append(series_id(metro["bls_area_code"], occ["soc"], dtype))

    for i in range(0, len(series), batch_size):
        chunk = series[i : i + batch_size]
        payload = {
            "seriesid": chunk,
            "startyear": "2025",
            "endyear": "2025",
        }
        if api_key:
            payload["registrationkey"] = api_key
        try:
            result = http_json(BLS_API_URL, payload)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                time.sleep(5)
                result = http_json(BLS_API_URL, payload)
            else:
                raise
        if result.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS API error: {result}")
        for item in result.get("Results", {}).get("series", []):
            parsed = parse_series_id(item["seriesID"])
            if not parsed:
                continue
            area7, soc, dtype = parsed
            area = area_by_bls.get(area7)
            if area is None:
                continue
            field = DATA_TYPES[dtype]
            points = item.get("data") or []
            may = next((p for p in points if p.get("year") == "2025"), None)
            value = parse_number(may.get("value")) if may else None
            rows_by_key[(area, soc)][field] = value
        print(f"API batch {i // batch_size + 1}/{(len(series) + batch_size - 1) // batch_size}")
        time.sleep(pause)

    for row in rows_by_key.values():
        mark_suppressed(row)
    return [rows_by_key[(m["area_code"], o["soc"])] for m in metros for o in occupations]


def write_source(method: str, extra: str) -> None:
    text = f"""# WageGrid data source

All wages on WageGrid come from the U.S. Bureau of Labor Statistics
[Occupational Employment and Wage Statistics (OEWS)](https://www.bls.gov/oes/)
May 2025 estimates. WageGrid is not affiliated with BLS.

## Retrieval

- Period: May 2025 (published 2026)
- Method: {method}
- Retrieved: {date.today().isoformat()}
- Catalog: `catalog/metros.json` × `catalog/occupations.json`
- Seed: `data/oews-may2025-seed.json`

{extra}

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
"""
    SOURCE_PATH.write_text(text, encoding="utf-8")


def write_seed(observations: list[dict], method: str, source_url: str) -> None:
    payload = {
        "source": {
            "survey": "Occupational Employment and Wage Statistics (OEWS)",
            "period": "May 2025",
            "publisher": "U.S. Bureau of Labor Statistics",
            "url": "https://www.bls.gov/oes/",
            "tables": "https://www.bls.gov/oes/tables.htm",
            "retrieved": date.today().isoformat(),
            "method": method,
            "source_url": source_url,
            "citation": "U.S. Bureau of Labor Statistics, Occupational Employment and Wage Statistics, May 2025.",
        },
        "observations": observations,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    SEED_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-only", action="store_true", help="Skip the workbook download")
    parser.add_argument("--zip-only", action="store_true", help="Fail if the workbook is unavailable")
    parser.add_argument("--api-key", default=None, help="Optional BLS Public Data API key")
    args = parser.parse_args()

    metros, occupations = load_catalog()
    observations = None
    method = ""
    source_url = ""
    extra = ""

    if not args.api_only:
        zip_path = download_zip(RAW / "oesm25ma.zip")
        if zip_path:
            print(f"Parsing {zip_path}")
            observations = extract_from_zip(zip_path, metros, occupations)
            method = "BLS OEWS metropolitan workbook (oesm25ma.zip)"
            source_url = OEWS_ZIP_URLS[0]
            extra = (
                "Parsed `oesm25ma.zip` from BLS special requests. The raw zip and "
                "xlsx are gitignored; this seed is the committed slice."
            )
        elif args.zip_only:
            print("Workbook download failed and --zip-only was set", file=sys.stderr)
            return 1

    if observations is None:
        print("Falling back to BLS Public Data API")
        observations = fetch_via_api(metros, occupations, api_key=args.api_key)
        method = "BLS Public Data API (OE metro series, May 2025)"
        source_url = BLS_API_URL
        extra = (
            "BLS workbook hosts blocked automated download from this environment, "
            "so the seed was built from official OE series IDs "
            "(`OEUM` + 7-digit area + `000000` + SOC + data type) for May 2025."
        )

    write_seed(observations, method, source_url)
    write_source(method, extra)
    filled = sum(1 for row in observations if row["annual_mean"] is not None or row["annual_median"] is not None)
    print(f"Wrote {SEED_PATH} ({filled}/{len(observations)} rows with an annual wage)")
    print(f"Wrote {SOURCE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
