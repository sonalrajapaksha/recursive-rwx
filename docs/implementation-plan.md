# Blast Radius implementation plan

Start with the worker sweep and a zero-miss full-catalog fallback. Add impact selection next. That gives each later experiment a runnable, scored comparison point.

| Order | Deliverable | Estimated effort | Ready when |
| --- | --- | --- | --- |
| 1 | Integer-millisecond scheduler and baseline report | 30–60 min | Matches the starter’s test set and reproduces the measured scheduling gain. |
| 2 | Reproducible pinned dependency map | 2–4 hours | Catalog, setup and fixture edges are audited, including the two longest tests. |
| 3 | Diff-to-impact selector and safe submission | 2–4 hours | Zero sample misses and zero known misses on the first independent holdout, with valid container output. |
| 4 | One measured narrowing pass and a replay decision | 2–4 hours | Improvements survive held-out test cases and repeated CPU-inclusive runs. |
| 5 | Final rebuild and cutoff check | 30–60 min | The intended public commit rebuilds from scratch and is selected for final scoring. |

Times exclude downloads, reference suite runs and submission queues. Stages 1–3 are the first submission path.

Run `make sample` with Docker Desktop for the local container check. The starter’s Linux/amd64 image built and scored 1,210.470 simulated seconds with zero misses. Use the Python-only command below for quick iterations between container runs.

## Docker-free sample check

Run this from the repository root with Python 3.9 or newer. It points the starter’s input path at `sample/`, captures stdout, and passes it to the same scorer used by `make sample`. Keep the selector’s input path override working as it evolves.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import score
import selector

sample = Path("sample").resolve()
selector.DATA = sample
output = io.StringIO()
with redirect_stdout(output):
    selector.main()

