# Stripe Integration Setup Guide for Cognimend

> **Current Status:** Plan limits (document count, query count) are **fully enforced without Stripe**. Stripe integration is an optional upgrade for paid billing. The system works end-to-end on the free plan without any Stripe configuration.

---

## What Works Without Stripe

- ✅ Free plan enforced via database (`plans` table)
- ✅ Document upload blocked when limit reached (`403` returned by Gateway)
- ✅ Query count blocked when monthly limit reached (`403` returned by Gateway)
- ✅ Plan data served from `subscriptions` and `plans` PostgreSQL tables
- ✅ Billing page shows current plan and usage

---

## Environment Variables

Add these to `backend/.env` when you are ready to integrate Stripe:

```env
# Stripe — leave empty to disable Stripe (plan limits still enforce from DB)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Stripe Price IDs for recurring subscription plans
STRIPE_PRICE_PERSONAL=price_xxxxxxxxxxxxx
STRIPE_PRICE_TEAM=price_xxxxxxxxxxxxx
STRIPE_PRICE_BUSINESS=price_xxxxxxxxxxxxx
```

The code checks `STRIPE_SECRET_KEY` before doing anything Stripe-related. If it is blank, all Stripe calls silently no-op and plan limits still function from the database.

---

## Stripe Dashboard Setup

### Step 1: Create a Stripe account

1. Go to [https://dashboard.stripe.com/](https://dashboard.stripe.com/)
2. Sign up or log in

### Step 2: Create Products and Prices

1. Navigate to **Products → Add Product**
2. Create the following products and prices:

| Product | Plan Name | Billing |
|---------|-----------|---------|
| Cognimend Personal | `personal` | Monthly recurring |
| Cognimend Team | `team` | Monthly recurring |
| Cognimend Business | `business` | Monthly recurring |

3. Copy each **Price ID** (format: `price_xxx`) into your `.env`

### Step 3: Configure the Webhook

1. Navigate to **Developers → Webhooks → Add endpoint**
2. Set the endpoint URL:
   - Local: Use [Stripe CLI](https://stripe.com/docs/stripe-cli) to forward locally
   - Production: `https://api.yourdomain.com/webhooks/stripe`
3. Select events to listen for:
   - `checkout.session.completed`
   - `customer.subscription.deleted`
   - `customer.subscription.updated`
   - `invoice.payment_failed`
4. Copy the **Webhook Signing Secret** (`whsec_xxx`) into your `.env`

### Step 4: Test with Stripe CLI (Local)

```bash
# Install Stripe CLI: https://stripe.com/docs/stripe-cli
stripe login
stripe listen --forward-to http://localhost:8007/webhooks/stripe
```

---

## How the Integration Works

```
User clicks "Upgrade" on Billing page
            ↓
Frontend calls POST /billing/checkout?plan=personal
            ↓
Gateway calls billing.py → create_stripe_checkout()
            ↓
Stripe Checkout page opens
            ↓
User pays
            ↓
Stripe sends POST /webhooks/stripe (checkout.session.completed)
            ↓
Gateway validates Stripe signature
            ↓
billing.py → handle_stripe_event() → update_workspace_plan()
            ↓
DB: workspaces.plan_id updated, subscriptions row upserted
            ↓
User's limits automatically increase
```

---

## Webhook Signature Verification

The webhook handler in `gateway/main.py` uses Stripe's official library to verify the signature:

```python
event = stripe.Webhook.construct_event(payload, stripe_sig, stripe_secret)
```

This prevents forged webhook payloads from being processed. **Never process Stripe events without verifying the signature.**

---

## Adding a Checkout Endpoint

To expose a checkout URL, add this route to the gateway or a new billing service:

```python
@app.post("/billing/checkout")
async def create_checkout(plan: str, ws: dict = Depends(require_workspace_access)):
    url = await create_stripe_checkout(ws["workspace_id"], plan)
    if not url:
        raise HTTPException(503, "Billing not configured")
    return {"checkout_url": url}
```

---

## Plan Switching

The `update_workspace_plan()` function in `billing.py` handles plan assignment:

```python
await update_workspace_plan(workspace_id, "team", stripe_sub_id="sub_xxx")
```

This updates:
- `workspaces.plan_id`
- `subscriptions` row (upsert with Stripe subscription ID and status)

---

## Downgrade / Cancellation

When a subscription is cancelled in Stripe, the `customer.subscription.deleted` event fires. The handler sets the subscription `status` to `cancelled`. You may optionally downgrade the plan to `free` by also calling `update_workspace_plan(workspace_id, "free")`.

---

## Security Checklist

- [ ] `STRIPE_SECRET_KEY` only in `.env`, never committed
- [ ] Webhook endpoint validates `stripe-signature` header before processing
- [ ] Price IDs hardcoded server-side — client never sends price data
- [ ] Use `sk_live_` keys only in production; use `sk_test_` for development
- [ ] Restrict Stripe API key scopes to only what is needed (no payouts, no disputes access)
