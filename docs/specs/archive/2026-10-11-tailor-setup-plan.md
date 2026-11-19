# Spec-Driven Setup Tailoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `tailor-setup` skill and an `npm run tailor` script that tailor skills, roadmap, package metadata, and baton test commands from a manifest the agent derives from a brainstormed spec.

**Architecture:** The agent writes a manifest into the `project` block of `project-blueprint.json`. `scripts/tailor.mjs` validates it fully, then applies it using a root-aware `skills-manager.mjs` and a roadmap renderer extracted from `init-project.mjs`. `baton.mjs` reads `project.verify` once the blueprint is initialized. Prose rewriting and scaffolding are instructions in the skill, not code.

**Tech Stack:** Node 22 ES modules, standard library only (no new dependencies). Tests are Python `unittest` driving the scripts through `subprocess`.

**Spec:** [`docs/specs/2026-10-11-tailor-setup-design.md`](2026-10-11-tailor-setup-design.md)

## Global Constraints

- No new npm dependencies.
- `npm run init:project` and every existing test keep passing. Existing exported function signatures stay call-compatible: new parameters are optional and trailing.
- A manifest that fails validation changes nothing on disk.
- `status: "initialized"` is the last write `tailor` makes.
- Always-kept skills, exactly: `tailor-setup`, `fast-track`, `caveman`, `ponytail`.
- Priorities, exactly: `P0`, `P1`, `P2`. Owners, exactly: `dev1`, `dev2`. `archetype` must be `"custom"`.
- `docs/PLAN.md` must contain these headings: `Mission & Hackathon Objective`, `Current Sprint Focus`, `P0: Must-Have for Demo`, `P1: High Impact Polish`, `P2: Post-Hackathon Stretch`, `Rules for Adding Features`.
- Per `CLAUDE.md`, do not run `npm test`, `pytest`, or `unittest discover` directly. Run one test file with `npm run verify:agent -- --tier 2 --scope tests/<file>.py` and the full suite with `npm run verify:agent -- --tier 3`.
- Each failing baton run increments a turn counter that trips at 5; a passing run resets it. If it trips, run `npm run sync:reset`.
- The baton rewrites `.agents/sync/handoff.json` on every run. Include it in each commit.
- New tests import the fixture helper as `from tests import tailor_fixture`, which resolves under both the scoped and the full baton run.
- New tests never mutate the real repo. They build a fixture repo in a temp directory and pass it with `--root` or `{ root }`.

## Review Focus

1. **Unparseable blueprint or missing `project` block.** `tailor` exits 1 with a one-line message naming `project-blueprint.json`, not a stack trace. Test in Task 4.
2. **Duplicate or always-kept names in `skills`.** Accepted and de-duplicated; no error, no double move. Test in Task 3 (validation) and Task 4 (apply).
3. **Skill names that are not plain directory names** (`../x`, `_staging`, empty string). Reported as unknown; nothing moves. Test in Task 1.
4. **Manifest written but `tailor` not yet run.** The baton keeps its current commands until `status` is `initialized`. Test in Task 5.
5. **Multi-line or padded roadmap text.** A `title` or `description` containing newlines renders on one line, so the task list stays valid Markdown. Test in Task 2.

---

## File Structure

| File | Responsibility |
| :--- | :--- |
| `scripts/skills-manager.mjs` (modify) | Skill moves. Gains `{ root }` options and `syncSkillsToList`. |
| `scripts/roadmap.mjs` (create) | Renders `docs/PLAN.md` text from project info and a task list. Pure, no file I/O. |
| `scripts/init-project.mjs` (modify) | Uses `roadmap.mjs`; keeps its six placeholder tasks as data. |
| `scripts/install-hooks.mjs` (modify) | `installHooks` gains `{ root }`. |
| `scripts/tailor.mjs` (create) | Manifest validation, change-set computation, apply, CLI. |
| `scripts/baton.mjs` (modify) | Reads `project.verify`; `resolveTestExecution` accepts it. |
| `.agents/skills/tailor-setup/SKILL.md` (create) | The agent-facing workflow. |
| `tests/tailor_fixture.py` (create) | Builds the temp fixture repo; shared by the new tests. |
| `tests/test_skills_sync_list.py`, `tests/test_roadmap.py`, `tests/test_tailor_validation.py`, `tests/test_tailor_apply.py`, `tests/test_baton_verify_config.py`, `tests/test_tailor_skill.py` (create) | One test file per task. |

