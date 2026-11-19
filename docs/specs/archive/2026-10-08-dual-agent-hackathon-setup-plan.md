# Dual-Agent Hackathon Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the dual-agent synchronization bus, baton coordinator script (`scripts/baton.mjs`), universal living roadmap (`docs/PLAN.md`), and tailored agent rule files (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`) in `dual-yzentic-setup`.

**Architecture:** Node.js-native file-based synchronization (`.agents/sync/handoff.json` and `handoff.md`) with a lightweight CLI runner (`scripts/baton.mjs` executed via `npm run verify:agent`). The runner enforces a 5-turn circuit breaker and isolates raw test output to prevent Claude Pro token exhaustion.

**Tech Stack:** Node.js (ESM), Bash, Markdown, Vitest/Pytest/Jest compatibility.

**Spec:** [`docs/specs/2026-10-08-dual-agent-hackathon-setup-design.md`](2026-10-08-dual-agent-hackathon-setup-design.md)

## Global Constraints

- Must run natively in Node.js (v18+) without requiring external daemons or heavy compilation chains.
- All file links across markdown files and scripts MUST use the clickable `file://` scheme.
- Zero raw test dumps or browser DOM spam returned to Claude's terminal; error outputs must be distilled to <= 25 lines.
- Maximum 5 turns per task cycle before triggering circuit breaker halting.
- All commands must be non-interactive.

## Review Focus

1. **Corrupted or Missing `handoff.json`:** If the JSON state file is missing or contains malformed JSON, `baton.mjs` must auto-heal by regenerating default state rather than crashing with unhandled exceptions.
2. **Circuit Breaker Ceiling (`turn_count >= 5`):** When the 5th attempt fails, the runner must exit with a non-zero code and display an explicit human intervention notice.
3. **Empty / No Tests Found:** If the underlying test runner finds no tests, the baton must report a warning rather than falsely declaring "all tests passed".
4. **Concurrent File Access:** Ensure state file writes use atomic write/rename patterns to avoid partial file reads.
5. **Path Normalization:** Work correctly across POSIX Linux/macOS and Windows path separators.

---

### Task 1: Initialize Synchronization Bus Schemas (`.agents/sync/`)

**Files:**
- Create: `.agents/sync/handoff.json`
- Create: `.agents/sync/handoff.md`
- Test: `tests/test_sync_schema.py`

**Interfaces:**
- Produces: Default JSON state and Markdown template consumed by `scripts/baton.mjs`.

- [x] **Step 1: Write the failing test for sync schemas**

Create `tests/test_sync_schema.py` validating that `.agents/sync/handoff.json` exists, is valid JSON, contains `version`, `status`, `active_agent`, `turn_count`, `max_turns`, and that `.agents/sync/handoff.md` exists with required headings.

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_sync_schema.py`
Expected: FAIL (files missing).

- [x] **Step 3: Create `.agents/sync/handoff.json` and `.agents/sync/handoff.md`**

Initialize `.agents/sync/handoff.json`:
```json
{
  "version": "1.0",
  "task_id": "INIT-00",
  "active_agent": "claude",
  "status": "idle",
  "turn_count": 0,
  "max_turns": 5,
  "last_updated": "2026-10-08T00:00:00.000Z",
  "summary": "Initial synchronization bus created",
  "files_modified": []
}
```
Initialize `.agents/sync/handoff.md` template matching Section 4 of the spec.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_sync_schema.py`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add .agents/sync/ tests/test_sync_schema.py
git commit -m "feat(sync): initialize handoff.json and handoff.md schema"
```

---

### Task 2: Implement Baton Coordinator Runner (`scripts/baton.mjs`)

**Files:**
- Create: `scripts/baton.mjs`
- Modify: `package.json`
- Test: `tests/test_baton_runner.py`

**Interfaces:**
- Consumes: `.agents/sync/handoff.json`
- Produces: CLI commands `npm run verify:agent`, `npm run sync:status`, `npm run sync:reset`.
- Exported functions (Node ESM):
  - `readSyncState(filePath?: string): SyncState`
  - `writeSyncState(state: SyncState, filePath?: string): void`
  - `checkCircuitBreaker(state: SyncState): boolean`
  - `distillDiagnostics(rawOutput: string): string`
  - `detectExecutionTier(modifiedFiles: string[]): number`
  - `resolveTestExecution(tier: number, scope?: string): { command: string, isExpress: boolean }`

- [x] **Step 1: Write failing unit tests for baton state, circuit breaker, and execution tiers**

In `tests/test_baton_runner.py`, add tests that verify:
1. `readSyncState()` loads state or auto-heals when missing.
2. `checkCircuitBreaker()` throws or halts when `turn_count >= 5`.
3. `distillDiagnostics()` truncates outputs longer than 25 lines and extracts error lines.
4. `detectExecutionTier()` returns `1` for cosmetic/markdown/CSS files, `2` for a single component/test file, and `3` for schema/multi-file changes.
5. CLI arguments `--tier 1`, `--tier 2 --scope <path>`, and `--tier 3` override auto-detection correctly.

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_baton_runner.py`
Expected: FAIL (script does not exist).

- [x] **Step 3: Implement `scripts/baton.mjs`**

Implement ESM Node script providing:
- CLI argument parsing (`verify`, `status`, `reset`, `--tier`, `--scope`).
- Git diff inspection for auto-detecting Tier 1 (fast-track), Tier 2 (scoped), or Tier 3 (full).
- Fast-track execution for Tier 1: runs syntax/sanity check, skips heavy test runners, sets status `verified` immediately.
- Scoped execution for Tier 2: runs only the specified/affected test file.
- Full execution for Tier 3: runs complete test suite.
- State management with atomic write to `handoff.json`.
- Output distillation capturing error diffs, maximum 25 lines.
- Updating `.agents/sync/handoff.json` and `.agents/sync/handoff.md`.

