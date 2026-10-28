/**
 * The Help area's content: topics (one page each) and their guides.
 *
 * Every guide is short on purpose: one sentence that says what the thing is,
 * then at most one line each for how to reach it, the setting that controls
 * it, and the one thing worth knowing before you trust it. Long explanations
 * belong on the surface itself or in a screenshot, not here.
 *
 * Titles are part of the deep-link contract: `HelpHint` and the runners
 * navigate to `/help?q=<title>`, and the landing page resolves an exact (or
 * unique partial) title match straight to the guide. Keep the titles named in
 * `DEEP_LINKED_TITLES` (see `helpContent.spec.ts`) stable.
 *
 * Copy follows D-014 (Dora's voice) and D-025 (no em dashes, no tails).
 */
import { ICONS } from 'src/style/icons';

export interface HelpSetting {
    label: string;
    path: string;
}

export interface HelpEntry {
    slug: string;
    title: string;
    /** One sentence. What it is and what it does. */
    summary: string;
    /** One line. Where to find it or how to trigger it. */
    how?: string;
    /** The setting that controls it, when there is one. */
    setting?: HelpSetting;
    /** One line. What it costs or what it might get wrong. */
    note?: string;
    /** The surface this guide is about; rendered as an "Open" link. */
    path?: string;
    /** Basename of a screenshot under `src/assets/help/` (no extension). */
    image?: string;
    imageAlt?: string;
    /** A live component rendered inside the guide instead of prose. */
    block?: 'legend' | 'faces';
    /** Question-shaped guides are also listed under Common questions. */
    faq?: boolean;
}

export interface HelpTopic {
    slug: string;
    title: string;
    blurb: string;
    icon: string;
    entries: HelpEntry[];
}

const ASSISTANT: HelpSetting = { label: 'Settings → Assistant', path: '/settings/assistant' };
const NOTIFICATIONS: HelpSetting = { label: 'Settings → Notifications', path: '/settings/notifications' };
const VOICE: HelpSetting = { label: 'Settings → Voice', path: '/settings/voice' };
const BUDGET: HelpSetting = { label: 'Settings → Budget', path: '/settings/budget' };
const MONEY: HelpSetting = { label: 'Admin → Money', path: '/settings/admin/system/money' };
const NUTRITION: HelpSetting = { label: 'Admin → Nutrition', path: '/settings/admin/system/nutrition' };
const COOKING: HelpSetting = { label: 'Admin → Cooking', path: '/settings/admin/system/cooking' };
const STOCK_ADMIN: HelpSetting = { label: 'Admin → Stock', path: '/settings/admin/system/stock' };
const STOCKTAKE_ADMIN: HelpSetting = { label: 'Admin → Stocktake', path: '/settings/admin/system/stocktake' };
const ALERTS_ADMIN: HelpSetting = { label: 'Admin → Alert thresholds', path: '/settings/admin/system/alerts' };
const REGION: HelpSetting = { label: 'Admin → Region', path: '/settings/admin/system/region' };
const RECONCILE: HelpSetting = { label: 'Admin → Meal reconciliation', path: '/settings/admin/system/meal-reconcile' };

