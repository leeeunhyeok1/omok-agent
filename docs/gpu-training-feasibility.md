# GPU acceleration feasibility

October 16, 2026. Research from current repository code and official documentation.
No GPU backend was implemented or measured; no new games, training, or benchmarks
were run for this note. This is an engineering recommendation, not a speedup claim.

## What currently consumes training time

The optimizer proposes coefficient mutations and evaluates them through complete
games and successive gates; it does not train a neural network by gradient descent
([evolution implementation](../offline/evolution.py),
[profile](colab-training/balanced.md)). The evaluator extracts line, capture,
capture-effect, and multiplicity features before multiplying them by coefficients
([evaluator](../omok/evaluation.py)). Moving the small coefficient dot product to
a GPU would leave the feature extraction and game search in Python.

The engine uses immutable 19-by-19 tuple boards and copy-based moves
([simulator](../omok/simulator.py)). Search traverses children recursively with
alpha-beta bounds, transposition lookups, and cooperative deadline checks
([search](../omok/search.py)). These observations identify likely migration costs,
not a fresh profile proving the present distribution of runtime. The earlier
[repair measurements](simpleplayer-search-repair.md) already show that removing
redundant feature work can increase search coverage.

## Can it run on a GPU?

Yes, with substantial implementation work. Selecting a GPU runtime alone does
not make existing code use the GPU; Google explicitly documents that distinction.
Colab accelerator availability and resource limits also vary.
([Colab FAQ](https://research.google.com/colaboratory/faq.html))

NVIDIA recommends enough parallel work, minimizing transfers, and retaining data
on the device. Different branch paths within a warp can reduce instruction
throughput. Those constraints make many independent boards a more promising
candidate than sending each individual alpha-beta leaf to the GPU. This is an
inference from the engine design, not a claim that GPU tree search is impossible.
([CUDA best practices](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html))

Two possible designs:

- **Preserve the evaluator:** represent boards as packed numeric arrays, implement
  rule/feature kernels, and batch work across many active games or search
  frontiers. The scheduler must respect dependencies, deadlines, partial results,
  capture semantics, and exact-five outcomes. Larger batches can add waiting
  latency, so aggregate throughput and single-move latency need separate checks.
- **Introduce a learned policy/value evaluator:** train with batched board data
  and use it to guide search. This requires a new dataset, model, training
  objective, inference integration, and evaluation protocol. It changes the
  learning system rather than accelerating the existing 24-coefficient loop.

Neither design guarantees stronger play or a particular acceleration factor.

## Recommended next implementation

Start with a bounded **compiled CPU hotpath prototype** rather than a full GPU
rewrite. Profile representative saved positions using the existing
[feature-family instrumentation](../omok/measurement.py), then move the measured
hot rule/feature loops behind a numeric-array interface while preserving the
Python implementation as a reference. Numba is one candidate: its official docs
support compiled loops and stress compilation in nopython mode; the present
callbacks, report dictionaries, and custom objects would need an adapted boundary,
not just a decorator.
([Numba performance tips](https://numba.readthedocs.io/en/stable/user/performance-tips.html))

Before adopting a backend, compare feature/score/rule results on saved fixtures,
including captures and simultaneous outcomes, and check deadline/cancellation
behavior. Measure warm execution separately from compilation/startup. Benchmark
end-to-end move latency and completed games per hour, not only kernel time.
Keep the same work budget when assessing semantic equivalence, and separately
use the intended game clock when assessing practical play.

CPU game parallelism already exists through the batch scheduler and isolated
players ([batches](../offline/batches.py), [registry](../offline/registry.py)).
Increase workers only after measuring allocated CPU capacity: clock-limited
games compete for CPU, and changing contention can change selected moves.
Official gate jobs are intentionally dispatched with one worker
([evolution stage execution](../offline/evolution.py)).

Consider GPU batching only if a representative, transfer-inclusive prototype
beats that CPU baseline. Preserve frozen run provenance: source/runtime changes
require a fresh experiment, as documented in [optimizer rules](optimizer.md).
Before choosing CUDA or compiled dependencies for the submitted agent, verify
the actual course submission and execution constraints; GPU access and native
dependency support in grading have not been established here.

More games per hour improves experiment capacity. Faster search can allow more
useful replies within a move budget. Neither replaces a diverse opponent pool,
separate holdouts, or evidence of playing strength beyond SimplePlayer.
