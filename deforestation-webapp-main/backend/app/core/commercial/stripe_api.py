"""Pinned Stripe API contract for ForestWatch billing.

Stripe versions webhook payloads from the *webhook endpoint*, not from the SDK
request header. ForestWatch therefore has two pins that must stay aligned:

* outbound SDK calls (``STRIPE_API_VERSION`` / :data:`STRIPE_API_VERSION`)
* the Dashboard webhook endpoint API version

The pin is ``2026-07-29.dahlia`` — the current GA as of August 2026. That is
not a freshness upgrade of an existing pin: the repository previously left the
version empty, which meant "whatever the Stripe account happens to default to".
An empty pin is not a contract a first paying customer can depend on.

Object shapes ForestWatch actually reads last broke in ``2025-03-31.basil``
(invoice parent, item-level period). Clover and Dahlia did not move those
fields. Checkout Session creation does not set ``ui_mode``, so Dahlia's
``hosted`` → ``hosted_page`` rename does not apply. Webhook readers still
accept the pre-basil shape so an endpoint pinned earlier than basil keeps
working.
"""
from __future__ import annotations

# Current GA as of 2026-08. Additive Dahlia versions after 2026-03-25 share
# this object shape; we pin the latest additive release so new Stripe accounts
# do not silently pick a newer breaking version later.
STRIPE_API_VERSION = "2026-07-29.dahlia"

# Last release that changed a field ForestWatch reads. Documented so an
# operator comparing Dashboard endpoint versions knows what "compatible" means.
STRIPE_PAYLOAD_COMPATIBLE_SINCE = "2025-03-31.basil"
