# Blast Radius strategy

Build a conservative impact selector from the pinned sqlglot checkout. Use per-test line coverage to narrow local edits, fixture and setup dependencies to catch changes coverage misses, and the scorer’s exact cost function to schedule the result. Promote runtime pytest replay only where a measured CPU-inclusive comparison shows a gain.

## What the sample says

The starter kit contains 30 patches, 1,620 numbered tests across 58 files, and 103.047 seconds of recorded test work. Twelve patches have zero failing tests. The parser’s `test_max_nodes` and executor’s `test_execute_tpcds` account for 50.271 seconds of the catalog. Incorrectly dragging either into unrelated selections often costs more than optimizing the worker split.

| Selection and scheduling | Sample simulated seconds | Misses |
| --- | ---: | ---: |
| Every test, starter’s three workers | 1,210.470 | 0 |
| Every test, best of 1–8 longest-first schedules | 1,104.510 | 0 |
| Known failing tests only, best of 1–8 longest-first schedules | 94.351 | 0 |

These are local scorer results, before CPU charges. The advertised starter baseline is 1,614.1 seconds. The 94.351-second result uses sample labels solely as an evaluation reference and is a feasible schedule rather than a proof of optimality. None of these figures estimates hidden-set recall.

## Where to spend complexity

| Priority | Decision | Reason |
| --- | --- | --- |
| 1 | Select from pinned dependencies with explicit fallback | A 300-second miss can erase the savings from many commits. Unknown or global impact can fall back to the full catalog, which costs 36.817 simulated seconds per sample commit with the worker sweep. |
| 2 | Distinguish execution, setup and fixture impact | Runtime line coverage cannot see an edit that introduces a new path, changes collection, changes an import or affects a data file read only once during setup. |
| 3 | Schedule using integer milliseconds and 1–8 workers | An extra worker earns its 2 seconds only when it drops the busiest load by more than 2 seconds. A set of short failures often fits one worker. |
| 4 | Replay inexpensive candidates selectively | A faithful replay can turn a clean commit into a zero-cost selection. Startup, collection and test CPU count, and replay cannot reveal failures outside its candidate set. |

For a choice between a narrower and wider selection, a widening that costs `Δ` seconds pays if it reduces the probability of a missed commit by more than `Δ / 300`. A 6-second widening needs only a two-percentage-point reduction. Estimate that risk per commit, because omitting several failures from one commit incurs a single penalty.

Keep full-suite replay as an offline validation tool. Applying it to every sample patch would imply roughly 3,091 seconds of recorded test work before selection overhead. Live replay of the two largest tests also needs its own justification, particularly when either controls the simulated makespan. Spend the first tuning pass on mapping their actual dependencies.

## Evidence and rules

Use `sample/answers.json` only in the evaluation harness. The shipped selector and its data come from the pinned source, observed baseline dependencies and the current runtime inputs. Keep patch IDs, sample labels, and tables of which changes break which tests out of shipped decision logic and map generation. Evaluate several independent patch families, including generated changes whose outcomes come from the full pytest suite.

Build and test on Linux/amd64 against the pinned image and locked dependencies. Budget for the 180-second practice and 270-second final batch limits as well as charged CPU. Ship the earliest validated competitive commit and improve it using repeated measurements. The final ranks entries within one second of the best in each tie group by submission time, and hidden final patches include change types absent from practice.

Continue with the [implementation plan](implementation-plan.md) for the map format, selection rules, replay gate and release checks.
