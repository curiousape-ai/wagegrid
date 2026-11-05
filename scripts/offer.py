"""HTML for the one-off OEWS wage-card PDF offer.

The buy control is emitted only for a resolved Stripe Payment Link.
The Austin software-developers card is the free sample and never gets a
buy href.
"""

from __future__ import annotations

import html

from stripe_link import checkout_href, resolve_stripe_payment_link

PRICE_LABEL = "US$19.99"
PENDING_NOTE = "PDF unlock pending Stripe"
SAMPLE_METRO_SLUG = "austin-round-rock-san-marcos-tx"
SAMPLE_OCC_SLUG = "software-developers"
SAMPLE_PDF_REL = "samples/austin-software-developers-oews-may2025.pdf"
SAMPLE_PDF_HREF = f"/{SAMPLE_PDF_REL}"


def is_sample_pair(metro_slug: str, occ_slug: str) -> bool:
    return metro_slug == SAMPLE_METRO_SLUG and occ_slug == SAMPLE_OCC_SLUG


def _slug_text(value: str) -> None:
    if not value or len(value) > 80:
        raise ValueError("slug is empty or too long")
    if any(not (char.islower() or char.isdigit() or char == "-") for char in value):
        raise ValueError("slug has characters outside lowercase letters, digits, and hyphens")


def render_checkout_status(payment_link: str | None) -> str:
    """Index-level status. No Payment Link href on the index itself."""
    link = resolve_stripe_payment_link(payment_link)
    if link is None:
        return f'<p class="offer-pending">{PENDING_NOTE}</p>'
    return "<p>Checkout is on each metro and occupation page.</p>"


def render_pdf_offer(
    *,
    metro_name: str,
    metro_short: str,
    metro_slug: str,
    occ_title: str,
    occ_slug: str,
    payment_link: str | None,
) -> str:
    _slug_text(metro_slug)
    _slug_text(occ_slug)
    link = resolve_stripe_payment_link(payment_link)
    price = f'<p class="offer-price">{PRICE_LABEL} <span>one-time</span></p>'
    if is_sample_pair(metro_slug, occ_slug):
        action = (
            f'<p><a href="{SAMPLE_PDF_HREF}">Free sample PDF</a> '
            f"for {html.escape(occ_title)} in {html.escape(metro_name)}. "
            f"Other metro and occupation cards are {PRICE_LABEL}.</p>"
        )
    elif link:
        href = html.escape(checkout_href(link, metro_slug, occ_slug), quote=True)
        action = (
            f'<p><a class="buy" href="{href}" rel="noopener noreferrer">Unlock this PDF</a></p>'
        )
    else:
        action = f'<p class="offer-pending">{PENDING_NOTE}</p>'
    return f"""
<section class="offer" aria-labelledby="pdf-offer-heading">
  <h2 id="pdf-offer-heading">Print-ready PDF</h2>
  <p>One page for {html.escape(occ_title)} in {html.escape(metro_short)}: official OEWS May 2025 estimates already on this page (mean, median, and percentiles when the seed publishes them). Suppressed cells stay blank. The wages above stay free to read.</p>
  {price}
  {action}
  <p class="offer-disclaimer">Estimates. If this card and the Bureau of Labor Statistics disagree, BLS prevails. Not career, legal, or pay-setting advice. WageGrid is not affiliated with BLS or the U.S. Department of Labor.</p>
</section>
"""