export const HELP_TOPICS: HelpTopic[] = [
    {
        slug: 'dashboard',
        title: 'Dashboard',
        blurb: 'Your home page and the cards on it.',
        icon: ICONS.dashboard,
        entries: [
            {
                slug: 'your-dashboard',
                title: 'Your dashboard',
                summary: 'A set of cards you own. Cards (top right) shows, hides and reorders them, and the layout is saved to your account.',
                note: 'A card whose feature is off for the install is hidden, not shown empty.',
                path: '/',
                image: 'dashboard',
                imageAlt: 'The dashboard with its cards',
            },
            {
                slug: 'kitchen-health',
                title: 'Kitchen health',
                summary: 'One score from four signals over the last 30 days: waste, budget, freshness and plan coverage.',
                note: 'A signal with nothing to score is left out, never scored zero. The arrow compares with a week ago.',
            },
            {
                slug: 'next-to-cook',
                title: 'Next to cook',
                summary: 'The next meals someone actually has to cook, in day and slot order.',
                note: 'With batch cooking on, meals the pool already covers are left out. Cook opens cook mode at the batch’s yield.',
            },
            {
                slug: 'use-it-up',
                title: 'Use it up',
                summary: 'What is about to go off, expired first, and the recipes that would use the most of it.',
                setting: ALERTS_ADMIN,
            },
            {
                slug: 'whats-coming',
                title: "What's coming",
                summary: 'A fortnight at a glance: green dots for meals, red for expiries, blue for a shopping day. Tap a day for the list.',
            },
            {
                slug: 'restock-radar',
                title: 'Restock radar',
                summary: 'Items that went low or out in the last 30 days, newest first, with a cart button.',
                note: 'Planned means a meal in the next fortnight still needs it.',
            },
            {
                slug: 'my-budget',
                title: 'My budget',
                summary: 'Spend this period against the household budget, plus what is still to buy on open lists.',
                setting: BUDGET,
                note: 'Spend counts ticked lines on finished lists with a price.',
            },
            {
                slug: 'price-drops',
                title: 'Price drops',
                summary: 'Tracked products at a genuine new low against their own history, never a retailer’s ticket price.',
                note: 'An opt-in card. Needs products on.',
            },
            {
                slug: 'message-of-the-day',
                title: 'The message of the day',
                summary: 'A greeting that stays all day, and under it a tip about something easy to miss.',
            },
        ],
    },
    {
        slug: 'stock',
        title: 'Stock',
        blurb: 'Your pantry: items, levels, expiry and Dora’s hunches.',
        icon: ICONS.inventory_2,
        entries: [
            {
                slug: 'add-item',
                title: 'Add a stock item',
                summary: 'Stock → New item. A name and a level are enough; location, group, essential and expiry can come later.',
                path: '/stock',
            },
            {
                slug: 'reading-a-row',
                title: 'Reading a stock row',
                summary: 'The square is the level: green stocked, amber low, red out. A dashed ring means the number might be wrong. A row outline means something needs you. A dimmed row is out but not essential.',
                setting: NOTIFICATIONS,
                note: 'The outline follows the alert kinds you keep on.',
                block: 'legend',
                image: 'stock-rows',
                imageAlt: 'Stock rows with level squares and an outlined row',
            },
            {
                slug: 'finding-things',
                title: 'Finding things',
                summary: 'Search by name, quick chips (Needs attention, Expiring soon, Essential, Open), filters for level, location and group, and a sort.',
                note: 'Filters survive leaving and returning, not a reload.',
            },
            {
                slug: 'quick-actions',
                title: 'Quick actions on a row',
                summary: 'Tap the square to set a level. The expiry button offers +1, +7 and +14 days, Clear and Log waste. Seal or open an item, or add it to your list.',
            },
            {
                slug: 'bulk-select',
                title: 'Doing several at once',
                summary: 'Bulk select, or hold a row on a phone: add to a list, move, restock, log waste for one reason, or print QR labels.',
            },
            {
                slug: 'essentials-auto-add',
                title: 'Essentials and auto-add',
                summary: 'An essential is chased as soon as it runs low. With auto-add on, a low or out item lands on your draft list by itself.',
                setting: STOCK_ADMIN,
                note: 'Nothing is auto-added when you have no draft list, or more than one.',
            },
            {
                slug: 'expiry-opened',
                title: 'Expiry and opened',
                summary: 'Set a date from the calendar, push it with +1d, +7d or +14d, or clear it. Marking an item opened asks whether to shorten its expiry.',
                note: 'Every change is kept on the History tab.',
            },
            {
                slug: 'dora-thinks',
                title: 'The "Dora thinks…" hint',
                summary: 'Dora infers a rough Out, Low or Stocked from your purchases, your buying rhythm and your cooking. She only speaks when she disagrees with what you recorded.',
                setting: ASSISTANT,
                note: 'Her guess never changes your level. A level you set in the last three days wins outright.',
            },
            {
                slug: 'hints-elsewhere',
                title: 'Hints on other pages',
                summary: 'Three switches put the same opinion on the cookbook (May be short, May be cookable), shopping lists (you may be out of…) and the planner.',
                setting: ASSISTANT,
                note: 'Off by default. They only ever add a remark.',
            },
            {
                slug: 'quick-checks',
                title: 'Quick checks',
                summary: 'When a list or a planned meal depends on an item Dora is unsure of, she asks one question: Still have rice? Set the level and it goes away.',
            },
            {
                slug: 'buy-verdict',
                title: 'The Buy / Wait / Skip ring',
                summary: 'A ring on the cart button: green worth buying now, amber maybe wait, red probably skip. Built from your own prices, pace and waste only.',
                setting: MONEY,
                note: 'When Dora is not confident she says nothing.',
            },
            {
                slug: 'stock-item-page',
                title: 'The stock item page',
                summary: 'Every row is its own editor and saves as you change it. Tabs for Products, Recipes, Substitutes, Scanning, Lists and History.',
                note: 'A tab is hidden when the feature behind it is off for the install.',
                image: 'stock-item',
                imageAlt: 'A stock item’s page',
            },
            {
                slug: 'three-cards',
                title: 'Dora’s three cards on an item',
                summary: 'Dora thinks (her inferred level), planned meals that need it, and Should I buy it? Each opens to its reasoning.',
                note: 'None of them is an alert.',
            },
            {
                slug: 'your-prices',
                title: 'Your prices',
                summary: 'Your own price record: prices you log plus prices from finished shops. Usually is the median of the last year, shown once there are three.',
                note: 'Paying more than usual means 15% over that median. Shelf prices of linked products never count.',
            },
            {
                slug: 'price-chart',
                title: 'The price history chart',
                summary: 'Your logged prices as a solid line, store offers dashed, your usual price dotted. One unit, one axis.',
            },
            {
                slug: 'preferred-buys',
                title: 'Preferred buys',
                summary: 'A note of what you actually buy, with no price or store.',
                note: 'Hidden when Products is on, because linked products answer the same question with real prices.',
            },
            {
                slug: 'nutrition-item',
                title: 'Nutrition on an item',
                summary: 'In complex mode, link the item to a food so recipes using it can total their energy. Suggestions are never saved until you tap Use this.',
                setting: NUTRITION,
            },
            {
                slug: 'item-history',
                title: 'An item’s history',
                summary: 'One timeline, newest first: level changes, waste, lists, purchases, cooks and the expiry trail.',
                note: 'Each kind keeps its latest 50 and says how many were cut.',
            },
            {
                slug: 'substitutes',
                title: 'Substitutes',
                summary: 'Items that can stand in for one another, with a note and a ratio. Cook mode offers them when something is low.',
                note: 'A swap made in cook mode is temporary. The recipe is untouched.',
            },
            {
                slug: 'barcodes',
                title: 'Barcodes',
                summary: 'A product’s real EAN or UPC, typed or scanned. One code belongs to one item.',
                setting: STOCK_ADMIN,
                note: 'Dora never looks the number up online.',
            },
            {
                slug: 'qr-label',
                title: 'QR label',
                summary: 'Dora’s own printable label for an item. Scanning it opens the item’s page.',
                how: 'Print one from the Scanning tab, or a batch under Kitchen setup → QR labels.',
            },
            {
                slug: 'scanning',
                title: 'Scanning with an action',
                summary: 'Scan opens the camera on Open item. Switch to Set to a level and walk the pantry marking things.',
                note: 'A barcode Dora does not know opens New item prefilled.',
            },
            {
                slug: 'export',
                title: 'Exporting your stock',
                summary: 'Export → CSV or Print / Save as PDF of exactly the rows shown.',
            },
            {
                slug: 'delete-item',
                title: 'Deleting a stock item',
                summary: 'Removes the item with its history, prices, substitutes and barcodes.',
                note: 'Dora refuses while the item is in a recipe, and names them.',
            },
            {
                slug: 'how-stocktake-works',
                title: 'How stocktake works',
                summary: 'Dora walks you through the items due a check, least certain first. Three parts: agree with what she is sure about, the walk, then items that left the rotation.',
                how: 'Still correct · Change level · Skip · Push 3 days · Mute.',
                setting: STOCKTAKE_ADMIN,
                note: 'At the end anything you marked low or out can go on a list in one go.',
                path: '/stocktake',
                image: 'stocktake',
                imageAlt: 'The stocktake runner',
            },
            {
                slug: 'starter-packs',
                title: 'Starter packs',
                summary: 'At setup, five packs you tick item by item, plus your own items.',
                note: 'Items you already have are skipped, not duplicated.',
            },
        ],
    },
    {
        slug: 'cookbook',
        title: 'Cookbook',
        blurb: 'Recipes: writing them, importing them, cost and nutrition.',
        icon: ICONS.menu_book,
        entries: [
            {
                slug: 'add-edit-recipe',
                title: 'Add and edit a recipe',
                summary: 'Cookbook → New recipe makes a stub. Each block has its own pencil; Save commits them together.',
                path: '/cookbook',
                image: 'recipe',
                imageAlt: 'A recipe page',
            },
            {
                slug: 'ingredients-pantry',
                title: 'Ingredients and the pantry',
                summary: 'An ingredient points at a pantry item so Dora knows whether you have it, or stays as plain text.',
                note: 'Typing a name the pantry does not have offers to add it.',
            },
            {
                slug: 'can-i-cook',
                title: 'Can I cook this?',
                summary: 'Yes, no (with what is missing) or unknown (some rows are not linked to the pantry).',
                note: 'Missing means out of stock. A low item still counts as cookable.',
                image: 'cookbook',
                imageAlt: 'The cookbook, with cookable chips on the cards',
                faq: true,
            },
            {
                slug: 'method-modes',
                title: 'Three ways to write a method',
                summary: 'Free text (each line a step), Structured (steps, sub-steps, links to ingredients and tools, timers) or Photos.',
                note: 'Switching never deletes the other modes’ content.',
            },
            {
                slug: 'sections',
                title: 'Sections',
                summary: 'Named groups inside a recipe, like For the sauce, holding ingredients and steps.',
            },
            {
                slug: 'import-paste',
                title: 'Import a recipe by pasting',
                summary: 'Cookbook → Import. Paste a page’s text and Dora picks out the name, times, servings, ingredients and steps.',
                how: 'On Android, share the page to Dora instead.',
                note: 'Matching to your pantry is fuzzy. Check the rows.',
            },
            {
                slug: 'unlinked-bulk',
                title: 'Fix unlinked ingredients in bulk',
                summary: 'Every unlinked ingredient grouped by its text, so "1 onion" in nine recipes is linked once.',
                path: '/settings/kitchen-setup/unlinked-ingredients',
            },
            {
                slug: 'versions',
                title: 'Versions of a recipe',
                summary: 'New version copies everything into a sibling named (vN). Versions are equal peers, each with its own pool and favourite.',
            },
            {
                slug: 'meals-prepared',
                title: 'Meals prepared',
                summary: 'Cooked portions waiting in the fridge or freezer. Cook mode adds them; past planned days use them.',
                setting: COOKING,
                note: 'Shown in Batch style, hidden in Fresh.',
            },
            {
                slug: 'recipe-cost',
                title: 'What a recipe costs',
                summary: 'An estimate from your own prices, ingredient by ingredient. Rows that cannot be priced are reported, not guessed.',
                setting: MONEY,
            },
            {
                slug: 'nutrition-modes',
                title: 'Nutrition: off, simple, complex',
                summary: 'Simple: type kcal per serving. Complex: link items to foods and Dora totals energy per serving, with coverage and a Health Star Rating or Nutri-Score.',
                setting: NUTRITION,
                note: 'Ratings are estimates. A missing figure flatters them, and the panel says which.',
            },
            {
                slug: 'dietary-tags',
                title: 'Dietary tags',
                summary: 'A planning aid for the include and exclude filter. Check the ingredient list when food safety matters.',
                setting: { label: 'Kitchen setup → Dietary tags', path: '/settings/kitchen-setup/recipe-dietary-tags' },
            },
            {
                slug: 'mark-cooked',
                title: 'Marking a recipe cooked',
                summary: 'Cooking stamps Last cooked today, adds to the pool in batch style, and writes a Used in event on each ingredient’s history.',
            },
        ],
    },
    {
        slug: 'cooking',
        title: 'Cook mode',
        blurb: 'One step at a time, with a voice if you want one.',
        icon: ICONS.chef_hat,
        entries: [
            {
                slug: 'cook-mode',
                title: 'Cook mode',
                summary: 'One step at a time, large enough to read from across the kitchen. The step’s ingredients and tools light up; tap the progress bar to jump.',
                how: 'Cook on a recipe. Keys: → or space next, ← back, R repeat, Esc exit.',
                path: '/cookbook',
                image: 'cook-mode',
                imageAlt: 'Cook mode showing one step',
            },
            {
                slug: 'cooking-for',
                title: 'Cooking for a different number',
                summary: 'The Cooking for pill rescales every quantity for this cook only: whole numbers for things you count, kitchen fractions for the rest.',
                setting: COOKING,
            },
            {
                slug: 'sous-chef',
                title: 'Sous Chef',
                summary: 'Dora reads each step as you reach it; Repeat reads it again. Her own voice when it is installed on the server, your device’s otherwise.',
                setting: VOICE,
                note: 'On a phone, a step read after a long silence may be muted by the browser.',
            },
            {
                slug: 'hands-free',
                title: 'Hands-free commands',
                summary: 'Mic on, then say next, back, repeat, ingredients, tools, start, pause or reset timer, stop, or exit.',
                note: 'Chrome, Edge and Safari. Firefox has no speech recognition.',
            },
            {
                slug: 'timers',
                title: 'Step timers',
                summary: 'A step’s own timer, or one Dora reads out of its wording. At zero: a toast, a chime and, with Sous Chef on, a spoken Timer finished.',
                note: 'One timer at a time. Moving to another step resets it.',
            },
            {
                slug: 'swap',
                title: 'Swapping an ingredient',
                summary: 'When something is low or out, pick a recorded substitute with its ratio and note.',
                note: 'Temporary. The recipe is untouched.',
            },
            {
                slug: 'finishing',
                title: 'Finishing a cook',
                summary: 'Each ingredient with its level preselected; change the ones you used up. Last cooked moves to today.',
                note: 'Batch households also say how many spare servings went in the pool.',
            },
            {
                slug: 'screen-on',
                title: 'The screen stays on',
                summary: 'In Cook mode and in a shop the phone does not lock.',
                note: 'Needs a browser with wake lock and HTTPS. Elsewhere it locks as usual.',
            },
        ],
    },
    {
        slug: 'meal-plans',
        title: 'Meal plans',
        blurb: 'A week at a time, with Dora’s help if you want it.',
        icon: ICONS.calendar_month,
        entries: [
            {
                slug: 'plan-a-week',
                title: 'Plan a week',
                summary: 'Monday to Sunday with your meal slots on each day. Tap a slot, then a recipe in the rail. Tap the same recipe again to add a serving.',
                setting: { label: 'Kitchen setup → Meal slots', path: '/settings/kitchen-setup/recipe-meal-slots' },
                note: 'Past days are read-only.',
                path: '/meal-plans',
                image: 'meal-plan',
                imageAlt: 'A planned week',
            },
            {
                slug: 'build-my-week',
                title: 'Build my week',
                summary: 'Dora proposes a week from light guidance: days, meals, an emphasis, servings and optionally a budget cap. Edit it before saving.',
                note: 'Each meal uses a distinct recipe, so a small cookbook leaves gaps.',
            },
            {
                slug: 'dora-suggests',
                title: 'Dora suggests',
                summary: 'The rail’s first chip ranks your cookbook for the week: expiring stock, cookable now, not had lately, favourites, with the reason beside each row.',
            },
            {
                slug: 'cook-batches',
                title: 'Cook once for several days',
                summary: 'Link one recipe across days. The earliest day is the cook day and carries the whole yield; later days are leftovers.',
                setting: COOKING,
                note: 'Batch style only. Cost is counted once, on the cook day.',
            },
            {
                slug: 'cook-fresh',
                title: 'Cooked fresh on the day',
                summary: 'Marks a meal as cooked on its day, outside the pool. It shows a Fresh chip and never takes a ready serving.',
            },
            {
                slug: 'meal-glyphs',
                title: 'What the meal glyphs mean',
                summary: 'Chef hat: can you make it (green yes, amber missing ingredients). Fridge: is a serving ready (batch only). The card’s edge rolls them up.',
            },
            {
                slug: 'templates-sets',
                title: 'Templates and rotating sets',
                summary: 'Save a week as a template and apply it to one week or a run of weeks. A set rotates templates week by week.',
                note: 'Applying replaces the week’s future meals and asks first.',
                path: '/meal-plans/templates',
            },
            {
                slug: 'reconcile',
                title: 'Reconcile past meals',
                summary: 'As days pass Dora records what happened to each meal. Auto assumes you cooked it and logs it; manual asks you: Cooked, Different portions, Cooked later, Didn’t cook, Skip.',
                setting: RECONCILE,
                note: 'Every decision is a new receipt. Nothing is overwritten.',
                path: '/meal-plans/reconcile',
            },
            {
                slug: 'missing-this-week',
                title: 'Missing this week',
                summary: 'The rail totals the week’s ingredients, splits them into out, low and stocked, and hands the missing ones to a shopping list.',
            },
            {
                slug: 'cost-this-week',
                title: 'Cost this week and the budget',
                summary: 'Each meal’s price is its recipe estimate times servings. The week’s total sits under the rail against the budget, with cheaper swaps when it is over.',
                setting: MONEY,
            },
            {
                slug: 'lighter',
                title: 'Find a lighter option',
                summary: 'From a meal’s menu: recipes with fewer kcal per serving and the saving. Never volunteered.',
                setting: NUTRITION,
            },
            {
                slug: 'daily-brief',
                title: 'Tomorrow at a glance',
                summary: 'One evening notification naming tomorrow’s meals and any shopping day. Silent when there is nothing to say.',
                setting: NOTIFICATIONS,
            },
        ],
    },
    {
        slug: 'shopping',
        title: 'Shopping lists',
        blurb: 'From a draft to the shop to the receipt.',
        icon: ICONS.shopping_cart,
        entries: [
            {
                slug: 'three-faces',
                title: 'One list, three faces',
                summary: 'A draft while you build it, a shop while you are in the store, a receipt once you finish. Shop starts the trip; Finish ends it.',
                note: 'Finishing is final. Ticked items restock when you finish, never before.',
                path: '/shopping-lists',
                image: 'shopping-list',
                imageAlt: 'A shopping list in draft',
            },
            {
                slug: 'which-list',
                title: 'Which list does the cart button use?',
                summary: 'Your only draft. With two or more drafts it asks once and remembers for the tab; with none it asks you to create one.',
                note: 'There is no primary list. Shop day is what orders the rail.',
                faq: true,
            },
            {
                slug: 'adding-items',
                title: 'Adding items',
                summary: 'Add item searches every stock item, frequent ones first. The cart button on stock rows, ingredients and products adds with one tap. Add to a list pre-ticks what is missing.',
                note: 'A new line remembers your last choice for that item.',
            },
            {
                slug: 'start-a-list',
                title: 'Start a list from stock, a recipe or a plan',
                summary: 'New list fills from low or out items, essentials, frequent buys, a recipe, a plan week or a template.',
                note: 'Nothing is added twice.',
            },
            {
                slug: 'offers-preferred',
                title: 'Picking which one',
                summary: 'The item’s name on a row is a menu of its offers (products on) or its preferred buys. Picking an offer moves the line to that store.',
            },
            {
                slug: 'line-cost-store',
                title: 'What a line is expected to cost',
                summary: 'Estimate: your entered price, else the picked offer, else what you last paid. Store: where you bought it, else the list’s store, else the item’s usual store.',
                setting: MONEY,
            },
            {
                slug: 'prices-while-shopping',
                title: 'Entering prices as you shop',
                summary: 'Tap a row’s price to record what you paid, how many and where. Log price records a shelf price for something not on the list.',
                note: 'Only entered prices become spend and history.',
            },
            {
                slug: 'finish-restock',
                title: 'Finish and restock',
                summary: 'Ticked items go to Stocked, priced lines become purchase history, names are frozen. Unticked items go to another list or the bin.',
            },
            {
                slug: 'amend',
                title: 'Amend a receipt',
                summary: 'On a finished list, correct price, store and quantity per line. The purchase record is rewritten, so a typo stops feeding estimates.',
            },
            {
                slug: 'trim',
                title: 'Keep a shop under budget',
                summary: 'Over budget, Dora offers to set lines aside, each with its reason. Keep protects a line; Add back restores it.',
                setting: BUDGET,
                note: 'Essentials and meals in the next two days are never cut.',
            },
            {
                slug: 'shopping-templates',
                title: 'Templates',
                summary: 'Save a list as a template and start new lists from it in one tap.',
                path: '/shopping-lists/templates',
            },
            {
                slug: 'receipt-photos',
                title: 'Receipt photos',
                summary: 'Attach up to 20 photos to a shop or a receipt.',
                note: 'Record-keeping only. Nothing is read from the image.',
            },
            {
                slug: 'may-be-out',
                title: 'You may be out of…',
                summary: 'On a draft, a strip of items Dora thinks you have run out of that are not on the list yet. Tap to add.',
                setting: ASSISTANT,
                note: 'Nothing is added for you.',
            },
        ],
    },
    {
        slug: 'products',
        title: 'Products and prices',
        blurb: 'Saved products, price history and deals.',
        icon: ICONS.shopping_bag,
        entries: [
            {
                slug: 'what-is-product',
                title: 'What a product is',
                summary: 'One thing at one shop with a price. A stock item is the thing in your kitchen. Link them and the price rides with your pantry record.',
                path: '/my-products',
                image: 'products',
                imageAlt: 'My products',
            },
            {
                slug: 'finding-products',
                title: 'Finding products',
                summary: 'Product Search opens the page your admin set up. What you save there lands in My products.',
                note: 'No Product Search in the menu? Your admin sets it up under Admin → Product data.',
            },
            {
                slug: 'link-unlink',
                title: 'Link or unlink a product',
                summary: 'Grey broken link means not linked: tap to pick a stock item. Green means linked: tap to unlink.',
            },
            {
                slug: 'custom-products',
                title: 'Custom products',
                summary: 'For a shop Dora cannot check. You type the price, size and store; Dora never refreshes it and marks it Custom.',
            },
            {
                slug: 'pack-count',
                title: 'Items in the pack',
                summary: 'Set how many are in a pack so a recipe’s 3 eggs can be priced.',
            },
            {
                slug: 'tracking',
                title: 'Tracking prices',
                summary: 'Stop tracking hides a product from deals and the weekly email without deleting it.',
            },
            {
                slug: 'bulk-products',
                title: 'Bulk select',
                summary: 'All visible, On deal, Low stock on deal and more. Then add to a list, unlink, stop tracking or delete in one go.',
            },
            {
                slug: 'watch-price',
                title: 'Watch a price',
                summary: 'From a product’s menu, Alert me on a price drop. A new offer at or below your figure raises a bell alert, once per offer.',
            },
            {
                slug: 'price-history',
                title: 'Price history',
                summary: 'Compare up to five products over 30 days, 90 days, a year or all time, with your usual price where you have logged one.',
                path: '/price-history',
            },
            {
                slug: 'deals-email',
                title: 'Weekly deals email',
                summary: 'Pick a day under Notifications; the mail arrives at 7 am with the best specials across your tracked products.',
                setting: NOTIFICATIONS,
                note: 'A quiet week sends nothing. Needs a verified email address.',
            },
            {
                slug: 'real-deal',
                title: 'Is it really a deal?',
                summary: 'Dora checks a special against the product’s own 90-day history and what you have paid. A special dearer than your usual price is called out.',
                faq: true,
            },
            {
                slug: 'delete-product',
                title: 'Deleting a product',
                summary: 'Gone for good, with its price history and any watch on it.',
                note: 'Finished lists keep their record of it.',
            },
        ],
    },
    {
        slug: 'alerts',
        title: 'Alerts and notifications',
        blurb: 'The bell, push, and Dora’s suggestions.',
        icon: ICONS.notifications,
        entries: [
            {
                slug: 'the-bell',
                title: 'The bell',
                summary: 'Counts the actionable things: expired food, an essential low or out, expiring soon, a missed shop, a price hit. Lower-key nudges are listed, not counted.',
                image: 'alerts-bell',
                imageAlt: 'The alerts panel',
            },
            {
                slug: 'alert-kinds',
                title: 'What each alert means',
                summary: 'Expired · Expiring soon · Essential low or out · Did you forget your shopping? · Shopping day · No meals planned · Past meals need confirming · Hit your price.',
                note: 'A non-essential running low is not an alert. The stock row already says it.',
            },
            {
                slug: 'snooze-dismiss',
                title: 'Snooze, dismiss, and why alerts come back',
                summary: 'Each alert is one episode. Dismiss hides it until that episode ends; Snooze hides it for seven days. The next pack of apples is a new alert.',
                setting: NOTIFICATIONS,
            },
            {
                slug: 'choose-alerts',
                title: 'Choosing which alerts you get',
                summary: 'A switch per kind, for you only. Off removes it from the bell, the stock rows and push.',
                setting: NOTIFICATIONS,
            },
            {
                slug: 'push',
                title: 'Push notifications',
                summary: 'Needs push keys from an admin, a browser that supports push, and the switch on for this device. Dora pushes new actionable alerts hourly, once each.',
                setting: NOTIFICATIONS,
                note: 'On an iPhone, add Dora to the home screen first.',
            },
            {
                slug: 'evening-brief',
                title: 'The evening brief',
                summary: '7 pm in your household’s timezone: tomorrow’s meals and any shopping day due. Rides push and sends nothing on an empty evening.',
            },
            {
                slug: 'suggestions',
                title: 'Dora’s suggestions',
                summary: 'Ideas, not alerts: use something soon, over budget, probably due, buy less, still have it?, meals to confirm. Cards at the top of her chat with Why?, Snooze and Dismiss.',
                note: 'Dismissing hides a suggestion for the whole household.',
            },
        ],
    },
    {
        slug: 'reports',
        title: 'Reports, budget and waste',
        blurb: 'What your own records say.',
        icon: ICONS.insights,
        entries: [
            {
                slug: 'built-from',
                title: 'What Reports is built from',
                summary: 'Your own records: finished lists with prices, cooks logged in cook mode, logged prices and marked waste. Nothing is looked up.',
                path: '/reports',
                image: 'reports',
                imageAlt: 'The Reports page',
            },
            {
                slug: 'range',
                title: 'The range and All time',
                summary: 'Every card answers for the range you pick. All time starts at your first record; waste looks back at most a year.',
            },
            {
                slug: 'money-went',
                title: 'Where the money went',
                summary: 'By store, by stock group, or against the same-length period before.',
                note: 'Items with no price are counted and named, never silently dropped.',
            },
            {
                slug: 'kitchen-memory',
                title: 'Kitchen memory',
                summary: 'Cooks finished in cook mode, the portions you made, and how many different recipes that was.',
            },
            {
                slug: 'price-changes',
                title: 'Price changes',
                summary: 'First and last price in the range for items with two or more logged prices, per shelf unit. Tap an item for its chart.',
            },
            {
                slug: 'logging-waste',
                title: 'Logging waste',
                summary: 'On a stock row, open the expiry menu, Mark as wasted, then a reason. Undo within five seconds puts it back.',
                path: '/stock',
            },
            {
                slug: 'budget',
                title: 'The household budget',
                summary: 'One amount, weekly from Monday or monthly. Spent is ticked lines on finished lists; projected is what is on open lists dated in the period.',
                setting: BUDGET,
            },
            {
                slug: 'money-off',
                title: 'Reports with money off',
                summary: 'Waste and Kitchen memory stay. Summary, Spend and Price changes go.',
                setting: MONEY,
            },
        ],
    },
    {
        slug: 'dora',
        title: 'Dora',
        blurb: 'The assistant in the corner, and what she can do.',
        icon: ICONS.smart_toy,
        entries: [
            {
                slug: 'two-modes',
                title: 'Basic or AI',
                summary: 'Basic is always on and works offline: lookups, conversions, substitutes, adding to your list, page help. AI understands looser phrasing and needs a provider you connect.',
                setting: ASSISTANT,
                note: 'If AI drops out mid-chat, Dora answers in Basic for that message.',
                image: 'dora-chat',
                imageAlt: 'Dora’s chat panel',
            },
            {
                slug: 'what-to-ask',
                title: 'What you can ask',
                summary: 'How’s my pantry · what’s low · what’s expiring · where’s the milk · what’s for dinner · recipe for carbonara · what’s on my list · 1 cup to ml · substitute for butter · what can I do here.',
            },
            {
                slug: 'add-to-list-basic',
                title: 'Adding to your list by chat',
                summary: 'Type add milk and eggs. Dora matches the names against your pantry and adds the clear ones to your draft list.',
                note: 'Anything ambiguous she asks about, never guesses.',
            },
            {
                slug: 'never-on-her-own',
                title: 'Dora never changes anything on her own',
                summary: 'In AI mode every change arrives as a card you Confirm or Cancel. Until you tap Confirm, nothing has happened.',
            },
            {
                slug: 'what-she-sees',
                title: 'What Dora can see',
                summary: 'Your household’s data in this install. Never another household, never the web.',
                note: 'With OpenAI, Anthropic or Gemini your messages go to that provider. Ollama keeps everything on your own machine.',
            },
            {
                slug: 'set-up-ai',
                title: 'Set up AI mode',
                summary: 'Ollama (a local model, no key) or OpenAI, Anthropic or Gemini (your own key). Test connection before turning it on. Per account.',
                setting: ASSISTANT,
            },
            {
                slug: 'ai-unavailable',
                title: 'Why does AI mode say unavailable?',
                summary: 'The provider did not answer: Ollama is not running, the key is wrong, the model is mistyped, or the server cannot reach the URL.',
                note: 'The URL is from the server’s point of view, not your browser’s. Retry on the banner after fixing it.',
                faq: true,
            },
            {
                slug: 'encryption-key',
                title: 'Paid providers need an encryption key',
                summary: 'The install needs DORA_SECRET_ENCRYPTION_KEY set so your API key is stored encrypted. The Assistant page says so and can generate one.',
                note: 'Rotating the key invalidates every saved key.',
            },
            {
                slug: 'talking',
                title: 'Talking to Dora',
                summary: 'Tap the mic, speak, tap again. Your words land in the box so you can read them before sending.',
                note: 'Chrome and Edge. Firefox has no speech recognition.',
            },
            {
                slug: 'hearing',
                title: 'Hearing Dora',
                summary: 'The speaker button has Dora read her replies aloud, with her own voice when it is installed on the server.',
                setting: VOICE,
            },
            {
                slug: 'which-browsers',
                title: 'Which browsers can Dora speak in?',
                summary: 'All of them, with her own voice installed on the server. The browser’s voice is the part that varies, and Firefox often has none.',
                setting: VOICE,
                faq: true,
            },
            {
                slug: 'page-aware',
                title: 'How does Dora know what page I’m on?',
                summary: 'She reads the route. Ask what can I do here on any page.',
                faq: true,
            },
            {
                slug: 'suggestions-in-chat',
                title: 'Suggestions in the chat',
                summary: 'The number on the launcher is how many suggestions Dora has. Open the chat to Accept, Snooze a day, Dismiss, or ask Why.',
            },
            {
                slug: 'slow-down',
                title: 'Why does Dora say slow down?',
                summary: 'Twenty questions a minute per person is the ceiling, so a stuck script cannot run up your provider bill. She answers in Basic until the minute is up.',
                faq: true,
            },
            {
                slug: 'turn-off',
                title: 'Turning Dora off',
                summary: 'Show digital assistant chat bubble, off. Hides the launcher everywhere for your account only.',
                setting: ASSISTANT,
            },
            {
                slug: 'faces',
                title: 'Her faces',
                summary: 'The burger in the corner reacts to the conversation.',
                block: 'faces',
            },
        ],
    },
    {
        slug: 'getting-started',
        title: 'Getting started',
        blurb: 'First run, signing in and your account.',
        icon: ICONS.play_circle,
        entries: [
            {
                slug: 'first-run',
                title: 'Your first run',
                summary: 'A short story, then a one-minute setup. Nothing is saved until Finish.',
                note: 'Skip keeps the defaults, and the dashboard offers to continue for a day.',
            },
            {
                slug: 'what-finish-sets',
                title: 'What Finish sets up',
                summary: 'Your look; for the first user also the household, the feature switches, starter items and optionally one demo recipe.',
                note: 'Everything is editable afterwards in Stock and Settings.',
            },
            {
                slug: 'run-setup-again',
                title: 'Running setup again',
                summary: 'Settings → About → Welcome tour starts it over.',
                path: '/settings/about',
            },
            {
                slug: 'sign-in-register',
                title: 'Signing in and creating an account',
                summary: 'A username and password. Register creates an account with a password of 8 or more characters. New accounts are never admins.',
                note: 'A failed sign-in never says which half was wrong.',
            },
            {
                slug: 'first-admin',
                title: 'The first admin',
                summary: 'A brand-new install opens on a one-time page that creates the first admin and signs them in. Then the page is gone for good.',
            },
            {
                slug: 'forgot-password',
                title: 'Forgot your password',
                summary: 'Enter your email; if it is on an account a one-hour reset link arrives.',
                note: 'The button appears only when the install can send email. Otherwise an admin sets a new password for you.',
            },
            {
                slug: 'verify-email',
                title: 'Verifying your email',
                summary: 'Accounts with an address get a 24-hour link. Scheduled emails only go to verified addresses.',
                setting: NOTIFICATIONS,
            },
            {
                slug: 'signed-out',
                title: 'Why was I signed out?',
                summary: 'A password change or reset signs out your other devices. An admin deactivating an account signs it out. Cleared cookies end a session.',
                faq: true,
            },
            {
                slug: 'phone-app',
                title: 'The phone app and your Dora address',
                summary: 'The app asks for your server’s address once and adds /api for you.',
                how: 'Change it later under Settings → About.',
                path: '/settings/about',
            },
            {
                slug: 'username-email-password',
                title: 'Username, email and password',
                summary: 'Edit them inline under Account and Save.',
                note: 'Changing your password signs out your other devices.',
                path: '/settings/account',
            },
            {
                slug: 'profile-picture',
                title: 'Profile picture',
                summary: 'Upload a photo or pick a preset. It saves the moment you choose.',
                path: '/settings/account',
            },
        ],
    },
    {
        slug: 'settings',
        title: 'Settings and admin',
        blurb: 'Your preferences, the kitchen setup, and the install.',
        icon: ICONS.settings,
        entries: [
            {
                slug: 'two-modes-settings',
                title: 'Settings and Admin',
                summary: 'Personal settings and install-wide Admin settings are two modes. Admins switch with the pill at the top.',
                note: 'Kitchen setup is shared by the household even though it sits on the personal side.',
            },
            {
                slug: 'who-can-change',
                title: 'Who can change what',
                summary: 'Anyone edits their own account, appearance, notifications, voice and the shared kitchen setup. Only admins change install-wide behaviour.',
            },
            {
                slug: 'appearance',
                title: 'Appearance',
                summary: 'Mode (System, Light, Dark), a theme family, a font and one of four text sizes. Per account, and it follows you across devices.',
                note: 'The sign-in page is always the light brand look.',
                path: '/settings/preferences',
                image: 'appearance',
                imageAlt: 'Appearance settings',
            },
            {
                slug: 'notifications-page',
                title: 'Notifications',
                summary: 'Which alert kinds reach your bell, how long alerts live, push for this device, the evening brief and the weekly deals email.',
                path: '/settings/notifications',
            },
            {
                slug: 'voice-settings',
                title: 'Voice',
                summary: 'Speak to Dora, and let her speak back with her own voice or your device’s.',
                note: 'Her voices are 60 to 110 MB downloads on the server.',
                path: '/settings/voice',
            },
            {
                slug: 'locations',
                title: 'Stock locations',
                summary: 'A three-level map of where things live: zones, areas, sections. Items can sit at any level.',
                note: 'Deleting a zone leaves its items unassigned, not deleted.',
                path: '/settings/kitchen-setup/stock-locations',
            },
            {
                slug: 'vocab',
                title: 'Stock groups and recipe vocabulary',
                summary: 'Name-only lists used as filters and pickers, each showing how many things use it.',
                note: 'Meal slots are the one reorderable list, and their order drives the planner.',
                path: '/settings/kitchen-setup/stock-groups',
            },
            {
                slug: 'stores',
                title: 'Stores',
                summary: 'The shops Dora knows about. Add one, give it a logo, remove the ones you do not use.',
                path: '/settings/kitchen-setup/stores',
            },
            {
                slug: 'formatting',
                title: 'How Dora shows dates, money and units',
                summary: 'Every date, price and unit follows the household’s region, not your browser.',
                setting: REGION,
            },
            {
                slug: 'shortcuts',
                title: 'Keyboard shortcuts',
                summary: 'Press ? anywhere for the list. / focuses search; g then s, l, r, d or h jumps to Stock, Lists, Cookbook, Dashboard or Help.',
                note: 'Shortcuts never use Ctrl or Cmd, so they cannot collide with the browser’s.',
                image: 'shortcuts',
                imageAlt: 'The keyboard shortcuts sheet',
            },
            {
                slug: 'region',
                title: 'Region and locale (admin)',
                summary: 'Currency, language, units and the household timezone. Match this device fills zone, locale and units.',
                note: 'The timezone decides which day is today everywhere.',
                path: '/settings/admin/system/region',
            },
            {
                slug: 'kitchen-features',
                title: 'Kitchen features (admin)',
                summary: 'One page per switch: stock auto-add and scanning, stocktake, cooking style, meal reconciliation, money, nutrition, alert thresholds, image quality.',
                note: 'Each flip is install-wide and applies to everyone on their next page load.',
                path: '/settings/admin/system',
            },
            {
                slug: 'email-push-admin',
                title: 'Email and push setup (admin)',
                summary: 'SMTP details, the email switch, the public URL used in links, and the keys for web push.',
                note: 'Secrets are stored encrypted and need DORA_SECRET_ENCRYPTION_KEY on the server.',
                path: '/settings/admin/system/email',
            },
            {
                slug: 'users-admin',
                title: 'Manage users (admin)',
                summary: 'Add, rename, reset passwords, promote, deactivate (locks them out, keeps everything) or delete.',
                note: 'You cannot demote or remove yourself, or the last admin who can still sign in.',
                path: '/settings/admin/users',
            },
            {
                slug: 'audit-log',
                title: 'Audit log (admin)',
                summary: 'Every change, sign-in attempt and client crash, filterable, with CSV export.',
                note: 'Retention is 1 to 3650 days, pruned nightly.',
                path: '/settings/admin/audit-log',
            },
        ],
    },
    {
        slug: 'data',
        title: 'Data and access',
        blurb: 'Backups, imports and API keys. Admins only.',
        icon: ICONS.storage,
        entries: [
            {
                slug: 'backup',
                title: 'Back up your install',
                summary: 'Everything Dora knows, saved to one file in the Backup library on the server. Download any of them to keep a copy elsewhere.',
                note: 'Passwords and secrets are never included. Backups are manual.',
                path: '/settings/admin/data/backup',
                image: 'backup',
                imageAlt: 'Backup and restore',
            },
            {
                slug: 'restore',
                title: 'Restore a backup',
                summary: 'Brings rows in. Rows that already exist are skipped, never overwritten. From a file you first see a preview and pick exactly what to bring.',
                note: 'Restore adds, it does not delete. Reload afterwards.',
            },
            {
                slug: 'import-spreadsheet',
                title: 'Import stock items from a spreadsheet',
                summary: 'An .xlsx or .csv with at least a name column. Download the template, fill it, check the column mapping, import.',
                note: 'Levels must already exist. Locations and groups can be created on the fly.',
                path: '/settings/admin/data/import',
            },
            {
                slug: 'api-key',
                title: 'Create an API key',
                summary: 'Lets a program you run push products and prices into Dora. The key is shown once, right after you create it.',
                note: 'Anyone holding the key can change products in this install. Lose it, revoke it and make a new one.',
                path: '/settings/admin/api-access',
            },
            {
                slug: 'store-mappings',
                title: 'Map the store names a source uses',
                summary: 'An unknown store name holds the record as pending under that key until you say which of your stores it means.',
                note: 'Records pushed before you map are not queued. The source pushes them again.',
            },
            {
                slug: 'source-working',
                title: 'See whether a source is working',
                summary: 'Each key shows when it was last used and running totals of records accepted, skipped and failed.',
            },
            {
                slug: 'disable-revoke',
                title: 'Disable or revoke a key',
                summary: 'Disable pauses a source and keeps its mappings. Revoke deletes the key for good.',
                note: 'Neither removes the products already pushed.',
            },
        ],
    },
    {
        slug: 'app',
        title: 'Offline, install and updates',
        blurb: 'Dora on your devices, and where your data lives.',
        icon: ICONS.install_desktop,
        entries: [
            {
                slug: 'offline',
                title: 'Use Dora when the connection drops',
                summary: 'A red strip appears and you can keep looking at anything you have opened before. Changes wait until you are back.',
                note: 'Dora never saves a change for later, so what you see is always what the server has.',
            },
            {
                slug: 'install',
                title: 'Install Dora on your phone or computer',
                summary: 'Settings → About → Install as an app. On an iPhone, Share → Add to Home Screen.',
                note: 'Needs HTTPS. Installing does not change your data or sign you in anywhere new.',
                path: '/settings/about',
            },
            {
                slug: 'new-version',
                title: 'A new version is ready',
                summary: 'After the server is updated a blue strip appears. Reload when convenient.',
                note: 'The yellow notice on About is about the server itself, for whoever runs it.',
            },
            {
                slug: 'android-app',
                title: 'The Android app',
                summary: 'The same Dora in a native wrapper. It asks for your server’s address on first launch.',
                note: 'Push is not available inside the Android app. Use the installed web app for that.',
            },
            {
                slug: 'where-data',
                title: 'Where Dora keeps your data',
                summary: 'On the server: the dora_data volume on Docker, or your app-data folder with the desktop app. Never in the browser.',
                note: 'Deleting that folder deletes the install. Take a backup first.',
            },
            {
                slug: 'newer-dora',
                title: 'Is there a newer Dora?',
                summary: 'Help → About shows the version you run and whether a newer release exists. Updating is the operator’s job.',
                path: '/help/about',
                faq: true,
            },
            {
                slug: 'demo-mode',
                title: 'Why does a banner say Demo mode?',
                summary: 'The install was started as a public demo. Sample data, and everything resets on a timer.',
                note: 'Nothing you change is kept.',
                faq: true,
            },
            {
                slug: 'something-wrong',
                title: 'Something went wrong, and the ref code',
                summary: 'A short code like ref: 3f9a2c1b on an error is the id of that request in the server log. Quote it when you report a problem.',
            },
            {
                slug: 'report-problem',
                title: 'Reporting a problem',
                summary: 'Help → About → Report an issue, when the operator has set one up. Otherwise note the steps and pass them on.',
                path: '/help/about',
            },
        ],
    },
];

