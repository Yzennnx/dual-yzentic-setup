# Project Blueprint & Dynamic Repo Tailoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a project blueprint manifest and dynamic tailoring engine that guides developers upon cloning to customize their tech stack, soft-delete unneeded skills into an archive, tailor domain rules, and initialize the living roadmap.

**Architecture:** A root configuration manifest (`project-blueprint.json`) defines project archetypes, active/archived skills, and stack choices. A standalone Node engine (`scripts/skills-manager.mjs` and `scripts/init-project.mjs`) deterministically partitions `.agents/skills/` vs `.agents/skills-archive/`, tailors `docs/rules/`, and resets `docs/PLAN.md`. Agent contracts in `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` trigger an onboarding dialogue on Turn 1 if the blueprint is uninitialized.

**Tech Stack:** Node.js (ES Modules, standard `fs`, `path`, `readline`), Python 3 (`unittest`), Markdown schemas.

**Spec:** [`docs/specs/2026-10-08-project-blueprint-dynamic-tailoring-design.md`](2026-10-08-project-blueprint-dynamic-tailoring-design.md)

## Global Constraints

- Zero third-party runtime dependencies: All Node scripts must use native Node.js standard libraries (`node:fs`, `node:path`, `node:readline`).
- 100% reversible skill archival: Skills are never permanently deleted; they are moved between `.agents/skills/` and `.agents/skills-archive/`.
- All paths and symbols in markdown files and tests MUST use clickable Markdown links formatted with the `file://` scheme.
- All Python tests must execute cleanly via `python3 -m unittest discover tests`.
- Zero secret exposure: No sensitive data or environment variables written to disk or logs.

## Review Focus

1. **Non-interactive / CI safety:** If `init-project.mjs` is run without TTY in automated environments or tests, it must not hang on `readline`; it must respect `--preset` and `--non-interactive` flags.
2. **Archived skill preservation:** Moving skills between `.agents/skills/` and `.agents/skills-archive/` must never lose nested files, scripts, or examples.
3. **Existing test suite resilience:** `test_skills_structure.py` must account for skills residing in either `.agents/skills/` or `.agents/skills-archive/` so test discovery does not fail when skills are archived.
4. **Invalid archetype fallback:** Passing an unknown archetype name must fail gracefully with exit code 1 and list available archetypes.
5. **Circuit breaker & sync integrity:** Project initialization must reset `.agents/sync/handoff.json` to clean `idle` status without corrupting the baton schema.

---

### Task 1: Blueprint Schema & Manifest Initialization

**Files:**
- Create: `project-blueprint.json`
- Test: `tests/test_blueprint_schema.py`

**Interfaces:**
- Consumes: None (root configuration)
- Produces: `project-blueprint.json` with status `uninitialized`, project metadata, and 4 archetypes (`fullstack-web`, `ai-agent-app`, `frontend-dashboard`, `minimal-hackathon`).

- [x] **Step 1: Write the failing test**

```python
# tests/test_blueprint_schema.py
import unittest
import json
from pathlib import Path

class TestBlueprintSchema(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.blueprint_file = self.root / "project-blueprint.json"

    def test_blueprint_file_exists_and_valid(self):
        self.assertTrue(self.blueprint_file.exists(), "project-blueprint.json must exist")
        data = json.loads(self.blueprint_file.read_text(encoding="utf-8"))
        self.assertIn("status", data)
        self.assertIn(data["status"], ["uninitialized", "initialized"])
        self.assertIn("project", data)
        self.assertIn("archetypes", data)
        for expected in ["fullstack-web", "ai-agent-app", "frontend-dashboard", "minimal-hackathon"]:
            self.assertIn(expected, data["archetypes"])
            self.assertIn("keep_skills", data["archetypes"][expected])
            self.assertIn("rules_preset", data["archetypes"][expected])
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_blueprint_schema.py`
Expected: FAIL (`AssertionError: project-blueprint.json must exist`)

- [x] **Step 3: Implement `project-blueprint.json`**

Create `project-blueprint.json` at repo root with the schema and archetype definitions from the spec.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_blueprint_schema.py`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add project-blueprint.json tests/test_blueprint_schema.py
git commit -m "feat(blueprint): add project blueprint manifest and schema test"
```

---

### Task 2: Skills Manager Engine & Reversible Archiving

**Files:**
- Create: `scripts/skills-manager.mjs`
- Modify: `tests/test_skills_structure.py:24-36`
- Modify: `package.json:6-10`
- Test: `tests/test_skills_manager.py`

**Interfaces:**
- Consumes: `project-blueprint.json` (archetype `keep_skills`)
- Produces: `enableSkill(name)`, `disableSkill(name)`, `listSkills()`, `syncSkillsToArchetype(archetype)`

- [x] **Step 1: Write the failing test**

```python
# tests/test_skills_manager.py
import unittest
import subprocess
import json
from pathlib import Path

class TestSkillsManager(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.skills_dir = self.root / ".agents" / "skills"
        self.archive_dir = self.root / ".agents" / "skills-archive"

    def test_skills_manager_list_command(self):
        res = subprocess.run(["node", "scripts/skills-manager.mjs", "list", "--json"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertIn("active", data)
        self.assertIn("archived", data)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_skills_manager.py`
Expected: FAIL (Cannot find module `scripts/skills-manager.mjs`)

- [x] **Step 3: Implement `scripts/skills-manager.mjs` and update `tests/test_skills_structure.py`**

