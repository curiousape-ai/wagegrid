"""Resolve STRIPE_PAYMENT_LINK for WageGrid checkout.

Unset, blank, and the unsubstituted template token leave checkout off.
Any other value must be an https URL on buy.stripe.com or
checkout.stripe.com. Anything else fails the build so a bad value cannot
leak into HTML, PDF, llms.txt, or the sample card.
"""

from __future__ import annotations

import urllib.parse

# Detect the unsubstituted deploy-template token. Compared, never emitted.
PLACEHOLDER = "{{STRIPE_PAYMENT_LINK}}"
ALLOWED_HOSTS = frozenset({"buy.stripe.com", "checkout.stripe.com"})


class StripeLinkError(ValueError):
    """STRIPE_PAYMENT_LINK is set but is not a usable Payment Link."""


def resolve_stripe_payment_link(raw: str | None) -> str | None:
    """Return a Payment Link, or None when checkout must stay off."""
    if raw is None:
        return None
    value = raw.strip()
    if value == "" or value == PLACEHOLDER:
        return None
    if "{{" in value or "}}" in value or "STRIPE_PAYMENT_LINK" in value:
        raise StripeLinkError("STRIPE_PAYMENT_LINK is not a Stripe Payment Link URL")
    parsed = urllib.parse.urlsplit(value)
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or host not in ALLOWED_HOSTS
        or parsed.username
        or parsed.password
        or parsed.port is not None
        or parsed.netloc != host
        or parsed.fragment
        or parsed.path in ("", "/")
        or any(char.isspace() for char in value)
        or "\\" in value
    ):
        raise StripeLinkError("STRIPE_PAYMENT_LINK is not a Stripe Payment Link URL")
    return value


def _slug_ok(value: str) -> bool:
    if not value or len(value) > 80:
        return False
    return all(char.islower() or char.isdigit() or char == "-" for char in value)


def checkout_href(payment_link: str, metro_slug: str, occ_slug: str) -> str:
    """Payment Link tagged with the metro and occupation being purchased."""
    base = resolve_stripe_payment_link(payment_link)
    if base is None or not _slug_ok(metro_slug) or not _slug_ok(occ_slug):
        raise StripeLinkError("STRIPE_PAYMENT_LINK is not a Stripe Payment Link URL")
    parts = urllib.parse.urlsplit(base)
    query = [
        (key, val)
        for key, val in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if key != "client_reference_id"
    ]
    query.append(("client_reference_id", f"{metro_slug}--{occ_slug}"))
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))
