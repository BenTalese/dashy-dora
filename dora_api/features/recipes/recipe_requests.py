"""Request shapes shared by `POST /recipes` and `PATCH /recipes/<id>`: one
ingredient, step and section model for both (finalisation 01-R46). The two
top-level request models stay separate; their optionality differs."""
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecipeIngredientRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — either ``stock_item_id`` or
    # ``raw_text`` MUST be set; both may be set (after the bulk-linker
    # promotes an unlinked ingredient, the raw_text audit trail survives the
    # link). Paste-based imports whose fuzzy match missed a StockItem send
    # raw_text only; quick-add flows send stock_item_id only.
    stock_item_id: UUID | None = None
    raw_text: str | None = Field(default = None, max_length = 500)
    quantity: float | None = None
    unit: str | None = Field(default = None, max_length = 50)
    notes: str | None = Field(default = None, max_length = 255)
    # Optional client-side identifier (any string) used by
    # `steps[].ingredient_client_ids` to point at this ingredient before the
    # server has assigned its UUID. Omit when no step references it.
    client_id: str | None = Field(default = None, max_length = 64)
    # Optional section grouping: the client_id of one of the sections in the
    # same payload (or, on update, an existing section's UUID string when the
    # sections are left untouched). Null = the implicit "main" group.
    section_client_id: str | None = Field(default = None, max_length = 64)
    # Cookbook revision §1.9 — optional ingredients are ignored by the
    # cookability rule. Omitting the field = a required ingredient.
    is_optional: bool = False
    # Which one of the stock item this recipe means (`ingredient_choice`).
    label: str | None = Field(default = None, max_length = 255)
    preferred_buy_id: UUID | None = None
    selected_product_id: UUID | None = None

    @model_validator(mode="after")
    def _require_anchor(self) -> "RecipeIngredientRequest":
        if self.stock_item_id is None and not (self.raw_text or "").strip():
            raise ValueError(
                "A recipe ingredient needs either stock_item_id or raw_text; both are null."
            )
        return self


class RecipeStepRequest(BaseModel):
    """One structured step (C-4 Chunk 6). `client_id` is required (any string
    the client picks) so steps can refer to one another (parent_client_id) and
    to ingredients (ingredient_client_ids) before the server has issued ids."""
    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(min_length = 1, max_length = 64)
    parent_client_id: str | None = Field(default = None, max_length = 64)
    sequence: int = Field(default = 0, ge = 0)
    text: str = Field(min_length = 1)
    hint: str | None = None
    ingredient_client_ids: List[str] = Field(default_factory = list)
    tool_ids: List[UUID] = Field(default_factory = list)
    # Optional section grouping; resolved against the sibling `sections[]`
    # entry with the same client_id.
    section_client_id: str | None = Field(default = None, max_length = 64)
    # Owner feedback 2026-09-01 — explicit per-step timer, in minutes. The
    # ceiling is a day: past that it isn't a cook-mode countdown, it's a
    # ferment, and nobody stands at the bench for it.
    timer_minutes: int | None = Field(default = None, ge = 1, le = 1440)


class RecipeSectionRequest(BaseModel):
    """A named section (C-4 Chunk 10)."""
    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(min_length = 1, max_length = 64)
    sequence: int = Field(default = 0, ge = 0)
    name: str = Field(min_length = 1, max_length = 255)
