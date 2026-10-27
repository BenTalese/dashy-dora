# Power-user guide — sourcing product data for Dora

**Audience:** admins and power-users running this install. Not part of the
end-user onboarding (see [PROPOSAL_PRODUCTS_AS_OVERLAY](04_proposals/PROPOSAL_PRODUCTS_AS_OVERLAY.md) §5).

Dora is built to be **legally clean and easy to ship** (Charter Decision 1):
it never scrapes retailer sites, never makes live merchant calls, and never
hosts a deal-comparison engine inside the app. That means the product layer
(My Products, Price History, the per-stock-item Products tab, best-deals) is
**off by default and stays off unless you provide the data yourself**.

You provide the data by pushing it into Dora through one authenticated inbound
endpoint: **`POST /api/ingest`**. As soon as the first record lands, the
product surfaces light up automatically — there is no on/off switch.

## What "lights up" when product data is present

Dora derives the `features.products` capability from **data presence** alone
(`GET /api/health` → `features.products`). The moment a `Product` row exists,
these surfaces appear; the moment the last one is gone, they disappear:

- The **My Products** page (in the side nav, admin section).
- The **Price History** page (with charting + per-product notify-under).
- The per-stock-item **Products** tab (link-to-product, cheapest highlighted).
- Cart / best-deals integrations that depend on linked products.

The **API access** page itself is **always available** (Settings → Admin ·
global → API access) — it is the way you bootstrap the data, so gating it on
data-presence would be a chicken-and-egg.

## Step 1 — mint a key

1. Sign in as an admin and go to **Settings → API access**.
2. **New key** → give it a free-text label (e.g. "home box"). The label is
   for your own bookkeeping — Dora itself never names or assumes anything
   about the source on the other end.
3. **Copy the key immediately.** It is shown **once**. If you lose it, revoke
   it and mint a new one.
4. The new row shows `Created ... · Never used · Accepted 0 / Skipped 0 / Failed 0`.

You can disable a key (without deleting it) or revoke it (delete it). A
disabled or revoked key is rejected with **401** on the next call.

## Step 2 — map the stores you plan to push

Dora **never auto-creates stores** when you push (FU-190). A record names its
store one of two ways — exactly one:

- **`store_id`** — a Dora store's id, read from `GET /api/ingest/stores`
  (below). Nothing to map; this is the path to prefer.
- **`store`** — the external store *name* your source uses, resolved through
  the **Store mappings** panel on the source's row.

For the `store` path the panel populates two ways:

- **You pre-map it.** Open the source → Store mappings → assign each external
  name to a Dora store via the picker.
- **You push and let Dora flag it.** The first time you push a record for an
  unknown external name, Dora creates a **quarantined** mapping (no store
  assigned), skips that record with reason `store_not_mapped`, and surfaces a
  `pending` badge on the source's header. Open the panel, assign it, and
  re-push.

Either way, **stores are never created on the fly**. The picker only shows
stores that already exist in this install.

### The read side

The same bearer key also reads, so a producer can sync against what Dora
already holds:

| Endpoint | What it answers |
|---|---|
| `GET /api/ingest/stores` | Dora's stores (`store_id`, `name`, `has_image`) — the source of truth for `store_id` |
| `GET /api/ingest/stores/<store_id>/image` | the store's logo bytes, if it has one |
| `GET /api/ingest/products?store_id=…` | the ingested products already in Dora for a store (paged) |
| `POST /api/ingest/link-status` | for a list of `{ref, store|store_id, merchant_stockcode?, name?}`: whether each is in Dora, its product id, and which stock items it is linked to |
| `DELETE /api/ingest/products/<product_id>` | remove an ingested product (never a hand-entered custom one — 403) |

Every one of these stamps the source's `last_used_at`.

## Step 3 — push records

Call `POST /api/ingest` with:

```http
POST /api/ingest
Authorization: Bearer <your raw key>
Idempotency-Key: <a stable batch id, optional but recommended>
Content-Type: application/json

{
  "products":           [ ... ],
  "offers":             [ ... ]
}
```

### Auth

`Authorization: Bearer <key>` against the raw key minted on the API access
page. No session cookie required — the session middleware exempts this one
endpoint. A missing / wrong / disabled key yields **401**.

### Idempotency

Set `Idempotency-Key` to a stable string per batch (UUID, hash, whatever).
If you re-send the same key under the same source within ~7 days, Dora
returns a no-op:

```json
{ "accepted": [], "skipped": [], "failed": [], "idempotent_replay": true }
```

This makes retries safe over flaky networks.

### Payload — records

