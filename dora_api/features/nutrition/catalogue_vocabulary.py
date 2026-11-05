"""AU/UK food words, in the US words the nutrition catalogue uses (FU-643).

The catalogue (USDA) is US vocabulary from end to end, and the matcher scores
word overlap, so "Tinned tomatoes" never met "Tomatoes, canned" and an
Australian pantry got "no match" for capsicum, aubergine, mince and prawns.
Before scoring, the stock item's name has these phrases swapped for the
catalogue's words. Only the stock-item side is rewritten; catalogue names are
never touched, and a US name has nothing here to match, so it scores as before.

A plain table on purpose (R-019, no magic): one row per word, read top to
bottom, easy to extend when a "no match" turns out to be a vocabulary gap.
Multi-word phrases are matched before single words ("spring onion" before
"onion" would ever matter), on whole words only.
"""
import re

CATALOGUE_WORDS: dict[str, str] = {
    # Vegetables
    "capsicum": "sweet pepper",
    "capsicums": "sweet pepper",
    "aubergine": "eggplant",
    "aubergines": "eggplant",
    "courgette": "zucchini",
    "courgettes": "zucchini",
    "rocket": "arugula",
    "coriander": "cilantro coriander",
    "spring onion": "scallion",
    "spring onions": "scallion",
    "shallot": "scallion",
    "beetroot": "beet",
    "swede": "rutabaga",
    "mangetout": "snow pea",
    "snow peas": "snow pea",
    "broad beans": "fava bean",
    "broad bean": "fava bean",
    "butter beans": "lima bean",
    "cos lettuce": "romaine lettuce",
    "cos": "romaine",
    "butternut pumpkin": "butternut squash",
    "kumara": "sweet potato",
    "rockmelon": "cantaloupe",
    "chickpeas": "chickpea garbanzo",
    # Meat and seafood
    "mince": "ground",
    "minced": "ground",
    "prawns": "shrimp",
    "prawn": "shrimp",
    "streaky bacon": "bacon",
    # Pantry
    "tinned": "canned",
    "tin": "canned",
    "plain flour": "all purpose flour",
    "self raising flour": "self rising flour",
    "self-raising flour": "self rising flour",
    "cornflour": "cornstarch",
    "icing sugar": "powdered sugar",
    "caster sugar": "granulated sugar",
    "bicarbonate of soda": "baking soda",
    "bicarb soda": "baking soda",
    "thickened cream": "heavy cream",
    "double cream": "heavy cream",
    "single cream": "light cream",
    "biscuits": "cookies",
    "biscuit": "cookie",
    "wholemeal": "whole wheat",
    "sultanas": "raisins golden",
    "lollies": "candies",
    "porridge oats": "rolled oats",
}

# Longest phrases first, so "spring onion" wins over a shorter key inside it.
_PATTERN = re.compile(
    r"\b(" + "|".join(
        re.escape(k) for k in sorted(CATALOGUE_WORDS, key=len, reverse=True)
    ) + r")\b",
    re.IGNORECASE,
)


def in_catalogue_words(name: str) -> str:
    """``name`` with AU/UK food words swapped for the catalogue's."""
    return _PATTERN.sub(lambda m: CATALOGUE_WORDS[m.group(0).lower()], name or "")
