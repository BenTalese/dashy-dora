from flask import Blueprint

AUTH_ROUTER = Blueprint("AUTH_ROUTER", __name__, url_prefix="/api/auth")
DASHBOARD_ROUTER = Blueprint("DASHBOARD_ROUTER", __name__, url_prefix="/api/dashboard")
HEALTH_ROUTER = Blueprint("HEALTH_ROUTER", __name__, url_prefix="/api/health")
STORE_ROUTER = Blueprint("STORE_ROUTER", __name__, url_prefix="/api/stores")
PRODUCT_ROUTER = Blueprint("PRODUCT_ROUTER", __name__, url_prefix="/api/products")
MEAL_PLAN_ROUTER = Blueprint("MEAL_PLAN_ROUTER", __name__, url_prefix="/api/meal-plans")
MEAL_PLAN_TEMPLATE_ROUTER = Blueprint("MEAL_PLAN_TEMPLATE_ROUTER", __name__, url_prefix="/api/meal-plan-templates")
MEAL_PLAN_TEMPLATE_SET_ROUTER = Blueprint("MEAL_PLAN_TEMPLATE_SET_ROUTER", __name__, url_prefix="/api/meal-plan-template-sets")
RECIPE_ROUTER = Blueprint("RECIPE_ROUTER", __name__, url_prefix="/api/recipes")
RECIPE_COLLECTION_ROUTER = Blueprint("RECIPE_COLLECTION_ROUTER", __name__, url_prefix="/api/recipe-collections")
CUISINE_ROUTER = Blueprint("CUISINE_ROUTER", __name__, url_prefix="/api/cuisines")
CATEGORY_ROUTER = Blueprint("CATEGORY_ROUTER", __name__, url_prefix="/api/categories")
DIETARY_TAG_ROUTER = Blueprint("DIETARY_TAG_ROUTER", __name__, url_prefix="/api/dietary-tags")
TOOL_ROUTER = Blueprint("TOOL_ROUTER", __name__, url_prefix="/api/tools")
MEAL_SLOT_ROUTER = Blueprint("MEAL_SLOT_ROUTER", __name__, url_prefix="/api/meal-slots")
STOCK_ITEM_ROUTER = Blueprint("STOCK_ITEM_ROUTER", __name__, url_prefix="/api/stock-items")
STOCK_LEVEL_ROUTER = Blueprint("STOCK_LEVEL_ROUTER", __name__, url_prefix="/api/stock-levels")
STOCK_GROUP_ROUTER = Blueprint("STOCK_GROUP_ROUTER", __name__, url_prefix="/api/stock-groups")
LOCATION_ROUTER = Blueprint("LOCATION_ROUTER", __name__, url_prefix="/api/locations")
SHOPPING_LIST_ROUTER = Blueprint("SHOPPING_LIST_ROUTER", __name__, url_prefix="/api/shopping-lists")
SHOPPING_LIST_TEMPLATE_ROUTER = Blueprint("SHOPPING_LIST_TEMPLATE_ROUTER", __name__, url_prefix="/api/shopping-list-templates")
ALERT_ROUTER = Blueprint("ALERT_ROUTER", __name__, url_prefix="/api/alerts")
SEARCH_ROUTER = Blueprint("SEARCH_ROUTER", __name__, url_prefix="/api/search")
HELP_ROUTER = Blueprint("HELP_ROUTER", __name__, url_prefix="/api/help")
ASSISTANT_ROUTER = Blueprint("ASSISTANT_ROUTER", __name__, url_prefix="/api/assistant")
APP_SETTINGS_ROUTER = Blueprint("APP_SETTINGS_ROUTER", __name__, url_prefix="/api/app-settings")
USER_ROUTER = Blueprint("USER_ROUTER", __name__, url_prefix="/api/users")
ONBOARDING_ROUTER = Blueprint("ONBOARDING_ROUTER", __name__, url_prefix="/api/onboarding")
DATA_ROUTER = Blueprint("DATA_ROUTER", __name__, url_prefix="/api/data")
CLIENT_LOGS_ROUTER = Blueprint("CLIENT_LOGS_ROUTER", __name__, url_prefix="/api/client-logs")
AUDIT_ROUTER = Blueprint("AUDIT_ROUTER", __name__, url_prefix="/api/audit")
STOCKTAKE_ROUTER = Blueprint("STOCKTAKE_ROUTER", __name__, url_prefix="/api/stocktake")
DESKTOP_ROUTER = Blueprint("DESKTOP_ROUTER", __name__, url_prefix="/api/desktop")
# Desktop A: pywebview's window points at Flask, so Flask itself has
# to serve the built SPA. Registered without a url_prefix so the
# catch-all in features/spa.py can fall back to index.html for any
# unmatched path (vue-router history mode). The Docker deployment is
# unaffected because nginx intercepts every non-/api/ request before
# Flask ever sees it.
SPA_ROUTER = Blueprint("SPA_ROUTER", __name__)
PRICE_HISTORY_ROUTER = Blueprint("PRICE_HISTORY_ROUTER", __name__, url_prefix="/api/price-history")
REPORTS_ROUTER = Blueprint("REPORTS_ROUTER", __name__, url_prefix="/api/reports")
BUDGET_ROUTER = Blueprint("BUDGET_ROUTER", __name__, url_prefix="/api/budget")
WASTE_ROUTER = Blueprint("WASTE_ROUTER", __name__, url_prefix="/api/waste")
SUGGESTIONS_ROUTER = Blueprint("SUGGESTIONS_ROUTER", __name__, url_prefix="/api/suggestions")
TTS_ROUTER = Blueprint("TTS_ROUTER", __name__, url_prefix="/api/tts")
# Server-side speech-to-text for browsers without the Web Speech API (FU-788).
STT_ROUTER = Blueprint("STT_ROUTER", __name__, url_prefix="/api/stt")

# Nutrition complex-mode: source status, dataset import, and the unified
# food lookup that the stock-item picker searches.
NUTRITION_ROUTER = Blueprint("NUTRITION_ROUTER", __name__, url_prefix="/api/nutrition")

# admin CRUD over IngestionSource (session-cookie, admin-only).
INGESTION_SOURCE_ROUTER = Blueprint(
    "INGESTION_SOURCE_ROUTER", __name__, url_prefix="/api/ingestion-sources"
)

# the producer-facing endpoint. Session-middleware exempts it
# (see middleware.PUBLIC_ENDPOINTS) so its handlers can authenticate via
# `Authorization: Bearer` instead of the dora_session cookie.
INGEST_ROUTER = Blueprint("INGEST_ROUTER", __name__, url_prefix="/api/ingest")
