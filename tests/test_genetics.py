"""Statistical and rules tests for the genetics core.

Run with:  python3 -m unittest discover -s tests
"""

import os
import random
import tempfile
import unittest
from collections import Counter

from dracohatchery import genetics
from dracohatchery.data import GameData
from dracohatchery.game import Game, GameError
from dracohatchery.models import ADULT, Dragon

DATA = GameData.load()
TRIALS = 20000
TOLERANCE = 0.015   # absolute tolerance on a probability (about 4-5 std devs at 20k trials)


def make_adult(game, element, alleles, name=None):
    d = Dragon(id=game._take_id(), name=name or f"Test{game.next_id}", element=element,
               alleles=alleles, traits=genetics.express_all(game.rng, game.data, alleles),
               age_days=game._adult_age(), stage=ADULT)
    game.flock.append(d)
    return d


def uniform_alleles(variant_by_slot):
    """Alleles dict with the given pair for each slot (default: standard-ish dominants)."""
    out = {}
    for slot in DATA.slots:
        out[slot] = list(variant_by_slot.get(slot, [DATA.starter_variants[slot][0]] * 2))
    return out


class DataFileTests(unittest.TestCase):
    def test_element_counts(self):
        self.assertEqual(len(DATA.elements), 15)
        self.assertEqual(sum(1 for e in DATA.elements.values() if e["base"]), 6)
        self.assertEqual(len(DATA.recipes), 9)

    def test_element_placeholders(self):
        for e in DATA.elements.values():
            self.assertIn("palette", e)
            self.assertEqual(e["signature_decorations"], [])

    def test_recipes_are_unordered(self):
        self.assertEqual(DATA.combine("fire", "water"), "steam")
        self.assertEqual(DATA.combine("water", "fire"), "steam")
        self.assertEqual(DATA.combine("shadow", "water"), "poison")
        self.assertIsNone(DATA.combine("earth", "air"))

    def test_parts(self):
        self.assertEqual(DATA.slots, ["head", "neck", "torso", "wings", "tail", "legs"])
        for slot in DATA.slots:
            starters = DATA.starter_variants[slot]
            self.assertEqual(len(starters), 4)
            self.assertEqual(sum(DATA.is_dominant(v) for v in starters), 2)
            mutation = DATA.mutations[slot]
            self.assertFalse(DATA.is_dominant(mutation))
            self.assertNotIn(mutation, starters)
            for vid in starters + [mutation]:
                self.assertTrue(vid.startswith(slot + "_"))


class ElementOddsTests(unittest.TestCase):
    def roll_many(self, a, b, seed=1):
        rng = random.Random(seed)
        odds = genetics.element_odds(DATA, a, b)
        counts = Counter(genetics.roll_element(rng, odds) for _ in range(TRIALS))
        return {k: v / TRIALS for k, v in counts.items()}

    def test_same_element_always_same(self):
        for el in DATA.elements:
            self.assertEqual(self.roll_many(el, el), {el: 1.0})

    def test_recipe_40_40_20(self):
        freq = self.roll_many("fire", "water")
        self.assertEqual(set(freq), {"fire", "water", "steam"})
        self.assertAlmostEqual(freq["fire"], 0.4, delta=TOLERANCE)
        self.assertAlmostEqual(freq["water"], 0.4, delta=TOLERANCE)
        self.assertAlmostEqual(freq["steam"], 0.2, delta=TOLERANCE)

    def test_recipe_order_does_not_matter(self):
        freq = self.roll_many("shadow", "water", seed=2)
        self.assertAlmostEqual(freq["poison"], 0.2, delta=TOLERANCE)
        self.assertAlmostEqual(freq["shadow"], 0.4, delta=TOLERANCE)

    def test_no_recipe_50_50(self):
        freq = self.roll_many("earth", "air")
        self.assertEqual(set(freq), {"earth", "air"})
        self.assertAlmostEqual(freq["earth"], 0.5, delta=TOLERANCE)
        self.assertAlmostEqual(freq["air"], 0.5, delta=TOLERANCE)

    def test_combined_elements_without_recipe(self):
        freq = self.roll_many("steam", "magma")
        self.assertAlmostEqual(freq["steam"], 0.5, delta=TOLERANCE)

    def test_full_breeding_through_game(self):
        """Element odds hold when breeding through the Game API too."""
        game = Game.new_game(seed=5)
        fire, water = game.find("Cinder"), game.find("Brook")
        counts = Counter()
        n = 5000
        for _ in range(n):
            fire.rest_days = water.rest_days = 0
            result = game.breed(fire, water)
            counts[result.child.element] += 1
            game.release(result.child)
        self.assertAlmostEqual(counts["steam"] / n, 0.2, delta=0.025)
        self.assertAlmostEqual(counts["fire"] / n, 0.4, delta=0.025)


