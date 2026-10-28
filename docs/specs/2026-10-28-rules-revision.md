# Rules Revision: Feature Docs That Own Code

**Date:** 2026-10-28
**Status:** Approved by the developer in chat (four sections, each approved). Tooling and docs only; no project code.
**Scope:** this template. Projects started from it get the layout at kickoff. Existing projects (Luna) migrate later, on their own decision.

## Why

One long `docs/DESIGN.md` is too long to read (Luna's: 404 lines, ~17k tokens), so agents read all of it or none. Nothing keeps it current, so it drifts from the code. The old `docs/rules/` held generic stack standards (`frontend.md`, `backend.md`, `requirements.md`) that go stale and say nothing about the product. PLAN tasks name no feature, so agents search for files.

## Goal

The design lives in `docs/rules/`, split by feature. Each feature doc owns the code paths that implement it. Checks fail verify when code changes without its doc, when a new file has no owner, when an open PLAN task names no feature, or when a changed rule has no test citing it. An agent reads `invariants.md` plus one feature doc (~150 lines), not a monolith.

## 1. Layout and formats

```
docs/rules/
  README.md          mission, principles, and the feature map (generated table between markers)
  invariants.md      promises that must never break, numbered inv#1, inv#2, ...
  architecture.md    stack, apps, how they talk, data model, conventions, testing; owns cross-cutting files
  features/
    <feature>.md     one per feature
    _example.md      template only: a filled-in sample (files starting with _ are skipped by checks)
```

A feature doc:

```markdown
---
owns:
  - packages/shared/src/domain/session*.ts
  - apps/desktop/src/renderer/pages/Session*.tsx
---
# Sessions

## What the user sees
Plain words, 5-15 lines. No code names.

## Rules
- [sessions#1] A session has a target length between 10 and 240 minutes.
- [sessions#2] A break cannot be skipped.
- [sessions#3] (manual) The dialer is never blocked.

## How it works
Data flow, file by file: Start button -> SessionStart.tsx -> bridge -> main/session.ts -> db -> sync.

## Limits and out of scope
```

- `owns` is the only hand-kept field. A feature's tasks come from PLAN tags, its boards from the mockup maps (a board's target component matched against `owns`), its tests from test files citing `feature#N`.
- Rule IDs never change. A deleted rule leaves a gap; a new rule takes the next number. The ID prefix is the file name. `(manual)` marks a rule only a hand test can prove.
- `architecture.md` has `owns` too, for cross-cutting files (shared UI kit, theme, bridge, config).
- PLAN tags: `- [ ] Task 1.2 [auth]: ...`; a task may name several features, or `[arch]`.
- Size targets: README ~40 lines, invariants ~30, architecture ~100, a feature doc 40-120.
- `npm run rules:map` regenerates the README map table between `<!-- rules:map -->` and `<!-- /rules:map -->`: feature, doc, open/done task counts, boards, rules, rules with a test. `npm run rules:map -- <feature>` prints one feature: owns, files matched, tasks, boards, rules with their tests.

## 2. Checks (`scripts/rules-check.mjs`, `npm run rules:check`)

Run by the baton on every verify (after the mockup check) and summarised in one line at session start. Reads files and one `git diff`; no test runs. Skipped entirely while `docs/rules/features/` holds no doc other than `_*.md` (an uninitialized template).

Always (whole repo, fail verify):
1. Shape: each feature doc has `owns:` (list, may be empty) and the four sections; rule IDs are well formed, unique, prefix matches the file name.
2. Dead paths: every `owns` pattern matches at least one file.
3. Double owners: no file owned by two docs (features and architecture together).
4. PLAN tags: every open task names at least one existing feature or `[arch]`; done tasks exempt.
5. Dead rule links: a test cites a rule ID that does not exist.

