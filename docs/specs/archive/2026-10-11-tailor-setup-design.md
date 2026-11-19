# Design Spec: Spec-Driven Setup Tailoring (`tailor-setup`)

- **Date:** 2026-10-11
- **Status:** Draft / Pending Review
- **Repository:** [`dual-yzentic-setup`](../../../)
- **Builds on:** [`2026-10-08-project-blueprint-dynamic-tailoring-design.md`](2026-10-08-project-blueprint-dynamic-tailoring-design.md)

---

## 1. Objective

### Problem Statement
`npm run init:project` tailors the repository from one of four fixed archetypes. Real projects rarely match a preset, so the active skills, the roadmap in [`docs/PLAN.md`](../../PLAN.md), the rules in [`docs/rules/`](../../rules/README.md), the starter scaffold, and the baton's test command all stay generic after initialization.

### Intended Outcome
At project kickoff, after the team has brainstormed the project into a design spec in [`docs/specs/`](../), one skill turns that spec into a setup that fits the project: the right skills active, a roadmap of the real features, rules for the real stack, a scaffold from the stack's own generator, and a baton that runs the project's own tests.

### Success Criteria
1. A project whose stack matches no archetype can be fully tailored from its spec without hand-editing setup files.
2. The developer sees and approves what will change before anything changes.
3. A bad manifest changes nothing.
4. `npm run init:project` and its tests keep working unchanged.

### Out of Scope
- Re-tailoring mid-project as the plan evolves. `tailor` refuses to run on an initialized blueprint without `--force`.
- Feeding lessons from a finished project back into the template.
- New archetypes or changes to [`scripts/scaffolder.mjs`](../../../scripts/scaffolder.mjs).

---

## 2. Approach: Agent Decides, Script Applies

Judgement and mechanics are split:

- **The agent** reads the spec and writes one artefact, the manifest (Section 4). It also rewrites prose and runs the scaffold generator, since neither can be templated for arbitrary stacks.
- **A script**, `npm run tailor`, applies the manifest deterministically: skill archival, roadmap rendering, package metadata, sync bus reset.

Rejected alternatives: a prompt-only skill (non-deterministic, token-heavy, untestable) and more composable archetypes (still preset-driven).

---

## 3. Flow

1. The team brainstorms the project into a design spec in `docs/specs/`.
2. The developer invokes the `tailor-setup` skill.
3. The agent reads the spec and the skill catalogue (`npm run skill:list -- --json`, plus the `name` and `description` frontmatter of each skill, active and archived). If no project spec exists, the skill stops and directs the developer to `superpowers:brainstorming`.
4. The agent writes the manifest into `project-blueprint.json`, leaving `status` untouched.
5. The agent runs `npm run tailor -- --dry-run` and shows the developer a summary: skills kept and archived, stack, team, roadmap tasks, verify commands. The developer approves or corrects.
6. The agent runs `npm run tailor`.
7. The agent rewrites the prose files (Section 6) and scaffolds `src/` (Section 7).
8. The agent runs `npm run verify:agent`, which now uses the project's commands.

`init:project` remains the quick archetype path. Both paths set `status: "initialized"`, so Gate 0 in [`AGENTS.md`](../../../AGENTS.md) passes either way.

---

## 4. The Manifest

The manifest extends the existing `project` block of [`project-blueprint.json`](../../../project-blueprint.json). The `archetypes` block is not modified.

```json
"project": {
  "name": "ai-flow-canvas",
  "description": "One-sentence mission",
  "archetype": "custom",
  "source_spec": "docs/specs/2026-10-11-ai-flow-canvas-design.md",
  "stack": { "frontend": "…", "backend": "…", "database": "…", "auth": "…" },
  "team": {
    "dev1": { "name": "Steve", "role": "Fullstack & AI" },
    "dev2": { "name": "Partner", "role": "Frontend & Design" }
  },
  "skills": ["webapp-testing", "owasp-security", "varlock"],
  "verify": {
    "test": "npm test",
    "test_scoped": "npm test -- {scope}",
    "build": "npm run build"
  },
  "roadmap": [
    { "id": "1.1", "title": "…", "priority": "P0", "owner": "dev1", "description": "…" }
  ]
}
```

### Field Rules

| Field | Required | Rule |
| :--- | :--- | :--- |
| `name`, `description` | yes | Non-empty strings. |
| `archetype` | yes | Must be `"custom"` for this path. |
| `source_spec` | yes | Repo-relative path to an existing file. |
| `stack` | yes | Object of free-form strings. Keys are not fixed; a CLI tool may have only `runtime`. Not read by the script; it informs prose rewriting. |
| `team.dev1`, `team.dev2` | yes | Each has a non-empty `name`; `role` optional. |
| `skills` | yes | Array of names, each existing in `.agents/skills/` or `.agents/skills-archive/`. |
| `verify.test` | yes | Shell command for the full suite. |
| `verify.test_scoped` | no | Shell command containing `{scope}`. |
| `verify.build` | no | Shell command for the production build. Recorded for agents; the baton does not run it in this iteration. |
| `roadmap` | yes | At least one task. `id` unique; `priority` one of `P0`, `P1`, `P2`; `owner` one of `dev1`, `dev2`; `title` and `description` non-empty. |

