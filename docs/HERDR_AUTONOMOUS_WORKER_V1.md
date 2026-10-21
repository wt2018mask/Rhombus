# Herdr Autonomous Issue Worker (pilot)

Status: **prototype, not production-qualified**. This is a Windows local GitHub Issue dispatcher, not a scientific evaluator or a self-hosted GitHub Actions runner. It does not merge branches, bypass required reviews, or independently verify any Draft PR.

## What is implemented

The operator can discuss a development task with ChatGPT and create a GitHub Issue under wt2018mask/Rhombus. The worker accepts an Issue only when ALL conditions hold:

- The author is exactly wt2018mask.
- Its title begins with [agent-task].
- A maintainer has applied the exact label herdr-approved.
- Its body has 10–12,000 characters and the Issue is open.
- The issue number has not already been claimed locally.

The worker runs in dry-run mode by default. Explicit --execute mode requires FOUR distinct live Herdr agents:

| Herdr alias | CLI/model | Function |
| --- | --- | --- |
| lead | Codex GPT-5.6 Sol Medium (or other verified coordinator) | Queue, classification, scope and delegation; not deep reasoning or routine code writing |
| reasoner | Separate Codex **account-verified** high-capability model; try GPT-6 Astra High first if supported | Deep design, complex inference, difficult failure analysis |
| builder | OpenCode DeepSeek V4.1 Flash Free, supported Max variant | Main code implementation and tests |
| helper | Antigravity Agy Gemini 3.8 Flash Low/Medium | Repetitive tasks, documents, uncomplicated code review |

For exceptional independent reviews, switch the Agy helper to a confirmed available **free** Sonnet/Opus thinking model when appropriate, or add a fifth Agy session with a unique name. Do not treat any subscription Codex session or Codex Luna as an external free model. The two Codex sessions share one ChatGPT account usage allowance. Kilo is excluded after its failed Herdr integration test. The worker forwards the approved task to the coordinator only, which delegates it across the remaining agents. The prompt requires isolated branches/worktrees, a Draft PR rather than a direct main change, focused tests, preserved science gates and no paid-model fallback for free agents.

The worker writes the Issue number and SHA-256 prompt fingerprint to a local state file BEFORE submitting it. Timeouts and unexpected process exits do not trigger automatic re-submission. A single-process lock prevents two local workers from dispatching in parallel. Successful terminal state is recorded as needs-review, NOT PASS: terminal idle does not prove scientific success, code tests or PR publication.

**Still unimplemented:** automatic startup after reboot, a restricted GitHub PR publisher, authoritative PR/CI verification, GitHub Issue status comments and unattended permissions. This is the first reviewable development slice, not a claim of completed hands-free development.

## Existing Rhombus contracts

This branch does not change README science conclusions, main, CURRENT.json, historical checkpoints or frozen evidence. Before merging, follow AGENTS.md: mandatory continuity check, exactly one small append-only checkpoint event, regeneration of the canonical handoff and all applicable CI. Do not bypass the O_ONLY restrictions or declare a scientific GO.

## One-time setup on Windows

Prerequisites: Python 3.10+, Git, gh (authenticated), Herdr, an authenticated ChatGPT Codex CLI, and free-account OpenCode and Agy CLI sessions. Launch the Herdr team and verify aliases lead, reasoner, builder and helper. A missing reasoner is an explicit blocker, not a reason to silently downgrade its role.

In PowerShell:

~~~powershell
gh auth status
gh repo clone wt2018mask/Rhombus "$HOME\Rhombus"
cd "$HOME\Rhombus"
python -m unittest discover -s tests -p test_herdr_issue_worker.py
herdr agent list
~~~

If the repository is already cloned, do not clone again; review this branch in your local checkout. The worker requires the existing cloned repository as its workspace. That local Git worktree is necessary for local code execution and tests; GitHub remains the source of truth.

## Model access preflight — 2026-10-21

The actual Windows Codex CLI 0.154.0 test under ChatGPT login returned **HTTP 400**:

