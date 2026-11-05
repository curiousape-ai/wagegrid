"""Offer markup hides checkout unless the Payment Link is real."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import offer
import stripe_link


def _token() -> str:
    return "{{" + "STRIPE_PAYMENT_LINK" + "}}"


CHICAGO = dict(
    metro_name="Chicago-Naperville-Elgin, IL-IN",
    metro_short="Chicago",
    metro_slug="chicago-naperville-elgin-il-in",
    occ_title="Registered Nurses",
    occ_slug="registered-nurses",
)
AUSTIN_DEV = dict(
    metro_name="Austin-Round Rock-San Marcos, TX",
    metro_short="Austin",
    metro_slug=offer.SAMPLE_METRO_SLUG,
    occ_title="Software Developers",
    occ_slug=offer.SAMPLE_OCC_SLUG,
)
BUY = "https://buy.stripe.com/test_a1b2c3"


class OfferMarkupTests(unittest.TestCase):
    def test_unset_has_price_and_pending_note_and_no_buy_href(self) -> None:
        html = offer.render_pdf_offer(**CHICAGO, payment_link=None)
        self.assertIn(offer.PRICE_LABEL, html)
        self.assertIn(offer.PENDING_NOTE, html)
        self.assertNotIn("buy.stripe.com", html)
        self.assertNotIn("checkout.stripe.com", html)
        self.assertNotIn(_token(), html)
        self.assertNotIn("<a ", html)

    def test_placeholder_is_treated_as_unset(self) -> None:
        html = offer.render_pdf_offer(**CHICAGO, payment_link=_token())
        self.assertIn(offer.PENDING_NOTE, html)
        self.assertNotIn("buy.stripe.com", html)
        self.assertNotIn("checkout.stripe.com", html)
        self.assertNotIn(_token(), html)
        self.assertNotIn("href=", html)

    def test_valid_buy_link_emits_one_href(self) -> None:
        html = offer.render_pdf_offer(**CHICAGO, payment_link=BUY)
        href = stripe_link.checkout_href(BUY, CHICAGO["metro_slug"], CHICAGO["occ_slug"])
        self.assertEqual(html.count(f'href="{href}"'), 1)
        self.assertEqual(html.count("buy.stripe.com"), 1)
        self.assertNotIn(offer.PENDING_NOTE, html)
        self.assertIn(offer.PRICE_LABEL, html)
        self.assertNotIn(_token(), html)

    def test_valid_checkout_host_emits_one_href(self) -> None:
        link = "https://checkout.stripe.com/c/pay/cs_test_a1b2"
        html = offer.render_pdf_offer(**CHICAGO, payment_link=link)
        self.assertEqual(html.count("checkout.stripe.com"), 1)
        self.assertEqual(html.count("<a "), 1)
        self.assertNotIn("buy.stripe.com", html)

    def test_sample_pair_is_free_even_when_checkout_is_on(self) -> None:
        html = offer.render_pdf_offer(**AUSTIN_DEV, payment_link=BUY)
        self.assertIn(f'href="{offer.SAMPLE_PDF_HREF}"', html)
        self.assertEqual(html.count("<a "), 1)
        self.assertNotIn("buy.stripe.com", html)
        self.assertNotIn("checkout.stripe.com", html)
        self.assertNotIn(offer.PENDING_NOTE, html)
        self.assertIn(offer.PRICE_LABEL, html)

    def test_invalid_link_fails_closed(self) -> None:
        with self.assertRaises(stripe_link.StripeLinkError):
            offer.render_pdf_offer(**CHICAGO, payment_link="https://example.com/pay")

    def test_export_status_has_no_buy_href(self) -> None:
        off = offer.render_checkout_status(None)
        on = offer.render_checkout_status(BUY)
        held = offer.render_checkout_status(_token())
        self.assertIn(offer.PENDING_NOTE, off)
        self.assertIn(offer.PENDING_NOTE, held)
        self.assertNotIn("href=", on)
        for block in (off, on, held):
            self.assertNotIn("buy.stripe.com", block)
            self.assertNotIn("checkout.stripe.com", block)
            self.assertNotIn(_token(), block)


if __name__ == "__main__":
    unittest.main()
