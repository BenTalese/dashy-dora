// THIS FILE IS GENERATED — DO NOT EDIT BY HAND.
// Source of truth: dora_api/domain/units.py
// Regenerate via: python scripts/dump_units.py
//
// Mirror of the server-side unit-conversion table for the offline assistant
// rule-engine fallback (web_app/src/services/doraIntents.ts) and the
// price-entry widget's instant validation (web_app/src/components/dora/
// PriceEntry.vue). R-003: nothing here is hand-maintained.


export type Dimension =
    | 'volume'
    | 'mass'
    | 'count'
    | 'temperature'
    | 'length'
    | 'energy';

export const PRICE_DIMENSIONS: ReadonlyArray<Dimension> = ['volume', 'mass', 'count'];

export interface UnitDef {
    /** Dimension the unit belongs to. */
    readonly dimension: Dimension;
    /** Multiplier to the dimension's base unit (ml / g / ea / mm / kJ). */
    readonly factor: number;
    /** Preferred display string (e.g. "L" for "litre"). */
    readonly canonical: string;
}


export const UNIT_TABLE: Readonly<Record<string, UnitDef>> = {
    "ml": { dimension: "volume", factor: 1.0, canonical: "ml" },
    "milliliter": { dimension: "volume", factor: 1.0, canonical: "ml" },
    "millilitre": { dimension: "volume", factor: 1.0, canonical: "ml" },
    "milliliters": { dimension: "volume", factor: 1.0, canonical: "ml" },
    "millilitres": { dimension: "volume", factor: 1.0, canonical: "ml" },
    "l": { dimension: "volume", factor: 1000.0, canonical: "L" },
    "litre": { dimension: "volume", factor: 1000.0, canonical: "L" },
    "liter": { dimension: "volume", factor: 1000.0, canonical: "L" },
    "litres": { dimension: "volume", factor: 1000.0, canonical: "L" },
    "liters": { dimension: "volume", factor: 1000.0, canonical: "L" },
    "smidgen": { dimension: "volume", factor: 0.156, canonical: "smidgen" },
    "smidge": { dimension: "volume", factor: 0.156, canonical: "smidgen" },
    "pinch": { dimension: "volume", factor: 0.3125, canonical: "pinch" },
    "pinches": { dimension: "volume", factor: 0.3125, canonical: "pinch" },
    "dash": { dimension: "volume", factor: 0.625, canonical: "dash" },
    "dashes": { dimension: "volume", factor: 0.625, canonical: "dash" },
    "tsp": { dimension: "volume", factor: 5.0, canonical: "tsp" },
    "teaspoon": { dimension: "volume", factor: 5.0, canonical: "tsp" },
    "teaspoons": { dimension: "volume", factor: 5.0, canonical: "tsp" },
    "tbsp": { dimension: "volume", factor: 20.0, canonical: "tbsp" },
    "tablespoon": { dimension: "volume", factor: 20.0, canonical: "tbsp" },
    "tablespoons": { dimension: "volume", factor: 20.0, canonical: "tbsp" },
    "us tbsp": { dimension: "volume", factor: 14.7868, canonical: "US tbsp" },
    "american tbsp": { dimension: "volume", factor: 14.7868, canonical: "US tbsp" },
    "us tablespoon": { dimension: "volume", factor: 14.7868, canonical: "US tbsp" },
    "cup": { dimension: "volume", factor: 250.0, canonical: "cup" },
    "cups": { dimension: "volume", factor: 250.0, canonical: "cup" },
    "us cup": { dimension: "volume", factor: 240.0, canonical: "US cup" },
    "us cups": { dimension: "volume", factor: 240.0, canonical: "US cup" },
    "american cup": { dimension: "volume", factor: 240.0, canonical: "US cup" },
    "american cups": { dimension: "volume", factor: 240.0, canonical: "US cup" },
    "fl oz": { dimension: "volume", factor: 29.5735, canonical: "fl oz" },
    "floz": { dimension: "volume", factor: 29.5735, canonical: "fl oz" },
    "fluid ounce": { dimension: "volume", factor: 29.5735, canonical: "fl oz" },
    "fluid ounces": { dimension: "volume", factor: 29.5735, canonical: "fl oz" },
    "pint": { dimension: "volume", factor: 568.261, canonical: "pt" },
    "pints": { dimension: "volume", factor: 568.261, canonical: "pt" },
    "pt": { dimension: "volume", factor: 568.261, canonical: "pt" },
    "quart": { dimension: "volume", factor: 946.353, canonical: "qt" },
    "quarts": { dimension: "volume", factor: 946.353, canonical: "qt" },
    "qt": { dimension: "volume", factor: 946.353, canonical: "qt" },
    "gallon": { dimension: "volume", factor: 3785.41, canonical: "gal" },
    "gallons": { dimension: "volume", factor: 3785.41, canonical: "gal" },
    "gal": { dimension: "volume", factor: 3785.41, canonical: "gal" },
    "mg": { dimension: "mass", factor: 0.001, canonical: "mg" },
    "milligram": { dimension: "mass", factor: 0.001, canonical: "mg" },
    "milligrams": { dimension: "mass", factor: 0.001, canonical: "mg" },
    "g": { dimension: "mass", factor: 1.0, canonical: "g" },
    "gm": { dimension: "mass", factor: 1.0, canonical: "g" },
    "gram": { dimension: "mass", factor: 1.0, canonical: "g" },
    "grams": { dimension: "mass", factor: 1.0, canonical: "g" },
    "kg": { dimension: "mass", factor: 1000.0, canonical: "kg" },
    "kilo": { dimension: "mass", factor: 1000.0, canonical: "kg" },
    "kilos": { dimension: "mass", factor: 1000.0, canonical: "kg" },
    "kilogram": { dimension: "mass", factor: 1000.0, canonical: "kg" },
    "kilograms": { dimension: "mass", factor: 1000.0, canonical: "kg" },
    "oz": { dimension: "mass", factor: 28.3495, canonical: "oz" },
    "ounce": { dimension: "mass", factor: 28.3495, canonical: "oz" },
    "ounces": { dimension: "mass", factor: 28.3495, canonical: "oz" },
    "lb": { dimension: "mass", factor: 453.592, canonical: "lb" },
    "lbs": { dimension: "mass", factor: 453.592, canonical: "lb" },
    "pound": { dimension: "mass", factor: 453.592, canonical: "lb" },
    "pounds": { dimension: "mass", factor: 453.592, canonical: "lb" },
    "stick": { dimension: "mass", factor: 113.0, canonical: "stick" },
    "sticks": { dimension: "mass", factor: 113.0, canonical: "stick" },
    "ea": { dimension: "count", factor: 1.0, canonical: "ea" },
    "each": { dimension: "count", factor: 1.0, canonical: "ea" },
    "unit": { dimension: "count", factor: 1.0, canonical: "ea" },
    "units": { dimension: "count", factor: 1.0, canonical: "ea" },
    "whole": { dimension: "count", factor: 1.0, canonical: "whole" },
    "wholes": { dimension: "count", factor: 1.0, canonical: "whole" },
    "pack": { dimension: "count", factor: 1.0, canonical: "pack" },
    "packs": { dimension: "count", factor: 1.0, canonical: "pack" },
    "dozen": { dimension: "count", factor: 12.0, canonical: "dozen" },
    "dozens": { dimension: "count", factor: 12.0, canonical: "dozen" },
    "mm": { dimension: "length", factor: 1.0, canonical: "mm" },
    "millimeter": { dimension: "length", factor: 1.0, canonical: "mm" },
    "millimetre": { dimension: "length", factor: 1.0, canonical: "mm" },
    "millimeters": { dimension: "length", factor: 1.0, canonical: "mm" },
    "millimetres": { dimension: "length", factor: 1.0, canonical: "mm" },
    "cm": { dimension: "length", factor: 10.0, canonical: "cm" },
    "centimeter": { dimension: "length", factor: 10.0, canonical: "cm" },
    "centimetre": { dimension: "length", factor: 10.0, canonical: "cm" },
    "centimeters": { dimension: "length", factor: 10.0, canonical: "cm" },
    "centimetres": { dimension: "length", factor: 10.0, canonical: "cm" },
    "m": { dimension: "length", factor: 1000.0, canonical: "m" },
    "meter": { dimension: "length", factor: 1000.0, canonical: "m" },
    "metre": { dimension: "length", factor: 1000.0, canonical: "m" },
    "meters": { dimension: "length", factor: 1000.0, canonical: "m" },
    "metres": { dimension: "length", factor: 1000.0, canonical: "m" },
    "in": { dimension: "length", factor: 25.4, canonical: "in" },
    "inch": { dimension: "length", factor: 25.4, canonical: "in" },
    "inches": { dimension: "length", factor: 25.4, canonical: "in" },
    "\"": { dimension: "length", factor: 25.4, canonical: "in" },
    "ft": { dimension: "length", factor: 304.8, canonical: "ft" },
    "foot": { dimension: "length", factor: 304.8, canonical: "ft" },
    "feet": { dimension: "length", factor: 304.8, canonical: "ft" },
    "kj": { dimension: "energy", factor: 1.0, canonical: "kJ" },
    "kilojoule": { dimension: "energy", factor: 1.0, canonical: "kJ" },
    "kilojoules": { dimension: "energy", factor: 1.0, canonical: "kJ" },
    "kcal": { dimension: "energy", factor: 4.184, canonical: "kcal" },
    "cal": { dimension: "energy", factor: 4.184, canonical: "kcal" },
    "calorie": { dimension: "energy", factor: 4.184, canonical: "kcal" },
    "calories": { dimension: "energy", factor: 4.184, canonical: "kcal" },
    "j": { dimension: "energy", factor: 0.001, canonical: "J" },
    "joule": { dimension: "energy", factor: 0.001, canonical: "J" },
    "joules": { dimension: "energy", factor: 0.001, canonical: "J" },
};

