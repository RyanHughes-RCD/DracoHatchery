"""Game state and actions. No printing or input here: every method returns
data so a text or graphical interface can present it however it likes."""

import json
import random
from dataclasses import dataclass, field

from . import genetics
from .data import GameData
from .models import ADULT, HATCHLING, JUVENILE, Dragon

SAVE_VERSION = 1


class GameError(Exception):
    """An action that isn't allowed; the message is player-readable."""


@dataclass
class BreedResult:
    child: Dragon
    odds: dict                 # element odds that were rolled against
    mutated_slots: list        # slots where a mutation occurred (hidden info)
    new_discovery: bool        # True if the child's element was never seen before


@dataclass
class DayReport:
    day: int
    grew_up: list = field(default_factory=list)   # [(dragon, new_stage)]
    rested: list = field(default_factory=list)    # dragons ready to breed again


class Game:
    def __init__(self, data=None, seed=None):
        self.data = data or GameData.load()
        self.rng = random.Random(seed)
        self.day = 1
        self.flock = []
        self.next_id = 1
        self.discovered = []   # element ids, in discovery order

    # Setup -------------------------------------------------------------------

    @classmethod
    def new_game(cls, data=None, seed=None):
        game = cls(data, seed)
        adult_age = game._adult_age()
        for starter in game.data.config["starter"]["dragons"]:
            alleles = genetics.random_starter_alleles(game.rng, game.data)
            dragon = Dragon(
                id=game._take_id(),
                name=starter["name"],
                element=starter["element"],
                alleles=alleles,
                traits=genetics.express_all(game.rng, game.data, alleles),
                generation=0,
                age_days=adult_age,
                stage=ADULT,
            )
            game.flock.append(dragon)
            game._discover(dragon.element)
        return game

    def _take_id(self):
        i = self.next_id
        self.next_id += 1
        return i

    def _discover(self, element):
        if element in self.discovered:
            return False
        self.discovered.append(element)
        return True

    # Ages --------------------------------------------------------------------

    def _adult_age(self):
        a = self.data.config["aging"]
        return a["hatchling_days"] + a["juvenile_days"]

    def stage_for_age(self, age_days):
        a = self.data.config["aging"]
        if age_days < a["hatchling_days"]:
            return HATCHLING
        if age_days < a["hatchling_days"] + a["juvenile_days"]:
            return JUVENILE
        return ADULT

    def next_day(self):
        self.day += 1
        report = DayReport(day=self.day)
        for dragon in self.flock:
            dragon.age_days += 1
            stage = self.stage_for_age(dragon.age_days)
            if stage != dragon.stage:
                dragon.stage = stage
                report.grew_up.append((dragon, stage))
            if dragon.rest_days > 0:
                dragon.rest_days -= 1
                if dragon.rest_days == 0 and dragon.is_adult:
                    report.rested.append(dragon)
        return report

    # Lookup ------------------------------------------------------------------

    def find(self, ref):
        """Find a dragon by id number or by name (case-insensitive)."""
        ref = str(ref).strip()
        if ref.isdigit():
            for d in self.flock:
                if d.id == int(ref):
                    return d
        for d in self.flock:
            if d.name.lower() == ref.lower():
                return d
        return None

    def get(self, ref):
        dragon = self.find(ref)
        if dragon is None:
            raise GameError(f"No dragon called '{ref}' in your flock.")
        return dragon

    def get_by_id(self, dragon_id):
        for d in self.flock:
            if d.id == dragon_id:
                return d
        return None

    # Breeding ----------------------------------------------------------------

    @property
    def flock_cap(self):
        return self.data.config["flock_cap"]

    def check_breed(self, a, b):
        """Raise GameError if these two dragons can't breed right now."""
        if a is b:
            raise GameError("A dragon can't breed with itself.")
        for d in (a, b):
            if not d.is_adult:
                raise GameError(f"{d.name} is a {d.stage}; only adults can breed.")
            if d.rest_days > 0:
                raise GameError(f"{d.name} is resting after breeding and can't breed today.")
        if len(self.flock) >= self.flock_cap:
            raise GameError(f"Your flock is full ({self.flock_cap} dragons). Release one first.")

    def breed_odds(self, a, b):
        return genetics.element_odds(self.data, a.element, b.element)

    def breed(self, a, b):
        self.check_breed(a, b)
        odds = self.breed_odds(a, b)
        element = genetics.roll_element(self.rng, odds)
        alleles, mutated = genetics.inherit_alleles(self.rng, self.data, a.alleles, b.alleles)
        traits = genetics.express_all(self.rng, self.data, alleles)

        ancestors = [a.element, b.element] + a.parent_elements + b.parent_elements
        child_id = self._take_id()
        child = Dragon(
            id=child_id,
            name=f"{self.data.element_name(element)} Hatchling {child_id}",
            element=element,
            alleles=alleles,
            traits=traits,
            markings=genetics.ancestry_markings(self.data, element, ancestors),
            parent_ids=[a.id, b.id],
            parent_elements=[a.element, b.element],
            generation=max(a.generation, b.generation) + 1,
            age_days=0,
            stage=HATCHLING,
        )
        self.flock.append(child)
        rest = self.data.config["breeding_rest_days"]
        a.rest_days = rest
        b.rest_days = rest
        new = self._discover(element)
        return BreedResult(child=child, odds=odds, mutated_slots=mutated, new_discovery=new)

    # Flock management --------------------------------------------------------

    def rename(self, dragon, new_name):
        new_name = new_name.strip()
        if not new_name:
            raise GameError("Name can't be empty.")
        if new_name.isdigit():
            raise GameError("Name can't be just a number (numbers are dragon ids).")
        other = self.find(new_name)
        if other is not None and other is not dragon:
            raise GameError(f"Another dragon is already named {new_name}.")
        dragon.name = new_name

    def release(self, dragon):
        self.flock.remove(dragon)

    # Saving ------------------------------------------------------------------

    def to_dict(self):
        version, internal, gauss = self.rng.getstate()
        return {
            "save_version": SAVE_VERSION,
            "day": self.day,
            "next_id": self.next_id,
            "discovered": list(self.discovered),
            "flock": [d.to_dict() for d in self.flock],
            "rng_state": [version, list(internal), gauss],
        }

    @classmethod
    def from_dict(cls, d, data=None):
        game = cls(data)
        game.day = d["day"]
        game.next_id = d["next_id"]
        game.discovered = list(d["discovered"])
        game.flock = [Dragon.from_dict(x) for x in d["flock"]]
        if d.get("rng_state"):
            version, internal, gauss = d["rng_state"]
            game.rng.setstate((version, tuple(internal), gauss))
        return game

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path, data=None):
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f), data)
