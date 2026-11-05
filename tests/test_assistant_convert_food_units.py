"""FU-900: the assistant's convert tool applies a food-specific unit's weight
only to a food it belongs to ("2 sticks of butter" is 226 g; "2 sticks" of
anything else, or of nothing named, is a question back)."""
from dora_api.features.assistant.tools import convert_measurement


def test__stick_of_butter__converts():
    result = convert_measurement({"amount": "2", "from_unit": "stick", "to_unit": "g", "ingredient": "butter"})
    assert result[0]["result"] == 226


def test__stick_without_a_food__asks():
    result = convert_measurement({"amount": "2", "from_unit": "sticks", "to_unit": "g"})
    assert "error" in result[0]


def test__stick_of_celery__asks():
    result = convert_measurement({"amount": "2", "from_unit": "stick", "to_unit": "g", "ingredient": "celery"})
    assert "error" in result[0]


def test__ordinary_units__unaffected():
    result = convert_measurement({"amount": "1", "from_unit": "kg", "to_unit": "g"})
    assert result[0]["result"] == 1000
