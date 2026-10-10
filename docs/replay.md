# Replay and loss inspection

Issue #31 adds `omok-game-v4` for supervised games. V4 deliberately requires the
saved factory/options/seed for each player, supervision limits and clock policy,
two worker lifecycle reports, and call/transport timings (nullable when no reply
arrived). Optional diagnostics remain bounded by the worker. Replay validates
this evidence as well as the existing move/capture/state/clock ledger. Readers
retain valid v1 trusted traces, v2 event traces, and v3 supervised traces.
Setup, crash, timeout, protocol and cleanup failures are execution facts; replay
does not turn an ongoing board into a strategic win or draw. Cleanup failures
retain and validate the preceding result. Truncated or inconsistent traces fail.
Cleanup timing or exit status may be unavailable only with an explicit worker cleanup error.
An infrastructure error without an offending side has no automatically selected
loss position; an explicit color can still select preceding applied turns.

```powershell
python -m offline --replay .scratch/game.json
python -m offline.inspection .scratch/game.json --output .scratch/loss.json
python -m offline.inspection .scratch/game.json --color 0 --ply 12 --ply 14 --max-positions 2 --history-limit 6
```

`inspect_loss` and its CLI never import/construct recorded players or invoke an
agent. The default selects the last eight turns of the board loser or offending
player, including the position before a failed call. A draw/cap has no inferred
loser; select a color explicitly to inspect it. Select specific zero-based plies
to investigate an earlier suspected error. An export contains the board **before**
the chosen move/call, side to move, player/opponent identities and source/specs,
full saved configuration (including registry/version identities when present),
both clocks before the turn, chosen move if available, returned-event diagnostics,
execution evidence, and up to twelve preceding applied moves with captures/clocks.
Selection and history limits are saved; the source trace digest links the artifact
to the complete game. V1 has no returned-event diagnostics to export.

Limits are 1–100 positions and 0–1000 preceding moves per position. Selection is
bounded after reading/validating the complete trace; this is not a streaming
parser or a hard input-file byte limit. The final board is reported only as an
outcome, not claimed to contain the decisive error. These recent turns are
representative inspection points, not causal identification of mistakes.

Automatic categories such as exact-five interaction, time management, pair
vulnerability and unclassified loss always carry `status: hypothesis`. No
candidate omission, evaluation error, horizon effect or best move is inferred
from a loss. Alternative agent analysis is not implemented; the schema records
`alternative_analysis: null`. Any later analysis must use a separately saved
offline budget and must not subtract from the original game clock.

Confirmed rule-result fixtures can enter the tactical regression suite:

```powershell
python -m offline.inspection .scratch/game.json --color 0 --ply 12 --confirm-outcome white_win --confirm-reason exact_five --output .scratch/confirmed.json
python -m offline.inspection .scratch/confirmed.json --verify-fixture
python -m verification.loss_inspection --output .scratch/loss-evidence
```

`checked_fixture` requires an explicit expected outcome/reason and verifies the
recorded move through both the simulator and independent full-board rules oracle.
The portable `omok-checked-rule-fixture-v1` artifact is runnable with
`verify_fixture` (a failed assertion raises `ValueError`). Its only supported
assertion is **recorded-move-rule-result**. Execution-only failures and incorrect
expectations are rejected. These fixtures establish a rule result, never that a
move is best or that a hypothesis is tactically proved. An ongoing result uses no
`--confirm-reason`. Checked expectations can be reverified without the source
agent or game manager; source position metadata retains the inspection context.
