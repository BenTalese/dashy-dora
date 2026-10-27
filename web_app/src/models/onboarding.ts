// Mirrors OnboardingStateDto / SeedResultDto from
// dora_api/features/onboarding/onboarding.py.

/** `{first_user}` only — completion rides `/auth/me` and the old store hint
 *  had no reader (finalisation 14-R12). */
export type OnboardingState = {
    first_user: boolean;
};

export type SeedRequest = {
    groups: boolean;
    locations: boolean;
    // optional per-name filter over the bundled defaults. Null
    // (or omitted) means "seed all" when the bool is true; a provided
    // list narrows the seed to just those names/paths.
    //
    // location_paths use "Zone" for a top-level zone alone, or
    // "Zone/Child" for a child under it. Selecting a child implicitly
    // creates its parent zone even when the parent's path isn't listed.
    group_names?: string[] | null;
    location_paths?: string[] | null;
    // The user's own group / zone names from the stock step, created in the
    // same unit of work as the defaults (finalisation 14-R19).
    extra_group_names?: string[] | null;
    extra_location_names?: string[] | null;
};

export type SeedResult = {
    groups_created: number;
    groups_skipped: number;
    locations_created: number;
    locations_skipped: number;
};

// starter catalogue (default groups/locations + starter packs) the
// wizard previews and lets the user pick from. Served by GET /onboarding/catalog.
export type LocationNode = {
    name: string;
    kind: string;
    children: LocationNode[];
};

export type StarterPackItem = {
    name: string;
    group: string | null;
    location: string | null;
};

export type StarterPack = {
    key: string;
    label: string;
    blurb: string;
    items: StarterPackItem[];
};

export type OnboardingCatalog = {
    groups: string[];
    locations: LocationNode[];
    packs: StarterPack[];
};

// create stock items by NAME (group/location resolved server-side
// against the seeded catalogues). Used for both starter-pack picks and the
// wizard's first stock items. Idempotent (dedupe by name).
export type SeedItemInput = {
    name: string;
    group_name?: string | null;
    location_name?: string | null;
};

export type SeedItemsRequest = {
    items: SeedItemInput[];
};

export type SeedItemsResult = {
    created: number;
    skipped: number;
};

// opt-in demo dataset (one recipe + the StockItems it needs + a
// current-week MealPlan with one entry). The handler is idempotent; `seeded`
// is `false` when the demo recipe already existed (so a re-finish never
// duplicates rows).
export type SeedDemoResult = {
    seeded: boolean;
    items_created: number;
    recipe_created: boolean;
    meal_plan_created: boolean;
};
