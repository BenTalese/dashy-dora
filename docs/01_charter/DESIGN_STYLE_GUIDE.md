# Dashy Dora — Design Style Guide (D-rules)

**Status:** authoritative — adopted 2026-07-18, strengthened 2026-07-19 (owner
directive: "make it more well-defined and leave less guess-work"). **Scope:**
every task that adds or changes anything a user sees. This is the *usage*
companion to `ENGINEERING_STANDARDS.md` R-002 (which owns the tokens-only
mechanics): R-002 says colour comes from tokens; **this doc says which token,
what size, how much space, what shape, and what the finished thing must look
like.**

**How to read this doc.** It is prescriptive, not suggestive. When a value or
token appears in a table here, **use it exactly** — do not invent a neighbouring
value, do not hardcode the resolved number, do not "round to what looks right".
The tables in **Part A (Foundations)** and **Part B (Components)** are a lookup:
building a card? go to B4 and copy the spec. The **D-rules (Part C)** are the
enforceable checklist R-035 runs at the close-gate. A deviation from any stated
value is a **carve-out** and follows the R-002 discipline: fix it, comment it in
place naming the rule (`// D-0NN carve-out: <reason>`), or log a
`DORA_FOLLOWUPS.md` finding. "It looked fine" is not a carve-out.

**How to use (agents):** on any UI-affecting task, check the change against the
D-rules the same way you check R-rules. When a design decision recurs that this
doc doesn't cover, propose a new D-rule at close-gate (same promotion path as
ADRs). Existing-screen violations are backlog, not licence —
`docs/04_proposals/DESIGN_REMEDIATION_PLAN.md` tracks them; new work complies
from the start.

**Source of truth for values:** `web_app/src/css/tokens.scss` (raw scales +
semantic defaults), `themes.scss` (per-theme overrides), `motion.scss` (timing),
`colours.scss` (utility classes). The px numbers below are computed at the
**16px default base**; the base is user-scalable, so **always ship the token, not
the px** — the px is for your judgement, the token is for the code.

---

# Part A — Foundations (the concrete spec)

## A1 · Colour — role → token map

Never pick a colour by eye. Pick it by **role**, then use that role's token.

### Text
| Role | Token | Use for |
|---|---|---|
| Primary text | `--text-primary` | headings, body, values the user reads |
| Secondary text | `--text-secondary` | supporting text, labels, metadata that must stay legible |
| Muted text | `--text-muted` | de-emphasised captions/timestamps **only** — never an actionable value (D-003) |
| On brand | `--text-on-primary` | text on a primary-filled button/surface |
| On accent | `--text-on-accent` | text on the accent (yellow) surface |
| On toolbar | `--text-on-toolbar` | text/icons in the top header |

### Surfaces (the elevation ladder — pick by depth, A5)
| Role | Token | Use for |
|---|---|---|
| Page | `--surface-page` | the app background |
| Component | `--surface-component` | cards, panels, list rows, dialogs — the default "thing on the page" |
| Elevated | `--surface-elevated` | menus, popovers, a card that floats above other cards |
| Sunken | `--surface-sunken` | wells, inset fields, the muted background of a neutral chip |
| Toolbar | `--surface-toolbar` | the top header only |

### Brand
| Role | Token | Use for |
|---|---|---|
| Primary | `--brand-primary` | the single primary CTA per view, active-nav indicator, brand marks |
| Primary soft | `--brand-primary-soft` | tint background behind primary-toned chips/highlights |
| Secondary | `--brand-secondary` | secondary emphasis, toolbar default, links where primary would over-shout |
| Accent (fill) | `--brand-accent` | sparingly — highlights, the wordmark, the toolbar's own ground; **not** a second CTA colour, and **not** as ink on a light surface (R-069) |
| Accent (ink) | `--accent-ink` | accent-coloured **text** sitting on page/component surfaces, however short — the accent hue held to this doc's 4.5:1 floor in every theme. Template-side helper: `.dora-text-accent` |
| Accent (mark) | `--accent-mark` | the same hue at the **3:1** floor, for the things D-002 grades at 3:1: *icons, hairlines, borders, outlines, active-state indicator bars*, and large display text (≥24px / ≥18px bold). ~7 lightness points brighter than the ink tier in every light theme; the dark themes point it at `--brand-accent`. Never use it for body text (owner, 2026-09-03) |

### Semantic (meaning, not decoration — constant across themes)
| Meaning | Fill token | Soft-bg token | Use for |
|---|---|---|---|
| Positive / success / stocked | `--semantic-positive` | `--semantic-positive-soft` | success toasts, Stocked level, "good" scores |
| Warning / low / caution | `--semantic-warning` | `--semantic-warning-soft` | Low-stock level, "fair" scores, non-blocking warnings |

**Warning ink:** the warning fill is a fill. As text or a glyph on a page,
component or soft ground use `--semantic-warning-ink` (held at 4.5:1 in every
light theme; the dark themes pass the fill through). Quasar's `text-warning`
class is routed to it. `--severity-attention-ink` is the same tier for the
attention tone (FU-986).
| Negative / danger / out | `--semantic-negative` | `--semantic-negative-soft` | Out-of-stock level, destructive actions, errors |
| Info | `--semantic-info` | `--semantic-info-soft` | neutral informational callouts |

**Soft-token rule:** a `-soft` token is a **background** only. Text/icons on a
soft background use the **full-strength** semantic token, never the soft one
(that is the D-002 badge failure). E.g. a Low chip = `background:
--semantic-warning-soft; color: --semantic-warning-ink` (warning is the one
semantic whose fill is too light to be ink; see Warning ink above).

