"""Plain data objects."""

from dataclasses import asdict, dataclass, field

HATCHLING = "hatchling"
JUVENILE = "juvenile"
ADULT = "adult"


@dataclass
class Dragon:
    id: int
    name: str
    element: str
    alleles: dict          # slot -> [allele, allele]   (hidden genes)
    traits: dict           # slot -> expressed variant id (fixed at hatching)
    markings: list = field(default_factory=list)   # [{element, name, description}]
    parent_ids: list = field(default_factory=list)
    parent_elements: list = field(default_factory=list)  # kept so grandparent markings survive releases
    generation: int = 0
    age_days: int = 0
    stage: str = HATCHLING
    rest_days: int = 0     # days left before this dragon can breed again

    @property
    def is_adult(self):
        return self.stage == ADULT

    @property
    def can_breed(self):
        return self.is_adult and self.rest_days <= 0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)
