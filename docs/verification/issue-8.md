# Issue #8 — Verify Phase 01 and preserve its handoff

Acceptance completed on 2026-10-09 (Asia/Seoul), against issue #2 section 9.
**Phase 01 core checks passed.** Local inheritance/constructor integration through
the recovered supplied Player also passed; unseen grader compatibility remains
unverified. AI-written by OpenAI Codex. No new LLM prompts/responses or usage records
were recorded, per the user's explicit override; existing attribution is preserved.

## Actual commands and results

Run from the repository root with Python 3.14.3. Targeted tests ran before final
discovery; no new rules/player behavior was introduced. The public test seams
are already specified by issue #2 section 4.

| Command | Observed result |
| --- | --- |
| `python3 -m unittest tests.test_simulator tests.test_reference -v` | 34 passed, 0.288 s. Same deterministic fixtures run against engine and independent reference. |
| `python3 -m unittest tests.test_player -v` | 8 passed, 0.836 s. Both colors, legal/nonmutating tiny-time and live empty/sparse/capture/dense calls; strict wins in all orientations, simultaneous draw classification, exposed-opponent loss avoidance, exception/deadline fallback. |
| `python3 -m unittest tests.test_runner tests.test_replay tests.test_provided -v` | 20 passed, 2.004 s. Short mover-win, capture-induced opponent-win, simultaneous draw and terminal-no-extra-call games; controlled exception/mutation/invalid move/timeouts, separate cumulative clocks; replay, damaged/truncated JSON rejection; actual supplied inheritance. |
| `python3 -m verification.differential > docs/verification/issue-8-differential.json` | 5,561 transitions checked with no mismatch, 28.186 s. Parent/sibling/nested ownership checked throughout. |
| `python3 -m verification.smoke --issue 8` | 8 completed, 0 capped, 0 failed regular games; deliberate probes: 2 capped, 1 failed at zero black clock. Every trace replayed. |
| `python3 -m verification.provided --output docs/verification/issue-8-integration.json --traces .scratch/issue-8-integration` | 16 completed, 0 capped, 0 failed; four as each color against each supplied bot. Every trace replayed. |
| `python3 -m unittest discover -s tests -v` | Final full suite: 64 passed, 5.273 s. Includes seeded differential tests. |
| `.scratch/typecheck-env/bin/mypy omok offline verification tests/test_player.py tests/test_runner.py tests/test_replay.py tests/test_provided.py` | Success, 22 source files; default mypy does not check untyped function bodies. Existing local development-only environment, no engine dependency. |
| `python3 -m compileall -q omok offline verification tests` | Passed syntax/bytecode compilation. |
| `git diff --check` | Passed whitespace checks; final working tree clean after checkpoint commit. |

Deterministic fixture coverage includes placement/coordinate order/ownership,
malformed and illegal moves, all eight capture rays and both colors, multiple and
consecutive captures/reuse, board edges and false capture patterns, strict five in
all orientations/edges, six/longer overlines, gaps, separate five plus overline,
capture-induced opponent and simultaneous wins, full draw, and final placement
with/without reopened captured cells. Dense generation is independently justified
in [the simulator contract](../simulator.md); random volume does not replace these
fixtures.

[Differential data](issue-8-differential.json): 16 ordinary sequences with seeds
20261008–20261023, 16 capture-biased with seeds 20361008–20361023, max 240 moves.
30 terminal sequences and two labeled verification caps; 1,064 captured stones.
Samples explore up to three siblings and a nested child every 20 plies. Every
transition compares all state fields and captured cells/prior values to the
independent reference; parent and sibling state remain unchanged. No mismatch
artifact was generated. Caps are not rules draws.

## Network-denied execution and isolated dependencies

These commands ran successfully on the actual macOS development machine:

```sh
sandbox-exec -p '(version 1)(allow default)(deny network*)' python3 -I -S verification/offline_engine.py > docs/verification/issue-8-offline.json
sandbox-exec -p '(version 1)(allow default)(deny network*)' python3 -I -S -c 'import json,socket
try:
    socket.create_connection(("127.0.0.1", 9), timeout=1)
except PermissionError as error:
    print(json.dumps({"os_network_denial_verified": True, "error": str(error)}))
else:
    raise SystemExit("Network denial was not enforced")' > docs/verification/issue-8-network-denial.json
```