export type MeasurementSystem = 'metric' | 'imperial' | 'us';

export const MEASUREMENT_SYSTEMS: ReadonlyArray<MeasurementSystem> = ["metric", "imperial", "us"];

/** Canonical units that belong to every system — the informal cooking
 *  amounts, the count units, and energy. Always offered. */
export const UNIVERSAL_CANONICAL_UNITS: ReadonlySet<string> = new Set(["J", "dash", "dozen", "ea", "kJ", "kcal", "pack", "pinch", "smidgen", "tsp", "whole"]);

/** Canonical unit → the systems that offer it. Units absent from both
 *  this map and `UNIVERSAL_CANONICAL_UNITS` are offered by no system. */
export const UNIT_SYSTEMS: Readonly<Record<string, ReadonlyArray<MeasurementSystem>>> = {
    "ml": ["imperial", "metric"],
    "L": ["imperial", "metric"],
    "tbsp": ["imperial", "metric"],
    "cup": ["imperial", "metric"],
    "US tbsp": ["us"],
    "US cup": ["us"],
    "fl oz": ["imperial", "us"],
    "pt": ["imperial"],
    "qt": ["us"],
    "gal": ["us"],
    "mg": ["imperial", "metric"],
    "g": ["imperial", "metric"],
    "kg": ["imperial", "metric"],
    "oz": ["imperial", "us"],
    "lb": ["imperial", "us"],
    "stick": ["us"],
    "mm": ["imperial", "metric"],
    "cm": ["imperial", "metric"],
    "m": ["imperial", "metric"],
    "in": ["imperial", "us"],
    "ft": ["imperial", "us"],
};