### Always-Kept Skills
`tailor-setup`, `fast-track`, `caveman`, and `ponytail` stay active whether or not they are listed, because [`AGENTS.md`](../../../AGENTS.md) and [`CLAUDE.md`](../../../CLAUDE.md) reference them directly.

---

## 5. Script Changes

### 5.1 `scripts/tailor.mjs` (new)
Exports `validateManifest(blueprint, { root })`, returning an array of problem strings, and `tailorProject({ root, dryRun, force })`.

`tailorProject` runs in this order:
1. Read the blueprint. Refuse if `status === "initialized"` and `force` is false.
2. Validate. If any problems exist, throw with all of them listed. Nothing has been written.
3. Compute the change set: skills to archive, skills to restore, files to write.
4. If `dryRun`, return the change set and stop.
5. Sync skills to `skills` plus the always-kept set.
6. Render `docs/PLAN.md` from `roadmap` and `team`.
7. Write `name` and `description` to `package.json`, slugifying the name as `init-project.mjs` does.
8. Reset the sync bus (`handoff.json`, `handoff.md`) with task id `INIT-01`.
9. Install the git hook via `installHooks({ root })`, only when `root` contains a `.git` directory.
10. Set `status: "initialized"` and write the blueprint. This is last, so a failure part-way leaves the blueprint uninitialized and the command re-runnable.

CLI: `node scripts/tailor.mjs [--dry-run] [--force] [--root <path>]`. It prints the change set, exits 0 on success and 1 with the problem list on failure. `package.json` gains `"tailor": "node scripts/tailor.mjs"`.

All paths resolve from a `root` parameter defaulting to the repo root, so tests can run against a temp fixture repo. The existing scripts hardcode the repo root, so `listSkills`, `enableSkill`, `disableSkill`, and `installHooks` each gain an optional `{ root }` argument with the same default.

### 5.2 `scripts/skills-manager.mjs`
Add `syncSkillsToList(names)`: archive every active skill not in `names`, restore every archived skill in `names`, and return `{ active_count, archived_count, disabled, enabled }`. It throws before moving anything if a name exists in neither directory. A name is only recognised if it matches `^[a-z0-9][a-z0-9-]*$`, which excludes `_staging` and path traversal. `syncSkillsToArchetype` becomes a wrapper that looks up `keep_skills` and calls it, preserving its current return shape.

### 5.3 `scripts/roadmap.mjs` (new, extracted)
`generateRoadmap` moves out of [`scripts/init-project.mjs`](../../../scripts/init-project.mjs) and takes a `tasks` array instead of hardcoding tasks. `init-project.mjs` passes its current six placeholder tasks, so its output is unchanged. Tasks are grouped under the existing `P0` / `P1` / `P2` headings, owners resolve to team names, and every task starts as `[ ]` with `Status: Backlog`. The P2 heading is `## P2: Post-Hackathon Stretch`, replacing the wizard's current `## P2: Post-Hackathon / Stretch Goals`, which the plan-integrity test does not accept. A priority with no tasks keeps its heading with "None yet." beneath it, because [`tests/test_plan_integrity.py`](../../../tests/test_plan_integrity.py) requires the sections.

### 5.4 `scripts/baton.mjs`
`resolveTestExecution(tier, scope)` gains a third parameter, `verify`, read from `project.verify` in the blueprint by the caller:
- Tier 1 is unchanged.
- With a scope and `verify.test_scoped`: substitute `{scope}`.
- Without a scope and with `verify.test`: use it.
- Otherwise: today's behaviour, unchanged.

A missing or unparseable blueprint is treated as no `verify`, and so is a blueprint whose `status` is not `"initialized"`: the agent writes the manifest before `tailor` runs, and the baton must not switch commands until it has.

---

## 6. Prose Rewriting (Agent)

The skill names exactly which files to touch and which text is fixed.

| File | Rewritten |
| :--- | :--- |
| `docs/rules/frontend.md`, `docs/rules/backend.md` | Overview, `## Core Standards`, and `## Dos and Don'ts` bodies, for the real stack. A file with no counterpart in the project is reduced to those three headings with a short "not applicable to this project" note under each. |
| `docs/rules/README.md` | The stack sentence and the "When to Read What" table. |
| `docs/ai/agent-handbook.md` | The skills quick-selection table, listing only active skills. |
| `CLAUDE.md` | The "Frontend Polish" bullet, removed when the project has no frontend. |