### Ordinal severity (when rank matters, not just meaning)
`--severity-critical` > `--severity-high` > `--severity-medium` >
`--severity-low`; `--severity-attention` for grabby-not-alarming. `--severity-low`
is the FYI tier and aliases `--semantic-info` (blue), so it never reads as a
shade of medium's orange. Alert-kind
categorical accents (`--alert-kind-*`), lifecycle accents (`--lifecycle-*`), and
the 6-hue chart palette (`--chart-1..6`) are the only sources for those
surfaces — never Quasar numbered palette classes (`red-6`, `amber-9`), which
R-002 forbids.

### Borders, focus, overlays
| Role | Token |
|---|---|
| Default border / card outline | `--border-default` |
| Strong border (emphasis, hover) | `--border-strong` |
| Divider (in-card separators) | `--divider` |
| Focus ring (outline or halo) | `--focus-ring` — the only focus token. Resolves to `--primary-ink`, so it clears D-002's 3:1 non-text floor on every surface in every theme (`--brand-primary` measured 1.35–2.34:1 in Lemon Tart / Sourdough light). The old `--ring-focus` 35–45 % wash was retired 2026-11-04 (FU-941): all eight uses painted it as a 2px outline, where a wash can't reach 3:1 |
| Scrim (modal backdrop) | `--overlay-scrim` |
| Hover veil (on page) | `--overlay-hover` · on coloured surfaces `--overlay-hover-on-coloured` |
| Active veil | `--overlay-active` · on coloured `--overlay-active-on-coloured` |

## A2 · Typography — role → size/weight/colour map

