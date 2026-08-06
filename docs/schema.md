# schema

Generated from the migrations. Schema version 24.

## audit

- `id` INTEGER (primary key)
- `done_at` TEXT (not null)
- `actor` TEXT (not null)
- `action` TEXT (not null)
- `subject` TEXT (not null)
- `detail` TEXT (not null)
- indexes: audit_by_day, audit_by_subject

## authorized_nuclide

- `user_id` TEXT (primary key, not null)
- `nuclide` TEXT (primary key, not null)
- `user_id` points at `authorized_user.id`

## authorized_user

- `id` TEXT (primary key)
- `customer_id` TEXT (not null)
- `name` TEXT (not null)
- `licence` TEXT (not null)
- `added_on` TEXT (not null)
- `ended_on` TEXT
- `customer_id` points at `customer.id`
- indexes: authorized_user_by_customer

## badge_reading

- `person` TEXT (primary key, not null)
- `period` TEXT (primary key, not null)
- `deep_mrem` TEXT (not null)
- `extremity_mrem` TEXT (not null)
- `read_on` TEXT (not null)
- indexes: badge_reading_by_period

## batch

- `id` TEXT (primary key)
- `kit_lot_id` TEXT (not null)
- `elution_id` TEXT (not null)
- `code` TEXT (not null)
- `made_at` TEXT (not null)
- `activity` TEXT (not null)
- `volume` TEXT (not null)
- `made_by` TEXT (not null)
- `rcp` TEXT
- `eluate_volume` TEXT (not null)
- `elution_id` points at `elution.id`
- `kit_lot_id` points at `kit_lot.id`
- indexes: batch_by_elution, batch_by_kit_lot, batch_by_made_at

## breakthrough

- `elution_id` TEXT (primary key)
- `tested_at` TEXT (not null)
- `moly` TEXT (not null)
- `technetium` TEXT (not null)
- `aluminium_ppm` TEXT (not null)
- `tested_by` TEXT (not null)
- `elution_id` points at `elution.id`

## check_source

- `serial` TEXT (primary key)
- `symbol` TEXT (not null)
- `certified_activity` TEXT (not null)
- `certified_on` TEXT (not null)
- `retired_on` TEXT

## container

- `id` TEXT (primary key)
- `kind` TEXT (not null)
- `opened_at` TEXT (not null)
- `closed_at` TEXT
- `disposed_at` TEXT
- `disposed_by` TEXT
- `survey_mrem` TEXT
- indexes: container_by_state

## customer

- `id` TEXT (primary key)
- `name` TEXT (not null)
- `kind` TEXT (not null)
- `licence` TEXT (not null)
- `street` TEXT (not null)
- `town` TEXT (not null)
- `zone` TEXT (not null)
- `opened_on` TEXT (not null)
- `closed_on` TEXT
- `telephone` TEXT (not null)
- `department` TEXT (not null)
- indexes: customer_by_zone

## customer_order

- `id` TEXT (primary key)
- `customer_id` TEXT (not null)
- `user_id` TEXT (not null)
- `code` TEXT (not null)
- `procedure` TEXT (not null)
- `patient_ref` TEXT (not null)
- `activity` TEXT (not null)
- `calibration_at` TEXT (not null)
- `ordered_at` TEXT (not null)
- `state` TEXT (not null)
- `priority` TEXT (not null)
- `user_id` points at `authorized_user.id`
- `customer_id` points at `customer.id`
- indexes: customer_order_by_calibration, customer_order_by_customer, customer_order_by_priority, customer_order_by_state, customer_order_by_user

## dose

- `id` TEXT (primary key)
- `order_id` TEXT (not null)
- `batch_id` TEXT (not null)
- `code` TEXT (not null)
- `drawn_at` TEXT (not null)
- `calibration_at` TEXT (not null)
- `volume` TEXT (not null)
- `assayed` TEXT (not null)
- `drawn_by` TEXT (not null)
- `calibrator_id` TEXT
- `calibrator_id` points at `instrument.id`
- `batch_id` points at `batch.id`
- `order_id` points at `customer_order.id`
- indexes: dose_by_batch, dose_by_calibrator, dose_by_drawn_at, dose_by_order

## dose_return

- `dose_id` TEXT (primary key)
- `returned_at` TEXT (not null)
- `reason` TEXT (not null)
- `received_by` TEXT (not null)
- `container_id` TEXT
- `container_id` points at `container.id`
- `dose_id` points at `dose.id`
- indexes: dose_return_by_container

## elution

- `id` TEXT (primary key)
- `generator_id` TEXT (not null)
- `drawn_at` TEXT (not null)
- `volume` TEXT (not null)
- `activity` TEXT (not null)
- `expected` TEXT (not null)
- `residual` TEXT (not null)
- `generator_id` points at `generator.id`
- indexes: elution_by_generator

## fridge_reading

- `id` INTEGER (primary key)
- `read_at` TEXT (not null)
- `celsius` TEXT (not null)
- `read_by` TEXT (not null)
- `reviewed_at` TEXT
- `reviewed_by` TEXT
- indexes: fridge_reading_by_day

## generator