---

### Task 1: Root-aware skills manager and `syncSkillsToList`

**Files:**
- Modify: `scripts/skills-manager.mjs`
- Create: `tests/tailor_fixture.py`
- Test: `tests/test_skills_sync_list.py`

**Interfaces:**
- Produces (Node): `listSkills({ root } = {})`, `enableSkill(name, { root } = {})`, `disableSkill(name, { root } = {})`, `syncSkillsToList(names, { root } = {}) -> { active_count, archived_count, disabled: string[], enabled: string[] }`. `root` defaults to the repo root. `syncSkillsToArchetype(archetypeName)` keeps its signature and its return shape `{ archetype, active_count, archived_count, disabled, enabled }`.
- Produces (Python): `tailor_fixture.make_repo(tmp: Path, project: dict | None = None, status: str = "uninitialized") -> Path` and `tailor_fixture.run_node(code: str) -> subprocess.CompletedProcess`, plus constants `SCRIPTS: Path` (the real `scripts/` directory) and `VALID_PROJECT: dict`.

- [ ] **Step 1: Write the fixture helper `tests/tailor_fixture.py`**

`make_repo` creates, under `tmp`:
- `.agents/skills/<name>/SKILL.md` for `tailor-setup`, `fast-track`, `caveman`, `ponytail`, `alpha`, `beta`, each with `name`/`description` frontmatter; plus an empty `.agents/skills/_staging/`.
- `.agents/skills-archive/gamma/SKILL.md`.
- `.agents/sync/handoff.json` containing `{}` and `.agents/sync/handoff.md`.
- `docs/PLAN.md` containing `ORIGINAL PLAN`, and `docs/specs/demo-design.md`.
- `package.json` containing `{"name": "template", "description": "template", "scripts": {"tailor": "node scripts/tailor.mjs"}}`.
- `project-blueprint.json` containing `{"status": status, "project": project or VALID_PROJECT, "archetypes": {}}`.

```python
VALID_PROJECT = {
    "name": "AI Flow Canvas",
    "description": "Visual canvas for chaining AI steps",
    "archetype": "custom",
    "source_spec": "docs/specs/demo-design.md",
    "stack": {"runtime": "Python 3.12 CLI"},
    "team": {"dev1": {"name": "Steve", "role": "Fullstack"}, "dev2": {"name": "Bob"}},
    "skills": ["alpha", "gamma"],
    "verify": {"test": "npm test", "test_scoped": "npm test -- {scope}", "build": "npm run build"},
    "roadmap": [
        {"id": "1.1", "title": "Canvas shell", "priority": "P0", "owner": "dev1", "description": "Drag and drop nodes."},
        {"id": "2.1", "title": "Seed flows", "priority": "P1", "owner": "dev2", "description": "Three demo flows."},
    ],
}
```

`run_node(code)` runs `node --input-type=module -e code` with `cwd` set to the real repo root, as `tests/test_baton_runner.py` does, so tests import with `./scripts/…`. Tests pass the fixture path into the code as a JSON-encoded string.

- [ ] **Step 2: Write the failing tests in `tests/test_skills_sync_list.py`**

Each test builds a fixture with `tempfile.TemporaryDirectory()` and calls `syncSkillsToList` via `run_node`, printing the result as JSON.

```python
def test_archives_unlisted_and_restores_listed(self):
    # names = ["alpha", "gamma", "caveman"]
    # active dirs afterwards (excluding _staging): {"alpha", "gamma", "caveman"}
    # archive dirs afterwards: {"beta", "tailor-setup", "fast-track", "ponytail"}
    # result["enabled"] == ["gamma"]; "beta" in result["disabled"]
    # result["active_count"] == 3; result["archived_count"] == 4

def test_unknown_name_moves_nothing(self):
    # names = ["alpha", "nope"] -> non-zero exit, stderr contains "nope"
    # active and archive directory listings are identical to before the call

def test_rejects_non_directory_names(self):
    # for bad in ["../alpha", "_staging", ""]: names = [bad] -> non-zero exit, nothing moved

def test_duplicates_are_harmless(self):
    # names = ["alpha", "alpha"] -> exit 0, "alpha" still active, active_count == 1

def test_list_skills_honours_root(self):
    # listSkills({ root }) -> active excludes "_staging", archived == ["gamma"]
```

