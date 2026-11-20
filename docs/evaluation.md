# Selector evaluation

The full-catalog schedule is the fallback for every patch outside the narrow
fixture map. The map contains only existing top-level `tests/fixtures/optimizer/*.sql`
files from sqlglot `eb11aec4be8cb2122afe713a4816662c3f0fb2fa`. Rebuild it with
`python3 tools/build_fixture_map.py /path/to/clean/sqlglot sample/tests.json`.
The generator checks the checkout SHA and cleanliness; the selector checks the
catalog fingerprint. The resulting gzip was reproduced byte-for-byte locally.

The mapped files are read through `tests.helpers` by `tests/test_optimizer.py`.
The selector also includes all of `tests/test_executor.py` as a conservative
shared-fixture and subprocess scope. This is a limited map, not a complete
execution, collection, import, setup, or file-access dependency map. New files,
renames, binaries, mode changes, malformed patches, and anything outside the
mapped fixture files fall back to the whole catalog. Old hunk content must match
the pinned fixture, and unsupported diff forms also fall back.

An exploratory macOS full-suite trace observed reads of all 24 mapped files in
optimizer tests. That run had one unrelated subprocess failure because `python`
was not on its PATH, and subprocess file access was not traced, so it does not
validate the rest of the dependency graph or replace the Linux holdout.
`tools/trace_dependencies.py` records exploratory per-test line contexts,
collection, fixture closures, file accesses, and subprocess warnings; its output
is not used by the selector. It needs coverage.py 7.13.4 and a clean checkout.
Its subprocess, dynamic-fixture, native-file-access, and shared-state gaps must
be resolved before its observations can justify narrower Python selections.

The sample's labels were used only by the offline scorer. In Linux/amd64 Docker,
with the Makefile limits, the full-catalog baseline scored 1,104.510 simulated
seconds with zero misses; fixture selection scored 1,029.606 with zero misses.
Three candidate process CPU measurements were 0.835, 0.830, and 0.587 seconds;
three full-catalog measurements were 0.754, 0.757, and 0.739 seconds. These
were made while other Docker workloads were active and are local emulation
measurements, not board scores.

An experimental pytest replay of the optimizer and executor candidate files
exceeded 200 container CPU seconds before completing, already exceeding the
candidate's simulated cost. It was stopped and is not included in the selector.

The sample's theoretical lower bound, calculated offline from the failing tests'
durations and an ideal worker partition, is 94.351 seconds before CPU. A naive
line-only prototype using the incomplete macOS trace scored 2,618.462 seconds
with seven missed commits; it is not included in the selector. The under-100
target therefore leaves at most 5.649 seconds above the perfect-selection lower
bound, including CPU.

Run `python3 tools/check_selector.py`, the Python-only sample check in
`docs/implementation-plan.md`, and `make sample` after changes. Holdout labels
must come from full-suite executions and must not enter the production image.
