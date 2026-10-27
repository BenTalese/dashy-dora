"""GET /api/alerts — items that need the user's attention right now.

All signals are derived from existing schema (expiry_date, stock_level,
is_essential), so the alert *conditions* are never stored — they're
recomputed every request and so always reflect current pantry state.

The three per-item kinds emitted here — `expired`, `expiring_soon`,
`essential_low` — ARE the stock-overview attention rule. `stock_attention.py`
reads the same evaluator so a row's outline and the bell can't disagree
(R-003); nothing re-derives "needs attention" client-side.

What *is* persisted (C-9.1) is each user's *decisions* about an alert —
snooze / dismiss — in `AlertInteraction`, keyed by the alert's
stable `<scope>:<id>:<kind>` key. This handler overlays the requesting
user's interactions so the badge, the bell list, the page, and (later)
the channels all agree on one definition of "what counts":

  - dismissed  → hidden everywhere.
  - snoozed    → moved to the `snoozed` list, out of the active counts.
  - everything else → `items`.

The badge counts the **actionable** tier; the **FYI** tier is shown in the
list but never inflates it — the rule is explicit (`actionable_count` == the
active actionable-tier list), not a silent exclusion. Tier is **derived from
severity** (high/medium → actionable, low → FYI) and is not stored or
overridable; `AlertPreference` can only disable a kind for a user (Step-0 Q2/Q3,
`IMPL_PLAN_STOCK_SIGNAL_CONSOLIDATION.md`). Severity is therefore the single
importance scale — the UI sorts and colours off it, and `tier` on the DTO is a
convenience label, not a second source.
"""
import logging
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from typing import List
from uuid import UUID


from dora_api.domain.entities.alert_interaction import AlertInteraction
from dora_api.domain.entities.alert_preference import AlertPreference
from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
from dora_api.domain.entities.shopping_list import (SHOPPING_LIST_STATUS_DONE,
                                                    ShoppingList)
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.stock_status import (effective_expiring_soon_window,
                                          is_out_of_stock)
from dora_api.domain.entities.price_alert import PriceAlert
from dora_api.domain.entities.product import Product
from dora_api.domain.entities.user import User
from dora_api.features.alerts.alert_key import (list_alert_key, meal_alert_key,
                                                product_alert_key,
                                                stock_alert_key)
from dora_api.features.app_settings.access import (get_or_create_app_setting,
                                                  money_features_enabled)
from dora_api.features.alerts.alert_kinds import (SEVERITY_HIGH, SEVERITY_LOW,
                                                  SEVERITY_MEDIUM,
                                                  SEVERITY_ORDER,
                                                  TIER_ACTIONABLE, TIER_FYI,
                                                  is_actionable)
from dora_api.features.app_settings.clock import household_today
from dora_api.features.products.product_links import linked_stock_items
from dora_api.features.stock_items.stock_attention import (is_essential_low,
                                                           is_expired,
                                                           is_expiring_soon)
from dora_api.features.routers import ALERT_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.infrastructure.utils import pluralize
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.session_user import current_user_id

_LOGGER = logging.getLogger(__name__)


# Severity is the one importance scale; the UI sorts high first. The bell badge
# counts the actionable tier, which is now *derived* from severity (high+medium)
# rather than stored beside it. Both the names and the order live in
# `alert_kinds.py` (R-003) and are re-exported here only for the emitters below.
_SEVERITY_ORDER = SEVERITY_ORDER

# how soon a list's planned shop date must be to nudge. A small
# constant default (not yet admin-tunable — these are FYI nudges, and per-user
# on/off already covers "I don't want this"); one source here (R-003).
SHOPPING_DAY_WINDOW_DAYS = 3

def _iso_week_label(day: date) -> str:
    """Stable ``YYYY-Www`` label for the ISO week containing ``day`` — the
    no_planned_meals discriminator, so the key matches across evaluations
    within the same week (ledger discipline, alert_key.py)."""
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


