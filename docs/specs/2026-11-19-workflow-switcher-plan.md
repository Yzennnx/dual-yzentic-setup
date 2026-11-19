# Implementation plan for the workflow switcher

**Add three solo presets and one Codex–Antigravity preset. Keep `classic` and `agy-build` compatible.** The switcher will change who owns the work in the current checkout. The tier, shared rules, verification commands, and approved design will continue to govern the task.

## Design

### Presets and role assignments

| Preset | Design and implementation | Testing and diagnosis | Tier 3 review |
|---|---|---|---|
| `codex-solo` | Current Codex session | Codex owns covering tests and investigates baton failures | Codex self-review, then the developer’s independent check or an explicit switch to paired review |
| `claude-solo` | Current Claude session | Claude owns covering tests and investigates baton failures | Same solo review policy |
| `agy-solo` | Current interactive Antigravity session | Antigravity owns covering tests and investigates baton failures | Same solo review policy |
| `codex-agy` | Current Codex session | Antigravity handles eligible Gatekeeper jobs. Codex writes ordinary tests named in Tier 3 plans. | Antigravity reviews once. Codex addresses the findings. |
| `classic` | Claude leads, with the existing Sonnet builder for Tier 3 | Existing builder and Gatekeeper assignments | Existing Antigravity review and documented fallback |
| `agy-build` | Claude leads design. Headless Antigravity implements. | Existing build and rule-test jobs. Claude verifies the work. | Existing Claude diff check and Antigravity branch review |

Tier 1 stays a direct edit and fast check in every preset. Tier 2 keeps the short design approval in chat, covering tests, and configured E2E when a user-facing flow changes. Tier 3 keeps the approved plan, named tests, configured E2E and build checks, one review, verification of review fixes, and full verification on the final branch tip before local merge.

### Where selection and instructions live

The tracked `project-blueprint.json` provides the shared default through its existing `workflow.mode` field. The current checkout can override it using `.agents/workflow.local.json`, a Git-ignored file containing one value such as `{"mode":"codex-solo"}`. Resolution order is **local selection → blueprint default → `classic` if the mode is absent**. An invalid preset or malformed local preference produces a clear error before a command can launch a delegated agent. This avoids silently falling back to a paid or unavailable agent when you intended solo.

```text
npm run workflow -- status       # Show the effective preset, its source, and role assignments
npm run workflow -- list         # Show the available presets
npm run workflow -- codex-solo   # Pin this checkout to Codex solo
npm run workflow -- agy-solo     # Pin this checkout to Antigravity solo
npm run workflow -- classic      # Pin this checkout to classic
npm run workflow -- reset        # Clear the pin and use the blueprint default
```

The `/workflow` skill uses the same command where the agent supports the skill. Switching writes one local setting and prints the new assignments. It works in the checkout you already have. A running command finishes under the preset it started with, and the next command reads the updated selection.

The rule migration happens once. `AGENTS.md` and `docs/ai/workflows.md` hold the shared lifecycle, including applicable rules currently documented only in `CLAUDE.md`. `CLAUDE.md` keeps Claude’s builder, hook, and worktree instructions. `GEMINI.md` distinguishes interactive Antigravity from a headless job with an assigned role. Each interactive entry point tells the agent to check the preset at task start, after a switch, and when resuming a handoff. If the preset names another interactive agent, it identifies who should take over. Codex uses the existing `AGENTS.md` entry point.

### Testing, switching mid-task, and independent checks

