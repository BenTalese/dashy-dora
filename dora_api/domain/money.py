"""Money as text on the server: the deals email and the assistant's replies
(finalisation 11-R13; the assistant hard-coded `$`). The SPA formats through
`Intl.NumberFormat`; this is the server's plain-text counterpart."""
from dora_api.domain.locale_format import format_locale_money


_CURRENCY_SYMBOLS = {
    "AUD": "$", "NZD": "$", "USD": "$", "CAD": "$",
    "GBP": "£", "EUR": "€", "JPY": "¥",
}


def format_money(amount: float | None, currency: str, locale: str | None = None) -> str:
    """Two decimal places, prefixed with the install's currency symbol or its
    ISO code. `None` renders as a dash rather than "0.00" — a missing
    price is not a free product.

    With `locale` (the household's `AppSetting.locale`) the amount is written
    the way that locale writes money, as the SPA's `Intl.NumberFormat` does:
    "$7.99" under en-AU, "7,99 €" under de-DE (`locale_format`). Without it,
    the plain symbol-prefix form below, which the assistant's replies use."""
    if amount is None:
        return "–"
    if locale:
        return format_locale_money(amount, currency, locale)
    symbol = _CURRENCY_SYMBOLS.get((currency or "").upper())
    if symbol:
        return f"{symbol}{amount:.2f}"
    return f"{(currency or '').upper()} {amount:.2f}".strip()
