# Search cost fix — October 15, 2026

The uploaded round-0 loss at ply 4 reproduced the reported failure locally:
250 ms expired with depth zero, 10 completed evaluations, and fallback `(0, 2)`.
With the same search settings, material-only evaluation reached depth two.
Profiling a complete depth-one search identified line scanning and duplicate
line/capture scans inside capture-effect evaluation as the main costs.

The change precomputes board-line geometry, skips lines that cannot contain the
reported features, and shares complete same-position scans between evaluator
families. Capture effects avoid line work when neither color has a capture move.
Rules, candidate membership, coefficients, and tactical verification remain
unchanged. The engine also now uses a useful fallback by default: a verified win,
the best fully evaluated depth-one child, a verified defense, or ordered root
candidate. Before search evidence exists, it ranks legal moves by nearby stones
and center distance. A partial move never receives a completed score/depth/PV or
an exact root cache entry. Completed iterations still take precedence over later
partial work. Diagnostics expose `fallback_source`.

Before the user requested stopping tests, the original position completed depth
one on three repeated 250 ms calls with the updated evaluator, choosing `(10, 11)`.
All 34 captured reference cases exactly matched the original feature outputs.
The deterministic first-iteration work regression passed. One existing
cancellation test used a fixed checkpoint count that the faster scan no longer
reached; it now cancels at the measured final inspection checkpoint and retains
all assertions about hiding partial results. That targeted test passed.

The full regression result was not collected before interruption. Further tests
were stopped at the user's request; the subsequent fallback and default training
initializer changes have not been executed or tested. Improved playing strength and Colab timing
are unverified. Local reproduction artifacts are in `.scratch/search-bottleneck/`;
the reusable replay harness is `verification/search_bottleneck.py`, with extracted
position/configuration provenance in `verification/fixtures/colab-search-positions.json`.

## Start training with the changed engine

Use the updated source in Colab. Preserve the old experiment; source changes are
incompatible with its frozen identity. Fresh optimizer initialization now registers
the current local material engine. The existing all24 initializer also registers
the current source, using the same all24 recipe. Historical catalog entries retain
their original checkpoint identities. Run from the repository root, choosing a
new directory for this experiment:

```python
!python3 docs/colab-training/initialize-all24-colab.py \
  --output .scratch/all24-search-fix-colab
```

Create the existing conditions declaration, with other training jobs stopped:

```python
import json
from pathlib import Path
Path('.scratch/colab-conditions.json').write_text(json.dumps({
    'power': 'Colab managed VM; power settings unknown',
    'load': 'No other training jobs running; shared-host load unknown',
    'other_experiments_stopped': True
}))
```

Start a bounded training invocation; repeat only this run command to resume:

```python
!python3 -m offline.optimizer run \
  --output .scratch/all24-search-fix-colab \
  --max-games 200 --max-seconds 1800 --workers 1 \
  --conditions .scratch/colab-conditions.json
```

Training retains its existing correctness gates. No separate verification runs
are required by these instructions. Back up the whole new run after each bounded
invocation. The [Colab notebook](../notebooks/all24-training.ipynb) automates bounded
training, whole-run Drive backups, exact-source restore, and optional champion
testing. The initializer and notebook have not been executed in Colab during this
session; their Python syntax and notebook structure were checked without running
additional engine tests.