class MendelianTests(unittest.TestCase):
    def offspring_traits(self, alleles_a, alleles_b, slot, seed=1):
        rng = random.Random(seed)
        counts = Counter()
        for _ in range(TRIALS):
            alleles, _ = genetics.inherit_alleles(rng, DATA, alleles_a, alleles_b, mutation_chance=0)
            counts[genetics.express(rng, DATA, alleles[slot])] += 1
        return {k: v / TRIALS for k, v in counts.items()}

    def test_two_carriers_show_recessive_25_percent(self):
        carrier = uniform_alleles({"tail": ["tail_standard", "tail_long"]})
        freq = self.offspring_traits(carrier, carrier, "tail")
        self.assertAlmostEqual(freq["tail_long"], 0.25, delta=TOLERANCE)
        self.assertAlmostEqual(freq["tail_standard"], 0.75, delta=TOLERANCE)

    def test_carrier_times_recessive_50_percent(self):
        carrier = uniform_alleles({"head": ["head_round", "head_snub_nosed"]})
        recessive = uniform_alleles({"head": ["head_snub_nosed", "head_snub_nosed"]})
        freq = self.offspring_traits(carrier, recessive, "head")
        self.assertAlmostEqual(freq["head_snub_nosed"], 0.5, delta=TOLERANCE)

    def test_homozygous_dominant_never_shows_recessive(self):
        dom = uniform_alleles({"legs": ["legs_sturdy", "legs_sturdy"]})
        rec = uniform_alleles({"legs": ["legs_long", "legs_long"]})
        freq = self.offspring_traits(dom, rec, "legs")
        self.assertEqual(freq, {"legs_sturdy": 1.0})

    def test_two_recessive_parents_breed_true(self):
        rec = uniform_alleles({"wings": ["wings_stubby", "wings_stubby"]})
        self.assertEqual(self.offspring_traits(rec, rec, "wings"), {"wings_stubby": 1.0})

    def test_different_dominants_split_evenly(self):
        a = uniform_alleles({"neck": ["neck_standard", "neck_standard"]})
        b = uniform_alleles({"neck": ["neck_thick", "neck_thick"]})
        freq = self.offspring_traits(a, b, "neck")
        self.assertAlmostEqual(freq["neck_standard"], 0.5, delta=TOLERANCE)
        self.assertAlmostEqual(freq["neck_thick"], 0.5, delta=TOLERANCE)

    def test_express_dominance_rules(self):
        rng = random.Random(0)
        self.assertEqual(genetics.express(rng, DATA, ["tail_long", "tail_short"]), "tail_short")
        self.assertEqual(genetics.express(rng, DATA, ["tail_curled", "tail_curled"]), "tail_curled")
        self.assertEqual(genetics.express(rng, DATA, ["tail_split_tipped", "tail_standard"]),
                         "tail_standard")


class MutationTests(unittest.TestCase):
    def test_mutation_rate_about_2_percent_per_slot(self):
        rng = random.Random(3)
        parent = uniform_alleles({})
        hits = Counter()
        for _ in range(TRIALS):
            alleles, mutated = genetics.inherit_alleles(rng, DATA, parent, parent)
            for slot in mutated:
                hits[slot] += 1
                self.assertIn(DATA.mutations[slot], alleles[slot])
        for slot in DATA.slots:
            self.assertAlmostEqual(hits[slot] / TRIALS, 0.02, delta=0.005)

    def test_mutation_replaces_only_one_allele(self):
        rng = random.Random(4)
        parent = uniform_alleles({})
        for _ in range(2000):
            alleles, _ = genetics.inherit_alleles(rng, DATA, parent, parent, mutation_chance=1.0)
            for slot in DATA.slots:
                self.assertEqual(alleles[slot].count(DATA.mutations[slot]), 1)

    def test_mutations_inherited_normally(self):
        carrier = uniform_alleles({"head": ["head_round", "head_third_eyed"]})
        rng = random.Random(5)
        shown = 0
        for _ in range(TRIALS):
            alleles, _ = genetics.inherit_alleles(rng, DATA, carrier, carrier, mutation_chance=0)
            if genetics.express(rng, DATA, alleles["head"]) == "head_third_eyed":
                shown += 1
        self.assertAlmostEqual(shown / TRIALS, 0.25, delta=TOLERANCE)

    def test_starters_never_carry_mutations(self):
        rng = random.Random(6)
        for _ in range(2000):
            alleles = genetics.random_starter_alleles(rng, DATA)
            for slot in DATA.slots:
                self.assertNotIn(DATA.mutations[slot], alleles[slot])

    def test_starters_favor_dominant(self):
        rng = random.Random(7)
        dom = total = 0
        for _ in range(5000):
            for pair in genetics.random_starter_alleles(rng, DATA).values():
                dom += sum(DATA.is_dominant(v) for v in pair)
                total += 2
        self.assertAlmostEqual(dom / total, 0.6, delta=0.01)  # weights 1.5 vs 1.0