@dataclass(frozen=True, slots=True)
class AlertDto:
    # Stable scoped key `<scope>:<id>:<kind>` (alert_key) — the frontend
    # treats it as an opaque id and posts it back to the snooze/read/dismiss
    # endpoints. Named `alert_id` for frontend continuity; its *value* is the
    # generalised key (alert_key.py).
    alert_id: str
    # One of the kinds in `alert_kinds.SEVERITY_BY_KIND` — don't restate the
    # list here, it drifted twice before (R-003).
    kind: str
    severity: str
    message: str
    detail: str | None
    # Stock-scoped alerts carry the owning item; the C-9.4 non-stock kinds
    # (no_planned_meals / shopping_day) leave these None. price_drop sets
    # them to the watched product's linked item, when it has one.
    stock_item_id: UUID | None = None
    stock_item_name: str | None = None
    # Deep-link target id for non-stock kinds (e.g. the shopping list uuid for
    # shopping_day). The client maps kind + this id to a route; None when the
    # kind links to a fixed page (no_planned_meals → the planner).
    target_id: str | None = None
    # ISO date string (if relevant — e.g. expiry alerts include the date).
    related_date: str | None = None
    # ISO date the alert's episode began (owner 2026-10-15): the day an item
    # entered its expiry window, the day a level changed, the day after a
    # missed shop. It is what "discard alerts older than N days" measures, so
    # every kind sets it from the fact that started the condition rather than
    # from when somebody first looked.
    started_on: str | None = None
    # A raw money amount the alert is about (price_drop's current price). The
    # server never formats currency (D-006); the client renders it.
    amount: float | None = None
    # Per-user interaction overlay (C-9.1). For an active (non-snoozed) alert
    # `snoozed_until` is None. There is no read state: dismiss is the one way
    # to put an alert away (owner 2026-10-15).
    snoozed_until: str | None = None
    # Derived tier: 'actionable' (counts toward the badge) or 'fyi'. A label
    # for the client's convenience — `severity` is the authority (Step-0 Q3).
    tier: str = TIER_ACTIONABLE


@dataclass(frozen=True, slots=True)
class AlertsDto:
    items: List[AlertDto] = field(default_factory=list)      # active (not snoozed, not dismissed)
    snoozed: List[AlertDto] = field(default_factory=list)    # snoozed by this user (not dismissed)
    # Active-set severity counts (for the "X high · Y medium · Z low" caption).
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    # The canonical numbers (PROPOSAL_ALERTS §3.4):
    # Active actionable tier, drives the bell badge. The FYI tier is exactly
    # `low_count` (tier derives from severity), so it has no second field.
    actionable_count: int = 0
    snoozed_count: int = 0


def _active_snooze_until(interaction: AlertInteraction | None, now: datetime) -> datetime | None:
    """The snooze cutoff if it's still in the future, else None."""
    if interaction is None or interaction.snoozed_until is None:
        return None
    until = interaction.snoozed_until
    if until.tzinfo is None:  # SQLite may hand back naive datetimes
        until = until.replace(tzinfo=timezone.utc)
    return until if until > now else None


class GetAlertsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(
        self,
        user_id: UUID | None = None,
        now: datetime | None = None,
    ) -> AlertsDto:
        # `now` is a test seam (FU-518): snooze-expiry checks compare against
        # it, and callers that already carry a tick time (the push job) pass
        # theirs through so one run evaluates at one instant. Default
        # preserves the wall-clock behaviour.
        items: List[StockItem] = (
            self.repository.get(StockItem)
            .include(StockItem.Fields.STOCK_LEVEL)
            .all()
        )
        # R-021 — calendar boundaries evaluate in the household timezone.
        today = household_today(self.repository)
        now = now or datetime.now(timezone.utc)

        # Household-wide threshold (C-9.2): the expiring-soon window resolves
        # from AppSetting, falling back to the seeded default — one source
        # (R-003), never a second literal 7 here.
        window = effective_expiring_soon_window(get_or_create_app_setting(self.repository))

        # Build the raw alert set (conditions, no counting yet — counts are
        # derived after the per-user interaction + preference overlay).
        raw: List[AlertDto] = []

        # The *conditions* live in `stock_attention.py` — this loop owns only
        # the copy. Emitting from the same predicates the stock rows read is
        # what makes "one attention rule" true rather than aspirational (R-003);
        # the previous arrangement restated the thresholds here and drifted (B1).
        for item in items:
            # ── Expiry ─────────────────────────────────────────────────
            if item.expiry_date is not None:
                days_remaining = (item.expiry_date - today).days
                expiry_iso = item.expiry_date.isoformat()
                if is_expired(item, today):
                    raw.append(AlertDto(
                        alert_id = stock_alert_key(item.id, f"expired:{expiry_iso}"),
                        kind = "expired",
                        severity = SEVERITY_HIGH,
                        stock_item_id = item.id,
                        stock_item_name = item.name,
                        message = f"{item.name} has expired",
                        detail = f"Expired {abs(days_remaining)} {pluralize(days_remaining, 'day')} ago.",
                        related_date = expiry_iso,
                        started_on = expiry_iso,
                    ))
                elif is_expiring_soon(item, today, window):
                    raw.append(AlertDto(
                        alert_id = stock_alert_key(item.id, f"expiring_soon:{expiry_iso}"),
                        kind = "expiring_soon",
                        severity = SEVERITY_MEDIUM,
                        stock_item_id = item.id,
                        stock_item_name = item.name,
                        message = f"{item.name} expires soon",
                        detail = (
                            "Expires today."
                            if days_remaining == 0
                            else f"Expires in {days_remaining} {pluralize(days_remaining, 'day')}."
                        ),
                        related_date = expiry_iso,
                        started_on = (item.expiry_date - timedelta(days=window)).isoformat(),
                    ))

            # ── Stock level ────────────────────────────────────────────
            # ONLY essentials. Step-0 Q1 cut `out_of_stock` and `low_stock`:
            # a non-essential running low is exactly the case the user said he
            # doesn't want to hear about, and the row's own level band already
            # says it. Non-essential + out still *dims and sinks* the row
            # (D-8) — that's a treatment read off the level, not an alert.
            if is_essential_low(item):
                # The episode is the level change that made it low or out, so
                # a restock and a later run-out is a new alert.
                level_since = (
                    item.stock_level_last_updated.date().isoformat()
                    if item.stock_level_last_updated is not None else today.isoformat()
                )
                if is_out_of_stock(item.stock_level):
                    raw.append(AlertDto(
                        alert_id = stock_alert_key(item.id, f"essential_out:{level_since}"),
                        kind = "essential_low",
                        severity = SEVERITY_HIGH,
                        stock_item_id = item.id,
                        stock_item_name = item.name,
                        message = f"Essential {item.name} is out of stock",
                        # DR-4 (FU-578 #17): action-neutral — the bell offers
                        # both "Mark restocked" (per row) and "Add to list"
                        # (footer), so the copy shouldn't prescribe one.
                        detail = "Out of stock and essential.",
                        related_date = None,
                        started_on = level_since,
                    ))
                else:
                    raw.append(AlertDto(
                        alert_id = stock_alert_key(item.id, f"essential_low:{level_since}"),
                        kind = "essential_low",
                        severity = SEVERITY_HIGH,
                        stock_item_id = item.id,
                        stock_item_name = item.name,
                        message = f"Essential {item.name} is low",
                        detail = "Essential and running low.",
                        related_date = None,
                        started_on = level_since,
                    ))

        # ── Stocktake overdue: deliberately NOT an alert ───────────────
        # Step-0 Q1 cut it. The stocktake runner owns this signal end to end —
        # it has its own queue, its own overdue resolver and its own toolbar
        # button. Mirroring it into the bell was one condition shouting from
        # two places, which is the pattern this plan exists to remove. If the
        # runner needs to be more discoverable, make the runner louder; don't
        # re-add a kind here.

        # ── Forward-looking nudges (C-9.4) ─────────────────────────────
        # Not per-item, so they sit outside the loop. R-021 — `today` is
        # the household-tz boundary built once at the top of `handle()`.
        raw.extend(self._no_planned_meals_alerts(today))
        raw.extend(self._shopping_day_alerts(today))
        # ── FU-317 Chunk 4 — meal-plan reconcile overdue ───────────────
        raw.extend(self._meal_reconcile_overdue_alerts(today))
        # ── Price watches (per user) ───────────────────────────────────
        if user_id is not None:
            raw.extend(self._price_drop_alerts(user_id))

        # ── Per-user overlay (C-9.1 interactions + C-9.2 preferences) ───
        # One bounded fetch each of this user's interactions + preferences,
        # then a Python-side filter — same shape as the suggestions flow.
        interactions: dict[str, AlertInteraction] = {}
        preferences: dict[str, AlertPreference] = {}
        if user_id is not None:
            interaction_rows: List[AlertInteraction] = self.repository.get(AlertInteraction).all(
                EntityField(AlertInteraction, AlertInteraction.Fields.USER_ID).eq(user_id)
            )
            interactions = {row.alert_key: row for row in interaction_rows}
            preference_rows: List[AlertPreference] = self.repository.get(AlertPreference).all(
                EntityField(AlertPreference, AlertPreference.Fields.USER_ID).eq(user_id)
            )
            preferences = {row.kind: row for row in preference_rows}

        # Owner 2026-10-15 — "discard alerts older than X days". An alert whose
        # episode began before the cutoff is dropped from every list and count,
        # as if dismissed. Per user; None means keep everything.
        discard_before = self._discard_cutoff(user_id, today)

        active: List[AlertDto] = []
        snoozed: List[AlertDto] = []
        high = medium = low = 0
        actionable = 0

        for alert in raw:
            # a kind this user disabled contributes nothing to their
            # set, counts, or (later) channels.
            pref = preferences.get(alert.kind)
            if pref is not None and not pref.enabled:
                continue
            # Tier is derived from severity, full stop — no stored default, no
            # per-user override (Step-0 Q3). The count split and the row outline
            # therefore cannot disagree about what "actionable" means.
            tier = TIER_ACTIONABLE if is_actionable(alert.severity) else TIER_FYI

            if (
                discard_before is not None and alert.started_on is not None
                and alert.started_on < discard_before
            ):
                continue  # older than the user's discard window
            interaction = interactions.get(alert.alert_id)
            if interaction is not None and interaction.dismissed_at is not None:
                continue  # dismissed → hidden everywhere
            snooze_until = _active_snooze_until(interaction, now)
            if snooze_until is not None:
                snoozed.append(replace(
                    alert, tier=tier, snoozed_until=snooze_until.isoformat()
                ))
                continue
            active.append(replace(alert, tier=tier, snoozed_until=None))
            # Severity counts feed the bell colour and Dora's attention answer;
            # the actionable tier feeds the badge.
            if alert.severity == SEVERITY_HIGH:
                high += 1
            elif alert.severity == SEVERITY_MEDIUM:
                medium += 1
            else:
                low += 1
            if tier == TIER_ACTIONABLE:
                actionable += 1

        # Severity-first ordering so the panel scans top-down.
        def _sort_key(a: AlertDto):
            # Non-stock kinds (C-9.4) have no item name — fall back to the
            # message so the secondary sort stays total.
            label = a.stock_item_name or a.message
            return (_SEVERITY_ORDER.get(a.severity, 99), label.lower())

        active.sort(key=_sort_key)
        snoozed.sort(key=_sort_key)

        return AlertsDto(
            items=active,
            snoozed=snoozed,
            high_count=high,
            medium_count=medium,
            low_count=low,
            actionable_count=actionable,
            snoozed_count=len(snoozed),
        )

    def _no_planned_meals_alerts(self, today: date) -> List[AlertDto]:
        """One FYI nudge when *next* week has no meal-plan entries. The key is
        keyed on next week's ISO label so it clears the moment a meal lands in
        that week and re-fires for the following empty week."""
        # Next week = the seven days following this week's Sunday. weekday():
        # Mon=0 … Sun=6, so days to next Monday is 7 - weekday().
        next_monday = today + timedelta(days=7 - today.weekday())
        next_sunday = next_monday + timedelta(days=6)
        entries: List[MealPlanEntry] = self.repository.get(MealPlanEntry).all(
            EntityField(MealPlanEntry, MealPlanEntry.Fields.SCHEDULED_FOR)
            .between(next_monday, next_sunday)
        )
        if entries:
            return []
        return [AlertDto(
            alert_id = meal_alert_key(f"no_planned_meals:{_iso_week_label(next_monday)}"),
            kind = "no_planned_meals",
            severity = SEVERITY_LOW,
            message = "No meals planned for next week",
            detail = (
                f"Next week ({next_monday.strftime('%a %d %b')} – "
                f"{next_sunday.strftime('%a %d %b')}) has nothing on the plan yet."
            ),
            related_date = next_monday.isoformat(),
            # Raised for the coming week during this one.
            started_on = (next_monday - timedelta(days=7)).isoformat(),
        )]

    def _meal_reconcile_overdue_alerts(self, today: date) -> List[AlertDto]:
        """FU-317 Chunk 4 — one FYI nudge when the meal-plan reconcile
        queue has grown long enough that it's worth reminding the user
        to walk it. Signal owned by `features/meal_plans/reconcile.py`
        (R-003 — same threshold the suggestion generator uses). The
        alert key is discriminated by the oldest unresolved entry's
        ISO date so a user snooze/dismiss decision persists as long as
        that entry sits at the head of the queue, and rolls to a fresh
        key once the queue is cleared or the head moves forward."""
        from dora_api.features.meal_plans.reconcile import \
            reconcile_overdue_signal
        signal = reconcile_overdue_signal(today)
        if not signal.fires:
            return []
        head_iso = (today - timedelta(days=signal.oldest_days_back)).isoformat()
        return [AlertDto(
            alert_id = meal_alert_key(f"meal_reconcile_overdue:{head_iso}"),
            kind = "meal_reconcile_overdue",
            severity = SEVERITY_LOW,
            message = f"{signal.unresolved_count} past meals need confirming",
            detail = (
                f"Oldest is {signal.oldest_days_back} {pluralize(signal.oldest_days_back, 'day')} back."
            ),
            related_date = head_iso,
            started_on = head_iso,
        )]

    def _shopping_day_alerts(self, today: date) -> List[AlertDto]:
        """Two kinds off one read of the open lists with a planned shop date.

        * `shopping_day` (FYI): the date is today or within the next
          `SHOPPING_DAY_WINDOW_DAYS`.
        * `shopping_overdue` (owner 2026-10-15, "Did you forget your
          shopping?"): the date has passed and the list is still in draft or
          shop mode.

        Both are keyed on the list **and** its planned date, so moving the date
        is a new episode, and the two kinds never share a dismissal (they used
        to be one kind on one key, so dismissing the reminder also silenced the
        missed-shop nudge). Clears when the list is finished."""
        horizon = today + timedelta(days=SHOPPING_DAY_WINDOW_DAYS)
        lists: List[ShoppingList] = self.repository.get(ShoppingList).all(
            EntityField(ShoppingList, ShoppingList.Fields.PLANNED_SHOP_DATE)
            .lte(horizon)
            & EntityField(ShoppingList, ShoppingList.Fields.STATUS)
            .ne(SHOPPING_LIST_STATUS_DONE)
        )
        out: List[AlertDto] = []
        for lst in lists:
            planned = lst.planned_shop_date
            planned_iso = planned.isoformat()
            days = (planned - today).days
            if days < 0:
                overdue = -days
                when = "yesterday" if overdue == 1 else f"{overdue} days ago"
                out.append(AlertDto(
                    alert_id = list_alert_key(lst.id, f"shopping_overdue:{planned_iso}"),
                    kind = "shopping_overdue",
                    severity = SEVERITY_MEDIUM,
                    message = "Did you forget your shopping?",
                    detail = f"{lst.display_name} was planned for {when}.",
                    target_id = str(lst.id),
                    related_date = planned_iso,
                    started_on = (planned + timedelta(days=1)).isoformat(),
                ))
                continue
            when = (
                "today" if days == 0
                else "tomorrow" if days == 1
                else f"in {days} days"
            )
            out.append(AlertDto(
                alert_id = list_alert_key(lst.id, f"shopping_day:{planned_iso}"),
                kind = "shopping_day",
                severity = SEVERITY_LOW,
                message = f"Shopping day {when}: {lst.display_name}",
                detail = "Open the list to get ready.",
                target_id = str(lst.id),
                related_date = planned_iso,
                started_on = (planned - timedelta(days=SHOPPING_DAY_WINDOW_DAYS)).isoformat(),
            ))
        return out

    def _price_drop_alerts(self, user_id: UUID) -> List[AlertDto]:
        """One alert per watched product whose current price is at or below the
        user's threshold. The episode is the offer that crossed it: a new
        price observation at or under the line is a new alert; a price that
        stays put is the same one, so it fires once.

        Money-gated like every price surface (R-029): with money off, no watch
        fires. `PriceAlert.threshold_unit_price` is compared with the product's
        shelf `price_now`, which is what the watch dialog asks for."""
        if not money_features_enabled(self.repository):
            return []
        watches: List[PriceAlert] = self.repository.get(PriceAlert).all(
            EntityField(PriceAlert, PriceAlert.Fields.USER_ID).eq(user_id)
        )
        if not watches:
            return []
        threshold_by_product = {w.product_id: float(w.threshold_unit_price) for w in watches}
        products: List[Product] = (
            self.repository.get(Product)
            .include(Product.Fields.CURRENT_OFFER)
            .include(Product.Fields.STORE)
            .all(EntityField(Product, "id").in_(list(threshold_by_product)))
        )
        # The linked stock item rides along so the bell's add-to-list button
        # adds the same line My products does for this product (owner
        # 2026-10-17): via the item, with this product picked. Unlinked
        # products leave it None and add as a product-only line.
        links = linked_stock_items(self.repository, [p.id for p in products])
        out: List[AlertDto] = []
        for product in products:
            offer = product.current_offer
            if offer is None or offer.price_now is None:
                continue
            price = float(offer.price_now)
            if price <= 0 or price > threshold_by_product[product.id]:
                continue
            seen_on = offer.offered_on.date().isoformat() if offer.offered_on else None
            store = product.store.name if product.store is not None else None
            link = links.get(product.id)
            out.append(AlertDto(
                alert_id = product_alert_key(product.id, f"price_drop:{offer.id}"),
                kind = "price_drop",
                severity = SEVERITY_MEDIUM,
                message = f"{product.name} hit your price",
                detail = f"At {store}." if store else None,
                stock_item_id = link.stock_item_id if link else None,
                stock_item_name = link.name if link else None,
                target_id = str(product.id),
                related_date = seen_on,
                started_on = seen_on,
                amount = price,
            ))
        return out

    def _discard_cutoff(self, user_id: UUID | None, today: date) -> str | None:
        """ISO date before which this user's alerts are discarded, or None."""
        if user_id is None:
            return None
        user: User | None = self.repository.get(User).by_id(user_id)
        days = user.alert_discard_after_days if user is not None else None
        if not days:
            return None
        return (today - timedelta(days=int(days))).isoformat()

@ALERT_ROUTER.route("", methods=["GET"])
def get_alerts():
    _Alerts = GetAlertsHandler(SqlAlchemyRepository()).handle(current_user_id())
    _LOGGER.debug(
        "Alerts: %d actionable, %d fyi, %d snoozed",
        _Alerts.actionable_count, _Alerts.low_count, _Alerts.snoozed_count,
    )
    return ok(_Alerts)
