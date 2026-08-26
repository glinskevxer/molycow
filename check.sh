#!/usr/bin/env bash
# Everything ci runs, in the order ci runs it, against this checkout.
#
# Each step is gated on its own exit status rather than chained with &&, so the
# output says which one failed rather than which one happened to be last.
set -uo pipefail

python="${PYTHON:-python}"
failed=()

run() {
  local name="$1"; shift
  if "$@" > "/tmp/molycow-$name.log" 2>&1; then
    printf '  ok    %s\n' "$name"
  else
    printf '  FAIL  %s\n' "$name"
    tail -40 "/tmp/molycow-$name.log"
    failed+=("$name")
  fi
}

echo "lint"
run ruff-check "$python" -m ruff check .
run ruff-format "$python" -m ruff format --check .
run mypy "$python" -m mypy

echo "checks"
for check in check_docstrings check_layers check_wiring check_tests check_cli \
             check_sql check_indexes check_migrations check_naming check_errors \
             check_design check_rules check_package check_readme release_check; do
  run "$check" "$python" -m "molycow.tools.$check"
done
run schema_dump "$python" -m molycow.tools.schema_dump --check
run build_glossary "$python" -m molycow.tools.build_glossary --check
run build_rules "$python" -m molycow.tools.build_rules --check

echo "tests"
run pytest "$python" -m pytest -q "$@"
run smoke "$python" -m molycow.tools.smoke --quiet

if [ "${#failed[@]}" -gt 0 ]; then
  printf '\n%d failed: %s\n' "${#failed[@]}" "${failed[*]}"
  exit 1
fi
printf '\neverything passed\n'
