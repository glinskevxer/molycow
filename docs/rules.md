# rules

Every refusal this package can make, and what the rule behind it says.
The short name in brackets is what a message carries in front of it and
what the audit trail records.

49 rules in 14 groups.

## batches

- **batch-held** — nothing is drawn from a batch that is held
- **batch-product** — a batch fills only orders for its own product
- **batch-short** — no more comes out of a vial than went into it

## doses

- **draw-volume** — a syringe is not filled below what it can measure
- **dose-tolerance** — a syringe assays close to what was ordered

## eluate

- **eluate-failed** — a failed eluate is not used
- **eluate-not-released** — nothing is drawn from an eluate that is not released
- **eluate-short** — no more is drawn than the vial holds
- **eluate-untested** — an untested eluate is not used
- **test-after-elution** — an eluate is tested after it was drawn

## generators

- **elution-order** — a column is milked forwards in time
- **elution-yield** — a poor yield stops until somebody overrides it
- **generator-in-date** — a column is milked only while it is in date

## instruments

- **constancy-missing** — the calibrator is checked before the first dose
- **instrument-unusable** — an instrument out of calibration is not used
- **source-retired** — a retired source is not used for a check

## kits

- **fridge-excursion** — a cold kit waits while an excursion is open
- **prep-volume** — a prep is made up inside the insert's volumes
- **purity-after-prep** — a batch is tested after it was made

## licence

- **licence-nuclide** — only nuclides on the licence are held
- **possession-limit** — the premises stay under the possession limits

## orders

- **order-final** — an order is finished once
- **order-late** — nothing is drawn after its calibration time

## receiving

- **package-failed** — a package that failed its survey is not opened

## returns

- **return-early** — a syringe comes back after it was drawn
- **return-reason** — a return says why
- **return-twice** — a syringe comes back once
- **return-unsent** — only what left the building comes back

## routes

- **run-empty** — an empty van does not leave
- **run-gone** — nothing is loaded after the van has left
- **run-here** — nothing is delivered before the van leaves
- **run-loaded** — a box goes on one run
- **run-not-carrying** — a box is signed off the run that carried it
- **run-stop** — a box goes on a run that calls at its customer
- **van-index** — a van stays under its transport index

## shipping

- **shipment-a2** — a Type A package holds no more than its A2 quantity
- **shipment-customer** — a box holds one customer's doses
- **shipment-early** — nothing is packed before it was drawn
- **shipment-empty** — an empty box is not shipped
- **shipment-mixed** — one nuclide to a box
- **shipment-packed** — a dose is packed once

## surveys

- **contamination-open** — a dirty spot is open until it wipes clean
- **survey-missing** — the building is surveyed every day
- **survey-partial** — the day's survey covers every area

## waste

- **container-closed** — nothing goes into a closed container
- **container-early** — nothing goes in before the container was opened
- **container-gone** — a container is disposed of once
- **container-held** — a drum waits ten half lives and a survey
- **disposal-survey** — waste leaves only at background