- [ ] **Step 3: Run to verify they fail**

Run: `npm run verify:agent -- --tier 2 --scope tests/test_skills_sync_list.py`
Expected: FAIL, `syncSkillsToList` is not exported.

- [ ] **Step 4: Implement in `scripts/skills-manager.mjs`**

- Replace the module-level `SKILLS_DIR` / `ARCHIVE_DIR` uses inside `ensureDirs`, `listSkills`, `enableSkill`, `disableSkill` with paths derived from an optional `{ root = REPO_ROOT }` argument.
- Add `syncSkillsToList(names, { root = REPO_ROOT } = {})`. De-duplicate `names`. A name is known only if it matches `/^[a-z0-9][a-z0-9-]*$/` and exists in the active or archive directory. Collect every unknown name and throw `Error("Unknown skills: a, b")` before any move. `active_count` is the size of the de-duplicated list.
- Reimplement `syncSkillsToArchetype` as a lookup of `keep_skills` followed by `syncSkillsToList`. It must not throw on a `keep_skills` entry that exists nowhere (today it ignores such entries), so filter `keep_skills` to known names before calling, and keep `active_count` equal to `keep_skills.length` as today.

- [ ] **Step 5: Run to verify they pass, then the existing skills tests**

Run: `npm run verify:agent -- --tier 2 --scope tests/test_skills_sync_list.py`, then `--scope tests/test_skills_manager.py`
Expected: PASS for both.

- [ ] **Step 6: Commit**

```bash
git add scripts/skills-manager.mjs tests/tailor_fixture.py tests/test_skills_sync_list.py .agents/sync/handoff.json
git commit -m "feat(skills): add root-aware explicit-list skill sync"
```

---

### Task 2: Extract the roadmap renderer

**Files:**
- Create: `scripts/roadmap.mjs`
- Modify: `scripts/init-project.mjs:26-113` (remove `generateRoadmap`), `:152-160` (call site)
- Test: `tests/test_roadmap.py`

**Interfaces:**
- Produces: `generateRoadmap({ name, desc, dev1, dev2, preset, tasks, batonPath }) -> string`, where `tasks` is `Array<{ id, title, priority: 'P0'|'P1'|'P2', owner: string, description }>` and `owner` is already a display name. `batonPath` is the absolute path used in the Sync Protocol link.

- [ ] **Step 1: Write the failing tests in `tests/test_roadmap.py`**

Call `generateRoadmap` through `tailor_fixture.run_node` with `name="Demo"`, `dev1="Steve"`, `dev2="Bob"`, `preset="custom"`, and the tasks given.

```python
def test_groups_tasks_under_priority_headings(self):
    # tasks: one P0 (id 1.1, title "Canvas shell", owner "Steve"), one P1 (id 2.1, title "Seed flows", owner "Bob")
    # "- [ ] **Task 1.1: Canvas shell**" appears after "## P0: Must-Have for Demo" and before "## P1: High Impact Polish"
    # "- [ ] **Task 2.1: Seed flows**" appears after "## P1: High Impact Polish" and before "## P2: Post-Hackathon Stretch"
    # "  - **Owner:** Steve", "  - **Priority:** P0", "  - **Status:** Backlog" all present

def test_empty_priority_keeps_heading(self):
    # same tasks -> text after "## P2: Post-Hackathon Stretch" contains "None yet."

def test_contains_all_required_sections(self):
    # every heading listed in Global Constraints is present

def test_multiline_text_collapses_to_one_line(self):
    # title "Canvas\nshell", description "  Drag\n\nand drop.  "
    # output contains "**Task 1.1: Canvas shell**" and "  - **Description:** Drag and drop."
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm run verify:agent -- --tier 2 --scope tests/test_roadmap.py`
Expected: FAIL, `scripts/roadmap.mjs` not found.

- [ ] **Step 3: Implement `scripts/roadmap.mjs` and switch `init-project.mjs` to it**

