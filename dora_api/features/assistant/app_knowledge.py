"""A short routing guide to Dora, carried in every AI prompt.

Keep it short: small models follow short guides best. It only says where
things live. The detail (what a setting does, what a colour means, how a flow
works) comes from the Help guides through the `app_help` tool (11-D1), which
reads the same copy the Help pages render, so it is written once.
"""

APP_OVERVIEW = """\
Dora is a household grocery, pantry, recipe and shopping app. The left-hand
navigation (a bottom bar on a phone) has these areas:

- Dashboard: the home page of cards (kitchen health, next to cook, use it
  up, what's coming, restock radar, budget). Cards (top right) arranges them.
- Stock: every item the household tracks, its level, location, group and
  expiry. Tap an item for its detail page. Stocktake walks the items Dora is
  least sure of.
- My Products: products saved from stores, their prices, deals, price history
  and price alerts. Only shown once product data has been pushed in.
- Cookbook: recipes, with cost, ingredients, steps and Cook mode.
- Meal Plans: the week planner, templates and the auto builder.
- Shopping Lists: one list you build and tick off in the same place (a tick
  restocks the item), finished into a receipt; templates; the cart button on
  stock and recipes adds to your open list.
- Reports: spend, waste and budget over time (money features on).
- Help & Guides: one page per area, search, common questions.
- Settings: your own preferences (appearance, account, notifications,
  assistant, voice, budget); admins also get install-wide switches (stock,
  stocktake, cooking, money, nutrition, region, users, stores, email, data and
  backups).
- The bell in the top bar is Alerts: expiring food, low essentials, shopping
  days, an unplanned week, meals to reconcile, price alerts.

For anything beyond where something lives, call app_help and answer from the
guides it returns.
"""
