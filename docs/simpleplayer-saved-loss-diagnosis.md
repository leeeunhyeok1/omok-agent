# Saved SimplePlayer loss: a bounded search reproduction

The uploaded round-zero game contains a demonstrably avoidable fatal move at
zero-based ply 22. This diagnosis establishes one specific failure and its
mechanism; it does not establish the earliest strategic error in the game or
playing strength across complete games.

The compact, exact position and candidate configuration are in
`verification/fixtures/simpleplayer-ply22.json`. Its source record is
`run/rounds/0/screening/1b37e8152810935325825f8ed7e5f54af700c30794e58b77a0aab9dda8a6b8a2/390aa2d5ef3bb1a94e2dff1305b5b5d1d8de75097f9cd0a8f6e193e55f654fcc.json`.
The fixture records a canonical trace SHA-256, source ply, recorded move, reply,
and exact evaluation coefficients and search settings. It is a proposal
candidate's loss, not an independently tested champion result.

## The failure

Black played `(6, 8)`. SimplePlayer answered `(11, 8)`, giving White two exact-five
winning placements, `(7, 12)` and `(12, 7)`. A complete tactical scan of Black's
legal moves finds neither an immediate own win nor any defense, including
capture defenses. This is already a forced loss.

The same position has an explicit alternative: Black `(11, 11)`, followed by
the same White reply `(11, 8)`, permits Black to win immediately at `(12, 12)`.
Both sequences' terminal outcomes are checked using the independent board-rule
oracle. The fixture makes no claim that `(11, 11)` is the unique best move or
that it wins against every different White reply.

## Deterministic feedback loop

Run `python3 -m unittest tests.test_saved_simpleplayer_loss -v`.

The search test uses the real configured engine, exact captured coefficients,
and a limit of 100,000 cooperative checkpoints. This is a deterministic work
limit rather than a simulated number of milliseconds. It asserts that the
returned move does not permit this demonstrated forced loss. The second test
checks the fixture's losing and winning continuations independently.

Before the evaluator cost changes, the failing assertion was:

```text
AssertionError: True is not false : Chosen (6, 8) permits the saved forced loss; 4 evaluations, depth 0, checks 100001
Ran 2 tests in 0.250s
FAILED (failures=1)
```

This baseline was rerun without mutating the working tree: a temporary copy of
the `omok` package was loaded first on `sys.path`, with `lines.py` and
`captures.py` replaced by their Git HEAD versions. Exact baseline invocation:

```sh
python3 - <<'PY'
import pathlib, subprocess, shutil, tempfile, sys, unittest
with tempfile.TemporaryDirectory(prefix='omok-loss-baseline-') as tmp:
    target = pathlib.Path(tmp) / 'omok'
    shutil.copytree('omok', target, ignore=shutil.ignore_patterns('__pycache__'))
    for name in ('lines.py', 'captures.py'):
        (target / name).write_bytes(subprocess.check_output(
            ['git', 'show', 'HEAD:omok/' + name]))
    sys.path.insert(0, tmp)
    suite = unittest.defaultTestLoader.loadTestsFromName('tests.test_saved_simpleplayer_loss')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
PY
```

This invocation's historical meaning depends on HEAD remaining at its current
pre-fix revision. The fixture provenance remains valid after future commits.

## Causal distinction

The observations distinguish these possible causes:

1. Excess evaluation cost: more candidate evaluations within the same work
   allowance should avoid the demonstrated losing continuation.
2. Candidate pruning: the safe moves would be absent from root candidates,
   and completing depth one could not select them.
3. Unhelpful coefficients: even complete depth one would prefer the blunder
   over the specific safe alternatives.
4. Insufficient opponent-reply search: completing depth one might still fail
   while deeper search changes the decision.

For this position, completing depth one with the old evaluator selected
`(11, 11)`. Candidate membership and the coefficients therefore already allowed
a useful alternative. With fewer evaluations, the old engine selected the
recorded `(6, 8)` blunder. This supports evaluation cost and interrupted
candidate coverage as a concrete cause here, without ruling out the other
problems in different positions.

After sharing verified geometric completion candidates and enumerating capture
anchors more directly, the same 100,000-check allowance evaluates 14 children
and selects `(11, 8)`. That occupies the saved threat-creating reply square and
passes the regression. Both tests pass in about 0.2 seconds locally. The selected
move still has completed depth zero: partial candidate coverage is now enough
to avoid this specific failure, but it is not proof of reliable deeper play.

No complete games or training runs were performed for this diagnosis. Separate
controlled game results are required to evaluate overall strength.
