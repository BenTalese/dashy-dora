"""CSV formula injection: free-text cells a household member typed must not
run as a formula in whoever opens the export in a spreadsheet app."""
import csv
import io

import requests

from dora_api.features.data.export_shared import csv_safe_cell, csv_safe_row

BASE = "http://localhost:5170/api"


def test__csv_safe_cell__FormulaPrefixes__AreQuoted():
    for raw in ("=1+1", "+cmd", "-2+3", "@SUM(A1)", "\tx", "\rx"):
        assert csv_safe_cell(raw) == "'" + raw


def test__csv_safe_cell__PlainTextAndNumbers__PassThrough():
    assert csv_safe_cell("Milk") == "Milk"
    assert csv_safe_cell("100% juice") == "100% juice"
    assert csv_safe_cell("") == ""
    assert csv_safe_cell(-2) == -2
    assert csv_safe_row(["=x", 1.5, None]) == ["'=x", 1.5, None]


def test__export_stock_overview__FormulaInName__IsNeutralised(api):
    level_id = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    created = requests.post(f"{BASE}/stock-items", json={
        "name": '=HYPERLINK("https://evil.example","x")',
        "stock_level_id": level_id,
    })
    assert created.status_code in (200, 201), created.text
    item_id = created.json()["stock_item_id"]

    resp = requests.get(f"{BASE}/stock-items/export?format=csv&ids={item_id}")

    assert resp.status_code == 200, resp.text
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert len(rows) == 2
    header, row = rows
    assert row[header.index("name")] == '\'=HYPERLINK("https://evil.example","x")'
