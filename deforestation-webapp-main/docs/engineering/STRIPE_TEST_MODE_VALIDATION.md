# Stripe Test-Mode Validation Runbook

**Commercial package notice:** Stripe is an **optional** module. `ENABLE_BILLING`
defaults to **false**. This source package has **not** been validated against a live
Stripe account. Installation, demo, trial, and intelligence do not require Stripe.
Licensees who enable billing must use **their own** Stripe account and credentials.
See `docs/packaging/` and the root README.

Status of this document: the ForestWatch side of the commercial funnel is implemented and
covered by deterministic tests, **but it has not been exercised against a real Stripe
account**. Everything below is the procedure to close that gap. Nothing here has been
performed yet; treat every checkbox as open.

Validation requires three things this repository cannot contain: a Stripe test-mode API
key, a webhook signing secret, and a machine that can receive Stripe's webhook delivery.
Secrets belong in `backend/.env`, which is git-ignored — never in source, never in chat.

---

## 1. What must exist in Stripe (test mode)

Create these once, in the Stripe dashboard with the **Test mode** toggle on.

| Item | Requirement |
| --- | --- |
| Product "ForestWatch Foundation" | one recurring monthly price |
| Product "ForestWatch Professional" | one recurring monthly price |
| Product "ForestWatch Enterprise" | optional; leave unpriced while it is contact-sales |
| Customer portal configuration | Billing → Customer portal → save a configuration, otherwise portal session creation fails |
| Webhook endpoint | `POST https://<host>/api/billing/webhook/stripe` |

Webhook endpoint events — subscribe to these:

```
checkout.session.completed
customer.subscription.created
customer.subscription.updated
customer.subscription.deleted
customer.subscription.paused
customer.subscription.resumed
invoice.paid
invoice.payment_failed
```

Pin the webhook endpoint API version to **`2026-07-29.dahlia`**, matching
`STRIPE_API_VERSION` / `app.core.commercial.stripe_api.STRIPE_API_VERSION`.
Payload readers still accept the pre-`2025-03-31.basil` shape, so an older
endpoint keeps working, but a first-customer account should not rely on that.

Do not invent price ids. Copy the real `price_...` values out of the dashboard.

## 2. Configuration

In `backend/.env`:

```
ENABLE_BILLING=true
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_API_VERSION=2026-07-29.dahlia
STRIPE_PRICE_FOUNDATION=price_...
STRIPE_PRICE_PROFESSIONAL=price_...
PLAN_FOUNDATION_PRICE_LABEL=EUR 19 / month
PLAN_PROFESSIONAL_PRICE_LABEL=EUR 149 / month
PLAN_FOUNDATION_AREA_LIMIT=1
PLAN_PROFESSIONAL_AREA_LIMIT=10
BILLING_SUCCESS_URL=http://localhost:3000/billing?checkout=success
BILLING_CANCEL_URL=http://localhost:3000/billing?checkout=cancelled
BILLING_PORTAL_RETURN_URL=http://localhost:3000/billing
```

Install the SDK (`pip install -r requirements.txt`) — `stripe` is declared but is not
required for the offline suite, so it may not be present yet.

Then confirm the catalog is real, not just configured:

```
cd backend
python scripts/stripe_test_mode_check.py verify-config
```

This retrieves every configured price from Stripe and fails if one is archived, one-off,
from live mode, or missing. It refuses to run with a live key.

## 3. Receiving webhooks locally

```
stripe login
stripe listen --forward-to localhost:8001/api/billing/webhook/stripe
```

`stripe listen` prints its own `whsec_...`; that is the value `STRIPE_WEBHOOK_SECRET` must
hold while forwarding. Restart the backend after changing it.

## 4. Validation sequence

Run these in order and record what you observe. After each step,
`python scripts/stripe_test_mode_check.py inspect-org <organization_id>` prints the local
subscription, entitlements, capacity, and the last ten webhook events with their status
and attempt count.

- [ ] **Baseline.** A fresh organization shows no subscription, `1` monitored area, alerts
      and live sources off. `/billing` shows Foundation.
- [ ] **Checkout.** As owner, `/billing` → Professional → Subscribe. Stripe Checkout opens
      with the configured Professional price. Pay with `4242 4242 4242 4242`, any future
      expiry, any CVC.
- [ ] **Events.** `stripe listen` shows `checkout.session.completed`,
      `customer.subscription.created`, `invoice.paid`. Each returns `200`. Confirm the
      subscription payload's shape matches the endpoint's API version — under basil the
      period is on `items.data[].current_period_end`, not on the subscription.
