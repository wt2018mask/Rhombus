# Rhombus chat-session recovery: bounded context protocol v1

This file is a short **procedure**, not a second handoff or frozen project snapshot.
Canonical authority remains `data/development/CURRENT.json`, validated by
`python scripts/development/continuity.py check`. Never paste full chat history.

## First message in a new ChatGPT conversation

> Continue development of `wt2018mask/Rhombus`. Read `AGENTS.md`, then
> `data/development/CURRENT.json` on current `main`, validate development
> continuity and inspect current open PRs / CI before writing. Use only
> `CURRENT.refs` required by `CURRENT.frontier.next_action`. Preserve the
> active Kaggle full-run: do not cancel, resubmit or patch its exact-commit
> kernel, workflow or frozen source. Treat scientific evidence as fail-closed.
> Briefly report current canonical main, stacked branches, active blocker,
> latest tests, and the next smallest safe code change; then proceed.

The same message is reusable across model and chat changes: it does not contain
stale commit IDs or a copied timeline.

## Fixed reading / token budget

1. Read `AGENTS.md` and **only the current** `CURRENT.json` from `main`.
   If a stacked PR chain is open, inspect the HEAD `CURRENT.json` of the
   latest PR too, but *do not confuse proposed checkpoint with canonical main*.
2. Validate continuity and inspect open PR metadata + latest CI summaries.
3. Read max **three** files under `CURRENT.refs` or the relevant PR patch.
4. Cap initial recovery read to approximately **8,000 input tokens** (soft
   budget; correctness overrides if security/science requires more). If the
   response exceeds budget, load the next needed file in a separate step
   rather than pasting historical conversations.
5. Read historic `data/development/checkpoints/` **only** when a mismatch,
   stack repair, audit or missing transition requires it. Never replay all
   events by default.
6. Keep reports short: a 5-line state digest plus links to PRs and evidence.
   Do not repeat long log excerpts across chat sessions.

## Recommended digest shape (at most ~250 words)

- **Canonical:** main SHA, latest validated checkpoint, Phase / frontier
- **Proposed:** latest open PR, head SHA and stacked parent dependency
- **Remote compute:** provider observation and timestamp, plus uncertainty
- **Gates:** Fast CI / continuity / Wave 2 and what is still pending
- **Next safe action:** one implementable small PR; forbidden side effects

## Conflict handling

- Chat memory, README snapshots and generated narratives are not stronger than
  live GitHub `main` and verified evidence. `CURRENT.json` may describe an
  unmerged checkpoint while canonical `main` remains older: verify both.
- A CI check success on a **stacked PR** does not prove that the changes were
  canonically merged into `main`.
- Model session changes never give an agent permission to expose secrets, run
  new Kaggle production jobs, infer provider RUNNING from controller polling,
  or qualify scientific conclusions from diagnostic artifacts.
- For terminal Kaggle outcomes, follow
  `docs/PHASE3_KAGGLE_RECOVERY_PLAYBOOK_V1.md`.

## Continuity cost control

Never copy a growing chronological changelog into `CURRENT.json`. Keep compact
pointers, one append-only tiny checkpoint per PR and a generated handoff.
Periodically reduce superseded `refs` only via reviewed versioned cleanup;
never delete frozen evidence or historical checkpoints. New conversations can
regain authority with one CURRENT read, not an accumulating dialogue.
