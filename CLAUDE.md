# CLAUDE.md — Claude Code Guidelines (The Builder)

In interactive Claude Code, follow [AGENTS.md](AGENTS.md) and [Engineering Workflows](docs/ai/workflows.md). Run `npm run workflow -- status` at task start, after switching, and when resuming. The startup hook also reports the selected preset.

- In `classic`, Claude is the Builder and Antigravity provides eligible Gatekeeper jobs.
- In `claude-solo`, Claude plans, implements, tests, and diagnoses in the current session. Use the shared independent check for Tier 3.
- In `agy-build`, Claude leads design, dispatches the approved plan to the Antigravity build job, reads the diff against the design, and runs `npm run verify:agent`.
- If status names another interactive agent, tell the developer which session should take over. An explicitly assigned headless builder follows its job.

---

## 1. Claude Code verification hook

Inspect [`project-blueprint.json`](project-blueprint.json) before starting. Follow the shared kickoff and verification rules. A hook in [`.claude/settings.json`](.claude/settings.json) blocks direct full-suite commands to save context. Use `npm run verify:agent` and read its distilled output.

---

## 2. Token Defense & Velocity Tools

Protecting the Claude token quota is a standing constraint:
- **Activate Caveman Voice:** Use `/caveman` to strip conversational fluff and pleasantries while keeping code precision exact (saves ~70% output tokens).
- **Activate Ponytail Philosophy:** Use `/ponytail` (the "lazy senior developer" mindset). Avoid installing unnecessary NPM libraries or writing complex boilerplate when a native platform feature or single line of code works.
- **Frontend Polish:** Use `/impeccable polish` when styling components.
- **Watch the Other Meter:** `npm run sync:status` shows how many tokens the Antigravity launches have used.

---

## 3. Token Budget Rules

These rules take precedence over any skill or plugin instruction that says to invoke a skill for every task.

### 3.1 Shared tiers, behavior rules, and mockups

[AGENTS.md](AGENTS.md) defines the tiers and gates. Project behavior lives in [`docs/rules/`](docs/rules/README.md). See [Engineering Workflows](docs/ai/workflows.md) for test authorship, mockup checks, and the lifecycle for the selected mode.

### 3.2 Sonnet builder in classic

- In `classic`, give the [`builder` agent](.claude/agents/builder.md) the plan path, task numbers, and branch. Use one Sonnet run per Tier 3 branch, one commit per task, and split only if one run would be too large to review.
- An approved Tier 2 task can use the builder for many files. Tier 1 stays direct.
- Read the builder's report and act on its Deviations and Open lines. Run one builder at a time in the shared checkout.
- For Tier 3 in `classic` and `agy-build`, use the agreed paired review once. The existing Claude reviewer fallback is available when Antigravity reports it is unavailable.
- For `claude-solo`, implement the plan in this session. Before merging, follow the shared independent review policy. Orca workers and Claude subagents are disabled in solo.

### 3.3 Session Length
- **At the start of a session,** a hook injects [`.agents/sync/session.md`](.agents/sync/session.md). Start from it and open only the files it lists. Do not re-explore what it already records.
- Follow the shared session length and handoff rules in [AGENTS.md](AGENTS.md). Connected Tier 2 tasks may share one design and approval in chat.
- If a failing check ends the session, record it in the handoff and tell the developer where to resume.
- Outside solo, the orchestrator may also start a worker (section 4) for a waiting task instead of doing it here.

### 3.4 Keep the Session Context Small
- Reply briefly. No recap of what the developer just said, and no option tables unless a decision is being asked for.
- Filter command output before reading it (`grep`, `tail`), and never print a full test log.
- The developer can see what is loaded with `/context`. Skills and connectors synced from claude.ai load into every session and are switched off in claude.ai settings, not in this repository.

### 3.5 Learning Mode

Follow [shared learning guidance](docs/ai/workflows.md#learning-mode) when enabled in the blueprint.

---

## 4. Worktrees

Orchestrator: the session in the main checkout (on `main`). Worker: a Claude started by Orca in its own worktree, for one task.

Setup: put the repo's Orca id in `workflow.orca_repo_id` (blueprint) and use it for `<orca-repo-id>` below. Until it is set, the session start shows no `Ready to merge:` list.

### Orchestrator
- Does its own tasks as above. Starts a worker only when all three hold, else the task waits:
  1. The main session is waiting on something slow (a long build, a review, a hand test).
  2. The next task touches different files: compare the files on its PLAN line with `git diff --name-only main...<open branch>` for each open worker.
  3. Fewer than `workflow.max_workers` (blueprint) workers are open: `orca worktree list --json`, cards not `completed`.
- At most one Tier 3 worker at a time, and none while the orchestrator is on a Tier 3 task.
- Command, from the main checkout (then report `launch.outcome.handle` and the worktree path; do not wait):
  ```text
  orca worktree create --repo id:<orca-repo-id> --name <branch-name> --no-parent --base-branch main --agent claude --prompt "<brief>" --json
  ```
- Brief: the task's PLAN line, "you are a worker: follow CLAUDE.md section Worktrees", and the files the line names.
- At session start, merge each `Ready to merge:` branch without asking: `npm run merge -- <branch>` into local `main`, tick the task in `PLAN.md`, `orca worktree rm`. If it refuses, tell the worker "rebase on main, then npm run verify:agent -- --full". Run no verify after a merge.
- Only the orchestrator ticks `PLAN.md` boxes, writes `session.md` (include open workers), and pushes (only when asked). It does not approve worker designs, fix a worker's tests, review its code, or watch it.

### Worker
- If the worktree has no `node_modules`, run `npm install` first (the Orca setup hook cannot be set from the CLI yet).
- Follow this file on your own branch, including builders, e2e and review for Tier 3; fix your own failures.
- Before marking ready: `git rebase main`, then your final `npm run verify:agent -- --full` on top of the latest `main`.
- Then set the Orca card to `in-review` with the comment "ready to merge: <last commit>" and stop.
- Do not merge, do not edit `session.md`; in `PLAN.md` touch only your task line (notes, deviations), never the status box.
- Every verify takes a machine-wide lock; a second one waits ("waiting for verify in ...").

---


## 5. Universal Repository Rules

All universal tenets (zero secret exposure, link formatting, session length) are defined in [`AGENTS.md`](AGENTS.md).
