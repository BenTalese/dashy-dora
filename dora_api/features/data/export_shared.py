"""Helpers shared by every CSV / print-view export endpoint."""
import re

from dora_api.features.app_settings.clock import household_today
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


def slugify(value: str) -> str:
    """Filesystem-safe slug. Lowercase, ASCII-only letters/digits/dashes."""
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value or "").strip("-").lower()
    return text or "untitled"


def export_filename(prefix: str, list_name: str, extension: str) -> str:
    # R-021 — the date stamp on a download is the household's calendar day
    # ("recipe-bolognese-2026-06-29.csv"), not the server's.
    today = household_today(SqlAlchemyRepository()).isoformat()
    return f"{prefix}-{slugify(list_name)}-{today}.{extension}"


# Print-view stylesheet shared across every server-rendered print page.
# Centralised so a polish pass on print rules lands everywhere at once.
PRINT_CSS = """
<style>
  :root { color-scheme: light; }
  html, body {
    margin: 0;
    padding: 0;
    background: #fff;
    color: #222;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica,
                 Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
    font-size: 14px;
    line-height: 1.45;
  }
  .page {
    max-width: 720px;
    margin: 0 auto;
    padding: 32px 24px 64px;
  }
  h1 { font-size: 22px; margin: 0 0 4px; }
  h2 { font-size: 16px; margin: 24px 0 8px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
  .meta { color: #666; font-size: 12px; margin-bottom: 16px; }
  .totals {
    display: flex; gap: 16px; flex-wrap: wrap;
    background: #f4f4f4; border-radius: 6px; padding: 10px 14px; margin-bottom: 16px;
    font-size: 13px;
  }
  .totals strong { color: #111; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  td, th { padding: 8px 4px; text-align: left; vertical-align: top; }
  td.qty, th.qty, td.price, th.price { text-align: right; white-space: nowrap; }
  td.box { width: 22px; }
  .checkbox {
    display: inline-block; width: 18px; height: 18px;
    border: 1.5px solid #444; border-radius: 3px;
  }
  .item-name { font-weight: 600; }
  .item-store, .item-notes { color: #666; font-size: 12px; }
  .ingredient { padding: 6px 0; border-bottom: 1px dashed #ddd; }
  .ingredient:last-child { border-bottom: none; }
  .instructions { white-space: pre-wrap; margin-top: 8px; }
  .recipe-meta-chip {
    display: inline-block; background: #f4f4f4; border-radius: 4px;
    padding: 2px 8px; margin-right: 6px; font-size: 12px; color: #444;
  }
  .toolbar {
    position: fixed; top: 12px; right: 12px;
    background: #222; color: #fff; padding: 8px 14px; border-radius: 999px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.2); cursor: pointer; font-size: 13px;
    user-select: none;
  }
  @media print {
    .toolbar { display: none; }
    .page { max-width: none; padding: 12px 16px; }
    h2 { page-break-after: avoid; }
    tr, .ingredient { page-break-inside: avoid; }
    body { font-size: 12px; }
  }
</style>
"""

# A tiny "Print this page" floating button so the user doesn't need to know
# Ctrl/Cmd-P. Hidden in print output via @media print.
PRINT_TOOLBAR = (
    '<button class="toolbar" onclick="window.print()">Print / Save as PDF</button>'
)
