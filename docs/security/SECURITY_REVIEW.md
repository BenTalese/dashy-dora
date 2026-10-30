# Dora Security Review

**Standing audit.** Rebuilt against the P5-01 rubric from
`docs/06_legacy_prompt_plans/PROMPT_PLAN_PART_5_OPTIONAL.md` — six
buckets (auth & sessions, authorization, secrets, data privacy,
uploads, dependencies). This document is the artefact the P5-01
sweep produces; when a section here contradicts a running-code
observation, trust the code and update the section.

- **Baselined:** 2026-07-09 (FU-387 sweep — sessions 1 + 2).
- **Reviewer:** internal (single-maintainer project pre-release).
- **Threat model:** self-hostable single-household product following
  the "GitLab way" — one codebase runs as a self-hosted single
  instance, a managed single-tenant instance (Path B), or (deferred)
  a multi-tenant SaaS (Path A). No user-vs-user isolation surface
  inside a household by design (everyone shares stock, lists,
  recipes, plans). Admins are trusted.
- **Overall verdict:** healthy pre-release posture. All high-risk
  legacy findings resolved (FU-197 auth chain, FU-459 headers,
  FU-515 assistant hardening). Dependency baseline clean after the
  FU-387 bump; two low-severity dev-only Windows-only transient
  frontend items remain, accepted with rationale (§6).

Related standing docs:
- `docs/05_investigations/AUTH_ASSISTANT_SECURITY_FINDINGS.md` — the
  per-finding register for the auth + assistant surfaces. Read that
  alongside §1 and §7 below.
- `RECONCILED_FINISHING_PLAN.md` §7 — distribution/tenancy posture
  decisions that shape §2 and §7.

---

## 1. Auth & sessions

| Control | State | Notes |
|---|---|---|
| Password hashing | ✅ pinned scrypt | `hash_password()` in `dora_api/infrastructure/auth_helpers.py` — `method="scrypt:32768:8:1"` explicit so a werkzeug pin bump can't silently change the KDF. All eight call-sites route through this helper (R-003). `check_password_hash` auto-detects the method embedded in the stored hash, so old hashes verify unchanged. |
| Session invalidation on password change | ✅ | `password_changed_at` snapshot in the session cookie, cross-checked in `get_me`. Reset-password revokes outstanding tokens (`revoke_tokens_for_user`). |
| Cookie flags | ✅ | `HttpOnly`, `SameSite=Lax`, `Secure` **defaults to True in production** (2026-07-09, FU-387 P1). Explicit `DORA_SECURE_COOKIES=false` opts out for LAN-behind-VPN installs; the choice is surfaced at boot by `warn_if_insecure_cookies_in_production()`. |
| CSRF | ✅ FU-197 | Hand-rolled double-submit cookie (`dora_csrf` + `X-CSRF-Token` header) in `infrastructure/csrf.py`. Enforced by middleware on every mutating `/api/*` request that isn't in `PUBLIC_ENDPOINTS` or the bearer-authenticated ingestion route. Dev-only bypass via `DORA_CSRF_DISABLED` — refused in production by `is_production()` guard. |
| CORS | ✅ | Pinned via `DORA_CORS_ORIGINS` in production (hard-required at boot by `validate_production_requirements`); dev falls back to a fixed localhost list. `supports_credentials=True` — never `origins='*'` alongside credentials. |
| Rate limits | ✅ | In-process token-bucket in `auth_helpers.rate_limit()` — used on login (5/min per IP), bootstrap (5/min), verify-email (10/min), resend-verification (1/min per address), assistant `/ask` `/act` `/confirm` (per-user, FU-458). |
| Password policy | ✅ | NIST SP 800-63B — 8-char min, no composition rules, breach-list reject (~60 top offenders including product-name variants). No admin override. |
| Anti-enumeration | ✅ | forgot-password + resend-verification return the same shape whether the email is known or not; `try_send` swallows SMTP failures so a "couldn't send" doesn't leak known-address status. |
| Bootstrap admin | ✅ FU-200 | First-user path is a separate endpoint (`/api/auth/bootstrap-admin`) that 410s once any user exists. Self-registration never grants admin, and is itself off by default (SEC-3, 2026-10-30: `AppSetting.registration_enabled`, admin switch on Settings → Users). |