Implement `enableSkill`, `disableSkill`, `listSkills`, and `syncSkillsToArchetype` in `scripts/skills-manager.mjs`.
Add scripts to `package.json`:
- `"skill:list": "node scripts/skills-manager.mjs list"`
- `"skill:enable": "node scripts/skills-manager.mjs enable"`
- `"skill:disable": "node scripts/skills-manager.mjs disable"`
- `"skill:sync": "node scripts/skills-manager.mjs sync"`

Update `tests/test_skills_structure.py` so total domain skill count is calculated across `.agents/skills` plus `.agents/skills-archive`.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_skills_manager.py tests/test_skills_structure.py`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add scripts/skills-manager.mjs package.json tests/test_skills_manager.py tests/test_skills_structure.py
git commit -m "feat(skills): add skills manager with reversible archival engine"
```

---

### Task 3: Project Tailoring Engine (`scripts/init-project.mjs`)

**Files:**
- Create: `scripts/init-project.mjs`
- Modify: `package.json:6-10`
- Test: `tests/test_project_init.py`

**Interfaces:**
- Consumes: `project-blueprint.json`, `scripts/skills-manager.mjs`, `docs/rules/`, `docs/PLAN.md`
- Produces: `initProject({ preset, name, description, dev1, dev2 })`, resets sync bus, marks blueprint `initialized`.

- [x] **Step 1: Write the failing test**

```python
# tests/test_project_init.py
import unittest
import subprocess
import json
import shutil
from pathlib import Path

class TestProjectInit(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent

    def test_non_interactive_init_execution(self):
        # Run init in dry-run or targeted test mode
        cmd = [
            "node", "scripts/init-project.mjs",
            "--preset", "minimal-hackathon",
            "--name", "test-demo-app",
            "--desc", "Test Hackathon Project",
            "--dev1", "Alice",
            "--dev2", "Bob",
            "--non-interactive"
        ]
        res = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"init-project failed: {res.stderr}")
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_project_init.py`
Expected: FAIL (Cannot find module `scripts/init-project.mjs`)

- [x] **Step 3: Implement `scripts/init-project.mjs`**

Implement project tailoring logic:
- Parse CLI arguments (`--preset`, `--name`, `--desc`, `--dev1`, `--dev2`, `--non-interactive`).
- Interactive fallback using `node:readline` if run in TTY without args.
- Archive unselected skills via `syncSkillsToArchetype`.
- Customize `docs/rules/frontend.md` and `docs/rules/backend.md`.
- Generate clean-slate `docs/PLAN.md`.
- Reset `.agents/sync/handoff.json` to `idle` and `.agents/sync/handoff.md`.
- Update `package.json` name and description.
- Set `project-blueprint.json` status to `initialized`.
- Add `"init:project": "node scripts/init-project.mjs"` to `package.json`.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_project_init.py`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add scripts/init-project.mjs package.json tests/test_project_init.py
git commit -m "feat(init): add interactive and scripted project tailoring wizard"
```

---

### Task 4: Agent First-Turn Gate & Documentation Integration

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `GEMINI.md`
- Modify: `docs/ai/agent-handbook.md`
- Test: `tests/test_rules_integrity.py`

**Interfaces:**
- Consumes: `project-blueprint.json`
- Produces: Updated behavioral contracts directing agents to verify blueprint status on Turn 1.

- [x] **Step 1: Write the failing test**

Add assertions in `tests/test_rules_integrity.py` verifying that `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, and `docs/ai/agent-handbook.md` contain references to `project-blueprint.json` and the `npm run init:project` command.

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_rules_integrity.py`
Expected: FAIL

- [x] **Step 3: Update agent instruction files**

- Add Section in `AGENTS.md`: "Fresh Project Intake Gate"
- Update `CLAUDE.md` and `GEMINI.md` with instructions to detect `uninitialized` blueprint and prompt the user.
- Update `docs/ai/agent-handbook.md` Section 1 ("Initial Session Orientation") to include blueprint inspection.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_rules_integrity.py`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add AGENTS.md CLAUDE.md GEMINI.md docs/ai/agent-handbook.md tests/test_rules_integrity.py
git commit -m "docs(agents): add fresh clone intake gate across agent contracts"
```

---

### Task 5: End-to-End Verification & Documentation

**Files:**
- Create: `tests/test_e2e_project_blueprint.py`
- Modify: `README.md`
- Test: Full regression suite (`python3 -m unittest discover tests`)

**Interfaces:**
- Consumes: Complete project blueprint, skills manager, and init scripts.
- Produces: Passing E2E test simulating a fresh clone, archetype customization, skill restoration, and roadmap reset.

- [x] **Step 1: Write the E2E simulation test**

Author `tests/test_e2e_project_blueprint.py` simulating:
1. Blueprint initialization check.
2. Running `init-project.mjs` with `--preset fullstack-web`.
3. Verifying unneeded skills are moved to `.agents/skills-archive/`.
4. Restoring an archived skill using `node scripts/skills-manager.mjs enable <skill>`.
5. Verifying `docs/PLAN.md` has clean starter tasks.

- [x] **Step 2: Run test to verify behavior**

Run: `python3 -m unittest tests/test_e2e_project_blueprint.py`
Expected: PASS

- [x] **Step 3: Update `README.md`**

Add "Starting a New Project / Fresh Clone Setup" section explaining `npm run init:project` and `npm run skill:enable`.

- [x] **Step 4: Run full regression test suite**

Run: `python3 -m unittest discover tests`
Expected: 100% tests passing (all ~37 tests green).

- [x] **Step 5: Commit**

```bash
git add tests/test_e2e_project_blueprint.py README.md
git commit -m "feat(docs): add e2e blueprint verification and update README quickstart"
```