- Move the template text from `init-project.mjs` unchanged, except: the three priority sections are rendered from `tasks`; the P2 heading becomes `## P2: Post-Hackathon Stretch`; a priority with no tasks renders `None yet.` under its heading.
- Each task renders in the existing four-bullet shape (`Priority`, `Owner`, `Status: Backlog`, `Description`). Collapse any whitespace run in `title` and `description` to a single space and trim.
- In `init-project.mjs`, keep the six existing placeholder tasks as a local `defaultTasks(dev1, dev2)` array with the same titles, priorities, owners, and descriptions, and pass it in. Pass `batonPath: path.resolve(REPO_ROOT, 'scripts', 'baton.mjs')`.

- [ ] **Step 4: Run to verify they pass, then the existing init tests**

Run: `npm run verify:agent -- --tier 2 --scope tests/test_roadmap.py`, then `--scope tests/test_project_init.py`
Expected: PASS for both.

- [ ] **Step 5: Commit**

```bash
git add scripts/roadmap.mjs scripts/init-project.mjs tests/test_roadmap.py .agents/sync/handoff.json
git commit -m "refactor(init): extract task-list roadmap renderer"
```

---

### Task 3: Manifest validation

**Files:**
- Create: `scripts/tailor.mjs`
- Test: `tests/test_tailor_validation.py`

**Interfaces:**
- Consumes: `listSkills({ root })` from Task 1.
- Produces: `ALWAYS_KEPT_SKILLS: string[]` and `validateManifest(blueprint, { root }) -> string[]`. An empty array means valid. Every problem string starts with the offending field path: `project`, `project.name`, `project.description`, `project.archetype`, `project.source_spec`, `project.stack`, `project.team.dev1.name`, `project.team.dev2.name`, `project.skills`, `project.verify.test`, `project.verify.test_scoped`, `project.roadmap`, or `project.roadmap[<index>].<field>`.

- [ ] **Step 1: Write the failing tests in `tests/test_tailor_validation.py`**

A helper `problems(project)` builds a fixture, calls `validateManifest({ project }, { root })` via `run_node`, and returns the parsed list. Each case starts from a deep copy of `VALID_PROJECT`.

```python
def test_valid_manifest_has_no_problems(self):          # problems(VALID_PROJECT) == []

def test_each_rule_reports_its_field(self):
    cases = [
        (lambda p: p.update(name=""),                         "project.name"),
        (lambda p: p.update(description="  "),                "project.description"),
        (lambda p: p.update(archetype="fullstack-web"),       "project.archetype"),
        (lambda p: p.update(source_spec="docs/specs/no.md"),  "project.source_spec"),
        (lambda p: p.update(source_spec="../outside.md"),     "project.source_spec"),
        (lambda p: p.update(stack=[]),                        "project.stack"),
        (lambda p: p["team"]["dev2"].update(name=""),         "project.team.dev2.name"),
        (lambda p: p.update(skills="alpha"),                  "project.skills"),
        (lambda p: p.update(skills=["alpha", "nope"]),        "project.skills"),
        (lambda p: p["verify"].pop("test"),                   "project.verify.test"),
        (lambda p: p["verify"].update(test_scoped="npm test"),"project.verify.test_scoped"),
        (lambda p: p.update(roadmap=[]),                      "project.roadmap"),
        (lambda p: p["roadmap"][0].update(priority="P3"),     "project.roadmap[0].priority"),
        (lambda p: p["roadmap"][1].update(owner="Bob"),       "project.roadmap[1].owner"),
        (lambda p: p["roadmap"][1].update(id="1.1"),          "project.roadmap[1].id"),
        (lambda p: p["roadmap"][0].update(title=""),          "project.roadmap[0].title"),
    ]
    # for each: exactly one problem, and it starts with the expected path (use subTest)

def test_all_problems_reported_together(self):
    # name="" and roadmap[0].priority="P3" and skills=["nope"] -> len(problems) == 3

def test_missing_project_block(self):
    # validateManifest({}, { root }) -> one problem starting with "project"

def test_optional_fields_may_be_absent(self):
    # drop verify.test_scoped, verify.build, team.dev1.role -> []

def test_duplicate_and_always_kept_skills_are_valid(self):
    # skills = ["alpha", "alpha", "caveman"] -> []
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm run verify:agent -- --tier 2 --scope tests/test_tailor_validation.py`
Expected: FAIL, `scripts/tailor.mjs` not found.

