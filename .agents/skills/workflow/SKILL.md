---
name: workflow
description: Show or switch the checkout between solo and paired coding workflows. Use for /workflow, /workflow <preset>, or questions about the active workflow.
version: 1.0.0
---

# Workflow Skill

Run `npm run workflow -- status` to inspect the active preset and its roles. Run `npm run workflow -- list` to list all presets.

For `/workflow <preset>`, run `npm run workflow -- <preset>` and report the selected roles. For `/workflow reset`, run `npm run workflow -- reset` to follow the blueprint default. The selection is local to the current checkout.

If the next step belongs to another interactive agent, tell the developer which session to open in the same checkout. For a mid-task switch, save the agreed design, current edits, verification, and outstanding work in the local resume note first. Follow the [workflow guide](../../../docs/ai/workflows.md) for handoff and independent checks.

In `agy-build`, Claude gives the Antigravity build job the approved plan, task list, files, tests, and applicable mockups. Use `npm run agy:build -- --plan <spec> --tasks <list>` or `npm run agy:build -- --design <file>`. Antigravity commits once per task. Claude reads the diff against the design, fixes what stands by redispatching or making a Tier 1 edit, and runs the required checks. The [model fallback order](../../../README.md) still applies. `npm run sync:status` reports which model ran. For hands-on QA in this preset, use `npm run agy:qa -- <area>` and triage the findings.
