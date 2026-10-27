"""Export endpoints for recipes — CSV (ingredients) + print-view (recipe card).

Mirrors the shopping-list export pattern: CSV downloads + a server-rendered
HTML page the user prints via the browser. PDF is "Save as PDF" from the
print dialog.

  GET /api/recipes/<id>/export?format=csv
  GET /api/recipes/<id>/print-view
"""
import csv
import io
import logging
from datetime import datetime, timezone
from uuid import UUID

from flask import Response, render_template_string, request

from dora_api.domain.units import format_quantity
from dora_api.features.data.export_shared import (
    PRINT_CSS,
    PRINT_TOOLBAR,
    export_filename,
)
from dora_api.features.recipes.get_recipes import GetRecipesHandler, RecipeDto
from dora_api.features.routers import RECIPE_ROUTER
from dora_api.infrastructure.api_response import bad_request, not_found
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)


def _build_csv(recipe: RecipeDto) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ingredient", "quantity", "unit", "notes", "location"])
    for ingredient in recipe.ingredients:
        writer.writerow([
            ingredient.stock_item_name,
            ingredient.quantity if ingredient.quantity is not None else "",
            ingredient.unit or "",
            ingredient.notes or "",
            ingredient.stock_location_name or "",
        ])
    return buffer.getvalue()


_PRINT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{{ recipe.name }} · recipe</title>
  {{ css | safe }}
</head>
<body>
  {{ toolbar | safe }}
  <div class="page">
    <h1>{{ recipe.name }}</h1>
    <div class="meta">
      Generated {{ generated_at }}
      {% if recipe.category_name %} · {{ recipe.category_name }}{% endif %}
      {% if recipe.cuisine_name %} · {{ recipe.cuisine_name }}{% endif %}
    </div>
    <div>
      {% if recipe.servings %}
        <span class="recipe-meta-chip">{{ recipe.servings }} serving(s)</span>
      {% endif %}
      {% if recipe.prep_time_minutes %}
        <span class="recipe-meta-chip">{{ recipe.prep_time_minutes }} min prep</span>
      {% endif %}
      {% if recipe.cook_time_minutes %}
        <span class="recipe-meta-chip">{{ recipe.cook_time_minutes }} min cook</span>
      {% endif %}
      {% if recipe.difficulty %}
        <span class="recipe-meta-chip">{{ recipe.difficulty }}</span>
      {% endif %}
    </div>

    <h2>Ingredients</h2>
    {% if recipe.ingredients | length == 0 %}
      <p><em>No ingredients recorded.</em></p>
    {% else %}
      {% for ingredient in recipe.ingredients %}
        <div class="ingredient">
          <span class="item-name">{{ ingredient.stock_item_name }}</span>
          {% set qty_label = format_quantity(ingredient.quantity, ingredient.unit) %}
          {% if qty_label %}
            · {{ qty_label }}
          {% endif %}
          {% if ingredient.notes %}
            <div class="item-notes">{{ ingredient.notes }}</div>
          {% endif %}
        </div>
      {% endfor %}
    {% endif %}

    {% if recipe.instructions %}
      <h2>Instructions</h2>
      <div class="instructions">{{ recipe.instructions }}</div>
    {% endif %}

  </div>
</body>
</html>
"""


def _render_print_view(recipe: RecipeDto) -> str:
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    return render_template_string(
        _PRINT_TEMPLATE,
        recipe=recipe,
        generated_at=generated_at,
        css=PRINT_CSS,
        toolbar=PRINT_TOOLBAR,
        format_quantity=format_quantity,
    )


@RECIPE_ROUTER.route("/<uuid:recipe_id>/export", methods=["GET"])
def export_recipe(recipe_id: UUID):
    fmt = (request.args.get("format") or "csv").lower()
    if fmt not in ("csv",):
        return bad_request(
            f"Unsupported export format '{fmt}'. Supported: csv. "
            "For PDF, open the print-view and 'Save as PDF' from your browser."
        )
    recipe = GetRecipesHandler(SqlAlchemyRepository()).handle_by_id(recipe_id)
    if recipe is None:
        return not_found("Recipe", recipe_id)
    body = _build_csv(recipe)
    filename = export_filename("recipe", recipe.name, "csv")
    _LOGGER.info(
        "Exported recipe %s as %s (%d ingredients)",
        recipe_id, fmt, len(recipe.ingredients),
    )
    response = Response(body, mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@RECIPE_ROUTER.route("/<uuid:recipe_id>/print-view", methods=["GET"])
def print_view_recipe(recipe_id: UUID):
    recipe = GetRecipesHandler(SqlAlchemyRepository()).handle_by_id(recipe_id)
    if recipe is None:
        return not_found("Recipe", recipe_id)
    html = _render_print_view(recipe)
    return Response(html, mimetype="text/html; charset=utf-8")
