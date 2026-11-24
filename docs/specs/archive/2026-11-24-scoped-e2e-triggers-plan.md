# Scoped E2E & Triggered Full E2E

## Goal and scope
Keep Tier 2 and Tier 3 branches fast by allowing `npm run verify:agent` to run a single scoped E2E spec (`--e2e-scope <path>`) when a user-facing or cross-app flow changes, while tracking merge drift and blast-radius changes so Full E2E (`npm run verify:agent -- --e2e`) is scheduled in [docs/PLAN.md](../../PLAN.md) when objective risk thresholds are met.

App-specific build commands and paths remain configured per project in `project-blueprint.json`.

## Behavior and rules
- **Blueprint config (`project.verify`):**
  - Optional `e2e_scoped`: command containing `{scope}` (validated in `scripts/tailor.mjs`).
  - Optional `e2e_blast_radius`: array of non-empty path prefixes that trigger a Full E2E task on merge (falls back to `project.risky_paths` when omitted).
- **Scoped E2E execution (`scripts/baton.mjs`):**
  - `--e2e-scope <path>` (or `npm_config_e2e_scope`) implies E2E and resolves `verify.e2e_scoped` with `{scope}` substituted, independent of unit-test `--scope` and `--full`.
  - `--e2e` without `--e2e-scope` runs `verify.e2e` and resets the Full E2E drift counters on pass.
- **Full E2E trigger tracking (`.agents/sync/e2e-state.json`):**
  - Preserved across `npm run sync:reset`.
  - On `npm run merge -- <branch>` (when `verify.e2e` is configured): increments `merges_since_full_e2e`, increments `tier3_since_full_e2e` if the merged branch touched Tier 3 paths, and sets `blast_radius_pending` if it touched `e2e_blast_radius` (or `risky_paths`).
  - `merge` and `sync:status` print `[Baton] Full E2E due (...)` when `blast_radius_pending`, `tier3_since_full_e2e >= 3`, or `merges_since_full_e2e >= 5` (noting if `docs/PLAN.md` already has an open `Full E2E verification` task).

## Acceptance and verification
- `python3 tests/run_parallel.py` passes with coverage in `tests/test_tailor_validation.py`, `tests/test_baton_verify_config.py`, `tests/test_e2e_baton_flow.py`, `tests/test_docs_integrity.py`, and `tests/test_plan_integrity.py`.

## Tasks
1. **Blueprint & Tailor validation** — validate `project.verify.e2e_scoped` and `project.verify.e2e_blast_radius` in `scripts/tailor.mjs`; test in `tests/test_tailor_validation.py`.
2. **Scoped E2E & trigger tracking** — implement `--e2e-scope`, `resolveE2eExecution`, and `e2e-state.json` tracking in `scripts/baton.mjs`; test in `tests/test_baton_verify_config.py` and `tests/test_e2e_baton_flow.py`.
3. **Workflow & policy docs** — update `AGENTS.md`, `docs/ai/workflows.md`, and `docs/PLAN.md`.
