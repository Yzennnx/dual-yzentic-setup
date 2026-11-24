# Universal Living Roadmap & Feature Plan

> **For the developer and the AI agents:** This document is the single source of truth for the project. No feature is implemented without an entry here. Keep it updated after every completed task.

- **Project:** dual-yzentic-setup (template; no project started yet)
- **Last Synchronized:** 2026-10-11
- **Verification:** [`scripts/baton.mjs`](../scripts/baton.mjs) via `npm run verify:agent`

---

## Mission & Objective

Provide a single-developer workflow in which Claude Code plans and writes source code, and Antigravity scouts the codebase, writes and diagnoses tests, and reviews branches. Starting a real project replaces this file: `npm run tailor` or `npm run init:project` regenerates it.

---

## Rules for Adding Features

1. **Log it first:** Add every new idea below with a Priority and the status `[ ] Backlog` before any code is written. Link tasks created from an approved spec to that spec.
2. **Priorities:**
   - **`P0` (Must-Have):** Required for the core user journey to work.
   - **`P1` (Should-Have):** Improves the core journey: polish, seed data, secondary flows.
   - **`P2` (Later):** Parked until P0 and P1 are done.
3. **One task at a time:** Finish, verify with `npm run verify:agent`, and commit a task before starting the next.
4. **Archive after completion:** When the final linked task closes, move the spec and update every roadmap link in the same commit. Follow the [spec lifecycle](specs/README.md).
5. **Full E2E triggers:** Log `- [ ] **Task: Full E2E verification**` when Baton reports `[Baton] Full E2E due` (blast-radius path merged, `3` Tier 3 merges, or `5` total merges since the last full `--e2e` pass), when a milestone completes, or before a release build.

---

## Current Focus

Active milestone: **Workflow setup complete; waiting for a project to start**

---

## P0: Must-Have

- [x] **Task 0.1: Dual-Agent Sync Bus & Baton**
  - **Priority:** P0
  - **Status:** Done
  - **Description:** `scripts/baton.mjs`, `.agents/sync/`, and the Builder and Gatekeeper rule files.

- [x] **Task 0.2: Spec-Driven Setup Tailoring (`tailor-setup` skill)**
  - **Priority:** P0
  - **Status:** Done
  - **Description:** Skill plus `npm run tailor` that tailors skills, roadmap, rules, scaffold, and baton commands from a brainstormed spec. Design: [`2026-10-11-tailor-setup-design.md`](specs/archive/2026-10-11-tailor-setup-design.md).

- [x] **Task 0.3: Antigravity Delegation (Scout, Gatekeeper, Review)**
  - **Priority:** P0
  - **Status:** Done
  - **Description:** Scripts launch Antigravity headlessly to scout the codebase, write and diagnose tests on `npm run verify:agent`, and review branches. Design: [`2026-10-11-antigravity-delegation-design.md`](specs/archive/2026-10-11-antigravity-delegation-design.md).

- [x] **Task 0.4: Token Budget Rules & Sonnet Builder Agent**
  - **Priority:** P0
  - **Status:** Done
  - **Description:** Process sized by tier, plan tasks delegated to the `builder` agent on Sonnet, and sessions that chain up to 3 Tier 1/2 tasks in one area, with a handoff in `.agents/sync/session.md`. Rules: [`CLAUDE.md`](../CLAUDE.md) section 3.

- [x] **Task 0.5: Workflow Remediation**
  - **Priority:** P0
  - **Status:** Done
  - **Description:** Fixes from the 2026-10-11 audit: a gate that blocks, tests isolated from the real repo, portable links, one consistent rule set, enforcement hooks, single-developer framing. Plan: [`2026-10-11-workflow-remediation-plan.md`](specs/archive/2026-10-11-workflow-remediation-plan.md).

- [x] **Task 0.6: Faster Verification**
  - **Priority:** P0
  - **Status:** Done
  - **Description:** Opt-in end-to-end runs, no repeated run on commit, diagnosis only when needed, a fast model for scout and diagnosis, and lighter process rules. Plan: [`2026-10-12-faster-verification-plan.md`](specs/archive/2026-10-12-faster-verification-plan.md).

- [x] **Task 0.7: Switchable Agent Workflows**
  - **Priority:** P0
  - **Status:** Done
  - **Description:** Add checkout-local solo and paired presets, shared role resolution, and handoff guidance. Plan: [`2026-11-19-workflow-switcher-plan.md`](specs/archive/2026-11-19-workflow-switcher-plan.md).

- [x] **Task 0.8: Active and Archived Specs**
  - **Priority:** P0
  - **Status:** Done
  - **Description:** Link approved feature tasks to specs, organize active and archived documents, and select the matching spec for review.
  - **Spec:** [Active and archived specs](specs/archive/2026-11-19-spec-lifecycle-plan.md)

- [x] **Task 0.9: Scoped E2E & Triggered Full E2E**
  - **Priority:** P0
  - **Status:** Done
  - **Description:** Add `--e2e-scope`, `project.verify.e2e_scoped` / `e2e_blast_radius`, and Full E2E drift/blast-radius tracking across `merge` and `sync:status`.
  - **Spec:** [Scoped E2E & triggered full E2E](specs/archive/2026-11-24-scoped-e2e-triggers-plan.md)

- [ ] **Task 1.1: Core Application Shell & Navigation**
  - **Priority:** P0
  - **Status:** Backlog
  - **Description:** Placeholder. Primary app shell, responsive container, and header navigation.

- [ ] **Task 1.2: Core Data Models & API Endpoints**
  - **Priority:** P0
  - **Status:** Backlog
  - **Description:** Placeholder. Core data models and backend routes for the primary application flow.

- [ ] **Task 1.3: Primary User Journey**
  - **Priority:** P0
  - **Status:** Backlog
  - **Description:** Placeholder. The main action a user takes, end to end.

---

## P1: Should-Have

- [ ] **Task 2.1: Realistic Seed Data**
  - **Priority:** P1
  - **Status:** Backlog
  - **Description:** Placeholder. Populate realistic records and state using `demo-seed-data`.

- [ ] **Task 2.2: UI Contrast, Responsive Refinement & Polish**
  - **Priority:** P1
  - **Status:** Backlog
  - **Description:** Placeholder. Typography, motion, and WCAG contrast using `ui-ux-pro-max` and `impeccable`.

---

## P2: Later

- [ ] **Task 3.1: Secondary Workflows**
  - **Priority:** P2
  - **Status:** Backlog
  - **Description:** Placeholder. Advanced configuration and secondary settings.