stdout = output.getvalue().encode("utf-8")
assert len(stdout) <= 2_000_000, "sample stdout exceeds the 2 MB limit"
tests = json.loads((sample / "tests.json").read_text())["tests"]
answers = json.loads((sample / "answers.json").read_text())["commits"]
result = score.evaluate_run(stdout, tests, answers)
print(json.dumps(result))
raise SystemExit(0 if result["ok"] and not result["missed_commits"] else 1)
PY
```

The starter should report `1210470` simulated milliseconds with an empty miss list. Use this loop for scheduling, patch parsing, map lookup and format checks. Pytest map collection can run in a native Linux/amd64 Python environment with the starter’s pinned source and locked packages, after checking collection against the test catalog. Use a native Linux/amd64 runner for CPU-inclusive benchmarks.

## 1. Implement the scorer’s worker objective

Reuse the starter’s longest-processing-time-first algorithm. Preconvert each duration with `round(seconds * 1000)` as in `score.py`. For a nonempty selection, sort once by decreasing duration and test number as a deterministic tie-breaker. For each worker count from 1 to `min(8, selected_count)`, place the next test on the least-loaded worker, breaking load ties by worker index. Compare `max(loads) + 2_000 * occupied_workers`. Break equal costs in favor of fewer workers, and return `[]` for an empty selection.

Cache the full-catalog schedule for repeated fallbacks. Keep compact JSON Lines output, validate selected numbers and uniqueness at the output boundary, and account for the final newline in the 2 MB limit. Check a single long test, zero-duration tests, duplicate inputs and worker-count ties. Defer exact search until the lower bound `max(longest, ceil(total / k)) + 2_000 * k` shows material headroom over longest-first at candidate worker counts. When measured, use bounded improvements with longest-first always available.

## 2. Generate and audit baseline dependencies

1. **Reproduce collection.** Use the starter’s pinned Linux/amd64 image, the full sqlglot SHA, `requirements.lock`, `PYTHONPATH` pointing to the checkout and `SKIP_INTEGRATION=0`. Check the collected pytest node IDs and skip behavior against the supplied catalog. Resolve runtime test IDs through the actual batch catalog and emit its numbers. Any numbered test without a validated ID mapping stays in every selection until its coverage is understood.
2. **Capture execution and setup.** Use a pinned coverage.py dependency with a small pytest plugin to assign a context to each collected item across setup, call and teardown. Record collection and import execution separately. Shared fixtures can run once and be reused later, so attribute the fixture footprint to every dependent item using fixture requests and scope, including separately observed dynamic requests. Assign unattributed collection or setup activity to its observed collector or import scope, and widen to the suite if that scope is unknown.
3. **Capture data dependencies.** Record repository-local file opens and directory enumerations in the same contexts, for example through restricted Python audit hooks. Inspect observed gaps against pinned fixture loaders and test helpers. Preserve directory-to-consumer edges so adding a globbed fixture selects its consumers. Treat incomplete attribution, subprocess activity and untraced file access as uncertainty. Capture paths from the checkout relative to its root.
4. **Save one compact artifact.** Store schema version, baseline SHA, environment fingerprint, stable node IDs and reverse indexes for source lines, symbols, modules, fixtures and setup scopes. Derive symbols and source spans using the baseline AST, with conservative support for module/class bodies. Deduplicate repeated test sets and gzip only as needed. Include source files or source spans needed to interpret old-side coordinates. Keep the generator reproducible and require a manifest check before trusting the index.
5. **Audit trace completeness.** Compare labeled versus observed IDs, inspect the largest test footprints and confirm file reads from shared fixtures reach all consumers. Check import-time package and test setup effects, dynamic dialect registration, and cases where a fresh-process run reaches a different path from the full-suite run. Widen ambiguous scopes before using the artifact for selection.

Working layout can stay small. Keep `selector.py` as the entry point, add a local map-generation script and one versioned artifact, and use explicit Dockerfile `COPY` statements. The static image needs only runtime source or metadata and the map. Generate the artifact offline when practical so a clean submission build stays quick. Track the repository’s 20 MB limit and keep the scorer, patch corpus and labels out of the production image.

## 3. Resolve each diff to candidate tests

Read each patch independently against the pinned tree. Parse file status, old and new paths, hunk ranges, and changed lines with a tested unified-diff parser. Verify hunk context against the original where precision depends on it. Use original coordinates for coverage and reconstruct changed Python in memory when checking syntax or structural scope. A pure insertion has no deleted line to query, so resolve its enclosing or adjacent statement in both versions. Include both sides of renames and handle quoted paths, deleted files, binary changes and mode-only changes explicitly.

| Evidence in the patch | Initial candidate policy |
| --- | --- |
| Existing local Python statement or function body | Union old-side changed-line hits with the enclosing symbol’s baseline execution footprint. Include direct test consumers and setup edges that can observe the change. Use line-only narrowing later if independently validated. |
| Insertion, new branch, changed call, dispatch key, import, signature, decorator or class/module binding | Widen through the affected owners, observed callers or importers and their consumers. Treat changes to shared registries, dispatch tables and inheritance as potentially broader than the changed file. Use suite fallback when a bounded scope cannot be justified. |
| Fixture or test-data edit | Select baseline readers, owner tests, directory consumers and setup dependents. For a new path, consult its parent directories and actual loader behavior. Account for test discovery, expected output, and parse or import errors that can affect an entire file. |
| Test file, shared helper, conftest or entry-point edit | Select the numbered tests in affected files and the relevant collection or setup dependents. Include the entire known attribution scope for import errors, even when a hunk touched only one test. |
| Unknown path, unsupported diff, global config or setup, invalid artifact, contradictory evidence | Use the full catalog if the scope is unknown. Use a file or package scope only when concrete dependency evidence bounds it. |

Union impact across files and hunks before scheduling. Multi-file changes may interact through new paths, so widen the union when a producer and consumer change together across an unresolved dependency. Record reasons to stderr in local analysis mode. Empty selection requires positive evidence that every change is outside the test surface, a separately validated semantics-preservation rule, or complete faithful replay of a credible candidate set. A missing coverage entry and a comment-only diff are individually insufficient evidence. Comments can affect source text readers, source positions, text fixtures and tooling.

For the first implementation, verify selector behavior with independent cases that exercise old-side deletion, insertion into an uncovered branch, fixture addition, shared setup, module import failure, comment edits and missing map entries. Treat selector exceptions as local full-catalog fallbacks where possible. Precompute the catalog fallback so deadlines in optional work can still produce one valid line per commit.

## 4. Improve the measured score

### Build a comparison that can catch misses

1. Run `make sample` and use `score.py`’s `evaluate_run` offline for missed commits, selected counts and per-commit simulated costs. Record worker count, candidate reason, whether either long test was selected, CPU, wall time, peak memory, scratch use and stdout bytes. Docker Desktop timings on Apple Silicon can establish functional parity. Use native Linux/amd64 for performance estimates.
2. Build an independent development and holdout corpus from generic transformations of the pinned source. Cover parser/generator and optimizer edits, registry and import errors, fixture changes, new paths, tests and shared setup, and harmless changes. Use the full suite offline to label these. Split by transformation family and keep holdout outcomes out of artifact generation and shipped logic.
3. Measure one change at a time against the last accepted version. Run three repetitions under the same limits and compare median total. Charge container-wide user plus system CPU, including children and failed attempts. On Linux with cgroup v2, read the test container’s `cpu.stat` usage delta before exit from an external or disposable measurement harness. Keep the measurement output away from selector stdout.
4. Reject variants that add a known miss, violate a runtime limit or regress total score without a justified generalization benefit. First investigate why either long test was selected. Narrow proven local symbol edits and fixture ownership before changing fallback rules. A zero-miss holdout is evidence, with uncertainty that depends on the number and variety of patches.

### Gate optional pytest replay

Replay is a benchmark variant after static selection works. Start with complete, cheap candidate groups and a small measured startup budget. For candidate set `C` and emitted set `R`, compare `cost(C) - E[cost(R)]` with replay CPU plus a margin for timeouts, retries and underestimation. Estimate using held-out results by evidence quality and measured cost, independent of patch IDs. Test work can be more expensive than the simulated makespan because parallel workers hide load in the score while CPU is added in full. Classify long-test and global-fallback groups as low priority for replay until measurements change that judgment.

Use a clean process per patch initially. Stage and size-check the writable source and required tests under `/tmp`, preserve paths and fixtures, disable bytecode and pytest cache writes, and verify the applied patch. Restrict subprocess output and keep only bounded diagnostic data. Use the starter’s pinned interpreter, locked dependencies and integration setting. An optional warmed parent can import the runner before forking only after tests prove the parent has no sqlglot, patched test modules, pytest collection state or unsafe worker threads to inherit.

Collect structured pytest events with exact node IDs. Require completed collection and setup, call and teardown outcomes where applicable. Count failing subtests even when the parent status is passed. An import or collection error covers every numbered test in the affected file. Unexpected skips, missing reports, incomplete groups, timeout with unclear scope and process crashes retain their unresolved candidates. An issue with unbounded scope escalates to the full catalog. Completed, faithfully observed failures may be emitted directly. Remove passed candidates only when group completeness and isolation are established, including any shared fixtures or relevant order dependencies.

Check remaining wall time and measured CPU budget before each replay. Terminate and reap timed-out processes, clean scratch, and retain conservative schedules for work that exceeds the gate. Reserve enough wall time for static handling and output for the rest of the batch. Compare full static selection with static plus replay at the same workload size to determine which ships.

## 5. Package and submit

1. Build from scratch with only allowed sources and pinned inputs. Verify map readability as UID 65534, a read-only root, empty 64 MB tmpfs, no network, 2 cores, 4 GB RAM, and the 256-process limit. Confirm the whole batch produces exactly one valid line per patch with no duplicate tests and no stdout logs.
2. Run sample under the Makefile flags and a larger representative synthetic batch under final limits. Practice has 180 seconds and final has 270 seconds for roughly 1.5 times as many patches. Measure batch overhead and worst-case fallback output. Aim for operational margin below those limits since unobserved patches can cost more. Confirm deterministic static selections and stable repeated CPU-inclusive totals.
3. Push the chosen public repository commit with a root Dockerfile. Submit a validated competitive version early, allowing for the practice submission queue. Record the exact SHA, build source manifest and measured score. Before the published cutoff, confirm the final selection points to the intended commit, particularly if the best practice result came from a riskier selector.
