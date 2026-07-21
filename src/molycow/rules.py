"""Every rule this package can refuse on, with the sentence behind it.

The short names are what a message carries in front of it: ``[eluate-untested]``
in a terminal, and the same word in the audit trail. They are listed here so a
technologist can be told what the rule is without reading the source, and so
the check in ``molycow.tools.check_rules`` can refuse a rule that was invented
in a service and never written down.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    """One rule the pharmacy works to."""

    code: str
    about: str
    says: str

    def line(self) -> str:
        """The line the laws command prints."""
        return f"{self.code:22} {self.about:12} {self.says}"


RULES: tuple[Rule, ...] = (
    Rule("batch-held", "batches", "nothing is drawn from a batch that is held"),
    Rule("batch-product", "batches", "a batch fills only orders for its own product"),
    Rule("batch-short", "batches", "no more comes out of a vial than went into it"),
    Rule("constancy-missing", "instruments", "the calibrator is checked before the first dose"),
    Rule("container-closed", "waste", "nothing goes into a closed container"),
    Rule("container-early", "waste", "nothing goes in before the container was opened"),
    Rule("container-gone", "waste", "a container is disposed of once"),
    Rule("container-held", "waste", "a drum waits ten half lives and a survey"),
    Rule("contamination-open", "surveys", "a dirty spot is open until it wipes clean"),
    Rule("disposal-survey", "waste", "waste leaves only at background"),
    Rule("draw-volume", "doses", "a syringe is not filled below what it can measure"),
    Rule("dose-tolerance", "doses", "a syringe assays close to what was ordered"),
    Rule("eluate-failed", "eluate", "a failed eluate is not used"),
    Rule("eluate-not-released", "eluate", "nothing is drawn from an eluate that is not released"),
    Rule("eluate-short", "eluate", "no more is drawn than the vial holds"),
    Rule("eluate-untested", "eluate", "an untested eluate is not used"),
    Rule("elution-order", "generators", "a column is milked forwards in time"),
    Rule("elution-yield", "generators", "a poor yield stops until somebody overrides it"),
    Rule("fridge-excursion", "kits", "a cold kit waits while an excursion is open"),
    Rule("generator-in-date", "generators", "a column is milked only while it is in date"),
    Rule("instrument-unusable", "instruments", "an instrument out of calibration is not used"),
    Rule("licence-nuclide", "licence", "only nuclides on the licence are held"),
    Rule("order-final", "orders", "an order is finished once"),
    Rule("order-late", "orders", "nothing is drawn after its calibration time"),
    Rule("package-failed", "receiving", "a package that failed its survey is not opened"),
    Rule("possession-limit", "licence", "the premises stay under the possession limits"),
    Rule("prep-volume", "kits", "a prep is made up inside the insert's volumes"),
    Rule("purity-after-prep", "kits", "a batch is tested after it was made"),
    Rule("return-early", "returns", "a syringe comes back after it was drawn"),
    Rule("return-reason", "returns", "a return says why"),
    Rule("return-twice", "returns", "a syringe comes back once"),
    Rule("return-unsent", "returns", "only what left the building comes back"),
    Rule("run-empty", "routes", "an empty van does not leave"),
    Rule("run-gone", "routes", "nothing is loaded after the van has left"),
    Rule("run-here", "routes", "nothing is delivered before the van leaves"),
    Rule("run-loaded", "routes", "a box goes on one run"),
    Rule("run-not-carrying", "routes", "a box is signed off the run that carried it"),
    Rule("run-stop", "routes", "a box goes on a run that calls at its customer"),
    Rule("shipment-a2", "shipping", "a Type A package holds no more than its A2 quantity"),
    Rule("shipment-customer", "shipping", "a box holds one customer's doses"),
    Rule("shipment-early", "shipping", "nothing is packed before it was drawn"),
    Rule("shipment-empty", "shipping", "an empty box is not shipped"),
    Rule("shipment-mixed", "shipping", "one nuclide to a box"),
    Rule("shipment-packed", "shipping", "a dose is packed once"),
    Rule("source-retired", "instruments", "a retired source is not used for a check"),
    Rule("survey-missing", "surveys", "the building is surveyed every day"),
    Rule("survey-partial", "surveys", "the day's survey covers every area"),
    Rule("test-after-elution", "eluate", "an eluate is tested after it was drawn"),
    Rule("van-index", "routes", "a van stays under its transport index"),
)

BY_CODE = {one.code: one for one in RULES}


def rules() -> tuple[Rule, ...]:
    """Every rule, in the order the laws command lists them."""
    return RULES


def find(code: str) -> Rule | None:
    """One rule by its short name."""
    return BY_CODE.get(code.strip().lower())


def about(subject: str) -> tuple[Rule, ...]:
    """Every rule about one part of the work."""
    return tuple(one for one in RULES if one.about == subject)


def subjects() -> tuple[str, ...]:
    """The parts of the work the rules are grouped under."""
    seen: list[str] = []
    for one in RULES:
        if one.about not in seen:
            seen.append(one.about)
    return tuple(sorted(seen))
