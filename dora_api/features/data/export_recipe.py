"""Export endpoints for recipes — CSV (ingredients) + print-view (recipe card).

Mirrors the shopping-list export pattern: CSV downloads + a server-rendered
HTML page the user prints via the browser. PDF is "Save as PDF" from the
print dialog.

  GET /api/recipes/<id>/export?format=csv
  GET /api/recipes/<id>/print-view
"""
import base64
import csv
import io
import logging
from dataclasses import dataclass, field
from uuid import UUID

from flask import Response, render_template_string, request

from dora_api.domain.units import format_quantity
from dora_api.features.data.export_shared import (
    CSV_BOM,
    PRINT_CSS,
    PRINT_TOOLBAR,
    csv_safe_row,
    export_filename,
    print_format,
)
from dora_api.features.recipes.get_recipes import (
    GetRecipesHandler,
    RecipeDto,
    RecipeIngredientDto,
    RecipeStepDto,
)
from dora_api.features.recipes.recipe_step_image_access import get_step_image_bytes
from dora_api.features.routers import RECIPE_ROUTER
from dora_api.infrastructure.api_response import bad_request, not_found
from dora_api.infrastructure.data_url import decode_data_url
from dora_api.infrastructure.utils import pluralize
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)


def _ingredient_name(ingredient: RecipeIngredientDto) -> str:
    """The recipe's own label, else the linked stock item, else the pasted
    text. An unlinked (imported, never matched) row has no stock item, so the
    sheet used to print "None" and the CSV a blank name."""
    return ingredient.label or ingredient.stock_item_name or ingredient.raw_text or ""


def _build_csv(recipe: RecipeDto) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ingredient", "quantity", "unit", "notes", "location"])
    for ingredient in recipe.ingredients:
        writer.writerow(csv_safe_row([
            _ingredient_name(ingredient),
            # R-079: the formatter owns precision ("2", not "2.0").
            format_quantity(ingredient.quantity, None),
            ingredient.unit or "",
            ingredient.notes or "",
            ingredient.stock_location_name or "",
        ]))
    return CSV_BOM + buffer.getvalue()


# ── Print-view shaping ─────────────────────────────────────────────────
# The sheet follows the recipe's server-owned `steps_mode`: structured recipes
# print their sections and steps (hint, timer, sub-steps), image-mode recipes
# print their step photos, freeform recipes print the method text. It used to
# print only the legacy `instructions` blob, which for a structured recipe is
# a one-line summary and for an image recipe "See the photos."

@dataclass
class _StepNode:
    step: RecipeStepDto
    children: list[RecipeStepDto] = field(default_factory=list)


@dataclass
class _Group:
    name: str | None   # None = the recipe's implicit main group, no heading
    ingredients: list[RecipeIngredientDto] = field(default_factory=list)
    steps: list[_StepNode] = field(default_factory=list)


def _groups(recipe: RecipeDto) -> list[_Group]:
    """Main group first, then the named sections in their order. A row whose
    section has gone falls back to main rather than vanishing."""
    sections = sorted(recipe.sections, key=lambda s: (s.sequence, s.name.lower()))
    main = _Group(name=None)
    by_id = {s.section_id: _Group(name=s.name) for s in sections}
    for ingredient in recipe.ingredients:
        by_id.get(ingredient.section_id, main).ingredients.append(ingredient)
    if recipe.steps_mode == "structured":
        children: dict[UUID, list[RecipeStepDto]] = {}
        for step in recipe.steps:
            if step.parent_step_id is not None:
                children.setdefault(step.parent_step_id, []).append(step)
        for step in sorted(recipe.steps, key=lambda s: s.sequence):
            if step.parent_step_id is None:
                by_id.get(step.section_id, main).steps.append(_StepNode(
                    step=step,
                    children=sorted(children.get(step.step_id, []), key=lambda s: s.sequence),
                ))
    ordered = [main] + [by_id[s.section_id] for s in sections]
    return [g for g in ordered if g.ingredients or g.steps]


# One print page carries at most this much embedded image data (~5 photos at
# the 6 MB upload cap); past it a step prints "photo too large to print".
_PRINT_IMAGE_BUDGET_BYTES = 32_000_000


