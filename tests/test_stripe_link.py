"""Stripe Payment Link gate: unset and the template token stay off."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import stripe_link


def _token() -> str:
    return "{{" + "STRIPE_PAYMENT_LINK" + "}}"


class ResolveStripePaymentLinkTests(unittest.TestCase):
    def test_unset_and_blank_are_checkout_off(self) -> None:
        self.assertIsNone(stripe_link.resolve_stripe_payment_link(None))
        self.assertIsNone(stripe_link.resolve_stripe_payment_link(""))
        self.assertIsNone(stripe_link.resolve_stripe_payment_link("   "))

    def test_placeholder_is_checkout_off(self) -> None:
        self.assertEqual(_token(), stripe_link.PLACEHOLDER)
        self.assertIsNone(stripe_link.resolve_stripe_payment_link(_token()))
        self.assertIsNone(stripe_link.resolve_stripe_payment_link(f"  {_token()}  "))

    def test_buy_and_checkout_hosts_pass(self) -> None:
        buy = "https://buy.stripe.com/test_a1b2c3"
        checkout = "https://checkout.stripe.com/c/pay/cs_test_a1b2"
        self.assertEqual(stripe_link.resolve_stripe_payment_link(buy), buy)
        self.assertEqual(stripe_link.resolve_stripe_payment_link(checkout), checkout)

    def test_invalid_values_fail(self) -> None:
        bad = [
            "https://example.com/pay",
            "http://buy.stripe.com/abc",
            "https://buy.stripe.com",
            "https://buy.stripe.com/",
            "https://user:pass@buy.stripe.com/abc",
            "https://buy.stripe.com:443/abc",
            "https://buy.stripe.com.evil.example/abc",
            "https://evil.buy.stripe.com/abc",
            "https://checkout.stripe.com.evil.example/c/pay/cs_test",
            "javascript:alert(1)",
            "https://buy.stripe.com/abc#frag",
            _token().replace("STRIPE", "stripe"),
            "https://buy.stripe.com/" + _token(),
            '"https://buy.stripe.com/abc"',
        ]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(stripe_link.StripeLinkError) as caught:
                    stripe_link.resolve_stripe_payment_link(value)
                self.assertNotIn(_token(), str(caught.exception))
                self.assertNotIn(value, str(caught.exception))

    def test_checkout_href_adds_one_card_reference(self) -> None:
        href = stripe_link.checkout_href(
            "https://buy.stripe.com/test_a1b2c3",
            "chicago-naperville-elgin-il-in",
            "registered-nurses",
        )
        self.assertEqual(
            href,
            "https://buy.stripe.com/test_a1b2c3?client_reference_id="
            "chicago-naperville-elgin-il-in--registered-nurses",
        )
        self.assertEqual(href.count("buy.stripe.com"), 1)

    def test_checkout_href_rejects_placeholder(self) -> None:
        with self.assertRaises(stripe_link.StripeLinkError):
            stripe_link.checkout_href(
                _token(),
                "austin-round-rock-san-marcos-tx",
                "software-developers",
            )


if __name__ == "__main__":
    unittest.main()
