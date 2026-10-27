"""GET /api/help/food-fact. Random food trivia for the help panel.

Originally the spec referenced an external food-fact RSS feed; pulling RSS
from a public list at request time is unreliable (feed shape varies, CORS
on the client, rate-limits). Instead we ship a curated local list and
rotate randomly. Trivia is light, factual, and food-themed — keeps Dora's
personality consistent.

Want more facts? Add lines to FOOD_FACTS below. Keep them under ~140 chars
so they fit the chat bubble without truncation.
"""
import logging
import random
from dataclasses import dataclass

from dora_api.features.routers import HELP_ROUTER
from dora_api.infrastructure.api_response import ok

_LOGGER = logging.getLogger(__name__)


FOOD_FACTS: tuple[str, ...] = (
    "Honey never spoils. Sealed pots of it from ancient Egyptian tombs are still edible.",
    "Bananas are berries; strawberries are not.",
    "Carrots were originally purple. Orange ones were bred in the 17th century.",
    "Apples float because about 25% of their volume is air.",
    "The most stolen food in the world is cheese. About 4% of all cheese made gets nicked.",
    "Watermelons are 92% water, which is exactly the same percentage as a jellyfish.",
    "Pineapples take about two years to grow a single fruit.",
    "Pistachios are technically fruits: the seed of a drupe.",
    "Saffron is the world's most expensive spice by weight; 75,000 crocus flowers make one pound.",
    "A 'baker's dozen' became thirteen because medieval bakers added an extra loaf to avoid being fined for short-weight bread.",
    "Tomato ketchup was sold as medicine in the 1830s, including for indigestion and jaundice.",
    "Lobsters were once considered food for prisoners and the poor in colonial America.",
    "Mushrooms have more in common genetically with humans than with plants.",
    "Coconut water is so close to human blood plasma it was used as an emergency IV in WWII.",
    "Vanilla is the second-most expensive spice after saffron because the orchids must be hand-pollinated.",
    "The hottest part of a chilli pepper is the membrane that holds the seeds, not the seeds themselves.",
    "Peanuts aren't nuts. They're legumes, more closely related to beans and lentils.",
    "Chocolate was used as currency by the Aztecs; you could buy a turkey for 100 cocoa beans.",
    "Cucumbers are 96% water and were originally cultivated in India over 3,000 years ago.",
    "The bubbles in champagne were originally a defect. Early winemakers tried hard to prevent them.",
    "Avocados are toxic to most birds and many mammals, including parrots and horses.",
    "An average cob of corn has exactly 800 kernels, arranged in 16 rows.",
    "Spinach loses up to 90% of its vitamin C within 24 hours of being harvested.",
    "Cashews grow attached to the bottom of a fruit called a cashew apple, which is itself edible.",
    "The fear of cooking is called 'mageirocophobia'.",
    # ── Second batch (2026-08-17) ──────────────────────────────────────
    "Nutmeg was once worth more than its weight in gold, and the Dutch traded Manhattan for a single nutmeg island.",
    "Almonds are seeds of a stone fruit. The tree is a close cousin of the peach.",
    "Broccoli, cauliflower, kale, cabbage, Brussels sprouts and kohlrabi are all the same species.",
    "Rhubarb leaves are poisonous; only the stalks are edible.",
    "Wild strawberries carry their seeds on the outside because each 'seed' is actually a separate tiny fruit.",
    "Oranges aren't naturally orange. Most are picked green and only colour up in cold weather.",
    "The Cavendish banana is a clone; almost every banana sold worldwide is genetically identical.",
    "Ripe cranberries bounce. Growers once sorted them by dropping them down a set of steps.",
    "Onions make you cry because cutting them releases a gas that turns into a mild acid on contact with your eyes.",
    "Garlic's smell only appears once a clove is cut or crushed. The enzyme and the compound sit in separate cells.",
    "Potatoes were the first vegetable grown in space, aboard the shuttle Columbia in 1995.",
    "The first food eaten in space was apple sauce, squeezed from a tube by John Glenn in 1962.",
    "Sourdough needs no shop yeast. The starter cultures wild yeast and bacteria straight from the flour and the air.",
    "Bread staling isn't drying out; the starch recrystallises, which is why a stale loaf freshens in the oven.",
    "Cheese, butter, yoghurt and cream all come from milk, separated, soured or set four ways.",
    "Parmigiano Reggiano is aged at least 12 months, and wheels have been accepted as collateral by Italian banks.",
    "Blue cheese gets its veins from mould deliberately introduced, then aerated with skewers so it can breathe.",
    "Real wasabi is so perishable that most 'wasabi' outside Japan is horseradish, mustard and green colouring.",
    "Black pepper was once used to pay rents, dowries and taxes in medieval Europe.",
    "Cinnamon is tree bark. It curls into quills as it dries after being peeled.",
    "Cloves are unopened flower buds, picked and dried before they ever bloom.",
    "Ginger isn't a root but a rhizome, an underground stem, which is why it sprouts from its own 'eyes'.",
    "Capsaicin, the heat in chillies, binds to the same receptor that detects actual burning.",
    "Milk beats water for chilli burn: capsaicin dissolves in fat, not water.",
    "The Scoville scale was originally measured by diluting chilli extract until a panel of tasters stopped noticing it.",
    "Tomatoes were widely feared as poisonous in 18th-century Europe. The acid leached lead from pewter plates.",
    "Aubergines, potatoes, peppers and tomatoes are all nightshades, related to deadly nightshade itself.",
    "Rice feeds more than half the world's population and comes in over 40,000 varieties.",
    "Pasta shapes aren't decoration. Ridges and hollows are engineered to hold particular sauces.",
    "Instant noodles were invented in 1958 by Momofuku Ando, who flash-fried them to make them keep.",
    "Sushi began as a preservation method: fish was packed in fermenting rice, and the rice was thrown away.",
    "Soy sauce takes months to brew and contains hundreds of distinct aroma compounds.",
    "Tofu is made much like cheese. Soy milk is curdled with a coagulant and the curds are pressed.",
    "Kimchi is buried in jars through winter in Korea; the cold, steady ground temperature is the fridge.",
    "Yeast is a living fungus, and a loaf of bread is essentially a scaffold built from its exhaled carbon dioxide.",
    "Beer and bread share the same yeast species, Saccharomyces cerevisiae, meaning 'sugar-fungus of beer'.",
    "Worcestershire sauce is fermented anchovies, and the original batch was left in a cellar for 18 months by accident.",
    "Ketchup began as a fermented fish sauce in south-east Asia; tomatoes weren't added for centuries.",
    "Mayonnaise is an emulsion: oil suspended in droplets so small they no longer separate out.",
    "Whipping cream works because fat globules link into a mesh that traps air bubbles.",
    "Egg whites whip to eight times their volume, and a trace of yolk fat will stop them dead.",
    "A hard-boiled egg spins; a raw one wobbles, because the liquid inside lags behind the shell.",
    "Eggshells are porous, which is why eggs pick up fridge smells and why the old advice is to store them boxed.",
    "The green ring around an overcooked egg yolk is iron and sulphur reacting. It's harmless, just overdone.",
    "Butter browns rather than just melts because its milk solids toast, which is where the nutty smell comes from.",
    "The Maillard reaction, not caramelisation, is what browns steak, toast, coffee and roast potatoes.",
    "Caramelisation is sugar alone breaking down; it starts around 160°C and produces hundreds of new compounds.",
    "Resting meat lets the juices redistribute, so a rested steak loses far less liquid when you cut it.",
    "Salting food early doesn't dry it out. The brine that forms is drawn back in, seasoning it throughout.",
    "Adding salt to water raises its boiling point, but by so little that it's about taste, not speed.",
    "Cold water doesn't boil faster than hot. The old kitchen myth is about pipe sediment, not physics.",
    "Freezing doesn't kill most bacteria; it only pauses them, which is why thawed food spoils quickly.",
    "The fridge door is its warmest shelf, which makes it the worst place for milk and the best for condiments.",
    "Most 'best before' dates are about quality, not safety. 'Use by' is the one that matters.",
    "Roughly a third of all food produced worldwide is never eaten.",
    "Bruised apples release ethylene, which ripens everything nearby. One bad apple really does spoil the barrel.",
    "Bananas ripen faster in a bunch because each one's ethylene speeds up its neighbours.",
    "Storing potatoes with onions spoils both: the onions' moisture and gases sprout the potatoes.",
    "Never refrigerate tomatoes. Cold flattens the aroma compounds that make them taste of anything.",
    "Herbs like basil and coriander keep far longer standing in a glass of water than sealed in a bag.",
    "Honey's resistance to spoiling comes from being acidic and so low in water that bacteria can't survive it.",
    "Bees visit around two million flowers to make a single pound of honey.",
    "Maple syrup takes about 40 litres of sap to make one litre of syrup.",
    "Vanilla, chocolate and coffee all get their flavour from fermentation before they're ever roasted or dried.",
    "Coffee 'beans' are the seeds of a cherry-like fruit, and the fruit itself can be brewed as cascara.",
    "Decaf isn't caffeine-free. A cup still carries a few percent of the original dose.",
    "Tea, green and black, comes from one plant: the difference is how long the leaves are allowed to oxidise.",
    "Adding milk to tea before or after the water genuinely changes the flavour by altering how the proteins denature.",
    "Chocolate is tempered by melting and cooling it precisely, which is what gives good chocolate its snap.",
    "White chocolate contains no cocoa solids at all, just cocoa butter, sugar and milk.",
    "Sugar doesn't spoil, and neither does salt, dried rice or pure maple syrup kept sealed.",
    "Popcorn pops because a drop of water inside the kernel flashes to steam and bursts the hull.",
    "Crisps were reputedly invented by a chef slicing potatoes ever thinner to annoy a complaining customer.",
    "The sandwich is named after the Earl of Sandwich, who wanted to eat without leaving his card table.",
    "Pineapple contains an enzyme that digests protein, which is why it stops jelly setting and stings your tongue.",
    "Kiwi, papaya and figs carry the same protein-digesting enzymes, and all three ruin gelatine.",
    "Olives are inedibly bitter straight from the tree; every olive you've eaten was cured first.",
    "Extra-virgin olive oil is simply the first pressing, made without heat or chemicals.",
    "Balsamic vinegar is aged in a succession of barrels of different woods, sometimes for over a decade.",
    "A cucumber and a courgette are both technically fruits, as are peppers, pumpkins and okra.",
    "Wild carrots, parsnips, celery, parsley, dill, fennel and coriander are all in the same plant family.",
    "Asparagus can grow up to 25cm in a single day in warm weather.",
    "Lettuce turns bitter once it bolts, which is the plant redirecting everything into flowering.",
    "Mint spreads so aggressively by runners that gardeners plant it in sunken pots to contain it.",
    "Sweet potatoes and potatoes aren't related. One's a morning glory, the other a nightshade.",
    "Yams and sweet potatoes are routinely confused, but true yams are a different plant entirely.",
    "Corn, wheat, rice, oats, barley and sugarcane are all grasses.",
    "Quinoa is a seed, not a grain, and it's coated in a bitter compound that must be rinsed off.",
    "Oats are naturally gluten-free but are usually milled alongside wheat, which is why the label matters.",
    "Baking soda needs an acid to work; baking powder ships with its own, which is the whole difference.",
    "Cream of tartar is a by-product of winemaking. It crystallises inside the barrels.",
    "Gelatine sets by forming a mesh that traps liquid; it melts near body temperature, hence the mouthfeel.",
    "Ice cream is mostly air. Churning is what stops it setting into a solid block.",
    "Sorbet and granita differ only in how much they're stirred while freezing.",
    "Salt on icy roads and salt in an ice-cream churn work the same way: both lower the freezing point of water.",
    "A pinch of salt in sweet baking doesn't make it salty. It suppresses bitterness and lets the sugar read as sweeter.",
    "Umami was proposed as a fifth taste in 1908 and only widely accepted by science in the 1980s.",
    "Tomatoes, parmesan, mushrooms, anchovies and soy sauce are all umami-rich, which is why they pair so well.",
    "Most of what we call flavour is smell. Pinch your nose and an onion and an apple are hard to tell apart.",
    "Coriander tastes soapy to some people because of a genetic variation in their smell receptors.",
    "Supertasters have more taste buds per square centimetre and often find broccoli and coffee harsh.",
    "The 'tongue map' of separate taste zones is a mistranslation from 1901. All tastes register everywhere.",
    "Eating slowly genuinely helps: it takes about 20 minutes for fullness signals to reach the brain.",
)


@dataclass(frozen=True, slots=True)
class FoodFactDto:
    fact: str


@HELP_ROUTER.route("/food-fact", methods=["GET"])
def get_food_fact():
    fact = random.choice(FOOD_FACTS)
    _LOGGER.debug("Served food fact: %s", fact[:40])
    return ok(FoodFactDto(fact=fact))