def _step_image_uris(recipe: RecipeDto) -> list[str]:
    """Each step photo as a re-encoded `data:` URI, so the sheet carries its
    own images (the SPA opens it as a blob, where the authenticated bytes route
    can't be fetched — the QR sheet's reason). Going through the shared decoder
    keeps its raster-only allow-list (no SVG / HTML smuggled in as an image)."""
    uris: list[str] = []
    budget = _PRINT_IMAGE_BUDGET_BYTES
    for image in sorted(recipe.step_images, key=lambda i: i.sequence):
        stored = get_step_image_bytes(recipe.recipe_id, image.image_id)
        decoded = decode_data_url(stored)
        if decoded is None:
            continue
        # The stored value already is a `data:` URL (the allow-list check above
        # is what matters); re-encoding 20 × 6 MB would only cost memory. A
        # page past the budget stops embedding rather than growing unbounded.
        text = stored.decode("utf-8") if isinstance(stored, (bytes, bytearray)) else str(stored)
        if len(text) > budget:
            uris.append("")
            continue
        budget -= len(text)
        uris.append(text)
    return uris


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
        <span class="recipe-meta-chip">{{ servings_label }}</span>
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
      {% for group in groups if group.ingredients %}
        {% if group.name %}<h3>{{ group.name }}</h3>{% endif %}
        {% for ingredient in group.ingredients %}
          <div class="ingredient">
            <span class="item-name">{{ ingredient_name(ingredient) }}</span>
            {% set qty_label = format_quantity(ingredient.quantity, ingredient.unit) %}
            {% if qty_label %}
              · {{ qty_label }}
            {% endif %}
            {% if ingredient.is_optional %}
              <span class="optional-tag">(optional)</span>
            {% endif %}
            {% if ingredient.notes %}
              <div class="item-notes">{{ ingredient.notes }}</div>
            {% endif %}
          </div>
        {% endfor %}
      {% endfor %}
    {% endif %}

    {% macro step_body(step) %}
      {{ step.text }}
      {% if step.hint %}<div class="step-hint">Tip: {{ step.hint }}</div>{% endif %}
      {% if step.timer_minutes %}<div class="step-timer">Timer: {{ step.timer_minutes }} min</div>{% endif %}
    {% endmacro %}

    {% if has_steps %}
      <h2>Method</h2>
      {% for group in groups if group.steps %}
        {% if group.name %}<h3>{{ group.name }}</h3>{% endif %}
        <ol class="steps">
          {% for node in group.steps %}
            <li>
              {{ step_body(node.step) }}
              {% if node.children %}
                <ol>
                  {% for child in node.children %}
                    <li>{{ step_body(child) }}</li>
                  {% endfor %}
                </ol>
              {% endif %}
            </li>
          {% endfor %}
        </ol>
      {% endfor %}
    {% elif step_images %}
      <h2>Method</h2>
      {% for uri in step_images %}
        {% if uri %}<img class="step-image" src="{{ uri }}" alt="Step {{ loop.index }}" />
        {% else %}<p class="step-image step-image--missing">Step {{ loop.index }}: photo too large to print.</p>{% endif %}
      {% endfor %}
    {% elif recipe.instructions %}
      <h2>Method</h2>
      <div class="instructions">{{ recipe.instructions }}</div>
    {% endif %}

  </div>
</body>
</html>
"""


def _render_print_view(recipe: RecipeDto, generated_at: str) -> str:
    groups = _groups(recipe)
    step_images = _step_image_uris(recipe) if recipe.steps_mode == "image" else []
    servings = recipe.servings or 0
    return render_template_string(
        _PRINT_TEMPLATE,
        recipe=recipe,
        groups=groups,
        has_steps=any(g.steps for g in groups),
        step_images=step_images,
        servings_label=f"{servings} {pluralize(servings, 'serving')}",
        generated_at=generated_at,
        css=PRINT_CSS,
        toolbar=PRINT_TOOLBAR,
        format_quantity=format_quantity,
        ingredient_name=_ingredient_name,
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
    # `mimetype`, not a hand-written charset: Flask appends `; charset=utf-8`
    # itself, and spelling it out doubled it (same fix as barcodes.py).
    response = Response(body, mimetype="text/csv")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@RECIPE_ROUTER.route("/<uuid:recipe_id>/print-view", methods=["GET"])
def print_view_recipe(recipe_id: UUID):
    repository = SqlAlchemyRepository()
    recipe = GetRecipesHandler(repository).handle_by_id(recipe_id)
    if recipe is None:
        return not_found("Recipe", recipe_id)
    html = _render_print_view(recipe, print_format(repository).generated_at())
    return Response(html, mimetype="text/html")