Not touched: `docs/rules/requirements.md`, `AGENTS.md`, `GEMINI.md`, `.cursorrules`, `docs/ai/workflows.md`, `docs/ai/architecture.md`. They hold process rules, not stack rules.

**Fixed anchors.** These strings are asserted by the existing tests and must survive any rewrite: `## Core Standards` and `## Dos and Don'ts` in each rule file; `When to Read What` in the rules README; `Builder`, `verify:agent`, `caveman`, `ponytail`, and `project-blueprint.json` in `CLAUDE.md`; `project-blueprint.json` in the handbook. Rule files keep the existing token-lean style: principles, checklists, and Dos/Don'ts tables rather than long code blocks.

---

## 7. Scaffolding (Agent)

The skill instructs the agent to run the stack's official generator (for example `create-next-app`, `npm create vite`, `uv init`) non-interactively, targeting `src/` or the repo root where the generator requires it, and to record the exact command in the handoff summary. If `src/` already contains files, the agent skips scaffolding and reports that it did. If the generator would overwrite the template's `package.json`, the agent merges the template's `scripts` entries back in.

---

## 8. The Skill (`.agents/skills/tailor-setup/SKILL.md`)

Frontmatter matches the existing local skills (`name`, `description`, `version`). The description triggers on phrases such as "tailor the setup", "set up the repo for this spec", and `/tailor-setup`. The body covers, in order: when to use it and when not to (no spec yet, or already initialized); the eight-step flow from Section 3; the manifest schema and field rules; guidance for choosing skills (include a skill only when a roadmap task needs it); the prose-rewriting table and fixed anchors; the scaffolding rules; and the error table below.

`docs/ai/agent-handbook.md` gains one row for the skill, and `AGENTS.md` Gate 0 mentions `npm run tailor` alongside `npm run init:project`.

---

## 9. Error Handling

| Condition | Behaviour |
| :--- | :--- |
| Unknown skill, missing required field, bad `owner` or `priority`, duplicate task `id`, missing `source_spec` file | Exit 1 listing every problem. Nothing written. |
| `test_scoped` without `{scope}` | Validation problem, as above. |
| Blueprint already `initialized` | Refuse unless `--force`, so a re-run cannot overwrite a `PLAN.md` with checked-off tasks. |
| No spec in `docs/specs/` | The skill stops and directs the developer to brainstorming. |
| Failure after skills have moved | Blueprint stays `uninitialized`. Skill moves are reversible with `npm run skill:enable`, and re-running `tailor` converges. |

---

## 10. Testing

Python `unittest` in `tests/`, driving the Node scripts through `subprocess` as the existing tests do. Unlike the existing end-to-end tests, which mutate the real repo and restore it, each case runs against a small fixture repo built in a temp directory and passed with `--root`:

- **Validation:** each row of the field rules table has a failing case; all problems are reported together; a failing manifest leaves the tree byte-identical.
- **Skill sync:** explicit list archives the rest; restores from the archive; always-kept skills survive an empty list; an unknown name moves nothing.
- **Roadmap:** tasks render under the right priority with resolved owner names; an empty priority keeps its heading; the wizard's output is unchanged after the extraction.
- **Dry run:** writes nothing and reports the change set.
- **Initialized guard:** refuses without `--force`, proceeds with it.
- **Baton:** uses `verify.test` and `verify.test_scoped` when present; falls back when absent or when the blueprint is unreadable.
- **Skill structure:** `tailor-setup/SKILL.md` exists with valid frontmatter, covered by the existing skills-structure test.

### Known Consequence
Once `verify.test` points at the project's commands, the template's own tests in `tests/` no longer run on commit. This is intended: they test the template, not the application. They remain in the repo and can be run directly with `python -m unittest discover tests`. The skills-structure test already accepts archived skills, and the fixed anchors in Section 6 and the retained roadmap headings in Section 5.3 exist so that the docs and plan integrity tests still pass in a tailored project.

---

## Amendments (2026-10-11)

Changed by Tasks 1 to 3 of [`2026-10-11-workflow-remediation-plan.md`](2026-10-11-workflow-remediation-plan.md). Where this section and the text above differ, this section is what the code does.

- **Single developer.** The manifest has no `team` block and roadmap tasks have no `owner`. An optional `project.developer` string names the developer; without it the roadmap says "the developer".
- **Roadmap sections.** `Mission & Objective`, `Rules for Adding Features`, `Current Focus`, `P0: Must-Have`, `P1: Should-Have`, `P2: Later`. Tasks carry `Priority`, `Status`, and `Description`.
- **Links.** Generated and committed files use relative links. The roadmap's baton link is `../scripts/baton.mjs`.
- **Archetypes.** `minimal-hackathon` is now `minimal`, and `pitch-architect` is no longer kept by any archetype.