**Accepted** (recorded in `AUTH_ASSISTANT_SECURITY_FINDINGS.md`):
- **A.5 admin password reset returns plaintext in the response.** Kept as the self-host fallback when SMTP isn't configured; admin is expected to relay out-of-band. Not a bug in the current threat model.
- **A.6 in-memory rate-limit store.** Process-local, fine for a
  single-worker / single-instance deploy. Revisit at Phase 4 if
  horizontally scaled; the swap target is a Redis-backed bucket keyed
  by the same `(scope, subject)` tuple. Cross-ref FU-045 +
  `MULTI_USER_READINESS.md`.
- **A.7 auth tokens in URL query strings.** Standard for email flows;
  mitigated by single-use + short expiry (`RESET_PASSWORD_TTL=1h`,
  `VERIFY_EMAIL_TTL=24h`).

---

## 2. Authorization

**Model.** Single-tenant / single-household by design (Charter — see
`RECONCILED_FINISHING_PLAN.md` §7). Entities without a `user_id` FK
(StockItem, ShoppingList, Recipe, MealPlan, etc.) are install-scoped
— every authenticated user in the household sees the same data.
Multi-tenant tenant_id is deliberately not built (Path A deferred).

Per-user overlays that must be personal even inside a household:
- `AlertInteraction` — read / snooze / dismiss decisions.
- `AlertPreference` — per-kind tier override.
- `PushSubscription` — one per device.
- `AuthToken` — reset / verify tokens.
- Various `User` fields — `dashboard_layout`, `budget_amount`,
  `llm_api_key_encrypted`, `show_assistant`.

These use consistent `EntityField(...).eq(user_id)` filters. Because
the "isolation" surface is small and the model is single-household,
there is **no user-vs-user e2e isolation test suite** — a boundary
that doesn't exist can't regress.

**Admin gate.** Single-source `require_admin()` helper in
`dora_api/features/auth/admin_gate.py` (FU-341); every admin route
uses it directly rather than reimplementing the check.

**Invite / share-link flows.** None. Not applicable at current
tenancy posture.

---

## 3. Secrets

| Control | State | Notes |
|---|---|---|
| SECRET_KEY | ✅ | `DORA_SECRET_KEY` env-first; dev falls back to a random `data/.secret_key` file so sessions survive restarts. Hard-required in production by `validate_production_requirements()`. |
| At-rest secret encryption | ✅ FU-153 / FU-333 | Fernet-wrap via `DORA_LLM_KEY_ENCRYPTION_KEY` for per-user LLM API keys, the install-wide SMTP password, and the VAPID private key. Desktop bundle auto-generates the key into the user-data dir on first launch. |
| `.env` handling | ✅ | `.env` and `.env.local*` gitignored (verified via `git ls-files .env` — untracked). `.env.example` present and annotated (FU-333). |
| Prod refuses unsafe defaults | ✅ | Missing `DORA_SECRET_KEY` / `DORA_CORS_ORIGINS` / `ADMIN_BOOTSTRAP_EMAIL` → the app exits non-zero at boot with a friendly multi-line stderr message (`validate_production_requirements`). Desktop bundle sets `DORA_SKIP_PROD_VALIDATION` because its required-vars story is different. |
| `DORA_ALLOW_DESTRUCTIVE` | ✅ | dev-only; refused in production regardless of value (`DoraConfig.is_dev_data_reset_allowed`). |

---

## 4. Data privacy

