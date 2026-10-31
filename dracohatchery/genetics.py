"""Pure genetics rules. Every function takes the random generator and the
game data explicitly, so they are easy to test and reuse."""


def element_odds(data, element_a, element_b):
    """Return {element_id: probability} for an egg from these two parents."""
    if element_a == element_b:
        return {element_a: 1.0}
    rules = data.config["element_inheritance"]
    combined = data.combine(element_a, element_b)
    if combined is not None:
        r = rules["recipe"]
        odds = {element_a: r["parent_a"], element_b: r["parent_b"]}
        odds[combined] = odds.get(combined, 0.0) + r["combined"]
        return odds
    r = rules["no_recipe"]
    return {element_a: r["parent_a"], element_b: r["parent_b"]}


def roll_element(rng, odds):
    """Pick one element from an odds dict."""
    elements = list(odds)
    return rng.choices(elements, weights=[odds[e] for e in elements])[0]


def inherit_alleles(rng, data, alleles_a, alleles_b, mutation_chance=None):
    """Build an egg's genes: one random allele from each parent per slot.

    With ``mutation_chance`` per slot, the allele inherited from one parent
    (chosen at random) is replaced with that slot's mutation variant.
    Returns (alleles, mutated_slots).
    """
    if mutation_chance is None:
        mutation_chance = data.config["mutation_chance_per_slot"]
    alleles = {}
    mutated = []
    for slot in data.slots:
        pair = [rng.choice(alleles_a[slot]), rng.choice(alleles_b[slot])]
        if rng.random() < mutation_chance:
            pair[rng.randrange(2)] = data.mutations[slot]
            mutated.append(slot)
        alleles[slot] = pair
    return alleles, mutated


def express(rng, data, pair):
    """Expressed variant for one slot's allele pair.

    Dominant beats recessive. If both alleles have the same dominance but
    differ (two different dominants, or two different recessives), one is
    picked at random; the caller stores the result so it never changes.
    """
    a, b = pair
    if a == b:
        return a
    dom_a, dom_b = data.is_dominant(a), data.is_dominant(b)
    if dom_a and not dom_b:
        return a
    if dom_b and not dom_a:
        return b
    return rng.choice([a, b])


def express_all(rng, data, alleles):
    return {slot: express(rng, data, alleles[slot]) for slot in data.slots}


def random_starter_alleles(rng, data):
    """Random genes for a starter dragon, from starter variants only.
    Dominant variants are weighted a bit higher (see config)."""
    cfg = data.config["starter"]
    alleles = {}
    for slot in data.slots:
        options = data.starter_variants[slot]
        weights = [cfg["dominant_weight"] if data.is_dominant(v) else cfg["recessive_weight"]
                   for v in options]
        alleles[slot] = rng.choices(options, weights=weights, k=2)
    return alleles


def ancestry_markings(data, own_element, ancestor_elements):
    """Cosmetic markings for each ancestor element that differs from our own."""
    markings = []
    seen = set()
    for el in ancestor_elements:
        if el == own_element or el in seen:
            continue
        seen.add(el)
        marking = data.elements[el]["ancestry_marking"]
        markings.append({
            "element": el,
            "name": marking,
            "description": f"{marking} from {data.element_name(el)} ancestry",
        })
    return markings