> The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account.

The initial "model: gpt-6.1-sol" banner only echoed a requested model; it did not prove server-side authorization. Do **not** keep retrying this unsupported model, disable safety, or switch to paid API keys just to bypass the error. Rollout/plan access can change, so re-test only if the provider confirms new entitlement.

Maintain four independent Herdr sessions. The reasoning model is deliberately configurable: the operator first chooses a Codex model available to their existing ChatGPT subscription and verifies one successful server response. The documentation recommends testing **GPT-6 Astra High**, which official guidance lists for Codex Plus, but never assumes it works for this account until the live check succeeds. Otherwise choose the best model actually offered in Codex /model. The coordinator remains a separate lighter Codex session; do not duplicate or replace the leader.

Use an external PowerShell window, from the home directory (not System32):

~~~powershell
cd $HOME
codex exec --model gpt-6-astra -c 'model_reasoning_effort="high"' --sandbox read-only --ephemeral --skip-git-repo-check "Reply with exactly REASONER_OK"
~~~

Only a returned REASONER_OK with successful termination counts as a successful access check. This check consumes existing Codex usage; it does not separately subscribe to an API. If rejected, inspect the model picker instead of guessing alternate model identifiers. Launch the successful model as a second Codex session in an empty Herdr pane; check /status and name the pane reasoner. Example with the successfully validated model identifier:

~~~powershell
codex --model gpt-6-astra -c 'model_reasoning_effort="high"'
~~~

In another PowerShell window identify and rename the new pane using supported Herdr commands, after checking the installed CLI help:

~~~powershell
herdr agent list
~~~

Do not claim a model is running merely because the pane exists. The worker currently checks the distinct session identity and status, **not the authenticated model ID**. Human-supervised model validation is a required pilot prerequisite; machine-attested model identity and automatic startup remain future work.

The builder remains OpenCode DeepSeek, and Agy runs Gemini Flash as helper where free access is verified. Codex coordinator and reasoner use the SAME ChatGPT subscription quota. Model selection does NOT bypass interactive approvals.

## Dry run and explicit execution

First create a GitHub Issue written by wt2018mask with a [agent-task] prefix and bounded English instructions. Apply the herdr-approved label in GitHub, or create that label once as repository maintainer.

Preview the authorized queue, no writes:

~~~powershell
python scripts/development/herdr_issue_worker.py
~~~

After validating the separate Herdr lead permission model and local workspace:

~~~powershell
python scripts/development/herdr_issue_worker.py --execute
~~~

Continuous local polling is opt-in and runs only while the PC and terminal remain active:

~~~powershell
python scripts/development/herdr_issue_worker.py --execute --loop --poll-seconds 120
~~~

The default state path is %USERPROFILE%\.rhombus-herdr-worker\state.json. A worker.lock file prevents concurrent local dispatch. If a crash leaves a stale lock, examine the previous run and Herdr output before removing it. If any attempt is ambiguous, the worker refuses to resend it automatically.

DO NOT run an unattended Codex session with --yolo / disabled sandbox on a personal computer. Interactive Codex approval prompts can still block this pilot. A restricted unattended execution profile and least-privilege GitHub publisher must be implemented and validated separately.

## Test and acceptance criteria

~~~powershell
python -m unittest discover -s tests -p test_herdr_issue_worker.py
~~~

Tests are offline/mocked; do not confuse them with Windows end-to-end evidence. Before calling this system fully automated, verify: (1) a real Issue intake, (2) a separately isolated worktree, (3) coordinator delegating difficult reasoning to a DISTINCT **account-supported** Codex model, implementation to DeepSeek, and routine review to Gemini, (4) a real test run, (5) verified GitHub Draft PR and CI, (6) no repeated approval dialogs during allowed operations, (7) no unauthorized credentials/paid providers and (8) reliable, idempotent status updates after restart.

Never auto-merge a scientific PR or promote scientific claims based only on model output.