| Control | State | Notes |
|---|---|---|
| Audit-log payload scrubbing | ✅ | `dora_api/infrastructure/audit.py::_scrub` drops any payload key whose lower-cased name contains `password`, `token`, `secret`, `api_key`, `authorization`, `cookie`. Applied to every emit; login handler explicitly excluded from auto-audit because a wrong-password 200-with-body can't be distinguished from success at middleware level. |
| Backup credential exclusion | ✅ | `dora_api/features/data/restore_shared.py` `SECTIONS`. **User** section excludes `password_hash` + `llm_api_key_encrypted`. **AppSetting** section excludes `smtp_password_encrypted` + `vapid_private_key_encrypted`. Fernet-wrapped secrets never round-trip via backup even though ciphertext-alone isn't compromise (defence-in-depth against backup-plus-key exposure). Both sections are opt-in / off by default. |
| Backup format | ✅ | JSON, streamed through admin-only `data/uploads/*` chunked flow. Restore consumers reject foreign FKs / unknown sections at inspect time. |
| Assistant scoping | ✅ FU-515 | Tool-result injection mitigated by a system-prompt rule + control-byte stripping. Tool-arg bounds enforced (`push_expiry` day cap). `current_path` sanitised (`_safe_current_path`) + length-capped before being folded into the system prompt. Full triage in `AUTH_ASSISTANT_SECURITY_FINDINGS.md` §B. |
| Log content | ✅ | Login only logs the username on failed / succeeded events. No password / hash / token appears in application logs (verified by grep). Request bodies are only logged at DEBUG level and pass through the same audit-scrub key list on the way. |

**Not in scope for P5-01:** DSAR / privacy-page / export-my-data /
delete-my-account. Those belong to P5-02 (`FU-401`) and P7-08
(`FU-404`).

---

## 5. Uploads / imports

**Surface.** One chunked-resumable upload endpoint set at
`dora_api/features/data/uploads.py` — feeds admin backup restore and
admin spreadsheet import. Every endpoint (`/start`, `/chunk`,
`/finish`, `/abort`) calls `require_admin()`.

