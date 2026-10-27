"""Finalisation 18-R12 — slash dates in a spreadsheet import follow the
install locale's day/month order (`AppSetting.locale` is the one authority,
R-021 / R-003); ISO always wins and the other order remains a last resort."""
from datetime import date

from dora_api.features.data.import_spreadsheet import _coerce_to_date


def test__coerce_to_date__iso_wins_regardless_of_locale():
    assert _coerce_to_date("2027-04-03", day_first=True) == date(2027, 4, 3)
    assert _coerce_to_date("2027-04-03", day_first=False) == date(2027, 4, 3)


def test__coerce_to_date__slash_dates_follow_the_install_day_order():
    assert _coerce_to_date("03/04/2027", day_first=True) == date(2027, 4, 3)
    assert _coerce_to_date("03/04/2027", day_first=False) == date(2027, 3, 4)


def test__coerce_to_date__unambiguous_other_order_still_parses():
    assert _coerce_to_date("25/12/2027", day_first=False) == date(2027, 12, 25)
    assert _coerce_to_date("12/25/2027", day_first=True) == date(2027, 12, 25)
