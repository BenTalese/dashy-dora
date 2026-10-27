/**
 * DS2 — central icon catalogue.
 *
 * The app standardised on Material Design Icons (mdi-v7). Quasar's
 * iconSet is set in quasar.config.ts; every explicit icon reference
 * in the codebase goes through this map.
 *
 * The map is keyed by the *original* Material Icons name (snake_case)
 * so the historic sweep was a mechanical `icon="x"` → `:icon="ICONS.x"`
 * replacement. New code is encouraged to use the SEMANTIC aliases at
 * the bottom (e.g. `ICONS.add`, `ICONS.confirm`) rather than the raw
 * material name — they communicate intent and survive icon-set
 * changes without touching call sites.
 *
 * Adding a new icon:
 *   1. Look up the MDI name at https://pictogrammers.com/library/mdi/
 *   2. Add `<material-name>: 'mdi-<kebab-name>'` below.
 *   3. If the icon represents a domain concept (e.g. essential,
 *      merchant, location), add a semantic alias at the bottom.
 */
export const ICONS = {
    // ── 1:1 mapping from the Material Icons names used in templates ─
    account_circle: 'mdi-account-circle',
    add: 'mdi-plus',
    add_link: 'mdi-link-plus',
    add_shopping_cart: 'mdi-cart-plus',
    arrow_back: 'mdi-arrow-left',
    arrow_downward: 'mdi-arrow-down',
    arrow_upward: 'mdi-arrow-up',
    subdirectory_arrow_right: 'mdi-subdirectory-arrow-right',
    notes: 'mdi-note-text-outline',
    payments: 'mdi-cash',
    // A bare dollar glyph. The buy-verdict card leads with this in every
    // state (2026-08-21 feedback) — a per-verdict glyph put a question
    // mark in a bubble on `unsure`, which read as an info chip rather
    // than as "this card is about money".
    currency_usd: 'mdi-currency-usd',
    language: 'mdi-translate',
    record_voice_over: 'mdi-microphone-message',
    // The listening toggle's two faces. Added 2026-08-27 because cook
    // mode and Dora chat were passing the bare Material names 'mic' /
    // 'mic_off' / 'mic_none' straight to `q-btn`. This app's icon set is
    // MDI, so an unprefixed Material name isn't resolved as an icon at
    // all — Quasar renders it as a ligature, which with no Material font
    // loaded means the button literally read "mic_off" in text. Every
    // icon goes through this map (R-034); these were the two that didn't.
    mic: 'mdi-microphone',
    mic_off: 'mdi-microphone-off',
    mic_none: 'mdi-microphone-outline',
    auto_awesome: 'mdi-auto-fix',
    barcode: 'mdi-barcode',
    bolt: 'mdi-lightning-bolt',
    bookmark: 'mdi-bookmark',
    bug_report: 'mdi-bug',
    cancel: 'mdi-cancel',
    check: 'mdi-check',
    check_box: 'mdi-checkbox-marked',
    check_box_outline_blank: 'mdi-checkbox-blank-outline',
    check_circle: 'mdi-check-circle',
    checklist: 'mdi-format-list-checks',
    chevron_left: 'mdi-chevron-left',
    // Neutral "nothing here yet" state marker — the empty counterpart to
    // check_circle. Says no more than that on purpose: a (?) in this slot
    // reads as a control that will explain something when clicked.
    circle_outline: 'mdi-circle-outline',
    clear: 'mdi-close',
    close: 'mdi-close',
    compare: 'mdi-compare-horizontal',
    content_copy: 'mdi-content-copy',
    content_paste: 'mdi-content-paste',
    dark_mode: 'mdi-weather-night',
    delete: 'mdi-delete',
    delete_outline: 'mdi-delete-outline',
    done_all: 'mdi-check-all',
    // Dora's own voice — every "Dora thinks…" / "Dora suggests…" surface, and
    // nothing else. A literal burger, because the mascot is one (owner pick,
    // 2026-09-01): it says "this line is Dora's read, not a fact you recorded"
    // without borrowing a glyph that already means something else here.
    //   It replaced two icons that were doing this job side by side — the
    //   magic wand (`auto_awesome`) on "Dora suggests" and a
    //   lightbulb-with-a-question (`inferred_hunch`) on "Dora thinks" — which
    //   read as two different systems talking.
    //   `auto_awesome` is NOT retired, but its territory shrank on 2026-09-03:
    //   the owner asked for *"the consistent Dora burger icon"* on **Build my
    //   week**, which the wand/burger split had assigned to the wand ("wand =
    //   an action she performs; burger = an opinion she holds"). The revised
    //   rule: the burger is Dora's MARK — it goes on anything the user reads as
    //   Dora doing or thinking something, action or opinion. The wand is left
    //   with the AI-mode marker, where it means "a model is involved", not
    //   "Dora".
    //   The two sites left on the wand after that batch are gone: the plan
    //   row's hint became a burger, and the dashboard's Draft my shop card was
    //   deleted (FU-864).
    // Not to be confused with `menu` (mdi-menu) — MDI's hamburger is a drawn
    // sesame-bun burger, not three bars, and the two never appear together.
    dora_voice: 'mdi-hamburger',
    download: 'mdi-download',
    drive_file_move: 'mdi-folder-move',
    east: 'mdi-arrow-right',
    edit: 'mdi-pencil',
    event: 'mdi-calendar',
    expand_more: 'mdi-chevron-down',
    fact_check: 'mdi-clipboard-check',
    file_download: 'mdi-file-download',
    filter_alt_off: 'mdi-filter-off',
    filter_list: 'mdi-filter-variant',
    flag: 'mdi-flag',
    health_and_safety: 'mdi-shield-plus',
    help_outline: 'mdi-help-circle-outline',
    history: 'mdi-history',
    home: 'mdi-home',
    info: 'mdi-information',
    install_desktop: 'mdi-monitor-arrow-down',
    kitchen: 'mdi-fridge',
    lightbulb: 'mdi-lightbulb',
    light_mode: 'mdi-weather-sunny',
    link: 'mdi-link',
    link_off: 'mdi-link-off',
    list: 'mdi-format-list-bulleted',
    list_alt: 'mdi-format-list-checkbox',
    local_offer: 'mdi-tag',
    tag_multiple: 'mdi-tag-multiple',
    lock_open: 'mdi-lock-open',
    lock_reset: 'mdi-lock-reset',
    logout: 'mdi-logout',
    menu: 'mdi-menu',
    menu_book: 'mdi-book-open-page-variant',
    monitor_heart: 'mdi-heart-pulse',
    more_horiz: 'mdi-dots-horizontal',
    more_vert: 'mdi-dots-vertical',
    new_releases: 'mdi-new-box',
    notifications: 'mdi-bell',
    notifications_active: 'mdi-bell-ring',
    open_in_new: 'mdi-open-in-new',
    pause: 'mdi-pause',
    photo_camera: 'mdi-camera',
    picture_as_pdf: 'mdi-file-pdf-box',
    place: 'mdi-map-marker',
    play_arrow: 'mdi-play',
    print: 'mdi-printer',
    priority_high: 'mdi-exclamation',
    qr_code: 'mdi-qrcode',
    qr_code_scanner: 'mdi-qrcode-scan',
    receipt_long: 'mdi-receipt-text',
    redo: 'mdi-redo',
    refresh: 'mdi-refresh',
    remove: 'mdi-minus',
    remove_shopping_cart: 'mdi-cart-remove',
    replay: 'mdi-replay',
    report: 'mdi-alert-octagon',
    restart_alt: 'mdi-restart',
    restaurant: 'mdi-silverware-fork-knife',
    save: 'mdi-content-save',
    schedule: 'mdi-clock-outline',
    search: 'mdi-magnify',
    send: 'mdi-send',
    shopping_cart: 'mdi-cart',
    skip_next: 'mdi-skip-next',
    smart_toy: 'mdi-robot-happy',
    snooze: 'mdi-alarm-snooze',
    // PROPOSAL_STOCKTAKE_MODE §5 — Mute action on the runner card and
    // its inverse on the item-detail page (un-mute).
    mute: 'mdi-bell-off-outline',
    unmute: 'mdi-bell-outline',
    star: 'mdi-star',
    star_outline: 'mdi-star-outline',
    // Health Star Rating 2026-08-27 — the scheme is scored in half-star
    // steps, so a half glyph is load-bearing, not decoration.
    star_half: 'mdi-star-half-full',
    storage: 'mdi-database',
    swap_horiz: 'mdi-swap-horizontal',
    tune: 'mdi-tune',
    undo: 'mdi-undo',
    visibility_off: 'mdi-eye-off',
    visibility: 'mdi-eye',
    wifi_tethering: 'mdi-broadcast',
    warning: 'mdi-alert',
    volume_up: 'mdi-volume-high',
    volume_off: 'mdi-volume-off',

    // Nav / Layout (added during the sweep — these never appeared as
    // bare `icon="x"` strings but live in command-palette + drawer
    // configs, so they still need an MDI mapping).
    dashboard: 'mdi-view-dashboard',
    inventory_2: 'mdi-package-variant-closed',
    shopping_bag: 'mdi-shopping-outline',
    calendar_month: 'mdi-calendar-month',
    settings: 'mdi-cog',
    insights: 'mdi-chart-line',
    hub: 'mdi-hub',
    map: 'mdi-map',
    favorite: 'mdi-heart',
    favorite_border: 'mdi-heart-outline',
    volunteer_activism: 'mdi-hand-heart',
    coffee: 'mdi-coffee',
    keyboard: 'mdi-keyboard',
    play_circle: 'mdi-play-circle',
    add_box: 'mdi-plus-box',
    brightness_auto: 'mdi-brightness-auto',
    sync: 'mdi-sync',
    // Connectivity banner (finalisation 17-R21).
    wifi_off: 'mdi-wifi-off',
    sync_problem: 'mdi-sync-alert',

    // Status / level / domain icons used in stock + alerts.
    event_busy: 'mdi-calendar-remove',
    event_repeat: 'mdi-calendar-refresh',
    event_available: 'mdi-calendar-check',
    event_note: 'mdi-calendar-edit',
    // "No expiry set" — an *empty* calendar. Deliberately not a variant
    // of `event_available` (mdi-calendar-check): the two states used to
    // differ by colour alone, and a far-future expiry reads the same as no
    // expiry at a glance (owner feedback 2026-08-27).
    event_blank: 'mdi-calendar-blank-outline',
    inventory: 'mdi-package-variant',
    trending_down: 'mdi-trending-down',
    trending_up: 'mdi-trending-up',
    trending_flat: 'mdi-trending-neutral',
    circle: 'mdi-circle',

    // Additional UI icons surfaced by the JS-literal sweep.
    adjust: 'mdi-circle-double',
    announcement: 'mdi-bullhorn',
    archive: 'mdi-archive',
    arrow_forward: 'mdi-arrow-right',
    attach_file: 'mdi-paperclip',
    bookmark_add: 'mdi-bookmark-plus',
    bookmarks: 'mdi-bookmark-multiple',
    category: 'mdi-shape',
    blender: 'mdi-blender',
    eco: 'mdi-leaf',
    public: 'mdi-earth',
    celebration: 'mdi-party-popper',
    chat_bubble_outline: 'mdi-chat-outline',
    chevron_right: 'mdi-chevron-right',
    cloud_download: 'mdi-cloud-download',
    cloud_off: 'mdi-cloud-off-outline',
    image_off: 'mdi-image-off-outline',
    // PageErrorState variants (finalisation 20-R21 / R-034).
    not_found_explore: 'mdi-map-search-outline',
    blocked: 'mdi-cancel',
    error_outline: 'mdi-alert-circle-outline',
    cloud_upload: 'mdi-cloud-upload',
    code: 'mdi-code-tags',
    compare_arrows: 'mdi-compare-horizontal',
    donut_large: 'mdi-chart-donut',
    drag_indicator: 'mdi-drag',
    emoji_emotions: 'mdi-emoticon-happy-outline',
    error: 'mdi-alert-circle',
    file_upload: 'mdi-file-upload',
    folder: 'mdi-folder',
    google: 'mdi-google',
    group: 'mdi-account-group',
    person_add: 'mdi-account-plus',
    help: 'mdi-help',
    home_pin: 'mdi-home-map-marker',
    // `icon` is a placeholder used as a fallback when no specific icon
    // was supplied — render as a neutral help glyph rather than nothing.
    icon: 'mdi-help-box-outline',
    image: 'mdi-image',
    image_not_supported: 'mdi-image-off',
    // Recipe step photos 2026-08-27 — "open this at a size you can actually
    // read". `visibility` already means "show/hide" across the app, so a
    // second meaning needed its own glyph.
    zoom_in: 'mdi-magnify-plus-outline',
    // Its partner: the cook-mode photo zoom is a toggle, so "back to
    // fit-to-screen" needs a glyph of its own (owner feedback 2026-08-28).
    zoom_out: 'mdi-magnify-minus-outline',
    inbox: 'mdi-inbox',
    info_outline: 'mdi-information-outline',
    ios_share: 'mdi-export-variant',
    local_fire_department: 'mdi-fire',
    lock: 'mdi-lock',
    key: 'mdi-key-variant',
    mark_email_read: 'mdi-email-check',
    // Auth shell pages (finalisation 15-R20).
    dns: 'mdi-server-network',
    mail_lock: 'mdi-email-lock',
    mood: 'mdi-emoticon-happy',
    palette: 'mdi-palette',
    pan_tool: 'mdi-hand-back-right',
    password: 'mdi-form-textbox-password',
    people: 'mdi-account-multiple',
    person: 'mdi-account',
    phone_iphone: 'mdi-cellphone',
    playlist_add: 'mdi-playlist-plus',
    playlist_add_check: 'mdi-playlist-check',
    playlist_remove: 'mdi-playlist-remove',
    preview: 'mdi-eye-arrow-right',
    price_check: 'mdi-cash-check',
    cash_plus: 'mdi-cash-plus',
    query_stats: 'mdi-chart-line-variant',
    restaurant_menu: 'mdi-silverware-variant',
    savings: 'mdi-piggy-bank',
    settings_applications: 'mdi-cog-outline',
    shield: 'mdi-shield',
    show_chart: 'mdi-chart-line',
    splitscreen: 'mdi-view-split-horizontal',
    storefront: 'mdi-storefront-outline',
    straighten: 'mdi-ruler',
    system_update: 'mdi-cellphone-arrow-down',
    timer: 'mdi-timer-outline',
    warning_amber: 'mdi-alert-outline',
    x: 'mdi-close',
    shopping_cart_checkout: 'mdi-cart-check',
    update: 'mdi-update',
    upload: 'mdi-upload',
    upload_file: 'mdi-upload',
    label: 'mdi-label',
    label_important: 'mdi-label-variant',
    visibility_outline: 'mdi-eye-outline',
    // List-shape toggle (cookbook 2026-08-17): each glyph shows the shape
    // the button will switch TO, so the icon is the destination not the
    // current state.
    view_module: 'mdi-view-grid',
    view_list: 'mdi-view-list',

    // ── Semantic aliases — prefer these in new code ─────────────────
    // Common UI actions
    confirm: 'mdi-check',
    cancel_action: 'mdi-close',
    // (cancel above is the Material Icons `cancel` glyph; this alias
    //  exists so semantic call sites don't shadow it accidentally.)
    submit: 'mdi-check',
    open: 'mdi-open-in-new',
    export_data: 'mdi-export-variant',
    expand: 'mdi-chevron-down',
    collapse: 'mdi-chevron-up',
    overflowVertical: 'mdi-dots-vertical',
    overflowHorizontal: 'mdi-dots-horizontal',

    // Domain
    stockItem: 'mdi-package-variant-closed',
    shoppingList: 'mdi-cart',
    // A list still being written (2026-09-27). It wore the pencil, which sat
    // beside the rename pencil in the list picker and read as a second edit
    // button. A clipboard is "a list you're putting together" and nothing else
    // in Dora uses it.
    listDraft: 'mdi-clipboard-text-outline',
    cartAdd: 'mdi-cart-plus',
    cartRemove: 'mdi-cart-remove',
    expiry: 'mdi-clock-alert-outline',
    essential: 'mdi-flag',
    store: 'mdi-store',
    recipe: 'mdi-book-open-page-variant',
    ingredients: 'mdi-food-variant',
    meal: 'mdi-silverware-fork-knife',
    // Owner 2026-09-05 — `chef_hat` is THE glyph for *starting to cook*, on
    // every surface that offers the action: the cookbook row and card, the
    // recipe page's Cook mode button, both meal-plan "Cook now" menu items,
    // and the dashboard's Next-to-cook button. Before this the same action
    // wore three different glyphs (`chef_hat`, `restaurant_menu`,
    // `restaurant`) depending on which surface you found it on. If you are
    // adding a control that opens cook mode, it takes this icon.
    //
    // Not to be confused with the *state* axis below — `chef_hat` also marks
    // "the pool is short one of these" in `NextToCookCard`'s `cookState`,
    // which is the same idea (somebody has to cook it) rather than a clash.
    // `meal` is the dish itself and `restaurant` is eating/meals generally;
    // neither means the act.
    chef_hat: 'mdi-chef-hat',
    // Portions already cooked and waiting to be eaten (the surface formerly
    // called the "meal pool"). A fridge reads as "cooked, stored, ready" —
    // `meal` is the recipe/dish itself and `chef_hat` is the act of cooking,
    // so neither carries the "already done, waiting for you" sense.
    meals_prepared: 'mdi-fridge',
    // Owner 2026-09-04 — a planned meal cooked on its own day, outside the
    // cooked pool. Deliberately the opposite image to `meals_prepared`: the
    // fridge is "already done, waiting for you", the stove is "it happens on
    // the night". `chef_hat` is taken — it means "the pool is short one of
    // these, somebody has to batch it" — and these are different states.
    cookFresh: 'mdi-stove',
    // 2026-08-26 — the recipe masthead's two half-times. `timer` already means
    // *total* time on the cookbook row, so prep and cook can't borrow it and
    // can't share one glyph either; they separate by the activity rather than
    // by the clock. Board-and-knife = before the heat, pot = on it.
    prepTime: 'mdi-knife',
    cookTime: 'mdi-pot-steam-outline',
    // Filter/sort axis glyphs — see the cookbook filter row, where every
    // control carries one so the strip scans as a set (D-005).
    sort: 'mdi-sort',
    difficulty: 'mdi-speedometer',
    // Not `mdi-format-list-numbered` (reads as recipe steps) and not
    // `mdi-counter` (an odometer, owner 2026-10-15). A carrot is an ingredient
    // and nothing else in the app uses it.
    ingredientCount: 'mdi-carrot',
    collection: 'mdi-bookmark-multiple',
    location: 'mdi-map-marker',
    // 2026-08-20 — the stock-level filter's glyph (D-005: every control in a
    // filter row carries one). A gauge reads as "how much is left", which is
    // what a level is; `inventory` is already the item itself.
    stockLevel: 'mdi-gauge',
    user: 'mdi-account-circle',
    scan: 'mdi-qrcode-scan',
    alert: 'mdi-bell',
    // DR-3 (D-005) — the stock row's open / in-use toggle. A sealed vs
    // opened box reads as the domain state (an opened jar / packet) and
    // drops the padlock's security connotation (`lock`/`lock_open` above
    // stay for auth/permission surfaces).
    sealed: 'mdi-package-variant-closed',
    opened: 'mdi-package-variant',

    // C-waste — reason tiles on the Mark-as-wasted modal. One per
    // reason from `WASTE_REASON_*`. Glyphs picked to read at a glance
    // without leaning on shame iconography (no sad faces, no dollar
    // signs — anti-shame UX per `PROPOSAL_WASTE_MINIMISATION.md` §5).
    wasted: 'mdi-delete-outline',
    wasteExpired: 'mdi-clock-alert-outline',
    wasteSpoiled: 'mdi-bug-outline',
    wasteDidNotLike: 'mdi-emoticon-neutral-outline',
    wasteOverbought: 'mdi-cart-outline',
    wasteOther: 'mdi-dots-horizontal',
} as const;

export type IconKey = keyof typeof ICONS;