- [ ] **Step 3: Implement `ALWAYS_KEPT_SKILLS` and `validateManifest` in `scripts/tailor.mjs`**

Follow the Field Rules table in spec Section 4. Decisions the table leaves open:
- Strings are valid only if non-empty after trimming.
- `source_spec` must be a relative path that resolves inside `root` and names an existing file.
- `stack` must be a plain object (not an array, not null).
- An unknown skill is one that fails the name pattern from Task 1 or is in neither skills directory under `root`. Report all unknown names in one `project.skills` problem.
- A duplicate task `id` is reported on the later task.
- If `project` is missing or not an object, return that single problem and stop.

- [ ] **Step 4: Run to verify they pass**

Run: `npm run verify:agent -- --tier 2 --scope tests/test_tailor_validation.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/tailor.mjs tests/test_tailor_validation.py .agents/sync/handoff.json
git commit -m "feat(tailor): validate the tailoring manifest"
```

---

### Task 4: Apply the manifest (`tailorProject` and the CLI)

**Files:**
- Modify: `scripts/tailor.mjs`, `scripts/install-hooks.mjs`, `package.json` (add `"tailor": "node scripts/tailor.mjs"`)
- Test: `tests/test_tailor_apply.py`

**Interfaces:**
- Consumes: `validateManifest`, `ALWAYS_KEPT_SKILLS` (Task 3); `syncSkillsToList`, `listSkills` (Task 1); `generateRoadmap` (Task 2).
- Produces: `tailorProject({ root, dryRun = false, force = false } = {}) -> { dryRun, changes: { archive: string[], restore: string[], write: string[] }, project }`; `installHooks({ root } = {})`; CLI `node scripts/tailor.mjs [--dry-run] [--force] [--root <path>]`.

CLI output, on success, is exactly these lines followed by a status line (`[Tailor] Dry run: nothing written.` or `[Tailor] Project tailored.`), with `(none)` for an empty list:

```text
[Tailor] archive: beta
[Tailor] restore: gamma
[Tailor] write: docs/PLAN.md, package.json, .agents/sync/handoff.json, .agents/sync/handoff.md, project-blueprint.json
```

On failure it prints `[Tailor Error] <message>` to stderr, one validation problem per following line, and exits 1.

- [ ] **Step 1: Write the failing tests in `tests/test_tailor_apply.py`**

A helper `tailor(root, *flags)` runs `node <SCRIPTS>/tailor.mjs --root <root> *flags`. A helper `snapshot(root)` returns a dict of relative path to file bytes for every file under `root`.

```python
def test_applies_manifest(self):
    # exit 0
    # active skills == {"alpha", "gamma", "tailor-setup", "fast-track", "caveman", "ponytail"}; archive == {"beta"}
    # docs/PLAN.md contains "Task 1.1: Canvas shell", "**Owner:** Steve", "**Owner:** Bob", and not "ORIGINAL PLAN"
    # package.json name == "ai-flow-canvas", description == VALID_PROJECT["description"], scripts unchanged
    # handoff.json: task_id == "INIT-01", status == "idle", turn_count == 0
    # blueprint status == "initialized"; blueprint["project"] == VALID_PROJECT; "archetypes" key still present

def test_dry_run_writes_nothing(self):
    # before = snapshot(root); tailor(root, "--dry-run") exits 0; snapshot(root) == before
    # stdout contains "[Tailor] archive: beta", "[Tailor] restore: gamma", "Dry run"

def test_invalid_manifest_changes_nothing(self):
    # project with skills ["nope"] and roadmap[0].priority "P3"
    # exit 1; stderr contains "project.skills" and "project.roadmap[0].priority"; snapshot unchanged

def test_refuses_initialized_without_force(self):
    # make_repo(status="initialized"): exit 1, stderr mentions "--force", snapshot unchanged
    # with "--force": exit 0 and PLAN.md is regenerated

def test_unparseable_blueprint(self):
    # overwrite project-blueprint.json with "{not json": exit 1
    # stderr contains "project-blueprint.json" and does not contain "    at " (no stack trace)

def test_duplicate_skills_apply_once(self):
    # skills ["alpha", "alpha", "caveman"]: exit 0, "alpha" active, "gamma" stays archived

def test_no_git_dir_skips_hook(self):
    # fixture has no .git: exit 0 and <root>/.githooks does not exist
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm run verify:agent -- --tier 2 --scope tests/test_tailor_apply.py`
Expected: FAIL, the script produces no output and changes nothing.

