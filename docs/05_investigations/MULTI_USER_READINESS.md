# Multi-User Readiness: Pre-Flight Checklist

**Status:** Draft for discussion
**Date:** 2026-06-04
**Scope:** The single-tenant assumptions baked throughout DiscountDora that will break — simultaneously — the day "Multi-user support" (a stated roadmap item, `README.md:52`) ships. This is not a list of bugs; it's a list of *load-bearing assumptions* to dismantle deliberately before that card is picked up.

---

## 1. The core fact

DiscountDora is a **single-tenant, single-household app today, by design.** Verified:

- Core domain entities (`stock_item`, `shopping_list`, `recipe`, and by extension meals, products, locations) have **no `user_id` / `household_id` / `owner_id` column**. All data is one shared dataset.
- The README lists **"Multi-user support — so everyone can help grab the milk on sale"** as an *unchecked* roadmap item (`README.md:52`).

So every user in an install intentionally shares one pantry, one set of lists, one assistant. That is correct and fine *now*. The danger is that several independent subsystems each silently rely on it, and they all stop being safe at the **same moment** — when a second household's data enters the same database.

The purpose of this doc: make that moment a planned migration, not a security incident.

---

## 2. What breaks at the multi-user milestone

### 2.1 Data isolation — the foundation (CRITICAL)

There is no row-level ownership anywhere. The instant two households share a deployment:

- Every list query, stock query, recipe query returns **everyone's** data.
- There is no scoping to add "later" cheaply — it touches **every** feature's queries, DTOs, and the dashboard aggregates.

