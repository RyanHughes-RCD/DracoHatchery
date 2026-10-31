"""Loading of the JSON data files (elements, body parts, config).

Nothing about elements, parts or odds is hard-coded in the game logic;
everything comes from the files in the top-level ``data/`` directory.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class DataError(ValueError):
    """Raised when a data file is missing something the game needs."""


class GameData:
    def __init__(self, elements_doc, parts_doc, config):
        self.config = config

        # Elements, keyed by id ("fire"), in file order.
        self.elements = {e["id"]: e for e in elements_doc["elements"]}
        # Recipes are unordered: frozenset({"fire", "water"}) -> "steam".
        self.recipes = {}
        for recipe in elements_doc.get("recipes", []):
            self.recipes[frozenset(recipe["parents"])] = recipe["result"]

        # Body parts.
        self.slots = list(parts_doc["slots"])
        self.variants = {}          # variant id -> variant dict (with "slot" added)
        self.starter_variants = {}  # slot -> [variant ids that can appear in starters]
        self.mutations = {}         # slot -> mutation-only variant id
        for slot in self.slots:
            self.starter_variants[slot] = []
            for variant in parts_doc["variants"][slot]:
                v = dict(variant, slot=slot)
                self.variants[v["id"]] = v
                if v.get("mutation"):
                    self.mutations[slot] = v["id"]
                else:
                    self.starter_variants[slot].append(v["id"])

        self.validate()

    @classmethod
    def load(cls, data_dir=DATA_DIR):
        data_dir = Path(data_dir)
        with open(data_dir / "elements.json", encoding="utf-8") as f:
            elements_doc = json.load(f)
        with open(data_dir / "parts.json", encoding="utf-8") as f:
            parts_doc = json.load(f)
        with open(data_dir / "config.json", encoding="utf-8") as f:
            config = json.load(f)
        return cls(elements_doc, parts_doc, config)

    def validate(self):
        for parents, result in self.recipes.items():
            for el in list(parents) + [result]:
                if el not in self.elements:
                    raise DataError(f"Recipe refers to unknown element '{el}'")
        for vid, v in self.variants.items():
            if v["dominance"] not in ("dominant", "recessive"):
                raise DataError(f"Variant '{vid}' has bad dominance '{v['dominance']}'")
        for slot in self.slots:
            if not self.starter_variants[slot]:
                raise DataError(f"Slot '{slot}' has no starter variants")
            if slot not in self.mutations:
                raise DataError(f"Slot '{slot}' has no mutation variant")
        for starter in self.config["starter"]["dragons"]:
            if starter["element"] not in self.elements:
                raise DataError(f"Starter uses unknown element '{starter['element']}'")

    # Convenience lookups -------------------------------------------------

    def element_name(self, element_id):
        return self.elements[element_id]["name"]

    def variant_name(self, variant_id):
        return self.variants[variant_id]["name"]

    def is_dominant(self, variant_id):
        return self.variants[variant_id]["dominance"] == "dominant"

    def combine(self, element_a, element_b):
        """Combined element for two different elements, or None if no recipe."""
        return self.recipes.get(frozenset((element_a, element_b)))
