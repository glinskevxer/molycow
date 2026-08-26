# changelog

## 0.2.0

Everything a working pharmacy does around the bench, and the checks that keep
the repository honest about it.

- Instrument checks, and a dose that will not be drawn on a calibrator that has
  not passed its constancy check this morning.
- Area surveys and wipes, with a dirty spot held open until the same spot wipes
  clean, and decay in storage with a survey at the end of the hold.
- Possession limits: the building added up at one moment and held to the
  licence, including a delivery refused before it arrives.
- Courier routes, package receipts at the dock, returns, kit lot recalls that
  walk forward to the hospitals, badge readings, and the fridge log.
- An append only audit trail under every service, and a rule list the command
  line can print.
- Reports: the day sheet, a period report, a customer statement, the waste
  store, the instrument board, and a csv export.
- Fifteen checks under `molycow.tools`, all of them run by `./check.sh` and by
  ci, and generated documents for the schema, the glossary and the rules.
- The package ships a `py.typed` marker, so the types reach whatever installs
  it.

## 0.1.0

The first working shape of the package.

- Activity in microcuries and volume in millilitres, with decimal arithmetic
  from end to end and no float anywhere a printed number comes from.
- Local wall clock times, real elapsed time across the clock changes, and decay
  correction in both directions.
- Generators, ingrowth, elutions and the two clocks that end an eluate.
- Cold kits, batches made up with saline, and radiochemical purity read off
  both chromatography strips.
- Orders, the draw worked backwards from the calibration time, and the assay
  tolerance the syringe has to meet.
- Package readings, transport index, labels, courier runs and deliveries.
- Instrument checks, surveys and wipes, decay in storage, and the possession
  limits on the licence.
- A command line over all of it, a day sheet, and the checks in
  `molycow.tools` that hold the repository to its own rules.
