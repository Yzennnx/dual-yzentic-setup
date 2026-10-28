---
name: workflow
description: Switch the build workflow between classic (Claude's builder agent writes code, Antigravity writes tests) and agy-build (Antigravity builds each task, Claude designs and reviews the diff). Use when the user invokes /workflow agy-build or /workflow classic, or asks which workflow mode is active.
version: 1.0.0
---

# Workflow Skill (Build Mode Switch)

`/workflow agy-build` and `/workflow classic` change one field and nothing else: `workflow.mode` in [`project-blueprint.json`](../../../project-blueprint.json). Edit that value, then say which mode is now active. The session start hook prints it as `Mode: <mode>`.

## classic (default)

- Claude designs, then hands Tier 2 and Tier 3 tasks to the `builder` agent (Sonnet) on a `feat/<task>` branch.
- The Gatekeeper (Antigravity) writes missing tests during `npm run verify:agent`; a Tier 3 task that names its tests has the builder write them.
- Review, merge and tiers as in CLAUDE.md.

## agy-build

- Claude designs and plans only. Each task names its files, its tests and its mockups (the mockup map must pass `npm run mockups:check`).
- Each task, or a group, is dispatched to the Antigravity `build` job on the branch, one commit per task:
  `npm run agy:build -- --plan <spec> --tasks <list>` or `npm run agy:build -- --design <file>`.
- Antigravity writes the code AND the tests the task list names. The `builder` agent is not used, and the baton does not launch the Gatekeeper to write tests (it still runs them).
- Claude reads the diff (`git diff main...HEAD`, not the agent transcript) against the design, then runs `npm run verify:agent`. Fix what stands, either by re-dispatching with the correction or by a Tier 1 edit.
- Tier 3 still ends with `npm run verify:agent -- --e2e`, one `npm run review`, and the merge.
- Models: the first of `gemini-4-argon-medium`, `claude-sonnet-5-5-medium`, `gpt-oss-120b-medium` that is available; `npm run sync:status` shows which ran.
- QA attacks (`qa-break` skill) are run by Antigravity: `npm run agy:qa -- <area>`; Claude triages the findings.
