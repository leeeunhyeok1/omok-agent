# SimplePlayer-focused fresh experiment

The two-hour search-v2 run produced varying training gains but no eligible champion.
Its parents could only come from candidates that passed every league strength
regression gate. This profile separates exploration from champion qualification;
it does not claim that a new parent or more computation produces stronger play.

Use a **fresh directory** after the engine update. Existing runs and their policies
remain frozen. For this optional targeted profile, select
`TRAINING_PROFILE = "simple-focused"` and `RUN_NAME = "simple-search-v3"`.
The notebook defaults to the [balanced profile](balanced.md) and one 30-minute
segment. Select `all24` to use the original recipe in a fresh experiment.
Resume/restore uses the saved source and
profile; old backups without a profile retain `all24`.

The equivalent initialization command, which plays no games, is:

```sh
python3 docs/colab-training/initialize-all24-colab.py \
  --profile simple-focused --output .scratch/simple-search-v3
```

The profile keeps all 24 coefficient mutation groups and the original search/time
settings. It assigns SimplePlayer family weight 4 versus weight 1 for each of the
other four families: SimplePlayer contributes half of the initial screening
objective. The league also adds incumbent/history families, reducing that share.
SimplePlayer receives eight balanced games over four distinct opening pairs per
stage; other opponents receive four. Confirmation uses a separate four-opening
set. Opening variation is fixed before play and is not independent statistical
proof, especially under geometric symmetries and deterministic opponents.

The champion remains an immutable elite. Additional parents may come from
screening survivors whose completed league evidence failed only strength gain or
regression requirements. They are ranked by screening fitness, with identity as
the deterministic tie break. Known correctness/reliability failures, missing or
invalid coverage, censoring problems, and unresolved historical obligations block
exploratory ancestry. If a candidate receives fresh confirmation, it must pass that
training confirmation to parent. Later checks can veto on observed reliability
failure or official completion/clock feasibility; validation strength scores and
pairing outcomes never rank parents.

All existing league, confirmation, validation and champion promotion requirements
remain in force. The original recipe still uses the original parent policy. A
parent change is **exploration**, while a champion change requires the full saved
qualification process. Cell 8 displays selected parents and completed rounds
separately from the champion, so these two signals are visible.

This is a targeted development experiment, not a general strength result. It
exposes SimplePlayer to training; neither the training score nor a promotion
establishes the assignment's strict-win qualification target. Inspect move-search
diagnostics and actual SimplePlayer outcomes before allocating a long run.