- [ ] **Step 3: Implement `tailorProject`, the CLI, and `installHooks({ root })`**

Follow the ten-step order in spec Section 5.1. Decisions the spec leaves open:
- The change set is computed from `listSkills({ root })` against `skills ∪ ALWAYS_KEPT_SKILLS`, keeping only always-kept names that exist under `root`.
- Owners resolve through `team[owner].name` before rendering. `preset` is `"custom"`; `batonPath` is `<root>/scripts/baton.mjs`.
- The package name is slugified with the same expression `init-project.mjs` uses (`toLowerCase().replace(/[^a-z0-9_-]/g, '-')`). Only `name` and `description` change in `package.json`.
- The handoff files use the same shape `init-project.mjs` writes, with the summary `Project tailored (<name> - custom)`.
- JSON files are written with two-space indentation, as `init-project.mjs` does.
- `installHooks` takes `{ root = REPO_ROOT }` and runs its `git config` with `cwd: root`. `tailorProject` calls it only when `<root>/.git` exists.
- Guard the CLI entry with the same "run directly" check the other scripts use, so importing the module has no side effects.

- [ ] **Step 4: Run to verify they pass, then the existing hook tests**

Run: `npm run verify:agent -- --tier 2 --scope tests/test_tailor_apply.py`, then `--scope tests/test_hooks.py`
Expected: PASS for both.

- [ ] **Step 5: Commit**

```bash
git add scripts/tailor.mjs scripts/install-hooks.mjs package.json tests/test_tailor_apply.py .agents/sync/handoff.json
git commit -m "feat(tailor): apply the manifest via npm run tailor"
```

---

### Task 5: Baton reads `project.verify`

**Files:**
- Modify: `scripts/baton.mjs:123-141` (`resolveTestExecution`), `:214` (call site)
- Test: `tests/test_baton_verify_config.py`

**Interfaces:**
- Produces: `readVerifyConfig(blueprintPath = <repo>/project-blueprint.json) -> { test, test_scoped?, build? } | null` and `resolveTestExecution(tier, scope, verify = null) -> { command, isExpress }`.

- [ ] **Step 1: Write the failing tests in `tests/test_baton_verify_config.py`**

Use `tailor_fixture.run_node` to import from `./scripts/baton.mjs`. With `V = { test: "pnpm test", test_scoped: "pnpm vitest run {scope}" }`:

```python
def test_resolve_uses_verify_commands(self):
    # resolveTestExecution(3, null, V).command == "pnpm test"
    # resolveTestExecution(2, "src/a.test.ts", V).command == "pnpm vitest run src/a.test.ts"
    # resolveTestExecution(1, null, V) == { command: "git diff --stat", isExpress: true }

def test_resolve_falls_back_without_verify(self):
    # resolveTestExecution(3, null).command == "python3 -m unittest discover tests"
    # resolveTestExecution(2, "tests/x.py").command == "python3 -m unittest tests/x.py"
    # resolveTestExecution(2, "src/a.test.ts").command == "npm test -- src/a.test.ts"

def test_scope_without_scoped_command_falls_back(self):
    # resolveTestExecution(2, "src/a.test.ts", { test: "pnpm test" }).command == "npm test -- src/a.test.ts"

def test_read_verify_config(self):
    # fixture with status "initialized": readVerifyConfig(path) deep-equals VALID_PROJECT["verify"]
    # fixture with status "uninitialized": null
    # missing file: null
    # file containing "{not json": null
    # initialized but project.verify.test == "": null
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm run verify:agent -- --tier 2 --scope tests/test_baton_verify_config.py`
Expected: FAIL, `readVerifyConfig` is not exported.

- [ ] **Step 3: Implement in `scripts/baton.mjs`**

Add `readVerifyConfig`; extend `resolveTestExecution` per spec Section 5.4; in the `verify` command, pass `readVerifyConfig()` as the third argument. `{scope}` is replaced verbatim.

- [ ] **Step 4: Run to verify they pass, then the existing baton tests**

