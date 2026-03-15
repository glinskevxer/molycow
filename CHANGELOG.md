# changelog

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