export interface HelpHit {
    topic: HelpTopic;
    entry: HelpEntry;
}

export function topicBySlug(slug: string): HelpTopic | undefined {
    return HELP_TOPICS.find((t) => t.slug === slug);
}

export function allEntries(): HelpHit[] {
    return HELP_TOPICS.flatMap((topic) => topic.entries.map((entry) => ({ topic, entry })));
}

export function faqEntries(): HelpHit[] {
    return allEntries().filter((h) => h.entry.faq);
}

function text(entry: HelpEntry): string {
    return [entry.title, entry.summary, entry.how, entry.note, entry.setting?.label]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
}

/** Every guide whose words contain the query, title matches first. */
export function searchHelp(query: string): HelpHit[] {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    const hits = allEntries().filter((h) => text(h.entry).includes(q));
    return hits.sort((a, b) => {
        const at = a.entry.title.toLowerCase().includes(q) ? 0 : 1;
        const bt = b.entry.title.toLowerCase().includes(q) ? 0 : 1;
        return at - bt;
    });
}

/**
 * The deep-link resolver behind `/help?q=<title>`: an exact title match, or a
 * query that only one title contains, is "show me this guide" rather than a
 * search.
 */
export function resolveDeepLink(query: string): HelpHit | null {
    const q = query.trim().toLowerCase();
    if (!q) return null;
    const entries = allEntries();
    const exact = entries.find((h) => h.entry.title.toLowerCase() === q);
    if (exact) return exact;
    const partial = entries.filter((h) => h.entry.title.toLowerCase().includes(q));
    return partial.length === 1 ? partial[0]! : null;
}