- `id` TEXT (primary key)
- `serial` TEXT (not null)
- `maker` TEXT (not null)
- `calibrated_at` TEXT (not null)
- `calibrated_activity` TEXT (not null)
- `received_on` TEXT (not null)
- `expires_on` TEXT (not null)
- `retired_on` TEXT
- `package_reference` TEXT
- `package_reference` points at `package_receipt.reference`
- indexes: generator_by_expiry, generator_by_package

## instrument

- `id` TEXT (primary key)
- `kind` TEXT (not null)
- `maker` TEXT (not null)
- `model` TEXT (not null)
- `serial` TEXT (not null)
- `installed_on` TEXT (not null)
- `calibrated_on` TEXT (not null)
- `retired_on` TEXT

## kit_lot

- `id` TEXT (primary key)
- `code` TEXT (not null)
- `maker` TEXT (not null)
- `lot` TEXT (not null)
- `received_on` TEXT (not null)
- `expires_on` TEXT (not null)
- `vials` INTEGER (not null)
- `recalled_at` TEXT
- `recall_reason` TEXT
- indexes: kit_lot_by_code

## linearity_point

- `run_id` INTEGER (primary key, not null)
- `read_at` TEXT (primary key, not null)
- `measured` TEXT (not null)
- `run_id` points at `linearity_run.id`

## linearity_run

- `id` INTEGER (primary key)
- `instrument_id` TEXT (not null)
- `symbol` TEXT (not null)
- `checked_by` TEXT (not null)
- `instrument_id` points at `instrument.id`
- indexes: linearity_run_by_instrument

## package_receipt

- `reference` TEXT (primary key)
- `supplier` TEXT (not null)
- `received_at` TEXT (not null)
- `surface_mrem` TEXT (not null)
- `metre_mrem` TEXT (not null)
- `wipe_dpm` TEXT (not null)
- `received_by` TEXT (not null)
- indexes: package_receipt_by_day

## possession_limit

- `symbol` TEXT (primary key)
- `curies` TEXT (not null)
- `note` TEXT (not null)

## purity_test

- `batch_id` TEXT (primary key)
- `tested_at` TEXT (not null)
- `solvent_origin` INTEGER (not null)
- `solvent_front` INTEGER (not null)
- `solvent_background` INTEGER (not null)
- `saline_origin` INTEGER (not null)
- `saline_front` INTEGER (not null)
- `saline_background` INTEGER (not null)
- `tested_by` TEXT (not null)
- `batch_id` points at `batch.id`

## qc_check

- `instrument_id` TEXT (primary key, not null)
- `kind` TEXT (primary key, not null)
- `ran_at` TEXT (primary key, not null)
- `source_serial` TEXT (not null)
- `expected` TEXT (not null)
- `measured` TEXT (not null)
- `checked_by` TEXT (not null)
- `source_serial` points at `check_source.serial`
- `instrument_id` points at `instrument.id`
- indexes: qc_check_by_instrument, qc_check_by_source

## route

- `id` TEXT (primary key)
- `name` TEXT (not null)
- `zone` TEXT (not null)
- `leaves_at` TEXT (not null)

## route_run

- `route_id` TEXT (primary key, not null)
- `day` TEXT (primary key, not null)
- `driver` TEXT (not null)
- `left_at` TEXT
- `returned_at` TEXT
- `route_id` points at `route.id`

## route_stop

- `route_id` TEXT (primary key, not null)
- `position` INTEGER (primary key, not null)
- `customer_id` TEXT (not null)
- `customer_id` points at `customer.id`
- `route_id` points at `route.id`
- indexes: route_stop_by_customer

## run_shipment

- `route_id` TEXT (primary key, not null)
- `day` TEXT (primary key, not null)
- `shipment_id` TEXT (primary key, not null)
- `route_id` points at `route_run.route_id`
- `day` points at `route_run.day`
- `shipment_id` points at `shipment.id`
- indexes: run_shipment_once

## shipment

- `id` TEXT (primary key)
- `customer_id` TEXT (not null)
- `packed_at` TEXT (not null)
- `packed_by` TEXT (not null)
- `symbol` TEXT (not null)
- `activity` TEXT (not null)
- `surface_mrem` TEXT (not null)
- `metre_mrem` TEXT (not null)
- `delivered_at` TEXT
- `received_by` TEXT
- `customer_id` points at `customer.id`
- indexes: shipment_by_customer

## shipment_dose

- `shipment_id` TEXT (primary key, not null)
- `dose_id` TEXT (primary key, not null)
- `dose_id` points at `dose.id`
- `shipment_id` points at `shipment.id`
- indexes: shipment_dose_once

## survey

- `id` TEXT (primary key)
- `ran_at` TEXT (not null)
- `surveyed_by` TEXT (not null)
- indexes: survey_by_day

## survey_reading

- `survey_id` TEXT (primary key, not null)
- `area` TEXT (primary key, not null)
- `mrem` TEXT (not null)
- `survey_id` points at `survey.id`

## survey_wipe

- `survey_id` TEXT (primary key, not null)
- `area` TEXT (not null)
- `spot` TEXT (primary key, not null)
- `counts` INTEGER (not null)
- `background` INTEGER (not null)
- `efficiency` TEXT (not null)
- `survey_id` points at `survey.id`

## waste_item

- `container_id` TEXT (primary key, not null)
- `symbol` TEXT (not null)
- `activity` TEXT (not null)
- `added_at` TEXT (primary key, not null)
- `source` TEXT (primary key, not null)
- `container_id` points at `container.id`