Each record carries an optional `source` provenance string (defaults to the
source's id if omitted). Empty arrays are fine — push only what you have.

**`products`** — upsert a catalogue entry.

| Field                 | Required | Notes                              |
|-----------------------|----------|------------------------------------|
| `ref`                 | yes      | Stable id in this batch — referenced by `offers` |
| `name`                | yes      |                                    |
| `store` / `store_id`  | one of   | The external store name (resolved via the store mapping) **or** a Dora store id from `GET /api/ingest/stores`. Exactly one. |
| `merchant_stockcode`  | no       | Primary dedupe key when present (the producer's SKU code, kept verbatim) |
| `brand`               | no       |                                    |
| `size`, `size_unit`, `size_value` | no | Free strings + numeric size. `size_value` is the **total across the bundle** for multipacks (e.g. 4×125g yoghurt → `size_value=500`). |
| `pack_count`          | no       | Integer > 0; informational multipack count (e.g. `4` for a 4-pack). Drives the obs-list "4 × 125g" label and the PriceEntry multipack disclosure. Omit / `null` for single-packs. |
| `web_url`             | no       |                                    |
| `source`              | no       | Provenance string                  |
| `image`               | no       | The product picture as a `data:image/…;base64,…` URL (≤ 6 MB). A later push with one replaces it; absent leaves the stored picture alone. |

Dedupe — a product is matched on **`(store_id, merchant_stockcode)`** first;
failing that, **`(store_id, name)`**. Hand-entered (custom) products are never
matched or touched. Source is provenance, **not identity** — pushing the same
product from two different IngestionSources collapses to one `Product` row
(shared catalogue).

**`offers`** — append a price point and move the catalogue's "current" price.

| Field         | Required | Notes                                            |
|---------------|----------|--------------------------------------------------|
| `product_ref` | yes      | Matches a `ref` in `products`                    |
| `price_now`   | yes      | > 0                                              |
| `price_was`   | no       | Defaults to `price_now`                          |
| `observed_at` | yes      | ISO 8601 with timezone preferred                 |
| `source`      | no       |                                                  |

Dedupe — `(product_id, observed_at, price_now)`. Append-only; an identical
record is `skipped` with reason `duplicate`.

**`price_observations`** — **removed** (FU-227 chunk 7, J1). Price
*observations* are the user's own in-app record of what they paid; the
producer never writes them. If your batch carries a `price_observations[]`
field today, the request now returns a **400** (`extra="forbid"` rejection).

If you used to push observations via this endpoint:

- Anchored to a `product_ref` → publish the same point as a row in
  `offers[]`. The "your prices" union at read time treats offers and
  observations symmetrically, so the user still sees your point on the
  Price-History chart.
- Anchored to a `stock_item_ref` → that path is gone. Stock-item-level
  observations are now the user's pantry record (PriceEntry widget,
  shopping-list harvest). No replacement endpoint — by design.

### Result DTO

Bad records never fail the batch. The response groups every record into
`accepted`, `skipped`, or `failed`:

```json
{
  "accepted": [
    { "kind": "product", "ref": "p1", "id": "...", "note": "created (...)" },
    { "kind": "offer",   "ref": "p1", "id": "...", "note": "appended" }
  ],
  "skipped": [
    { "kind": "offer", "ref": "p1", "reason": "duplicate" }
  ],
  "failed": [
    { "kind": "offer", "ref": "p9", "reason": "product_unknown" }
  ],
  "idempotent_replay": false
}
```

Stable `reason` codes (will only grow, not change meaning):

- `store_not_mapped` — the external `store` name has no resolved mapping.
- `store_unknown` — the `store_id` names no store in this install.
- `duplicate` — same `(product, observed_at, price)` already on file.
- `product_unknown` — an offer referenced a `ref` not in this batch's
  products and no existing product matched.

Every batch also bumps the source's **Accepted / Skipped / Failed** counters
(visible on the API access page) and refreshes its `last_used_at`.

## The Product Search nav entry

When product data is present, Dora's left nav surfaces a **Product Search**
link. By default this points nowhere — set the **Product search URL** in the
admin app settings to point at whatever search surface you run yourself. From
the user's perspective it just looks like "Product Search"; Dora never names
or references the destination.

This is the **only** outward link the Dora app ever opens — and only when
product data exists (data-gated). See
[PROPOSAL_PRODUCTS_AS_OVERLAY](04_proposals/PROPOSAL_PRODUCTS_AS_OVERLAY.md) §4.1.

## Trust tiers

The `IngestionSource.trust` column is captured but not yet enforced
(`high` is the default). It exists so that future low-trust sources (e.g.
crowd-sourced pushes) can be labelled and filtered without a schema change.
For now, treat all keys as equally privileged — issue them only to producers
you actually trust.

## What this guide deliberately does not say

- **Where the data comes from.** That's your call. Dora is source-agnostic
  by design; the in-app surfaces never name a producer.
- **Whether you should scrape, parse receipt emails, or hand-curate.** All
  three feed the same `/api/ingest` contract. Dora doesn't care.

For the design rationale, see
[PROPOSAL_INGESTION_API](04_proposals/PROPOSAL_INGESTION_API.md) and the
runbook at [PRODUCTS_OVERLAY_RUNBOOK](04_proposals/PRODUCTS_OVERLAY_RUNBOOK.md).