Against the branch's change set (`main...HEAD` plus the working tree), fail verify:
6. Drift: a file owned by a feature changed, the feature doc did not. Passes when the doc changed, or a commit on the branch carries the trailer `Docs: no behaviour change (<feature>[, <feature>])`. Style files (`*.css`, `*.scss`) and test files do not count (looks are the mockup map's job).
7. New orphans: a new source file that no doc owns. Source = `rules.source` globs in the blueprint (minus test files and generated paths in `rules.ignore`).
8. Rule tests: a rule added or reworded on the branch with no test citing its ID (in a test name, or a `covers <feature>#<n>` comment). `(manual)` rules exempt.

Warnings only (session-start line): old orphans, and the count of rules without a test. Example: `rules: ok · 12 orphan files · 38 rules without a test`.

Messages name the file and the fix, for example `sessions.md may be stale: packages/shared/src/domain/session.ts changed (edit the doc, or add "Docs: no behaviour change (sessions)" to a commit)`.

Blueprint additions: `rules.source` (globs where code lives), `rules.ignore` (globs never owned: generated, vendored), `rules.tests` (globs of test files; default `**/*.test.*`, `**/*.spec.*`, `**/test_*.py`).

## 3. Rule tests written from the doc (Fix A and Fix B)

- Fix A, a design rule: every design that changes behaviour shows the exact new or changed rule text with its ID, and the developer's yes covers that text. The builder edits the doc first, then writes code to it.
- Fix B, tests from the doc, by an agent that has not written the code:
  - classic mode: when the baton launches the Gatekeeper, it passes the rules added or reworded on the branch (ID and text). Instruction: write one test per rule from the rule text, cite the ID, and if the code disagrees leave the test failing and report the mismatch; never bend a test to fit the code.
  - agy-build mode: a separate Antigravity job, `rule-tests`, runs before `build`. It sees only the doc diff (the changed rules) and the test layout, writes the tests citing each ID, and commits them. The `build` job then makes them pass. `npm run agy:build` runs `rule-tests` first when the plan's tasks change rules.

## 4. Kickoff (wayfinder, brainstorming, tailor-setup)

The template ships the skeleton above (README with placeholders and empty map markers, invariants with three example promises marked "replace", architecture with headings, `features/_example.md`). Deleted: `docs/rules/frontend.md`, `backend.md`, `requirements.md`, `blueprint/web-dev-rules/`, `tests/test_rules_integrity.py` (replaced by tests for the new checks).

Flow:
1. Blueprint `uninitialized`: `wayfinder` kickoff, as today.
2. Brainstorming writes the project design straight into `docs/rules/`: invariants, architecture, one full feature doc per feature (what the user sees, numbered rules, how it works, limits; `owns: []`). The developer reviews the `docs/rules/` diff as the spec. No separate `docs/specs/<project>-design.md`.
3. `tailor-setup` reads `docs/rules/` (manifest `source_rules: "docs/rules/README.md"` replaces `source_spec`). Roadmap tasks carry `features: [...]`; `npm run tailor` rejects a feature with no doc, writes PLAN lines with tags, and sets `rules.source`. Step 7 no longer rewrites stack rule files.
4. Scaffold: the generator's files go into `architecture.md`'s `owns`.
5. `npm run rules:check` passes (features own nothing yet, so nothing can drift).
6. A feature's first task adds its new files to that feature's `owns` (check 7 forces it).

`npm run init:project` (archetypes) is retired: it prints "Start with the wayfinder kickoff, then tailor-setup" and exits 1. The archetype code in `init-project.mjs`, `scaffolder.mjs`, the blueprint's `archetypes`, and their tests are removed. CLAUDE.md, AGENTS.md, GEMINI.md, `.cursorrules`, `docs/ai/*`, README and the tailor-setup skill point at `docs/rules/` instead of `DESIGN.md` and the old rule files; tests asserting the old anchors (`## Core Standards`, `When to Read What`) assert the new ones.

## 5. Migrating an existing project (not part of this change)

For a project that already has a `DESIGN.md` (Luna), a later, separate task: confirm `DESIGN.md` is current first; then move text (not rewrite) heading by heading into the new files, number the rules, assign every source file an owner, tag open PLAN tasks, and leave `DESIGN.md` as a 3-line pointer. A one-off script checks every `DESIGN.md` paragraph lands in some new file. Contradictions with the code are listed for the developer, not fixed silently. No test backfill: rule tests are linked the first time each rule is touched.

## Tasks

| # | Task | Tests |
|---|---|---|
| 1 | `scripts/rules-check.mjs` (checks 1-8, warnings), `scripts/rules-map.mjs` (README map, per-feature view), npm scripts, blueprint `rules.*` keys and schema, baton and session-context wiring, template skeleton in `docs/rules/` | `scripts/rules-check.test.mjs` (one case per check, plus the skip for an uninitialized template), `scripts/rules-map.test.mjs` |
| 2 | Rule tests from the doc: the Gatekeeper prompt carries changed rules (classic); the `rule-tests` job before `build` (agy-build) | `scripts/agy.test.mjs` (prompt carries rule ID and text; job order), a baton test for the rules passed to the Gatekeeper |
| 3 | Kickoff: brainstorming/tailor-setup write and read `docs/rules/`; `tailor.mjs`/`roadmap.mjs` feature tags and `source_rules`; `init:project` retired with archetype code; old rule files and `blueprint/web-dev-rules` deleted | tailor and roadmap tests updated; `test_project_init.py` asserts the retirement message; skills structure tests |
| 4 | References and docs: CLAUDE.md (a short "Rules" subsection: read `invariants.md` and the task's feature docs; Fix A), AGENTS.md, GEMINI.md, `.cursorrules`, `docs/ai/*`, README, the tailor-setup skill; anchor tests | `test_docs_integrity.py`, `test_root_rules.py` and the other anchor tests updated; `npm run verify:agent` |