Run: `npm run verify:agent -- --tier 2 --scope tests/test_baton_verify_config.py`, then `--scope tests/test_baton_runner.py`
Expected: PASS for both.

- [ ] **Step 5: Commit**

```bash
git add scripts/baton.mjs tests/test_baton_verify_config.py .agents/sync/handoff.json
git commit -m "feat(baton): run the project's verify commands once initialized"
```

---

### Task 6: The `tailor-setup` skill and routing docs

**Files:**
- Create: `.agents/skills/tailor-setup/SKILL.md`
- Modify: `docs/ai/agent-handbook.md` (one row in the "Hackathon & Domain Skills" table), `AGENTS.md` (Gate 0), `docs/PLAN.md` (Task 0.2 status)
- Test: `tests/test_tailor_skill.py`

**Interfaces:**
- Consumes: the CLI from Task 4 and the manifest schema from spec Section 4.

- [ ] **Step 1: Write the failing tests in `tests/test_tailor_skill.py`**

```python
def test_skill_frontmatter(self):
    # .agents/skills/tailor-setup/SKILL.md exists; frontmatter has "name: tailor-setup", "description:", "version: 1.0.0"

def test_skill_covers_the_workflow(self):
    # body contains each of: "npm run tailor -- --dry-run", "npm run tailor", "npm run verify:agent",
    # "superpowers:brainstorming", "source_spec", "test_scoped", "--force",
    # "## Core Standards", "## Dos and Don'ts", "When to Read What",
    # and each of the four always-kept skill names

def test_routing_docs_mention_tailor(self):
    # docs/ai/agent-handbook.md contains "tailor-setup"
    # AGENTS.md contains "npm run tailor" and still contains "init:project"
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm run verify:agent -- --tier 2 --scope tests/test_tailor_skill.py`
Expected: FAIL, `SKILL.md` not found.

- [ ] **Step 3: Write `.agents/skills/tailor-setup/SKILL.md`**

Match the structure of `.agents/skills/fast-track/SKILL.md` (frontmatter, numbered sections, token-lean). Description: triggers on "tailor the setup", "set up the repo for this spec", "configure the workspace from the spec", and `/tailor-setup`. Sections, in this order, with content taken from the named spec sections:

1. **When to use / when not to** — spec Sections 1 and 9 (no spec yet: stop and use `superpowers:brainstorming`; already initialized: stop unless the developer asks for `--force`).
2. **The 8-step flow** — spec Section 3, verbatim in substance, including the approval pause after the dry run.
3. **The manifest** — the JSON example and Field Rules table from spec Section 4, and the always-kept list.
4. **Choosing skills** — include a skill only when a roadmap task needs it; read only `name` and `description` frontmatter while choosing, never whole skill bodies.
5. **Rewriting the rules and agent docs** — the table, the "not touched" list, and the fixed anchors from spec Section 6.
6. **Scaffolding** — spec Section 7.
7. **Errors** — the table from spec Section 9.

- [ ] **Step 4: Update the routing docs**

- `docs/ai/agent-handbook.md`: add a row `| **Tailoring the repo to a brainstormed spec at kickoff** | tailor-setup | Derives skills, roadmap, rules, scaffold, and verify commands from the project spec |`, linking the skill in the same `file://` style as the neighbouring rows.
- `AGENTS.md` Gate 0: after "or guide them to run `npm run init:project`", add that when a project spec already exists in `docs/specs/`, the agent uses the `tailor-setup` skill (`npm run tailor`) instead.
- `docs/PLAN.md`: mark Task 0.2 `[x]` with `Status: Done`.

- [ ] **Step 5: Run to verify they pass, then the full suite**

Run: `npm run verify:agent -- --tier 2 --scope tests/test_tailor_skill.py`
Expected: PASS.

Run: `npm run verify:agent -- --tier 3`
Expected: PASS. If the baton reports failures in tests this plan did not touch, check whether they also fail on `main` before changing anything, and report them rather than fixing them here.

- [ ] **Step 6: Commit**

```bash
git add .agents/skills/tailor-setup/SKILL.md docs/ai/agent-handbook.md AGENTS.md docs/PLAN.md tests/test_tailor_skill.py .agents/sync/handoff.json
git commit -m "feat(skills): add tailor-setup skill and routing"
```