export interface DisplayDenominator {
    /** What the denominator is called on a shelf label. */
    readonly label: string;
    /** Divide a price in the dimension's canonical price unit by this. */
    readonly factor: number;
}

export interface DenominatorRule {
    readonly full: DisplayDenominator;
    readonly sub: DisplayDenominator;
    /** Pack size, in the dimension's canonical price unit, at or above
     *  which `full` takes over from `sub`; null means it never does. */
    readonly flipAt: number | null;
}

export type PricingConvention = 'AU' | 'US';

/** The dimension's **compute** denominator — what a per-unit price is
 *  normalised to before a display rule is applied. */
export const CANONICAL_PRICE_UNIT: Readonly<Record<string, string>> = {
    "volume": "L",
    "mass": "kg",
    "count": "ea",
};

/** Count has no fractional convention either way, so it sits outside
 *  the rule table. */
export const COUNT_DENOMINATOR: DisplayDenominator = { label: "ea", factor: 1.0 };

export const PRICE_DISPLAY_RULES: Readonly<Record<PricingConvention, Readonly<Record<string, DenominatorRule>>>> = {
    "AU": {
        "volume": { full: { label: "L", factor: 1.0 }, sub: { label: "100ml", factor: 10.0 }, flipAt: null },
        "mass": { full: { label: "kg", factor: 1.0 }, sub: { label: "100g", factor: 10.0 }, flipAt: null },
    },
    "US": {
        "volume": { full: { label: "qt", factor: 1.0566882094325938 }, sub: { label: "fl oz", factor: 33.81405650328842 }, flipAt: 0.946352946 },
        "mass": { full: { label: "lb", factor: 2.2046226218487757 }, sub: { label: "oz", factor: 35.27399072294044 }, flipAt: 0.45359237 },
    },
};

/** Which convention a measurement system prices by. Only the US
 *  sells by the quart and the pound; the UK is metric on the shelf. */
export const PRICING_CONVENTION_BY_SYSTEM: Readonly<Record<MeasurementSystem, PricingConvention>> = {
    "metric": "AU",
    "imperial": "AU",
    "us": "US",
};

