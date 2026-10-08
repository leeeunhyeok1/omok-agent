# AI provenance

Issue #3's simulator, independent reference, tests, verification tools, and new
documentation were written by OpenAI Codex. The local session metadata identifies
model `gpt-6.1-sol`. Subscription/paid-plan information was not provided and remains
unresolved for final submission disclosure. Existing professor-provided files in
`players/` were neither authored nor changed in this work.

`issue-3-interaction.jsonl` preserves exact visible user/assistant messages and tool
calls/results from this implementation session through the implementation/review
checkpoint. Internal reasoning and system/developer prompts are excluded. The
source session ID is `01a11a4b-1e04-7803-ad9c-4d35685475c5`. It includes the issue
and parent-spec reads. This is a checkpoint snapshot; final commit/final-response
records produced afterward can be added by rerunning:

```sh
python3 -m verification.export_interaction /path/to/codex-session.jsonl llm-usage/issue-3-interaction.jsonl
```

Keep the original session log until that refresh. Prior planning/specification
conversations are not reconstructed here; retain their originals for the eventual
submission's complete interaction archive. Do not treat this snapshot as a final
packaged LLM disclosure or invent missing team/plan metadata.

Issue #4's development player, offline runner/opponent/replay/CLI, public-boundary
checks, smoke command, and documentation were AI-written by OpenAI Codex
(GPT-6.1-sol). `issue-4-interaction.jsonl` records visible messages and tool calls
through the implementation/review checkpoint from session
`01a11a5b-c314-7461-bc9d-89356cea99b1`, including issue #1/#2/#4 reads. It can be
refreshed with the same exporter after this turn to include the final commit and
response. Subscription/plan and final submission metadata remain unresolved.