- [ ] **Synchronization.** `inspect-org` shows `professional / Active`, capacity `n / 10`,
      evidence, live sources, and alerts all `True`, and a period end date.
- [ ] **Capability.** Create a second monitored area — it must now be allowed. `/alerts`
      no longer shows the upgrade prompt. Command Center shows Professional.
- [ ] **Organization isolation.** Switch to a Foundation organization: capacity returns to
      `n / 1` and prompts reappear. Switch back: Professional again. No leakage.
- [ ] **Portal.** Owner opens Manage subscription and lands on the Stripe portal for the
      right customer. A `member` gets `403` on `POST /api/billing/portal`, as does a
      suspended organization.
- [ ] **Downgrade.** In the portal, switch Professional → Foundation.
      `customer.subscription.updated` arrives; capacity becomes `n / 1`; every existing
      monitored area, intelligence event, and alert record is still present; creating
      another area is refused; `/billing` reports being over the limit.
- [ ] **Payment failure.** Attach `4000 0000 0000 0341` and let a renewal fail (Stripe
      test clocks, or `stripe trigger invoice.payment_failed`). Status becomes `past_due`
      and capabilities are deliberately retained; `/billing` asks for payment attention.
- [ ] **Cancellation.** Cancel at period end: status stays entitling and `/billing` says
      "Cancels on <date>". Cancel immediately: `customer.subscription.deleted` drops the
      organization to Foundation defaults with no data deleted.
- [ ] **Idempotency.** Resend a delivered event from the Stripe dashboard. Response is
      `duplicate`, the ledger keeps one row, `attempt_count` stays `1`, and the
      subscription is untouched.
- [ ] **Bad signature.** `curl -X POST .../api/billing/webhook/stripe -d '{}'` and the same
      with a tampered body → `400`, nothing written.
- [ ] **Security.** A forged `X-Organization-Id` for a non-member organization → `403`. A
      `member` attempting checkout → `403`. An unknown plan key and a raw `price_...` as
      `plan_key` → `400`.
- [ ] **Stripe down.** Stop `stripe listen` and set an invalid secret key. Intelligence,
      map, alerts, and monitored areas keep working; `/billing` still renders from local
      state; only checkout and portal fail, with a service message.

## 5. First-customer production checklist

Do not tick anything here until step 4 is green in test mode.

### Stripe (live mode)

- [ ] Live products and recurring prices created, matching the test-mode structure
- [ ] `STRIPE_PRICE_*` set to the **live** price ids
- [ ] Live webhook endpoint on the production HTTPS host, subscribed to the six events
- [ ] Live webhook signing secret in the production environment
- [ ] Live restricted or secret API key in the production environment
- [ ] Customer portal configuration saved in live mode, with cancellation policy decided
- [ ] Business details, statement descriptor, and tax settings completed
- [ ] Payout bank account verified

### ForestWatch (production)

- [ ] `ENABLE_BILLING=true` with live credentials, loaded from the secret store
- [ ] Webhook endpoint reachable over HTTPS and excluded from any auth proxy
- [ ] `verify-config` green against live mode
- [ ] `BILLING_SUCCESS_URL` / `BILLING_CANCEL_URL` / `BILLING_PORTAL_RETURN_URL` on the
      production domain
- [ ] Plan limits and price labels confirmed as the commercial offer
- [ ] SMTP configured so alert delivery is real, not the development fake
- [ ] Mongo indexes present (created on startup; confirm on the production database)
- [ ] Backups and restore verified for organizations, subscriptions, and billing events
- [ ] Failed-webhook alerting: someone is told when `failed_event_count` rises

### Customer onboarding

- [ ] Organization created and the customer is `owner`
- [ ] Their forest drawn or imported as a monitored area, and enrichment confirmed
- [ ] Plan chosen and paid through Checkout
- [ ] Entitlements verified with `inspect-org`
- [ ] Alert policy configured with a real threshold
- [ ] Notification channel configured and a test delivery received
- [ ] Walkthrough of Command Center, map, and investigation flow
- [ ] Named contact for support, and a stated response expectation

## 6. Known gaps this runbook cannot close

- Proration, seats, quantities, and annual terms are not implemented.
- Dunning is Stripe's own retry schedule plus our `past_due` tolerance; there is no
  in-product escalation or forced downgrade after prolonged non-payment.
- Invoice history is not surfaced in ForestWatch; it lives in the Stripe portal.
- Enterprise is contact-sales until a live price id exists.
