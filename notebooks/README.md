# Colab training

[Open all24-training.ipynb in Colab](https://colab.research.google.com/github/leeeunhyeok1/omok-agent/blob/main/notebooks/all24-training.ipynb)

Use a CPU runtime. Set an unused `RUN_NAME`, keep `ACTION = "fresh"`, and run all
cells. The notebook initializes all 24 coefficients with the current engine,
uses the balanced profile with one worker for one bounded 30-minute
segment, and backs up the whole
run to Drive before training and after each segment. Game caps can end segments
earlier; cleanup and backup add time.

The default fresh run is `balanced-search-v3`. The profile gives equal screening
weight to five opponent families and allows reliable exploratory parents while
retaining all champion promotion gates. Cell 8 shows parents separately from the
champion. Select `TRAINING_PROFILE = "simple-focused"` for targeted SimplePlayer
diagnosis or `all24` for the original parent-selection policy. See the
[balanced profile instructions](../docs/colab-training/balanced.md) and
[measured repair evidence](../docs/simpleplayer-search-repair.md). Keep old runs
unchanged; updated source and policies require a fresh experiment.

Use `ACTION = "resume"` on the same VM or `ACTION = "restore"` after a reset,
keeping the same run name. Restore verifies the archive checksum and exact Python
build, then restores the saved source commit from its bundled Git snapshot.
Backups live under `MyDrive/omok-backups` by default. Interrupt the training cell
once to stop gracefully and let checkpoint/backup finish.

Champion export is included. Independent champion testing is disabled by default;
enable `RUN_CHAMPION_TEST` to create or resume a separate 40-game development test.
The notebook does not access the final holdout. It was structurally checked but
has not been run inside Colab.
