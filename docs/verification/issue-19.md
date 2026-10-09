# Issue #19 acceptance record

AI-written by OpenAI Codex. Issue: “Evaluate legal capture opportunities and
vulnerable pairs”; project context: GitHub #1. Review baseline:
`c7fe1216126f3dfc1dcc58fc434cac8e099ab10a`.

Implemented the experimental `capture-v1` schema, with unique legal moves,
canonical captured/vulnerable pairs and cells, multi-pair multiplicity, and
prospective outcome labels. Definitions, intentional feature overlap and
provisional coefficients are recorded separately in `docs/evaluation.md`.
Opportunity/risk contributions are independently configurable; family ablation
and earlier configuration identities remain isolated. Phase 2 remains the default.

TDD used the agreed inspection/scoring, matched-tree search and public-player
seams. The initial multi-pair fixture failed on unsupported capture-v1; the
saved-configuration fixture failed on the missing JSON file before implementation.
Eight behavior tests cover literal multiple/invalid-ray/control fixtures,
both colors in all eight rays and board symmetries, independent rule outcomes,
capture-induced opponent wins and simultaneous draws, post-capture recomputation,
configuration validation/ablation/saturation/interleaving, cancellation during
capture work with immutable state and no exact leaf table entry, null incomplete
inspection families, matched alpha-beta/reference trees through depth three,
public turns, perspective negation, table replacement, low-time legality,
mandatory strict wins and capture defenses, and terminal priority.

Commands and results:

```sh
python3 -m unittest tests.test_captures tests.test_potential tests.test_lines tests.test_evaluation -q
.scratch/typecheck-env/bin/mypy omok offline verification/evaluation.py verification/captures.py --ignore-missing-imports --follow-imports=silent
python3 -m unittest discover -s tests -q
python3 -m verification.captures --repetitions 5
python3 -m compileall -q omok offline verification tests
git diff --check
```

27 focused tests passed. Typechecking passed for 18 source files. Full suite:
146 tests passed in 23.675 seconds. Syntax and whitespace checks passed.

`issue-19-suite.json` embeds nine deterministic boards, complete inspection,
capture-disabled totals and five-sample static evaluation timings. The independent
oracle checked every legal move for each color: 5,958 transitions, including 272
on a live dense board (seed 20261030). Capture coordinate sets, captured cells,
multiplicity, resolved outcomes and mover-relative labels all agreed, including
a strict winning capture. Disabled contributions change scores without changing
rules or terminal values.

On this machine enabled median evaluation was 7.56–27.95 ms versus
5.71–10.43 ms with captures disabled; the live dense case was 27.95 versus
10.43 ms. These are sequential static samples with uncontrolled background load,
not official-clock games or a strength claim. The dense hypothetical work costs
substantially more, supporting retention of the Phase 2 default.
No leagues, optimization, search extensions or final packaging were implemented.
Capture effect scoring remains #20 scope. No LLM usage was recorded. Existing
user deletions and the untracked phase specification are excluded from commits.