export const INGREDIENT_DENSITY_G_PER_ML: Readonly<Record<string, number>> = {
    "water": 1.0,
    "milk": 1.03,
    "olive oil": 0.92,
    "oil": 0.92,
    "vegetable oil": 0.92,
    "canola oil": 0.92,
    "honey": 1.42,
    "maple syrup": 1.32,
    "golden syrup": 1.4,
    "flour": 0.53,
    "plain flour": 0.53,
    "all-purpose flour": 0.53,
    "all purpose flour": 0.53,
    "self-raising flour": 0.53,
    "self raising flour": 0.53,
    "wholemeal flour": 0.56,
    "whole wheat flour": 0.56,
    "bread flour": 0.55,
    "almond flour": 0.42,
    "almond meal": 0.42,
    "sugar": 0.85,
    "white sugar": 0.85,
    "caster sugar": 0.85,
    "granulated sugar": 0.85,
    "brown sugar": 0.93,
    "icing sugar": 0.56,
    "powdered sugar": 0.56,
    "confectioners sugar": 0.56,
    "butter": 0.91,
    "margarine": 0.91,
    "yogurt": 1.04,
    "greek yogurt": 1.05,
    "yoghurt": 1.04,
    "greek yoghurt": 1.05,
    "sour cream": 0.95,
    "cream cheese": 0.95,
    "ricotta": 0.85,
    "mascarpone": 1.0,
    "cream": 1.0,
    "heavy cream": 1.0,
    "thickened cream": 1.0,
    "ice cream": 0.55,
    "peanut butter": 1.05,
    "rice": 0.78,
    "white rice": 0.78,
    "brown rice": 0.76,
    "rolled oats": 0.41,
    "oats": 0.41,
    "porridge oats": 0.41,
    "quinoa": 0.72,
    "couscous": 0.72,
    "dried lentils": 0.85,
    "lentils": 0.85,
    "dried beans": 0.85,
    "chickpeas": 0.78,
    "pasta": 0.5,
    "dry pasta": 0.5,
    "cornstarch": 0.65,
    "cornflour": 0.65,
    "chocolate chips": 0.65,
    "chocolate": 0.62,
    "chopped almonds": 0.5,
    "sliced almonds": 0.45,
    "whole almonds": 0.6,
    "chopped walnuts": 0.55,
    "walnuts": 0.55,
    "raisins": 0.65,
    "sultanas": 0.65,
    "shredded coconut": 0.3,
    "desiccated coconut": 0.45,
    "breadcrumbs": 0.45,
    "panko": 0.3,
    "cocoa powder": 0.51,
    "cocoa": 0.51,
    "salt": 1.2,
    "parmesan": 0.45,
    "grated parmesan": 0.45,
    "cheddar": 0.48,
    "grated cheddar": 0.48,
    "grated cheese": 0.48,
};

export const GAS_MARK_TO_C: Readonly<Record<string, number>> = {
    "1/4": 110,
    "1/2": 120,
    "1": 140,
    "2": 150,
    "3": 160,
    "4": 180,
    "5": 190,
    "6": 200,
    "7": 220,
    "8": 230,
    "9": 240,
};

export const GAS_MARK_ALIASES: ReadonlySet<string> = new Set(["gas", "gas mark", "gm"]);

export interface CanonicalUnitChoice {
    readonly canonical: string;
    readonly label: string;
    readonly dimension: Dimension;
}

export const SUPPORTED_PRICE_UNITS: ReadonlyArray<CanonicalUnitChoice> = [
    { canonical: "ml", label: "ml", dimension: "volume" },
    { canonical: "L", label: "L", dimension: "volume" },
    { canonical: "g", label: "g", dimension: "mass" },
    { canonical: "kg", label: "kg", dimension: "mass" },
    { canonical: "oz", label: "oz", dimension: "mass" },
    { canonical: "lb", label: "lb", dimension: "mass" },
    { canonical: "ea", label: "ea", dimension: "count" },
    { canonical: "pack", label: "pack", dimension: "count" },
    { canonical: "dozen", label: "dozen", dimension: "count" },
];

/** DEC-3: units written tight against the number ("250g"). */
export const NO_SPACE_UNITS: ReadonlySet<string> = new Set(["floz", "g", "kg", "l", "lb", "mg", "ml", "oz", "pt", "qt"]);

/** Units a quantity is counted in — scaling rounds these to whole numbers.
 *  Singular forms; `isCountableUnit` also accepts the plural. */
export const COUNTABLE_UNITS: ReadonlySet<string> = new Set(["bunch", "can", "clove", "egg", "floret", "head", "knob", "leaf", "piece", "pinch", "rasher", "scoop", "slice", "sprig", "stalk", "stick", "wedge"]);

/** Cooking words the ingredient picker offers beside the table units. */
export const COOKING_WORD_UNITS: ReadonlyArray<string> = ["bunch", "can", "clove", "drizzle", "egg", "floret", "handful", "head", "knob", "leaf", "piece", "rasher", "scoop", "slice", "splash", "sprig", "stalk", "wedge"];