**Pre-flight work:**
- Decide the tenancy unit: per-**user** or per-**household** (the README's framing — "everyone helps" — implies *household*, a group of users sharing one pantry). This choice is foundational; get it right first.
- Add the scope column (`household_id`) to every domain entity and a `users → household` membership.
- Make scoping enforced at the **repository layer**, not per-handler, so no query can forget it. A handler that fetches "all stock items" must be structurally incapable of crossing households.
- Backfill: existing single-household installs collapse into one `household` row.

### 2.2 The Dora assistant — shared-everything by construction (CRITICAL)

The assistant's tools call `SqlAlchemyRepository()` directly with no scope filter (`tools.py`). Today that's correct — there's one dataset. Post-multi-user, **the chat becomes a cross-household data exfiltration path**: "show me all stock" returns every household's pantry, bypassing any UI-level scoping because the tools don't go through it.

**Pre-flight work:**
- The assistant must execute every tool **in the requesting user's household scope** — ideally by the same repository-layer enforcement as §2.1, so tools inherit it for free.
- Re-audit all 25+ data tools and 8 action tools (`tools.py`, `confirm_actions.py`) to confirm none construct queries that escape the scope.
- The mutation-confirmation gate (good today — see §2.3) must also confirm the *target* belongs to the user's household before committing.

### 2.3 What is already done right (preserve it)

Credit where due — these are correct now and must **stay** correct through the migration:

- **Mutation gate:** the assistant never auto-executes writes; action tools short-circuit into a user-confirmed proposal (`ask_assistant.py:187-190`). Keep this; just add household-scope validation at commit.
- **Auth tokens:** single-use, SHA-256-hashed at rest, expiring, constant-time compared. Multi-tenant-safe as-is.
- **Anti-enumeration:** forgot-password / resend-verification return 204 regardless. Stays valid.

### 2.4 Auth & session — sharper teeth at scale (HIGH)

These are *moderate* single-tenant and become *serious* multi-tenant (see the companion security doc for full detail):

- **CSRF** (`SameSite=Lax`, no CSRF token) — today an attacker can change *your* email; multi-tenant it's a lever against *any* account in a larger user base.
- **Email-change requires no password re-entry** (`email_flows.py:260`) while password-change does (`change_password.py`). Account-takeover surface that scales with user count.
- **Roles:** today `is_admin` is global ("first user is admin"). Multi-user needs **household-scoped roles** — an admin of household A must not administer household B. The current global admin model has no concept of this.
- **Rate limiting** is in-memory, per-process (`auth_helpers.py`) — fine for one box, leaky across a horizontally-scaled multi-tenant deployment.

### 2.5 The "primary list" and other global singletons (MEDIUM)

Several features assume *one* of something globally:
- `is_primary` shopping list is a global singleton flag (see `SHOPPING_LIST_REDESIGN_PROPOSAL.md`). Per-household it must become one-primary-**per-household**.
- Dashboard aggregates (`get_dashboard_summary.py`) count *all* rows — must become per-household counts.
- Stock-level definitions, locations, stock groups: shared catalog or per-household? A design decision, not a default.
- Meal plans: one plan per week per install. `MealPlan.start_date` is the lookup key (`_fork_template_onto_week` finds by it) and there is no per-user plan; per-household it becomes one plan per week per household (finalisation 02-D3).
- Quick-add target memory is per-tab `sessionStorage` while lists are household-shared; per-user or per-household it needs a home on the server (finalisation 03-D3).

---

## 3. The order that matters

The reason this is a checklist and not a backlog: **these fail together.** Shipping a login screen that supports multiple users *without* §2.1 and §2.2 doesn't add a feature — it opens every household's data to every other. The dependency order:

1. **Decide the tenancy unit** (user vs. household). Everything keys off this.
2. **Repository-layer scoping** (§2.1) — the structural guarantee. Nothing else is safe until this exists.
3. **Assistant inherits scope** (§2.2) — verify no tool escapes it.
4. **Household-scoped roles + auth hardening** (§2.4) — CSRF token, password proof on email change.
5. **De-globalize singletons** (§2.5) — primary list, dashboard, catalogs.
6. *Only then* — the user-facing multi-user features (invites, sharing, member management).

---

## 4. The one-line summary for the roadmap card

> "Multi-user" is not a feature you add to the UI; it's a data-isolation boundary you add to the *core*. Until every query is structurally household-scoped and the assistant inherits that scope, adding a second user is a data breach, not a feature. Budget the migration (§3 steps 1–5) **before** the visible work.

---

## 5. Open questions — the SaaS-path parking place

> **This section is the durable home for the SaaS / multi-tenant design questions**
> (FU-410 was folded in here on 2026-07-14 rather than tracked as a standalone
> backlog item — these only get answered *if the SaaS path is ever taken*, so they
> belong with the readiness doc, not the active follow-ups ledger). They are the
> first thing to settle at a Phase-4 tenancy kick-off, gating the Path-A work
> (Households-as-tenant `FU-400`, security hardening `FU-401`, launch readiness
> `FU-406`, provisioning control plane `FU-399`). Until then, the **distribution
> posture** (RECONCILED_FINISHING_PLAN Decision 5 / §7.5) governs: build the one
> self-hostable SaaS-style artifact, **don't pre-build multi-tenancy** — and note
> that posture already leans toward Q2's *per-install* answer as the near-term
> reality, which would moot most of §2. Related decisions already made: the shared
> demo stays single-dataset, not per-visitor (FU-555, won't-do).

- **Household vs. user tenancy?** The README's "everyone helps grab the milk" implies a shared household with multiple members — i.e., the scope unit is the *household*, and members within it still share everything. Confirm, because it changes the entire schema.
- Is multi-tenant **same-deployment** (one DB, many households — needs all of the above) or **per-install** (each household self-hosts its own box — needs almost none of it)? This is the single biggest descoping lever. The self-hosted/desktop-app framing suggests per-install might be the actual intent, which would make most of this moot — worth settling first.
- Shared catalogs (stock levels, locations) across households, or per-household copies?

### 5.1 Decision — Kivy P2P sync branch has no home here (FU-363 item 5, 2026-07-15)

**Question (owner feedback, 06-Jun-2026):** *"Looking at my kivy P2P test branch, does this
have any home in the current app? My vision was for standalone no-server installs to link and
communicate (syncing data)."*

**Decision: CUT / park as a separate experiment — it does not fold into Dora-core.** Rationale:

- **Architectural mismatch.** Dora-core is **client-server**: one Flask API + one datastore
  (SQLite/Postgres), many clients. The Kivy P2P vision is **serverless multi-master
  replication** — N independent installs, each authoritative, reconciling by sync. That is a
  different product shape, not an increment on the current one. Adopting it means
  conflict-resolution (CRDTs / vector clocks / last-writer-wins) across *every* mutable
  entity — the single largest architectural commitment the app could take on, for a feature
  no current feedback bullet other than this one asks for.
- **The need it targets is already met by the existing model.** "Standalone installs that link
  and communicate" is the multi-**user** / shared-household need. Dora already answers that the
  client-server way: multiple users point at **one** instance (self-hosted or managed), and the
  planned scoping work (§2 of this doc) makes that safe. You get shared pantry/lists/alerts
  without any P2P layer. Two *separate* installs syncing is strictly harder and buys nothing the
  one-instance model doesn't already give.
- **Cuts against the distribution posture (§7.5 / Decision 5).** The posture is *one artifact,
  one datastore target, don't pre-build multi-tenancy*. A P2P sync engine is exactly the kind of
  speculative, hard-to-reverse infrastructure that posture exists to keep out of core until a
  real, validated demand forces it.
- **Charter.** Effortless (P1) + Anti-creep (P10): a sync engine is heavy machinery whose
  failure modes (partial syncs, merge conflicts surfaced to a non-technical pantry user) are the
  opposite of effortless.

**If the underlying want ever resurfaces**, the cheaper paths in priority order are: (a) point
both households at one managed/self-hosted instance (today's model); (b) the Phase-4
same-deployment multi-tenant path (§2 above); (c) only then, if genuinely serverless-offline
sync is proven necessary, revisit P2P as its own project feeding Dora via `/api/ingest`-style
seams — never as a core rewrite. The Kivy branch stays an archived personal experiment, not a
Dora-core workstream.
