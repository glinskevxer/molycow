# design

The package is a stack, and every layer is allowed to know only about the ones
under it. The check in `molycow.tools.check_layers` enforces that; this note
says why the layers are where they are.

## core

`units`, `clock`, `nuclides`, `decay`, `ingrowth`, `formulary`, `transport`,
`glossary`, `ids` and `errors`. Physics, arithmetic and vocabulary. Nothing
here knows what a customer is, and nothing here reads a clock it was not
handed.

Activity is decimal from end to end. The only floats in the package are inside
the exponentials, and even those are done in decimal at a working precision of
34 digits, because a printed volume that moves in its last digit between two
runs is a question somebody has to answer at seven in the morning.

## model

The records the pharmacy keeps, as frozen dataclasses that validate
themselves. A record refuses to exist in a state the pharmacy cannot have: an
elution with no volume, a dose calibrated before it was drawn, a container
closed before it was opened.

Rules that need only the record itself live here. `Batch.hold_reason` is the
clearest example: whether a vial may be drawn from is a question about the vial
and the moment, not about the book.

## store

One sqlite file, one repository per table, and `Records` as the base they share.
Everything is stored as text: dates and moments as iso strings in utc, activity
as microcuries, volume as millilitres. `rows` is the only place that converts,
so a date written by one repository is readable by every other.

Migrations are numbered and never edited once shipped; `migrations.lock` is
what makes that a rule rather than an intention.

## service

The rules that need more than one record. An elution has to be compared against
what the column should have given. A dose has to be worked backwards from a
calibration time, drawn from a batch that has been released, on a calibrator
that passed its check this morning. Each service takes a book and does one job
with it, inside one savepoint.

Nothing in a service prints, and nothing in a service asks what time it is: the
moment is always passed in, which is what lets a whole working day be tested
without touching a clock.

The services, and the one job each of them does:

- `elution` milks a column against what it should have given.
- `breakthrough` tests an eluate and decides how long it may be drawn from.
- `compound` makes a batch up out of eluate, saline and a cold kit.
- `purity` reads both chromatography strips and releases or holds the batch.
- `orders` takes an order, against the customer's licence and the physician on it.
- `dispense` works a syringe backwards from the calibration time.
- `shipping` closes a box and reads it.
- `route` loads the van and gets the boxes signed for.
- `returns` books a syringe back in and puts it in a decay container.
- `waste` holds a drum ten half lives and surveys it out.
- `survey` walks the building and keeps a dirty spot open until it wipes clean.
- `qc` checks the instruments against their sealed sources.
- `fridge` logs the fridge and stops a cold kit while an excursion is open.
- `inventory` adds the building up at a moment and holds it to the licence.
- `recall` pulls a kit lot and walks forward to the hospitals it reached.
- `receipt` books a package in and refuses to let a failed one be opened.
- `dosimetry` keeps the badge readings and adds each person's year up.

## report

Reports assemble `Section` and `Sheet` objects and hand them back. They read
through repositories and never write. The cli decides what to do with the lines.

## cli

The only layer that prints. Every command opens the book, calls one service,
and turns our own errors into exit codes. The transcript in the readme is
replayed by `check_readme`, so the documentation cannot drift from the commands.

## tools

The checks this repository holds itself to. They run as their own ci steps and
again from the test suite, so a check that stops working is a failing test
rather than a green build that stopped looking.