class GameTests(unittest.TestCase):
    def setUp(self):
        self.game = Game.new_game(seed=42)

    def test_starting_flock(self):
        g = self.game
        self.assertEqual(len(g.flock), 6)
        self.assertEqual(sorted(d.element for d in g.flock),
                         sorted(e for e, v in DATA.elements.items() if v["base"]))
        self.assertTrue(all(d.is_adult for d in g.flock))
        self.assertEqual(len(g.discovered), 6)

    def test_seed_is_repeatable(self):
        a, b = Game.new_game(seed=9), Game.new_game(seed=9)
        self.assertEqual(a.to_dict(), b.to_dict())

    def test_breed_aging_and_rest(self):
        g = self.game
        a, b = g.find("Boulder"), g.find("Zephyr")
        child = g.breed(a, b).child
        self.assertEqual(child.stage, "hatchling")
        self.assertEqual(child.parent_ids, [a.id, b.id])
        self.assertEqual(child.generation, 1)
        with self.assertRaises(GameError):
            g.breed(a, g.find("Lumen"))   # Boulder is resting
        g.next_day()
        self.assertTrue(a.can_breed)
        self.assertEqual(child.stage, "hatchling")
        g.next_day()
        self.assertEqual(child.stage, "juvenile")
        with self.assertRaises(GameError):
            g.breed(child, a)            # juveniles can't breed
        g.next_day()
        g.next_day()
        self.assertEqual(child.stage, "adult")

    def test_traits_fixed_after_hatching(self):
        g = self.game
        child = g.breed(g.find("Cinder"), g.find("Lumen")).child
        before = dict(child.traits)
        for _ in range(6):
            g.next_day()
        self.assertEqual(child.traits, before)
        reloaded = Game.from_dict(g.to_dict())
        self.assertEqual(reloaded.get_by_id(child.id).traits, before)

    def test_flock_cap(self):
        g = self.game
        g.breed(g.find("Cinder"), g.find("Brook"))
        g.breed(g.find("Boulder"), g.find("Zephyr"))
        self.assertEqual(len(g.flock), 8)
        with self.assertRaises(GameError):
            g.breed(g.find("Lumen"), g.find("Umbra"))

    def test_cannot_breed_with_self(self):
        with self.assertRaises(GameError):
            self.game.breed(self.game.find("Cinder"), self.game.find("Cinder"))

    def test_discovery(self):
        g = Game.new_game(seed=1)
        fire, water = g.find("Cinder"), g.find("Brook")
        first = None
        for _ in range(200):
            fire.rest_days = water.rest_days = 0
            result = g.breed(fire, water)
            g.release(result.child)
            if result.child.element == "steam":
                if first is None:
                    first = result
                    self.assertTrue(result.new_discovery)
                else:
                    self.assertFalse(result.new_discovery)
        self.assertIsNotNone(first)
        self.assertIn("steam", g.discovered)

    def test_markings_from_parents_and_grandparents(self):
        g = self.game
        fire = g.find("Cinder")
        light = g.find("Lumen")
        shadow = g.find("Umbra")
        # Grandparents: Fire + Light -> child; then child + Shadow.
        for _ in range(100):
            fire.rest_days = light.rest_days = 0
            mid = g.breed(fire, light).child
            if mid.element == "fire":
                break
            g.release(mid)
        self.assertEqual(mid.element, "fire")
        self.assertEqual([m["element"] for m in mid.markings], ["light"])
        mid.stage, mid.age_days = ADULT, g._adult_age()
        g.release(fire)   # markings must survive releasing ancestors
        g.release(light)
        for _ in range(100):
            mid.rest_days = shadow.rest_days = 0
            kid = g.breed(mid, shadow).child
            if kid.element == "shadow":
                break
            g.release(kid)
        self.assertEqual(kid.element, "shadow")
        self.assertEqual(sorted(m["element"] for m in kid.markings), ["fire", "light"])
        self.assertIn("ember freckles from Fire ancestry", [m["description"] for m in kid.markings])

    def test_rename_and_release(self):
        g = self.game
        d = g.find("Cinder")
        g.rename(d, "Blaze")
        self.assertIs(g.find("blaze"), d)
        self.assertIs(g.find(str(d.id)), d)
        with self.assertRaises(GameError):
            g.rename(g.find("Brook"), "Blaze")
        g.release(d)
        self.assertIsNone(g.find("Blaze"))

    def test_save_load_roundtrip(self):
        g = self.game
        g.breed(g.find("Cinder"), g.find("Brook"))
        g.next_day()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "save.json")
            g.save(path)
            loaded = Game.load(path)
        self.assertEqual(loaded.to_dict(), g.to_dict())
        # The RNG continues identically after loading.
        self.assertEqual(loaded.rng.random(), g.rng.random())


if __name__ == "__main__":
    unittest.main()