[OS probe](issue-8-network-denial.json) returned `Operation not permitted`,
demonstrating enforcement rather than merely assuming connectivity was absent.
[Core probe](issue-8-offline.json) imported and executed `LegalBaseline` and
`Position.play` for both explicit colors, returned legal center moves, preserved
caller boards, and produced continuing children. Python `-I -S` disabled user/site
packages; the import guard rejects non-engine/non-stdlib modules, including
`offline`, `verification`, and `players`. The probe also denies Python socket audit
events. The OS sandbox is macOS-specific development tooling; the engine itself
does not depend on it. `python3 -I -S verification/offline_engine.py` reruns the
portable import/socket-guard check without claiming OS-level network denial.

Supplied code depends only on standard-library `abc` and `random`, loaded through
`offline.provided`; no opponent dependency is imported by `omok`. Provenance,
recovered-base inspection, and original integration are recorded in
[issue #7](issue-7.md). No supplied source was altered.

## Actual machine and measured timing

Python 3.14.3, macOS 13.7.8, x86_64, MacBookPro14,1; Intel Core i5-7360U @ 2.30 GHz,
8 GiB RAM (`sysctl -n machdep.cpu.brand_string hw.memsize hw.model`). One worker.
No grader runtime is inferred. Game wall times include subprocess startup and trace
writing/replay; they are not solely player thinking time. Traces retain per-turn
elapsed and cumulative remaining clocks.

Run `python3 -m verification.benchmark > docs/verification/issue-8-benchmark.json`.
The final benchmark ran separately after game and differential jobs finished;
three repeats of 1,000 transitions per fixture, best time reported, setup/reference
checks excluded. [Measured values](issue-8-benchmark.json) cover copying, placement,
capture resolution, and full-board terminal scan. No invented performance gate
or node-throughput claim is attached.

| Fixture | Best seconds / 1,000 transitions | Transitions / second |
| --- | --- | --- |
| Empty | 0.027653 | 36,162 |
| Capture | 0.031351 | 31,897 |
| Dense capture | 0.473259 | 2,113 |

[Local smoke data](issue-8-smoke.json): seeds 20261008–20261011 in both colors,
60,000 ms cumulative budget per player, cap 1,000, 30 s external subprocess deadline.
Eight completed games took 17–21 moves and 0.264–0.318 s each. Cap, zero-clock, and
unlimited probes are reported separately; the expected zero-clock failure did not
call black. No regular game failed.

[Supplied integration data](issue-8-integration.json): same four seeds in both
colors against RandomPlayer and SimplePlayer, 60,000 ms cumulative budget per
player, cap 1,000, 180 s external deadline. Sixteen games completed in 9–43 moves
and 0.195–0.564 s each. No mutation, illegal move, crash, post-return timeout, or
external timeout was observed. Deterministic SimplePlayer repeats are duplicate
evidence; seeds do not remove baseline wall-deadline variation. These are integration
runs, not strength estimates or cheaper screening.

## Limitations, handoff, and checkpoint

The runner cannot interrupt a player that never returns: hard per-turn process
isolation remains incomplete. External verification deadlines bound subprocesses
only. A submillisecond budget cannot guarantee baseline return; in-progress work
can exceed a checked deadline. Replay validates trace consistency, not authenticity.
No phase-01 speed or win-rate gate is imposed.

Pending external checks: unseen grader runtime, concrete board/coordinate types,
official unlimited-time interpretation, final class/inheritance arrangement, and
team/submission metadata. The authoritative local release Player is available and
verified, so it is no longer a missing input. No final package or Phase 02 search
was created.

[Phase 02 handoff](../phase-01-handoff.md) records representation, transitions,
ownership/restoration, terminal convention, baseline behavior, public integration,
trace format, timing, dependencies, and checkpoint restore instructions. The
checkpoint commit preserves runnable code/tests/docs and raw measured reports;
ignored `.scratch/` game traces and logs are reproducible outputs, not snapshot
contents. Required two-axis review is recorded in [issue-8-review.md](issue-8-review.md).