| Control | State | Notes |
|---|---|---|
| Auth | ✅ | Admin-gated on every endpoint (a leaked `upload_id` on its own can't write). |
| Size cap | ✅ | 2 GB total per session; oversized chunk truncated back to pre-write size so the session can still be resumed under the cap. |
| Path traversal | ✅ | `upload_id` is UUID-validated (`_is_valid_upload_id`) before being used to build a filename — no client-controlled string ever segments the path. Staged files live in a fixed dir under `data/uploads/` mode 0o600. |
| Type / mimetype validation | ➗ | Not enforced at the upload layer. Not a vulnerability at current usage (only the backup-restore / spreadsheet-import handlers consume these files, and they validate their own formats). If the endpoint is ever repurposed for non-admin uploads or file downloads, add magic-number + mimetype checks first. |
| Cleanup | ✅ | Every `/start` sweeps staged files older than 1 hour (`STAGE_TTL_SECONDS`). Best-effort; failure to unlink one file doesn't abort the sweep. |
| Image uploads | ✅ (different path) | Recipe / store / user / stock-item images are base64-in-DB as `data:image/…;base64,…`. No file-on-disk path; no filesystem traversal surface. Admin- or owner-gated at the entity endpoint. |

---

## 6. Dependencies

Baseline captured 2026-07-09 (FU-387 P7 + P8). Rerun with
`scripts/security-audit.sh` before releases.

### Python (`requirements.txt`)

**Bumped in this sweep:**
- `Flask-Cors` 4.0.0 → **6.0.0** — 7 CVEs across the 4.x line
  (PYSEC-2024-{71,260,271}, PYSEC-2026-{1383,1384,1385}). Call-site
  shape unchanged (`resources={r'/api/*': {…}}` still valid);
  behaviour smoke-tested (unlisted origin gets no `ACAO` header,
  allowed origin echoes correctly).
- `Flask` 3.0.2 → **3.1.3** — CVE-2026-27205.
- `Jinja2` 3.1.2 → **3.1.6** — five CVEs (PYSEC-2026-{1471,1472,1473,1474,1475}).
- `Requests` 2.32.4 → **2.33.0** — CVE-2026-25645.
- `pytest` 8.3.4 → **9.0.3** — PYSEC-2026-1845 (test-only).
- `pytest-asyncio` 0.25.3 → **1.4.0** — needed for pytest 9 compat.
- `typing_extensions` 4.9.0 → **4.16.0** — needed for pydantic 2.6 +
  qrcode compat under pytest 9.

**Current baseline:** `pip-audit -r requirements.txt --strict` → `No known vulnerabilities found`.

### Frontend (`web_app/`)

**Fixed via `npm audit fix` (lock-file only, no `package.json` change):**
- `form-data` — high, CRLF injection (transitive; runtime).
- `vite` — high, `server.fs.deny` bypass + `launch-editor` NTLMv2
  disclosure (both Windows-only, dev-time).
- `js-yaml` — moderate, quadratic-complexity DoS (dev-time).

**Accepted (still open):**
- `esbuild` 0.27.3–0.28.0 — **low**, arbitrary file read via
  dev-server on Windows only. Not applicable to Linux dev or any
  production surface (esbuild does not ship in the production
  bundle). No upstream fix available yet.
- `@quasar/app-vite` 2.5.0–2.6.2 — transitive on the esbuild above.
  Waiting on a Quasar release that pulls the fixed esbuild.

Both accepted items are **low severity, dev-only, Windows-only**. Recheck at every dep-bump pass; auto-fix when upstream Quasar cuts a release.

---

## 7. Follow-up register

Tracked separately in `DORA_FOLLOWUPS.md`:
- **[[FU-405]]** — CI ops. When CI is re-enabled at Phase 4, promote
  `scripts/security-audit.sh` to a scheduled job. Interim: manual invocation.
- **[[FU-409]]** — auth-findings delta re-audit before commercialisation.
  Distinct methodical walk; not folded into this sweep.
- **Hand-rolled-vs-library audit (ex-[[FU-510]], retired 2026-07-15 into
  [FINALISATION_PLAN.md](../01_charter/FINALISATION_PLAN.md) §3.3)** — includes
  the security-adjacent bits (CSRF impl vs Flask-WTF/SeaSurf, security headers vs
  Talisman, Fernet handling, password hashing). Runs as part of the finalisation
  plan; the security-adjacent `replace` verdicts spawn per-swap FUs at plan close
  (plan §7 DoD step 5).
- **[[FU-401]]** / **[[FU-404]]** — P5-02 privacy + P7-08 compliance.
  Own the DSAR / export / delete surface.

---

## 8. Standing controls checklist

Runbook — verify at every release:
- [ ] `pip-audit -r requirements.txt --strict` → clean.
- [ ] `cd web_app && npm audit` → no new high/critical, only the
  accepted low items from §6.
- [ ] `git ls-files .env` → empty (i.e. `.env` still untracked).
- [ ] Session cookie flags on a real request in prod: `HttpOnly`,
  `Secure`, `SameSite=Lax`.
- [ ] Every `require_admin` call-site still uses the shared helper
  (`grep -r require_admin dora_api/features/`).
- [ ] Backup section `excluded_columns` still cover `password_hash`,
  `llm_api_key_encrypted`, `smtp_password_encrypted`,
  `vapid_private_key_encrypted`.

---

## 9. History

- **2026-07-09 — FU-387 baseline.** This document created; SECURITY.md
  landed at repo root; `scripts/security-audit.sh` runner added;
  Python + frontend dep vulns triaged (see §6); `SESSION_COOKIE_SECURE`
  defaults to True in production; `hash_password()` helper pins scrypt
  method; backup `excluded_columns` extended to cover all three
  Fernet-encrypted secrets.
- Earlier resolved: FU-197 (CSRF + email-change), FU-447 (auth
  findings tier-1), FU-459 (security headers), FU-515 (assistant
  hardening B.1/B.3/B.4), FU-424 (senior-review Tier-2 gaps).
