# molycow

Hot lab records for a nuclear pharmacy: what came off the generator, what was
compounded from it, what was drawn for a patient, what left the building, and
what is still on the premises when the licence is counted at midnight.

The whole point of the package is that a nuclear pharmacy works in two clocks
at once. A hospital orders an activity for the moment they will inject it, and
everything in the building is decaying while that moment approaches, so almost
every number here is only true at an instant and has to be carried to another
one before it can be compared with anything.

## What it keeps

- **Generators.** The molybdenum column, what it should give up, and what it
  actually gave up when it was milked.
- **Eluate.** The breakthrough test, and the two clocks that end a vial: the
  twelve hour shelf life and the molybdenum ratio climbing past its limit.
- **Batches.** Cold kits made up with eluate and saline, held until both
  chromatography strips have been read.
- **Orders and doses.** An activity at a calibration time, the syringe drawn
  backwards from it, and the assay it has to agree with.
- **Shipping.** Package readings, the transport index, the label, and the run
  the box goes out on.
- **Radiation safety.** Instrument checks, area surveys and wipes, waste held
  for ten half lives, and the possession limits on the licence.

## Installing

```
python -m pip install -e ".[dev]" -c constraints.txt
```

Python 3.12 or 3.13. The only runtime dependency is click.

## A morning

```console
$ molycow --book day.sqlite3 book init
day.sqlite3 is at schema 19, 19 steps applied

$ molycow --book day.sqlite3 customer add "Saint Brannon Medical Centre" \
    --kind hospital --licence 42-28931-01 --street "1400 Weir Street" \
    --town Ardmore --zone north --opened 2025-01-06
CU-0001 Saint Brannon Medical Centre hospital north

$ molycow --book day.sqlite3 physician add CU-0001 "R. Okonkwo" \
    --licence 42-28931-01 --nuclide Tc-99m --added 2025-01-06
AU-0001 R. Okonkwo at CU-0001

$ molycow --book day.sqlite3 order take CU-0001 AU-0001 --code MDP \
    --procedure "whole body bone" --ref A-4471902 --activity "22 mCi" \
    --calibration "2025-04-08 09:00" --at "2025-04-07 16:10"
ORD-250407-01 CU-0001 MDP 22.0 mCi at 2025-04-08 09:00 CDT

$ molycow --book day.sqlite3 instrument add 551-40922 --kind "dose calibrator" \
    --maker Vernay --model CRC-55tR --installed 2023-06-12 --calibrated 2025-02-03
IC-0001 Vernay CRC-55tR (551-40922) due 2026-02-03

$ molycow --book day.sqlite3 instrument source CS-9912 --nuclide Cs-137 \
    --activity "200 uCi" --certified 2019-07-01
CS-9912 Cs-137 200.0 uCi certified 2019-07-01

$ molycow --book day.sqlite3 instrument check IC-0001 CS-9912 \
    --at "2025-04-08 06:05" --read "175.0 uCi" --by "K. Ruzicka"
IC-0001 constancy passed at -0.1%
expected 175.1 uCi

$ molycow --book day.sqlite3 generator receive M99-44182 \
    --maker "Corren Isotopes" --activity "2 Ci" --calibrated "2025-04-05 12:00" \
    --received 2025-04-05 --expires 2025-04-19
GEN-0001 M99-44182 2.00 Ci

$ molycow --book day.sqlite3 generator milk GEN-0001 --at "2025-04-08 06:30" \
    --volume "10 mL" --activity "940 mCi"
EL-250408-01 940.0 mCi in 10.000 mL at 97.9% of expected

$ molycow --book day.sqlite3 generator test EL-250408-01 --at "2025-04-08 06:45" \
    --moly "0.9 uCi" --aluminium 4 --by "K. Ruzicka"
EL-250408-01 passed at 0.0010 uCi/mCi, good until 2025-04-08 18:30 CDT (twelve hour shelf life)

$ molycow --book day.sqlite3 kit add MDP 9F4471 --maker "Sedgwick Radiochem" \
    --received 2025-03-20 --expires 2026-03-31 --vials 30
KL-0001 MDP lot 9F4471 30 vials

$ molycow --book day.sqlite3 kit compound MDP EL-250408-01 \
    --at "2025-04-08 07:15" --activity "300 mCi" --by "K. Ruzicka"
B-250408-01 MDP 300.0 mCi in 3.480 mL, expires 2025-04-08 13:15 CDT

$ molycow --book day.sqlite3 kit strips B-250408-01 --at "2025-04-08 07:35" \
    --solvent 48200 1100 --saline 900 47600 --by "K. Ruzicka"
B-250408-01 95.9% against a floor of 90%

$ molycow --book day.sqlite3 dose draw ORD-250407-01 B-250408-01 \
    --at "2025-04-08 07:40" --assay "25.65 mCi" --by "K. Ruzicka" --calibrator IC-0001
DS-250408-01 0.312 mL reading 25.65 mCi, 21.99 mCi at calibration (-0.0%)
DS-250408-01 Tc-99m medronate 22.0 mCi at 0900

$ molycow --book day.sqlite3 report day --on 2025-04-08
hot lab day sheet 2025-04-08
============================

elutions
  EL-250408-01 GEN-0001 2025-04-08 06:30 CDT 940.0 mCi in 10.000 mL yield 97.9% moly 0.0010

batches
  B-250408-01 MDP 2025-04-08 07:15 CDT 300.0 mCi in 3.480 mL rcp 95.9%

doses
  DS-250408-01 CU-0001 A-4471902 MDP 22.0 mCi at 2025-04-08 09:00 CDT drawn 0.312 mL off B-250408-01 (-0.0%)

shipments
  nothing left the dock

survey
  areas not surveyed: hot lab, dispensing bench, packaging, waste store

waste store
  nothing in the store

on the premises at midnight
  Mo-99 827.6 mCi 4.1% of limit
  Tc-99m 125.0 mCi 0.6% of limit
```

The dose command is refused unless that calibrator passed its constancy check
that morning, which is the sort of rule this package exists to hold.

## Working on it

```
./check.sh          # everything ci runs
python -m pytest -q
python -m molycow.tools.check_layers
```

The checks under `molycow.tools` run as their own ci steps and again from the
test suite. `docs/schema.md` and `docs/glossary.md` are generated; rebuild them
with `python -m molycow.tools.schema_dump` and
`python -m molycow.tools.build_glossary`.