Add `scripts` to `package.json`:
```json
"scripts": {
  "verify:agent": "node scripts/baton.mjs verify",
  "sync:status": "node scripts/baton.mjs status",
  "sync:reset": "node scripts/baton.mjs reset"
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_baton_runner.py`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add scripts/baton.mjs package.json tests/test_baton_runner.py
git commit -m "feat(baton): implement scripts/baton.mjs with tiered execution lanes"
```

---

### Task 3: Initialize Universal Living Roadmap (`docs/PLAN.md`)

**Files:**
- Create: `docs/PLAN.md`
- Test: `tests/test_plan_integrity.py`

**Interfaces:**
- Produces: The living sync roadmap for Dev 1 and Dev 2.

- [x] **Step 1: Write failing test for `docs/PLAN.md`**

Create `tests/test_plan_integrity.py` asserting that `docs/PLAN.md` exists and contains required sections: "Mission & Hackathon Objective", "Current Sprint Focus", "P0: Must-Have for Demo", "P1: High Impact Polish", "P2: Post-Hackathon Stretch", and "Rules for Adding Features".

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_plan_integrity.py`
Expected: FAIL (`docs/PLAN.md` not found).

- [x] **Step 3: Create `docs/PLAN.md`**

Create `docs/PLAN.md` with:
- Frontmatter and goal declaration.
- Task items with Priority (`P0`, `P1`, `P2`), Owner (`Dev 1`, `Dev 2`), Status (`[ ] Backlog`, `[▶] In Progress`, `[x] Completed`), and link references.
- Instructions for adding new features mid-hackathon to prevent rogue uncoordinated work.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_plan_integrity.py`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add docs/PLAN.md tests/test_plan_integrity.py
git commit -m "docs(plan): initialize universal living roadmap docs/PLAN.md"
```

---

### Task 4: Tailor Agent Rule Contracts (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`)

**Files:**
- Modify: `CLAUDE.md`
- Modify: `GEMINI.md`
- Modify: `AGENTS.md`
- Modify: `docs/ai/agent-handbook.md`
- Test: `tests/test_rules_integrity.py`

**Interfaces:**
- Produces: Authoritative system prompts directing Claude Code to act as Builder and Antigravity to act as Gatekeeper.

- [x] **Step 1: Update rule tests in `tests/test_rules_integrity.py`**

Assert that:
1. `CLAUDE.md` explicitly forbids running raw test runners and directs to `npm run verify:agent`.
2. `GEMINI.md` contains the Gatekeeper role and log absorption directives.
3. `AGENTS.md` references `docs/PLAN.md` and `.agents/sync/`.
4. All Markdown links in `CLAUDE.md`, `GEMINI.md`, and `AGENTS.md` resolve to valid files.

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_rules_integrity.py`
Expected: FAIL (rules not updated).

- [x] **Step 3: Update `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, and `docs/ai/agent-handbook.md`**

- In `CLAUDE.md`: Detail the Builder persona, token defense with `/caveman` and `/ponytail`, and `npm run verify:agent`.
- In `GEMINI.md`: Detail the Gatekeeper persona, test suite execution, error distillation.
- In `AGENTS.md`: Update task tiering to reference the dual-agent baton workflow and `docs/PLAN.md`.
- In `docs/ai/agent-handbook.md`: Add the newly installed skills (`caveman`, `ponytail`, `ui-ux-pro-max`, `impeccable`, `archify`, `pitch-architect`, `demo-seed-data`) to the Skills Quick-Selection Guide.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_rules_integrity.py`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add CLAUDE.md GEMINI.md AGENTS.md docs/ai/agent-handbook.md tests/test_rules_integrity.py
git commit -m "chore(rules): update CLAUDE.md, GEMINI.md, AGENTS.md for dual-agent contracts"
```

---

### Task 5: End-to-End Baton Simulation & Full Regression Verification

**Files:**
- Create: `tests/test_e2e_baton_flow.py`
- Modify: `README.md`
- Test: Full test suite (`python3 -m unittest discover tests`)

**Interfaces:**
- Verifies the complete loop: Claude creates task -> Baton runs test -> Records result -> Returns proper code.

- [x] **Step 1: Write E2E simulation test**

In `tests/test_e2e_baton_flow.py`:
1. Simulate a passing test run: `npm run verify:agent` succeeds, status is updated to `verified`, exit code is 0.
2. Simulate a failing test run: `npm run verify:agent` catches failure, updates status to `verification_failed`, records diff in `handoff.md`, increments `turn_count`, exit code is 1.
3. Simulate circuit breaker: after 5 fails, halts with circuit breaker message.

- [x] **Step 2: Run E2E test and verify it passes**

Run: `python3 -m unittest tests/test_e2e_baton_flow.py`
Expected: PASS.

- [x] **Step 3: Update `README.md` with Hackathon Quickstart Guide**

Document:
- Dual-terminal workflow: left terminal `claude`, right terminal `agy`.
- How to trigger `npm run verify:agent`.
- How to update `docs/PLAN.md`.
- Quick cheat-sheet of skills (`/caveman`, `/ponytail`, `/impeccable polish`, `/archify`).

- [x] **Step 4: Run full test suite**

Run: `python3 -m unittest discover tests`
Expected: All tests PASS (exit code 0).

- [x] **Step 5: Commit**

```bash
git add README.md tests/test_e2e_baton_flow.py
git commit -m "test(e2e): add baton flow integration tests and hackathon README"
```
