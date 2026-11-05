"""Built site hides checkout unless STRIPE_PAYMENT_LINK is a real Payment Link."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build
import offer
import stripe_link


def _token() -> str:
    return "{{" + "STRIPE_PAYMENT_LINK" + "}}"


def _read_tree(root: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for path in root.rglob("*"):
        if path.is_file():
            files[str(path.relative_to(root))] = path.read_bytes()
    return files


class SiteExportTests(unittest.TestCase):
    def _build(self, payment_link: str | None) -> Path:
        dest = Path(tempfile.mkdtemp(prefix="wagegrid-dist-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(dest, ignore_errors=True))
        build.Site(dist=dest, payment_link=payment_link).build()
        return dest

    def test_unset_omits_buy_href_and_keeps_wages_readable(self) -> None:
        dest = self._build(None)
        files = _read_tree(dest)
        blob = b"\n".join(files.values())
        self.assertNotIn(b"buy.stripe.com", blob)
        self.assertNotIn(b"checkout.stripe.com", blob)
        self.assertNotIn(_token().encode("ascii"), blob)
        self.assertNotIn(b'href="{{', blob)
        chicago = files[
            "metros/chicago-naperville-elgin-il-in/registered-nurses/index.html"
        ].decode("utf-8")
        self.assertIn(offer.PENDING_NOTE, chicago)
        self.assertIn(offer.PRICE_LABEL, chicago)
        self.assertNotIn("<a class=\"buy\"", chicago)
        austin = files[
            "metros/austin-round-rock-san-marcos-tx/software-developers/index.html"
        ].decode("utf-8")
        self.assertIn("$64.48", austin)
        self.assertIn("$134,120", austin)
        self.assertIn("31,960", austin)
        self.assertIn(f'href="{offer.SAMPLE_PDF_HREF}"', austin)
        self.assertIn('data-ad="adsense-stub"', austin)
        self.assertNotIn("adsbygoogle", austin)
        sample = files[offer.SAMPLE_PDF_REL]
        text = sample.decode("latin-1").replace(",", "").replace("$", "")
        self.assertIn("69.05", text)
        self.assertIn("64.48", text)
        self.assertIn("143630", text)
        self.assertIn("134120", text)
        self.assertIn("31960", text)
        self.assertIn("24.708", text)
        self.assertIn("2.28", text)
        self.assertIn("May 2025 OEWS", text)
        self.assertNotIn("buy.stripe.com", text)
        self.assertNotIn(_token(), text)
        sitemap = files["sitemap.xml"].decode("utf-8")
        self.assertNotIn("localhost", sitemap)
        self.assertNotIn("0.0.0.0", sitemap)
        self.assertNotIn("localhost", build.SITE_URL)
        self.assertNotIn("0.0.0.0", build.SITE_URL)
        self.assertIn(build.SITE_URL, sitemap)
        export = files["tools/export/index.html"].decode("utf-8")
        self.assertIn(offer.PENDING_NOTE, export)
        self.assertIn(offer.PRICE_LABEL, export)
        self.assertIn(f'href="{offer.SAMPLE_PDF_HREF}"', export)
        self.assertIn("at least one paid PDF", export)
        self.assertIn('href="/tools/export/"', files["index.html"].decode("utf-8"))
        self.assertEqual(export.count("<li>"), 75)
        self.assertNotIn("buy.stripe.com", export)

    def test_placeholder_is_treated_as_unset(self) -> None:
        dest = self._build(_token())
        blob = b"\n".join(_read_tree(dest).values())
        self.assertNotIn(b"buy.stripe.com", blob)
        self.assertNotIn(b"checkout.stripe.com", blob)
        self.assertNotIn(_token().encode("ascii"), blob)
        chicago = (dest / "metros/chicago-naperville-elgin-il-in/registered-nurses/index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn(offer.PENDING_NOTE, chicago)

    def test_valid_buy_link_emits_one_href_on_the_card(self) -> None:
        link = "https://buy.stripe.com/test_a1b2c3"
        dest = self._build(link)
        href = stripe_link.checkout_href(
            link,
            "chicago-naperville-elgin-il-in",
            "registered-nurses",
        )
        chicago = (dest / "metros/chicago-naperville-elgin-il-in/registered-nurses/index.html").read_text(
            encoding="utf-8"
        )
        self.assertEqual(chicago.count(f'href="{href}"'), 1)
        self.assertEqual(chicago.count("buy.stripe.com"), 1)
        self.assertNotIn(offer.PENDING_NOTE, chicago)
        austin = (dest / "metros/austin-round-rock-san-marcos-tx/software-developers/index.html").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("buy.stripe.com", austin)
        self.assertIn(f'href="{offer.SAMPLE_PDF_HREF}"', austin)
        files = _read_tree(dest)
        self.assertNotIn(_token().encode("ascii"), b"\n".join(files.values()))
        buy_pages = [
            name
            for name, data in files.items()
            if name.endswith(".html") and b"buy.stripe.com" in data
        ]
        self.assertEqual(len(buy_pages), 74)
        for name in buy_pages:
            self.assertEqual(files[name].count(b"buy.stripe.com"), 1)
        self.assertNotIn(b"buy.stripe.com", files["llms.txt"])
        self.assertNotIn(b"buy.stripe.com", files[offer.SAMPLE_PDF_REL])
        export = files["tools/export/index.html"]
        self.assertNotIn(b"buy.stripe.com", export)
        self.assertNotIn(b"checkout.stripe.com", export)
        self.assertIn(b"Checkout is on each metro and occupation page.", export)
        self.assertNotIn(offer.PENDING_NOTE.encode("utf-8"), export)

    def test_invalid_link_fails_and_cli_does_not_rewrite_dist(self) -> None:
        dest = Path(tempfile.mkdtemp(prefix="wagegrid-invalid-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(dest, ignore_errors=True))
        marker = dest / "marker.txt"
        marker.write_text("keep", encoding="utf-8")
        with self.assertRaises(stripe_link.StripeLinkError):
            build.Site(dist=dest, payment_link="https://example.com/pay")
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

        index = ROOT / "dist" / "index.html"
        before = index.read_bytes()
        env = os.environ.copy()
        env["STRIPE_PAYMENT_LINK"] = "https://example.com/pay"
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build.py")],
            cwd=ROOT,
            env=env,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(index.read_bytes(), before)
        self.assertNotIn(b"example.com", result.stdout)
        self.assertNotIn(_token().encode("ascii"), result.stderr)
        self.assertNotIn(b"example.com", result.stderr)


if __name__ == "__main__":
    unittest.main()