Font family is **Nunito Variable** (set on `body`; don't re-declare it). Weights
via Quasar classes: `text-weight-regular` (400), `text-weight-medium` (600),
`text-weight-bold` (700). Sizes are the `--font-size-*` **unitless ratios** —
apply as `calc(var(--font-size-x) * 1rem)` or the matching Quasar `text-*`
class; never a raw px font-size.

| Role | Size token | px@16 | Weight | Colour |
|---|---|---|---|---|
| Page / hero number | `--font-size-3xl` | 30 | bold | `--text-primary` |
| Page title (`h1`) | `--font-size-2xl` | 24 | bold | `--text-primary` |
| Section header (`h2`/card title `h3`) | `--font-size-xl` | 20 | bold | `--text-primary` |
| Sub-header / large emphasis | `--font-size-lg` | 18 | medium–bold | `--text-primary` |
| Body (default) | `--font-size-md` | 16 | regular | `--text-primary` |
| Secondary body / labels | `--font-size-sm` | 14 | regular–medium | `--text-secondary` |
| Caption / timestamp / metadata | `--font-size-xs` | 12 | regular | `--text-muted` |

**Hard floor: `--font-size-xs` (12px). Nothing smaller, ever** (D-003). The
floor is for non-actionable captions; any value the user acts on (price, count,
badge label, button text) is `--font-size-sm` (14) or larger. Numbers that are
the point of a card (score, total, count) get **bold**. Line-height ≥ 1.35 for
body, ≥ 1.2 for large display text. Don't set letter-spacing except on small
all-caps eyebrow labels (`+0.04em`).

## A3 · Spacing — context → token map

The scale is `--space-1`(4) `-2`(8) `-3`(12) `-4`(16) `-5`(20) `-6`(24) `-8`(32)
`-10`(40) `-12`(48). Everything spatial snaps to it (Quasar `q-pa-*`/`q-gutter-*`
roughly map to space-2/3/4/6/8). **No off-scale margins/paddings** (no 5px,
13px, 18px).

| Context | Token | px@16 |
|---|---|---|
| Icon↔label gap, tight inline | `--space-1` | 4 |
| Chip padding, dense inline gap | `--space-2` | 8 |
| Related controls in a row, list-row inner gap | `--space-3` | 12 |
| **Card / dialog / panel inner padding** | `--space-4` | 16 |
| Between form fields | `--space-4`–`--space-5` | 16–20 |
| **Between cards / between sections in a page** | `--space-6` | 24 |
| Major page-region separation | `--space-8` | 32 |
| Page outer margin (desktop) | `--space-6`–`--space-8` | 24–32 |

Consistency beats cleverness: a card's inner padding is `--space-4` **on all
four sides** unless the component spec says otherwise. Vertical rhythm inside a
card uses one gap value (`--space-3` or `--space-4`), not a different number per
pair of elements.

## A4 · Radius — element → token map

| Element | Token | px |
|---|---|---|
| Chips, small badges, tags | `--radius-sm` | 4 |
| Buttons, inputs, menu items | `--radius-md` | 6 |
| **Cards, panels, dialogs** | `--radius-lg` | 10 |
| Large feature surfaces, hero, bottom sheets | `--radius-xl` | 16 |
| Modal on mobile / prominent container | `--radius-2xl` | 22 |
| Pills (toggle groups, status pills) | `--radius-pill` | 999 |
| Avatars, dots, circular icon buttons | `--radius-full` | 50% |

One element type = one radius across the whole app. A card is `--radius-lg`
everywhere; don't ship a 8px card here and a 12px card there.

## A5 · Elevation & surface layering

Depth is expressed by **surface token + shadow together**, and they must agree —
a floating thing gets a lighter surface *and* a bigger shadow.

| Layer | Surface | Shadow | Examples |
|---|---|---|---|
| Flat on page | `--surface-component` | `--elevation-card` | cards, list rows, panels |
| Card hover | `--surface-component` | `--elevation-card-hover` | interactive card raise |
| Low float | `--surface-elevated` | `--elevation-2` | dropdown menus, popovers |
| High float | `--surface-elevated` | `--elevation-3` | dialogs/modals |
| Inset | `--surface-sunken` | none (inset look, optional inner border) | wells, neutral chips |

Rules: (1) **never stack two `--surface-component` cards with no separation** —
either a gap (`--space-6`) or a nested well (`--surface-sunken`). (2) Modals sit
on `--surface-elevated` + `--overlay-scrim` backdrop. (3) Don't invent shadows;
the five `--elevation-*` tokens are the whole vocabulary.

## A6 · Borders & focus

- Card/panel outline: `1px solid --border-default` (or shadow-only — pick one
  per surface, don't double up a heavy border **and** a heavy shadow).
- In-card separators: `--divider`, `1px`.
- Hover/emphasis border: `--border-strong`.
- **Focus is always visible.** Every interactive element shows a focus ring on
  keyboard focus: `outline: 2px solid --focus-ring; outline-offset: 2px`, or —
  where an outline would be clipped — a `0 0 0 3px --focus-ring` box-shadow.
  One token, one colour: no softened wash (it fails 3:1). Never `outline: none`
  without a replacement.
  This is not optional and not theme-dependent.

## A7 · Iconography

- Library: Quasar Material icons via the `ICONS` map in `src/style/icons.ts` —
  reference `ICONS.*`, never a raw string literal, so the set stays audited.
- Sizes: inline-with-text `1em`; standalone control icon **20px**; icon-button
  glyph **20–24px** inside a ≥44px target (A8/D-004); large empty-state/feature
  icon 32–48px.
- Colour: inherits `currentColor` — set the parent's text-colour token, don't
  colour the icon directly.
- Metaphors read in the **food/kitchen domain**. Never a security/system glyph
  for a domain state (padlock ≠ sealed; gear ≠ a pantry action). One glyph = one
  meaning app-wide (D-005).

## A8 · Breakpoints, targets & density

- Breakpoints (Quasar): **phone** < 600 · **tablet** 600–1023 · **desktop**
  ≥ 1024. Design mobile-first; the layout must hold from **360px** up with **no
  horizontal page scroll** (D-011). **The grid class for the app's desktop tier
  is `col-md-*`** — Quasar's `lg` is ≥ 1440 and is *not* one of Dora's tiers, so
  a `col-lg-*` rule does nothing on an ordinary laptop (FU-836).
- **Touch target minimum: 44×44px** effective (visual + padding) on any surface
  a finger uses. 32–36px dense controls are allowed *only* in desktop-only
  chrome. The 50×50 in-store tick box is the reference for a gesture that matters
  (D-004).
- Reading width: body text columns cap at ~72ch; don't run prose the full width
  of a wide desktop.
- Density: list rows ≥ 44px tall on touch; a comfortable stock/list row is
  ~56–64px. Don't pack rows tighter than 44px on primary surfaces.

---

# Part B — Component specs

Each spec is the **default**. A component may extend it; it may not silently
contradict it. Build from Quasar primitives, then apply these — do not accept
Quasar's raw defaults (casing, sizing, shadows) unstyled.

## B1 · Buttons
- **Primary** (filled): `--brand-primary` bg, `--text-on-primary`, `--radius-md`,
  `text-weight-medium`, **sentence case** (`no-caps`), min height **44px** on
  touch (36px desktop-dense chrome only), horizontal padding `--space-4`. **One
  primary button per view/section** — everything else is secondary/ghost.
- **Secondary** (outline): `1px --border-strong`, `--text-primary`, transparent
  bg; same geometry as primary.
- **Ghost/flat** (`flat`): text-only, `--brand-primary` or `--text-secondary`;
  for tertiary/inline actions.
- **Destructive:** `--semantic-negative`; **never the default-focused** button
  in a dialog.
- **Disabled:** reduced opacity **and** not focusable; must read visibly
  disabled (the bulk-bar failure, D-008/D-016).
- Icon-only buttons: see B-note + D-005 (aria-label **and** tooltip, always).

## B2 · Chips & badges
- Radius `--radius-sm` (or `--radius-pill` for status pills); padding
  `--space-1` vertical / `--space-2` horizontal; text `--font-size-sm`
  (**never below 14px if it carries a value** — D-003).
- **Semantic chip:** `-soft` background + full-strength semantic text (A1).
- **Neutral chip:** `--surface-sunken` bg + `--text-secondary`.
- A chip that encodes a state must be decodable — labelled, tooltip'd, or in a
  legend (D-013). Don't ship a bare coloured dot as the only signal.

## B2a · Segmented & toggle groups
- **One choice of several → `BaseSegmented`** (a `radiogroup`: roving tabindex,
  arrow keys move and select; `dense` for compact chrome, `spread` to share the
  full width — FU-848 merged the old `settings/DoraSegmented` into it). Small,
  mutually-exclusive vocabularies only (2–4 options); anything longer is a
  select.
- **Several independent choices at once → `BaseToggleGroup`.** A labelled row of
  card-sized toggle buttons plus a **Select all / Clear all** control that flips
  its own label to whichever action applies. Cards: `--radius-lg`,
  `--space-2`/`--space-3` padding, **44px minimum** either dimension (D-004),
  optional caption line under the label at `--font-size-xs`/`--text-muted`. The
  row wraps (`flex-wrap`) — it never h-scrolls (D-011).
- Selected = `--brand-primary` fill + `--text-on-primary`. Both components carry
  the full state set (hover / active / focus-visible / disabled / selected,
  D-016). `BaseSegmented` exposes `aria-checked` per option (radio semantics);
  `BaseToggleGroup` exposes `aria-pressed` (independent toggles).
- **Options that can't be chosen stay in place, disabled + tooltip'd** — don't
  filter them out. A row that reflows as options drop away costs the user their
  spatial memory (the meal-plan builder's past weekdays are the reference case).
- Reference consumer: `MealPlanBuilderDialog` (days row + meal-slots row).

## B3 · Inputs & form fields
- Quasar `outlined`, `--radius-md`, min height **44px**, label always present
  (placeholder is not a label), `--font-size-md` text.
- Helper/hint text `--font-size-xs` `--text-muted`; error text
  `--semantic-negative`.
- **Validate on blur/submit, not on pristine mount** — no "Username is required"
  before the user has typed (FU-578 #37, D-016).
- Focus state per A6.

## B4 · Cards & panels
- `--surface-component`, `--radius-lg`, `--elevation-card`, inner padding
  `--space-4`, `--space-6` gap between sibling cards.
- Header: title at section-header role (A2: `--font-size-xl` bold), optional
  right-aligned action/trend chip. Body uses one vertical rhythm value.
- Interactive cards raise to `--elevation-card-hover` on hover and show a focus
  ring; the **whole card is one target** (don't nest independent click zones
  that fight the card click).
- **No lone half-width card beside dead air** — a single card in a 2-col row
  goes full-width (D-011).

## B5 · List rows (stock, shopping, etc.)
- Min height 56–64px touch; inner gap `--space-3`; the row is the navigation
  target (and, ideally, a real link for middle-click — FU-578 #18).
- Trailing actions: cap at what fits without truncating the primary label; on
  phone collapse extras into an overflow menu rather than clipping the name
  (FU-578 #15b, D-011).
- State coding (edge/tint/level colour) follows A1 semantics (level =
  green→amber→red, D-001) and is documented in a legend (D-013). Late-arriving
  chips render into **reserved space** — no reflow on load (D-007).

## B6 · Dialogs & modals
- `--surface-elevated`, `--radius-lg` (`--radius-2xl` full-width mobile sheet),
  `--elevation-3`, `--overlay-scrim` backdrop, inner padding `--space-4`–`-6`.
- **Title** at section-header role. **Sentence-case buttons**, right-aligned,
  primary action last.
- **Every dialog: an explicit close (Cancel/✕) AND Escape-to-close AND
  backdrop-dismiss, and dismissing applies NO mutation** — mutate on confirm
  only (the open-toggle trap, D-008). Destructive confirm is red and not
  default-focused.

## B7 · Toasts & notifications
- Bottom-anchored, single column, `--radius-md`, `--elevation-2`, semantic
  colour by kind (success `--semantic-positive`, error `--semantic-negative`,
  info neutral).
- Auto-dismiss **≤5s**; **≤8s** if it carries an Undo; **dismiss on route
  change** — never let a toast outlive the screen that raised it (FU-578 #41).
- Bottom-right is a **single-occupancy zone** shared with the helper mascot
  (D-009): toasts stack in one column, the mascot docks clear of them, neither
  overlaps page content or controls.

## B8 · Menus & dropdowns
- `--surface-elevated`, `--radius-md`, `--elevation-2`; items min height 44px
  touch, `--space-2`/`-3` padding, hover = `--overlay-hover`.
- Selected item shows a check; destructive items are `--semantic-negative`.

## B9 · Empty states
- Anatomy: feature icon (32–48px, muted) · one-line what-goes-here · optional
  one primary action. Copy is Dora's voice (D-014), calm and specific ("Once
  you've restocked the same things a few times, I'll flag what to keep an eye
  on."), never a bare "No data".
- **Don't offer an action that lands on another empty/data-gated surface** on a
  fresh account (FU-578 #39); prefer a "fills in as you use Dora" caption.

## B10 · Skeletons & loading
- Any async surface >150ms shows a **skeleton shaped like its content**
  (Quasar `q-skeleton` blocks matching the real layout) — **never the literal
  string "Loading…"**, never a blank pane (D-007).
- Content arriving after first paint fades in within reserved space; it must not
  reflow neighbours (belief chips, verdict badges).
- A blocking full-screen loader (splash) must dismiss on a **timeout/event**,
  never solely on a transition that assumes paint (the splash-wedge, D-010).

## B11 · Tables & data grids
- Only when tabular; otherwise use list rows (B5). Right-align numbers, left-align
  text, header row `--text-secondary` `--font-size-sm` medium, zebra via
  `--surface-sunken` at low opacity, row height ≥ 44px. Wide tables scroll inside
  their own container — never the page (D-011).

## B12 · The helper / floating layer
- The Dora mascot + tip bubble are a docked FAB-style layer with safe-area
  insets, **behind/below** the toast column, and never overlapping interactive
  content (Level controls, calendar cells, ingredient lists — FU-578 #6/31). The
  panel's content is good; the entry point must not squat on the app. Any badge
  on it must have a defined meaning (no unexplained "6").

---

# Part C — D-rules (the enforceable checklist)

> D-001…D-015 numbering is stable — R-035, ADR-031 and the remediation plan
> reference it. New rules append as D-016+. A retired *clause* is struck from
> its rule in place with the reason (see D-015); a retired *rule* keeps its
> number and is marked retired, so nothing renumbers.

### D-001 — Stock-level colour semantics: green → amber → red; grey = unknown only
- **Rule:** Level/status colour escalates with urgency: Stocked =
  `--semantic-positive` (green), Low = `--semantic-warning` (amber), Out of stock
  = `--semantic-negative` (red). Grey/muted (`--text-muted`) is reserved for "no
  data / unknown / disabled" and must **never** represent a real level.
- **Why:** the audit found Out rendering grey — the worst state read *calmer*
  than Low (red), and grey level squares were indistinguishable from disabled
  rows (FU-578 #33). Alerts and buy-verdict already escalate amber→red.
- **Check:** any status→colour mapping derives from `stock_status` semantics and
  uses the A1 semantic tokens; screenshot both themes.

### D-002 — Contrast floors are non-negotiable
- **Rule:** body/secondary text **≥ 4.5:1** against its resolved background; large
  text (≥ 24px, or ≥ 18px bold) **≥ 3:1**; UI-component/graphic boundaries
  **≥ 3:1**. Text on a `-soft` chip uses the **full-strength** semantic token, not
  the soft one (A1). Never place text below 4.5:1 on an interactive element.
- **Why:** the light-mode muted ramp measured 3.0–3.7:1 across footer stats,
  chips, captions; BUY badge 2.5:1 at 11px (FU-578 #7). "Muted" means
  de-emphasised, not illegible.
- **Check:** compute the ratio (the drive.mjs eval probe from the 2026-07-18
  session is the reusable recipe) for every new text/background pair in **both**
  modes and **all five** theme families.

### D-003 — Type floor: 12px, and it's for captions only
- **Rule:** no text below `--font-size-xs` (12px@base). The floor is for
  non-actionable captions/timestamps/metadata. **Anything the user acts on or
  reads as data** — prices, counts, badge labels, button text, level names — is
  `--font-size-sm` (14px) **or larger**, and card-defining numbers are bold.
  Follow the A2 role table; don't default secondary UI to the floor.
- **Why:** 11px acting labels (BUY badges) and floor-size text used as the
  default for secondary UI (FU-578 critique §4).

### D-004 — Tap targets: 44px minimum on touch surfaces
- **Rule:** interactive elements on primary surfaces are **≥ 44×44px** effective
  target (A8). Dense 32–36px controls only in desktop-only chrome or where the
  row itself is the target. Reference: the 50×50 in-store tick box.
- **Why:** charter audience is pantry/mobile; the audit measured 32–36px across
  stock rows and toolbars (FU-578 #19).

### D-005 — Icon-only controls: accessible name + tooltip, domain-true metaphor
- **Rule:** every icon-only button ships `aria-label` **and** `<q-tooltip>` — no
  exceptions. Glyphs come from `ICONS` (A7) and read in the food/kitchen domain;
  never a security/system metaphor for a domain state (padlock-as-sealed is the
  canonical violation). Two glyphs may not share a meaning axis (cart vs
  cart-plus) without an explicit state cue (colour + tooltip).
- **Why:** FU-578 #3 (unlabelled open-toggle), #15c (padlock), #34 (cart glyphs).

### D-006 — One date/number formatting authority
- **Rule:** all user-facing dates/times/currency go through the single shared
  formatter (household locale + timezone aware). Components never call
  `toLocaleDateString`/hand-format. Relative phrases ("3 days ago") come from the
  same module. **No "(s)" pluralisation** — branch and write both forms.
- **Why:** three simultaneous date formats ("7/17/2026", ISO, "Mon, Jul 13") and
  "(s)" plurals (FU-578 #9/10/32/51). R-021 owns *which* day; this owns *how it
  reads*.

### D-007 — Loading: skeletons, not words; reserve space for late content
- **Rule:** async surfaces >150ms show a content-shaped skeleton (B10) — never
  "Loading…", never a blank pane. Late-arriving content renders into reserved
  space or fades in without reflowing neighbours.
- **Why:** dashboard cards showed "Loading totals…" text while list pages had
  skeletons; belief chips popped in and shifted rows (FU-578 #15/52).

### D-008 — Button & dialog conventions
- **Rule:** **sentence case everywhere** (`no-caps`); never Quasar's UPPERCASE
  default. Every dialog has an explicit close (Cancel/✕) **and** Escape-close
  **and** backdrop-dismiss, and **dismissal applies no mutation** (mutate on
  confirm — the open-toggle trap). Destructive confirms are red and never the
  default-focused action. Follow B1/B6.
- **Why:** casing drift ("SKIP / UPDATE EXPIRY" vs "Restock & finish") and the
  no-cancel expiry dialog were raw Quasar defaults (FU-578 #2).
- **Carve-out (owner, 2026-08-08):** the sentence-case rule governs *interactive
  controls* — buttons, dialog actions, chips, form labels. **Page/route titles use
  Title Case**: the mobile menu-bar header and browser-tab title (route `meta.title`
  in `web_app/src/router/routes.ts`) capitalise every principal word ("Stock Item",
  "Price History", "System: Alert Thresholds"). This is the one deliberate exception
  to "sentence case everywhere"; don't revert these to sentence case.

### D-009 — Toasts & floating chrome respect a placement budget
- **Rule:** bottom-right is single-occupancy — one toast column, mascot docked
  clear, nothing overlapping page content or controls. Toasts auto-dismiss ≤5s
  (≤8s with Undo) and **die on route change**. Floating elements honour mobile
  safe-areas. Follow B7/B12.
- **Why:** toasts + tip bubble + mascot + badge quadruple-booked; the bubble
  covered Level controls/calendar cells/ingredient lists; a toast survived
  navigation (FU-578 #6/31/41).

### D-010 — Micro-feedback on high-frequency actions; motion tokens or nothing
- **Rule:** the repeated gestures (level change, tick, add-to-list, chip toggle)
  give **≤ `--motion-fast` (120ms)** visual feedback (settle/scale/count-bump)
  with `--motion-ease`. All animation reads `--motion-*` tokens — **no literal
  `ms`**. No animation on per-keystroke/scroll churn. Anything gating *dismissal*
  of a blocking surface has a non-paint fallback (D-007/B10).
- **Why:** motion tokens exist but the most-touched interactions have zero
  feedback; the splash wedged when paint was throttled (FU-578 #23/26).

### D-011 — Page composition: no stranded cards, no non-wrapping toolbars, no page h-scroll
- **Rule:** 2-column card grids define collapse behaviour — a lone card goes
  full-width (or the grid packs); no card beside dead air. Toolbar/action rows
  wrap or collapse into a More menu. **No horizontal page scroll from 360px up**
  (wide content scrolls inside its own container). Page titles never collide with
  actions. Follow A3/A8/B4.
- **Why:** dashboard/reports dead zones; the 930px shopping-list toolbar
  overflowing mobile and colliding with its title at 1280px (FU-578 #4/30/40).

### D-012 — Data-dense widgets earn their area
- **Rule:** a visualisation carries information proportional to its footprint.
  Calendars label/count their cells (no bare 4px dots); a chart with <2 distinct
  values renders as a stat/list; long uniform event streams group repeats ("×50
  over 3 months") behind expansion. Charts read the `--chart-*` palette.
- **Why:** the alerts 14-day calendar, meal-plans mini-month, solid-block "Meals
  cooked" chart, the 6,500px history wall (FU-578 #28/29/32/50).

### D-013 — Colour-coded states get a legend
- **Rule:** any surface using colour/edge/tint coding for states exposes the
  mapping in-UI — a legend (filter panel) or tooltips on the coded element. A
  state with styling but no discoverable meaning is a defect.
- **Why:** stock rows spoke a consistent private colour language nobody was told
  (FU-578 #44); one undecodable state (dimmed row) read as a bug.

### D-014 — Copy voice: Dora's, everywhere
- **Rule:** copy is warm, concrete, first-person-Dora where natural (the register
  of the onboarding scenes and empty states). **No dev leakage:** no raw UUIDs,
  no username as a display name without casing, no "(file)"-style parentheticals,
  no internal jargon ("batch cooking covers several days", not "cook-pool
  controls"). Personalisation uses the display name.
- **Why:** the app has a distinctive voice in its best surfaces; the tells
  ("Add (file)", raw UUID, "Good afternoon, dora") are where it lapsed
  (FU-578 #12/13/21/38).

### D-015 — Pattern reuse: one anatomy per job
- **Rule:** new surfaces reuse the established pattern rather than inventing a
  sibling: **card-runner** (stocktake/reconcile) for queue-walking; **colour-dot
  level picker** for level selection; **labelled sidebar** for section nav.
  Diverging is a recorded design decision.
- **Why:** the runner reuse is the app's consistency high-water mark.
- **Retired clause (owner, 2026-08-20):** this rule used to include
  "**read-view + explicit edit mode** for detail pages (never an
  always-editable form as 'detail')". That clause existed for exactly one
  surface — `RecipeDetailPage.vue`, the form-as-page from critique §8.1 — and
  that page has been replaced by the redesigned recipe detail
  (`RecipeDetailNext.vue`), which reads as a document and edits in place. The
  clause was **deleted rather than carved out**: keeping a rule whose only
  named counterexample no longer exists, and whose only flagship consumer
  contradicts it, teaches the next task to check its work against nothing.
  The three surviving clauses are about genuinely reused anatomies and are
  unaffected. **What still holds** for a detail page: an explicit commit
  (D-019's carve-out — inline edit is fine, silent autosave is not) and a
  reading surface that isn't a wall of inputs. See ADR-045.
- **Partially restored at block granularity (owner, 2026-08-23):** the recipe
  page's per-field popups were reversed — they cost two clicks on every dropdown
  and sized each control to its own content. A **region** with several editable
  values now gets one read↔edit switch (masthead, ingredients), while the page
  overall still reads as a document and prose still edits in place. The page-wide
  form-as-detail the original clause banned stays banned. This is **R-055 /
  ADR-051**; that rule, not this note, is the authority on the detail.

### D-016 — Interactive states are all defined and distinct
- **Rule:** every interactive element defines **all** of: default, hover
  (`--overlay-hover`), active/pressed (`--overlay-active`), **focus-visible**
  (A6 ring — mandatory, never `outline:none` bare), disabled (reduced opacity +
  not focusable + visibly inert), and selected/current where applicable. The
  states must be visually distinguishable from each other and from neighbours
  (the bulk-bar's white-on-white disabled buttons are the violation, FU-578 #53).
- **Why:** polish is mostly state feedback; missing/duplicate states read as
  broken or unresponsive.

### D-017 — Snap to the scales; no off-token values
- **Rule:** spacing snaps to `--space-*` (A3), radius to `--radius-*` (A4),
  shadow to `--elevation-*` (A5), font-size to `--font-size-*` (A2). **No
  off-scale literals** — no `margin: 5px`, no `border-radius: 8px`, no
  `font-size: 13px`, no hand-mixed `box-shadow`. One element type = one radius
  and one padding value app-wide (a card is `--radius-lg` + `--space-4`
  everywhere).
- **Why:** inconsistent ad-hoc values are the single biggest "assembled from
  snippets" tell; the scales exist precisely so this never has to be judged
  twice.

### D-018 — Alignment, density & rhythm are consistent within a surface
- **Rule:** within a view, related elements share a baseline/edge grid; labels
  and values align to a consistent axis; one vertical rhythm value governs a
  card's stack (A3). Numbers in a column right-align (B11); icons in a list share
  one x-position. Don't mix comfortable and dense rows in the same list without a
  reason.
- **Why:** ragged alignment and per-pair spacing read as unfinished even when
  every individual element is fine.

### D-019 — Never bind transient async state to `disable` on a focusable control
- **Rule:** a save/load flag (`saving`, `busy`, `pending`) must not drive
  `:disable` / `:disabled` on an **input, select, toggle, segmented control or
  any other focusable field**. Disabled elements are not focusable, so flipping
  the flag mid-interaction blurs whatever the user just moved into. Permanent or
  semantic reasons to disable a field are fine (`!installEnabled`,
  `!smtpConfigured`, `emailUnchanged`) — it is the *transient* flag that is
  banned. **Action buttons are the carve-out:** `:disable="saving"` on a
  submit/Save/Test button is correct double-submit protection, and losing focus
  on the button you just clicked is expected. Show in-flight state with
  `:loading` on the button, or the success toast — never by inerting the form.
- **Why:** blur-triggered autosave plus a page-wide `saving` flag makes it
  impossible to tab or click through several fields in a row: field A's blur
  starts the save, which disables field B a frame after the user lands in it, and
  focus is silently dropped. Reported by the owner 2026-08-07 against the settings
  pages ("you can't easily/smoothly edit multiple inputs in a row"); stock detail
  was unaffected precisely because it only gates *buttons* on `busy`.
- **Violation signal:** `:disable="saving"` / `:disabled="savingX"` on a
  `q-input`, `q-select`, `q-toggle`, `q-btn-toggle`, `BaseSegmented` or a
  custom field wrapper. Concurrency is not a reason to keep it — per-field
  PATCHes are independent, and a double-toggle is last-write-wins, which is
  already the behaviour the user asked for.

### D-020 — A brand colour used as an *indicator* reads from the indicator token
- **Rule:** when `secondary` has to paint a **mark against the page** — a row
  stripe, an active filter chip, a coloured count — read
  `--brand-secondary-strong`, never `--q-secondary` / `--brand-secondary`. The
  plain token is **surface-grade**: in every dark theme it is the toolbar
  *background*, so an indicator painted in it sits at the page's own lightness.
  Each dark theme overrides the `-strong` variant with a lifted tone; light
  themes inherit, because there the surface-grade colour already reads as a mark.
  Same discipline applies if a future brand colour picks up an indicator role —
  add the `-strong` sibling rather than reaching for the surface value.
- **Why:** measured 2026-08-16 across the five dark themes, the Essential row
  stripe / Essential + Open filter chips / Essential footer count sat at
  **1.45–4.74:1** against the sunken surface (cherry-cola-dark being effectively
  invisible); the same three marks now measure **7.31–8.48:1**. Reported by the
  owner as "too dark in dark mode" on two separate surfaces before the shared
  cause was found — a per-surface patch would have missed the third.
- **Violation signal:** `var(--q-secondary)` or `var(--brand-secondary)` in a
  `background`/`border-color`/`color` on something that is not a surface, or a
  Quasar `color="secondary"` / `text-secondary` class on a chip, badge or count.

### D-021 — Navigation is one flat level: named groups of destinations, never sub-headers
- **Rule:** a navigation surface (the Settings sidebar + its mobile tab strip,
  and any future nav of the same shape) has exactly **two levels — a group, and
  the destinations in it**. No third level: no indented sub-list under a
  non-clickable sub-header, no collapsible tree. Every group heading names a
  question the user is answering and **is itself a link** to that group's first
  destination. When a group gets long, **split it into two groups**; that is the
  only permitted response to length.
- **Why:** Admin had grown a `System` sub-header holding twelve of its sixteen
  pages under one "Admin · global" heading, so the whole surface read as an
  undifferentiated pile with an arbitrary indent partway down, and depth was
  communicated only by left-margin. Owner call 2026-08-17: *"logical groupings,
  one flat level"* — the same instinct that produced the Stock-locations zone
  cards (D-012) and the 2026-08-14 personal-settings regroup. The sub-group type
  was deleted from `SettingsNavGroup` along with its last caller, so the shortcut
  can't be taken again without deliberately re-adding it.
- **Violation signal:** a `subheader` / `children` / `items`-of-`items` shape in a
  nav definition; a nav row whose only distinguishing feature is `padding-left`;
  a group heading that isn't a link; a group with more than ~8 destinations
  (that's the split signal, not a nesting signal).

### D-022 — One typeface family per install: no page-specific display face
- **Rule:** every surface renders in the **user's chosen font** (Settings →
  Appearance → `themeService FONT_FAMILY_CSS`). A page may not introduce a
  typeface of its own — not for a title, not for a section label, not "just as
  a display face". Hierarchy is made with the **size / weight / letter-spacing
  / colour scales already in Part A**, which is what those scales are for. The
  font picker's list is the complete set of faces the app may render, and a
  face that isn't offered there must not be loaded at all.
- **Why:** the redesigned recipe page shipped with Fraunces on its title,
  section labels and ingredient-section captions, reasoned as "display face
  only, body still inherits the preference". The owner's verdict on seeing it
  in use (2026-08-24) was that the page *"just doesn't feel like it's the same
  app"* — which is the accurate read: a face nobody else uses reads as a second
  brand, and it silently overrides a preference the user set precisely because
  they wanted the app to look one way. It also costs a font download for one
  route.
- **Violation signal:** a `font-family` declaration anywhere outside
  `themeService` / the font-picker vocabulary; a `--*-display` custom property;
  a `@fontsource*` import for a face the picker doesn't offer.

### D-023 — A persistent control keeps its shape and its place across modes
- **Rule:** when a surface has modes (a shopping list's draft / shopping /
  receipt faces, cook mode's step / image views, an edit-vs-read flip), a control
  that exists in more than one of them must be the **same control in the same
  place**. Change what it *contains* — its label, its state, whether it's
  disabled — but do not re-home it, and do not swap a persistent control for a
  differently-shaped stand-in that does the same job. If a control genuinely
  doesn't apply in a mode, **remove it**; that is a different, honest thing from
  moving it somewhere else.
- **Why:** the shopping list hid its list picker (a dropdown on mobile, a side
  rail on desktop) the moment you started shopping, and grew a **"Switch list"**
  toolbar button in its place — the same capability, a different shape, a
  different place, at the moment the user is least able to go hunting for it. The
  owner's verdict (2026-08-28): *"this will only lead to confusion with UI
  elements shape shifting."* The stated reason for hiding it didn't survive
  contact either — "the rail is the widest thing competing for a phone's screen"
  was written about a `gt-sm` column a phone never rendered. Mode-conditional
  chrome is also how a control quietly goes missing in exactly one mode: the same
  page kept its shop day on a plan-face-only card, so a list you were **actively
  shopping** never showed which day it was for, and nobody noticed for months.
- **Apply:** before adding a mode-conditional stand-in, ask what the original
  control costs in that mode. Usually the answer is "nothing" and it should just
  stay. A control worth showing in two modes is worth showing in the same place
  in both. Check the inverse too: when something lives on a mode-specific
  component, confirm the other modes genuinely don't need it.
- **Violation signal:** two controls with different shapes and the same verb,
  each `v-if`'d to a different mode; a `v-if="!someFace"` on a navigation or
  identity control; a toolbar button whose tooltip describes a thing that exists
  elsewhere on the page in another mode.
- **Established by:** shopping-list feedback batch 2, 2026-08-28.

### D-024 — App chrome is separable from the page it sits on
- **Rule:** a persistent chrome surface (the header, a sub-bar, a sticky footer)
  must be distinguishable from the page behind it — by a **value step** in its
  surface token, a **hairline**, or both. A chrome surface is never assigned the
  page's own value, and never the theme's *sunken* value, which in a dark theme
  puts the bar at or below the page and erases it.
- **Why:** Lemon Tart Dark set `--surface-toolbar` to its `--surface-sunken`
  value — the darkest surface in the theme — while every sibling dark family
  lifts its bar above the page (Pesto Dark 18%, Blueberry 22%, Sourdough 16%).
  Against the page it sat on, that was two near-identical near-blacks, and the
  owner's report was exactly what it looks like: *"just noticed lemon tart dark
  theme you can't see any colour for the menu bar. Is this intentional or a
  mistake?"* (2026-09-03). It also can't be caught by contrast rules — D-002
  governs ink on a surface, and the *ink* was fine; the bar had simply stopped
  being an object. The hairline is what makes the rule cheap to satisfy in a
  theme that deliberately wants a near-invisible bar (Salt & Pepper's
  modern-OS look, where the header is one step off a light page).
- **Apply:** draw the hairline once, app-wide, from the chrome's own ink token
  (`MainLayout` uses `color-mix(in srgb, var(--text-on-toolbar) 14%,
  transparent)`), so it resolves to a faint light line on a dark or saturated bar
  and a faint dark one on a light bar — one rule, no per-theme token. When
  authoring or reviewing a theme, look at page vs toolbar as a *pair*; and
  remember an authored surface token proves nothing until it paints (R-080).
- **Violation signal:** `--surface-toolbar` set to the same value as
  `--surface-page` or `--surface-sunken`; a header that disappears in a
  screenshot of one theme but not others; chrome that only reads as chrome
  because of a shadow that a flat theme removes.
- **Established by:** owner misc feedback, 2026-09-03 (with FU-709's dark-page
  fix, which is what made the collision visible at all).

### D-025 — No em dashes, and no explanatory tails
- **Rule:** user-facing copy (labels, tooltips, toasts, dialogs, empty states,
  help text, server messages, emails, assistant replies, seed data) never
  contains an em dash (U+2014). And the clause an em dash usually introduces is
  cut, not re-punctuated: a tooltip names the action, a toast states the
  outcome, an empty state says it's empty. Consequences the user already
  understands ("your pantry was already restocked when you finished") are not
  narrated. An empty-value placeholder uses an en dash ("–").
- **Why:** the owner would never write one, and they had spread across ~700
  strings as a tell of machine-written copy, nearly always leading into a
  hand-holding tail. Removed app-wide on 2026-09-27 after the owner had been
  deleting them one at a time.
- **Apply:** write the shortest sentence that lets the user act. Separators in
  data labels use a colon, parentheses or " · ". The assistant's system prompt
  tells the model the same thing.
- **Violation signal:** "—" anywhere in a template, string literal, email
  template or seed text; a tooltip longer than the control's name plus one
  short clause.
- **Established by:** owner feedback, 2026-09-27.

---

## Exemplars (the bar — protect these)

Cook mode (step type, per-step ingredient highlight) · stocktake/reconcile
runners · onboarding story + all-set hub · Stock-locations settings page ·
Draft-my-shop flow · Add-item dialog · instant search with re-scoping stats ·
404/splash art + empty-state copy. When unsure how something should feel, match
these — they already embody the spec above.

## Change process

D-rules follow the R-rule lifecycle: propose at close-gate, record the decision
(ADR if it constrains architecture; otherwise note here + worklog), append newest
(D-016+). Part A/B tables are updated in place when a token or component spec
genuinely changes — and only then. This doc is indexed from
`ENGINEERING_STANDARDS.md` (R-035) so it is checked on every UI-affecting task.