- **Testing stays on the existing baton path.** Solo skips automatic test writing, test repair, and failure diagnosis by a second agent. The current agent checks for an existing covering test or writes the missing one. Report known outstanding tests and their owner separately from the suite result. Source changes without a test edit can prompt the agent to check coverage, but they cannot prove a test is missing. Displaying that distinction adds no test run.
- **A mid-task switch carries forward the task.** Before moving to another chat, the current agent records a short local resume note with the branch, tier, agreed behavior or approved plan reference, current edits, checks run, tests or review still owed, and next step. That note is separate from the baton-generated handoff so another verify cannot overwrite it. The next agent opens the same checkout and reads the note and current diff. A Tier 2 approval from chat can travel in that note. A switch between tasks needs only the preset change.
- **Solo Tier 3 can reach review-ready with one agent.** The proposed policy lets the developer supply the independent review, or switch to a paired preset for review of the existing branch. Where changed rules require tests written independently of the implementation, the developer can author those tests from the approved rule text or hand that step to a separate agent. Record the reviewer, reviewed commit, and disposition of findings. Keep this as a workflow requirement, with the existing `merge` command continuing to enforce full verification on the branch tip. A local preset or a green test run does not supply review evidence.
- **Unavailable delegates remain visible.** In a paired preset, preserve the existing Gatekeeper fallback and report who owns the next step. If you choose to switch to solo, retain any outstanding test or review work. Scout and diagnosis can return to the interactive agent. Independent checks retain the policy above.

## Implementation phases and tests

Implement the phases in order on one feature branch, using the existing single-builder process for this change. Each phase has tests named below so changes to scripts, rules, and status can be reviewed together.

| Phase | Implementation | Tests |
|---|---|---|
| **1. Add preset resolution and CLI** | Add the shared resolver and `npm run workflow`. Define the six presets, selection precedence, Git-ignored local storage, and status output. Scope reads and writes to the checkout root. Make reset safe to repeat. Retain compatibility with legacy blueprints and keep the workflow skill available after tailoring. | Add `tests/test_workflow.py` for all six presets, legacy and missing-mode blueprints, override precedence, invalid input, malformed preferences, reset, and two independent checkouts. Assert that selection changes only the ignored preference and leaves tracked rules and handoff files intact. Extend `test_blueprint_schema.py` and `test_tailor_skill.py` for defaults and skill retention. |
| **2. Route commands through the resolver** | Update baton verification, `sync:status`, the Claude session context, scout, review, and the direct `agy:build` and `agy:qa` entry points. In solo, scout and review direct the task to the interactive workflow, and explicitly headless build and QA commands report that the selected preset disables them. Keep paired dispatch and `--no-gatekeeper` behavior compatible. Preserve the hook’s no-launch behavior and its same-content verification reuse. | Extend `test_e2e_baton_flow.py`, `test_scout.py`, `test_review.py`, `test_node_scripts.py`, and `test_claude_hooks.py`. Use the Antigravity stub to prove zero launches for all three solo presets, including missing tests and eligible failures. Verify `codex-agy` dispatches the intended jobs, `classic` and `agy-build` preserve their existing behavior, and hooks still avoid repeat verification. |
| **3. Migrate rules and publish the mode guide** | Move agent-neutral instructions into shared guidance and make role-dependent instructions conditional on the preset. Preserve tiers, mockup checks, rule IDs, approvals, E2E and build triggers, learning guidance, worktree ownership, and local merge policy. Update the workflow skill, README, handbook, and agent entry points. Document how a developer performs the independent solo review or switches to paired review. | Extend `test_root_rules.py` and `test_docs_integrity.py` for shared entry points, preset-aware role instructions, valid links, and paired defaults. Check every directive moved from `CLAUDE.md` and `GEMINI.md` against its destination so the migration preserves the rules. |
| **4. Exercise handoff and completion behavior** | Add the local resume-note convention and expose known test debt with its effective owner in status or the baton handoff. Keep resume notes and the workflow preference separate from resettable baton state. Register verification routes for the new workflow code and tests. Walk through a Tier 2 mid-task switch and a Tier 3 branch that moves from solo implementation to paired review. | Extend `test_workflow.py`, `test_sync_schema.py`, `test_baton_verify_config.py`, and `test_e2e_baton_flow.py` to cover `classic` → solo with outstanding work, solo → paired review, reset to blueprint default, preservation of local resume notes, and verification status distinct from test debt. Reuse `test_baton_fast.py` to check that merge still requires full verification on the branch tip. |

### Release checks

Run the phases through `npm run verify:agent`, then run the Tier 3 verification required by the repo. Exercise the switcher in isolated test checkouts, with stubs for automated dispatch checks. Manually confirm one session startup per agent where available, using the same checkout before and after a switch. Run any configured E2E and build checks, request one review, address and verify findings, then run `npm run verify:agent -- --full` on the final committed tip before merging into local `main`.
