"""The words this pharmacy uses, and what they mean here.

Half of these are ordinary words with a narrow meaning in a hot lab, which is
exactly the sort of word that gets used loosely in code six months later. The
list is the source the glossary document is built from, so a term that changes
meaning changes here and the document follows.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Term:
    """One word and what it means on this bench."""

    word: str
    meaning: str
    also: str = ""

    def line(self) -> str:
        """The line the glossary document carries."""
        if self.also:
            return f"**{self.word}** — {self.meaning} Also called {self.also}."
        return f"**{self.word}** — {self.meaning}"


TERMS: tuple[Term, ...] = (
    Term(
        "generator",
        "A sealed column of molybdenum-99 that is washed out to collect the "
        "technetium-99m that has grown in from it.",
        "a cow",
    ),
    Term(
        "elution",
        "One washing out of a generator, and the vial of eluate it produced.",
        "a milking",
    ),
    Term(
        "eluate",
        "What comes off the column: sodium pertechnetate in saline, with a "
        "twelve hour shelf life from the moment it was drawn.",
    ),
    Term(
        "ingrowth",
        "The technetium building back up in the column between elutions. It "
        "peaks just short of a day after a full strip.",
    ),
    Term(
        "breakthrough",
        "Molybdenum that came off the column with the technetium. The limit is "
        "a ratio at the moment of injection, and the ratio climbs all day.",
    ),
    Term(
        "cold kit",
        "A vial of freeze dried chemistry with no activity in it, which becomes "
        "a radiopharmaceutical when eluate is added.",
    ),
    Term(
        "batch",
        "One cold kit after the eluate has gone in, with its own activity, volume and expiry.",
        "a bulk vial",
    ),
    Term(
        "radiochemical purity",
        "The share of the activity in a batch that is bound to the right "
        "chemistry, read off two chromatography strips.",
        "rcp",
    ),
    Term(
        "calibration time",
        "The moment a dose is meant to read the ordered activity, which is "
        "when the department will inject it.",
    ),
    Term(
        "unit dose",
        "One syringe drawn for one patient, calibrated for one moment.",
    ),
    Term(
        "assay",
        "The reading a dose calibrator gives for what is actually in a syringe or a vial.",
    ),
    Term(
        "constancy",
        "The daily check that a dose calibrator still reads a long lived sealed "
        "source the same as it did yesterday.",
    ),
    Term(
        "transport index",
        "The dose rate a metre from a package, in millirem an hour, rounded up "
        "to a tenth. It decides the label and the van's load.",
        "ti",
    ),
    Term(
        "decay in storage",
        "Holding waste for ten half lives of the longest lived thing in it, "
        "then surveying it at background before it is disposed of.",
    ),
    Term(
        "wipe",
        "A swab of a surface, counted in a well counter and converted to "
        "disintegrations a minute to compare against the contamination limit.",
        "a smear",
    ),
    Term(
        "possession limit",
        "The most of one nuclide the licence allows on the premises at any one "
        "moment, counted by decaying everything to the same moment.",
    ),
    Term(
        "authorized user",
        "A physician named on a customer's licence for particular nuclides. "
        "Nothing is dispensed except against one.",
    ),
)


def terms() -> tuple[Term, ...]:
    """Every term, in the order the glossary lists them."""
    return tuple(sorted(TERMS, key=lambda one: one.word))


def find(word: str) -> Term | None:
    """One term by its word, folded."""
    wanted = word.strip().lower()
    for term in TERMS:
        if term.word == wanted:
            return term
    return None
