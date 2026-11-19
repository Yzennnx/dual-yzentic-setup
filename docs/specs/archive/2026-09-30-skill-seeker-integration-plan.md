# Skill Seeker Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest documentation websites, GitHub repositories, and technical PDFs into standardized, staged agent skills using Skill Seekers with zero root repository dependency bloat and automated compliance gates.

**Architecture:** Ephemeral `uvx skill-seekers` runner orchestrated via a Python wrapper script (`seek.py`), outputting into a safe staging directory (`_staging/`), with automated validation and promotion into the active catalog (`.agents/skills/<name>/`), updating handbook routing, tests, and IDE MCP configs.

**Tech Stack:** Python 3.12+, uv / uvx, unittest, Markdown, Git.

**Spec:** [`docs/specs/2026-09-30-skill-seeker-integration-design.md`](2026-09-30-skill-seeker-integration-design.md)

---

## Global Constraints

- All generated and edited Markdown documents MUST format file paths and symbols as clickable links using the `file://` scheme with forward slashes (`/`).
- No Python dependencies may be installed into the root repository or committed to git; `skill-seekers` is run ephemerally via `uvx`.
- Staged draft skills in `.agents/skills/_staging/` must remain untracked by git and must not be counted by active skill integrity tests.
- YAML frontmatter in all skill files must strictly include non-empty `name:` and `description:` keys between `---` delimiters.
- Every commit must follow semantic conventional commit conventions (`feat:`, `docs:`, `test:`, `fix:`).

---

## Review Focus

1. **Staging Directory Exclusion:** Ensure `_staging/` is never counted as an active domain skill by `tests/test_skills_structure.py`.
2. **Missing `uvx` Runtime Handling:** Ensure `seek.py` reports a helpful error with instructions if `uvx` is not in `PATH`.
3. **Skill Name Collision:** Ensure promoting a skill whose name already exists in `.agents/skills/` fails safely unless `--force` is provided.
4. **Malformed Frontmatter Extraction:** Ensure the validator checks that YAML delimiters `---` and `name:`/`description:` exist before promotion.
5. **Windows vs Linux Link Formatting:** Ensure all generated `file://` links normalize backslashes to forward slashes.

---

### Task 1: Staging Directory & Git Protection

**Files:**
- Create: `.agents/skills/_staging/.gitkeep`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `.agents/skills/_staging/` directory ready to receive draft skills while ignoring internal child directories from git tracking.

- [ ] **Step 1: Write gitignore rule for staging directory**

Add `.agents/skills/_staging/*` and `!.agents/skills/_staging/.gitkeep` to `.gitignore`.

- [ ] **Step 2: Create `.agents/skills/_staging/.gitkeep`**

Create empty file at `.agents/skills/_staging/.gitkeep`.

- [ ] **Step 3: Verify git ignore behavior**

Run: `mkdir -p .agents/skills/_staging/test-skill && touch .agents/skills/_staging/test-skill/SKILL.md && git status --porcelain`
Expected: Only `.gitignore` and `.agents/skills/_staging/.gitkeep` appear as modified/untracked; `test-skill/` is ignored.

- [ ] **Step 4: Clean up temporary test folder**

Run: `rm -rf .agents/skills/_staging/test-skill`

- [ ] **Step 5: Commit**

```bash
git add .gitignore .agents/skills/_staging/.gitkeep
git commit -m "chore(skills): add _staging directory and configure gitignore rules"
```

---

### Task 2: Automation & Validation Script (`scripts/seek.py`) and Unit Tests

**Files:**
- Create: `tests/test_seek_script.py`
- Create: `.agents/skills/skill-seeker/scripts/seek.py`

**Interfaces:**
- Produces: `validate_skill_directory(dir_path: Path) -> tuple[bool, list[str]]`
- Produces: `list_staged_skills(staging_dir: Path) -> list[str]`
- Produces: `promote_staged_skill(name: str, staging_dir: Path, target_dir: Path, force: bool = False) -> bool`
- Produces: CLI interface supporting `--url`, `--repo`, `--pdf`, `--name`, `--list-staged`, `--promote`, `--validate`

- [ ] **Step 1: Write the failing unit tests for `seek.py` validator and promotion logic**

Create `tests/test_seek_script.py` testing:
1. `validate_skill_directory` succeeds on valid `SKILL.md` with `name` and `description`.
2. `validate_skill_directory` fails when `SKILL.md` is missing or missing `description`.
3. `promote_staged_skill` moves directory from staging to target and checks collision.
4. `list_staged_skills` ignores `.gitkeep` and returns directory names.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_seek_script.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts'` or cannot find `seek`.

- [ ] **Step 3: Implement `seek.py`**

Create `.agents/skills/skill-seeker/scripts/seek.py` with:
- `validate_skill_directory(dir_path: Path) -> tuple[bool, list[str]]`
- `list_staged_skills(staging_dir: Path) -> list[str]`
- `promote_staged_skill(name: str, staging_dir: Path, target_dir: Path, force: bool = False) -> bool`
- Subprocess wrapper invoking `uvx --from skill-seekers skill-seekers ...`
- Argument parsing: `--url`, `--repo`, `--pdf`, `--name`, `--list-staged`, `--promote`, `--validate`, `--force`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests/test_seek_script.py`
Expected: PASS with 4 tests OK.

- [ ] **Step 5: Commit**

```bash
git add tests/test_seek_script.py .agents/skills/skill-seeker/scripts/seek.py
git commit -m "feat(skill-seeker): implement seek.py CLI orchestrator and validation tests"
```

---

### Task 3: Skill Definition (`skill-seeker/SKILL.md`) & Meta-Skill Bridges

**Files:**
- Create: `.agents/skills/skill-seeker/SKILL.md`
- Modify: `.agents/skills/find-skills/SKILL.md`

**Interfaces:**
- Produces: Complete procedural guide for autonomous agents to run `skill-seeker` during tasks.
- Produces: Fallback section in `find-skills` pointing directly to `skill-seeker`.

- [ ] **Step 1: Author `.agents/skills/skill-seeker/SKILL.md`**

Include YAML frontmatter:
```yaml
---
name: skill-seeker
description: Ingest documentation websites, GitHub repositories, and technical PDFs to automatically generate structured domain skills with AST parsing, code examples, and conflict detection. Use when encountering unfamiliar frameworks, private internal SDKs, bleeding-edge library updates, or when asked to create/seek a skill from documentation.
version: 1.0.0
---
```
Detail operational workflows:
- Scraping a doc URL into `_staging/`
- Analyzing a GitHub repo into `_staging/`
- Parsing a PDF into `_staging/`
- Running validation and promoting to `.agents/skills/`

- [ ] **Step 2: Update `.agents/skills/find-skills/SKILL.md`**

In Section *"When No Skills Are Found"*, add the automated fallback to `skill-seeker`:
```markdown
3. Suggest generating a skill from official docs using `skill-seeker`:
   `python .agents/skills/skill-seeker/scripts/seek.py --url <docs-url> --name <name>`
```

- [ ] **Step 3: Verify markdown formatting and link integrity**

Run: `python3 -m unittest tests/test_seek_script.py`

- [ ] **Step 4: Commit**

```bash
git add .agents/skills/skill-seeker/SKILL.md .agents/skills/find-skills/SKILL.md
git commit -m "docs(skills): add skill-seeker SKILL.md and integrate fallback in find-skills"
```

---

### Task 4: MCP Server Configuration & Architecture Documentation

**Files:**
- Modify: `docs/ai/architecture.md`
- Modify: `docs/ai/agent-handbook.md`

**Interfaces:**
- Produces: Documented MCP server configuration snippets for Claude Code, Cursor, Windsurf, and Antigravity.
- Produces: Updated domain skills routing table in `agent-handbook.md`.

- [ ] **Step 1: Update `docs/ai/architecture.md`**

Add Section *"Model Context Protocol (MCP) Integrations"*:
- Detail `skill-seekers` MCP server:
  - Command: `uvx skill-seekers mcp`
  - Integration steps for Claude Code CLI (`claude mcp add`) and Cursor/Antigravity (`mcp.json`).

- [ ] **Step 2: Update `docs/ai/agent-handbook.md`**

Add `skill-seeker` to the Domain & Tooling Skills table:
```markdown
| **On-demand documentation ingestion & skill synthesis** | [`skill-seeker`](../../.agents/skills/skill-seeker/SKILL.md) | Convert documentation sites, GitHub repos, and PDFs into staged, validated agent skills |
```

- [ ] **Step 3: Commit**

```bash
git add docs/ai/architecture.md docs/ai/agent-handbook.md
git commit -m "docs(ai): add skill-seeker to agent handbook and document MCP architecture"
```

---

### Task 5: Test Suite Updates & Repository Inventory Sync

**Files:**
- Modify: `tests/test_skills_structure.py`
- Modify: `AGENTS.md`
- Modify: `README.md`

**Interfaces:**
- Produces: Automated test coverage asserting 21 curated domain skills.
- Produces: Verification that `_staging/` is excluded from the active skill count.
- Produces: Synchronized inventory counts (21) across all root guides.

- [ ] **Step 1: Write failing test update in `tests/test_skills_structure.py`**

In `tests/test_skills_structure.py`:
- Update `len(skill_dirs)` assertion from 20 to 21.
- Add `"skill-seeker"` to `required_skills`.
- Ensure `skill_dirs = [p for p in self.skills_dir.iterdir() if p.is_dir() and p.name != "_staging"]` explicitly excludes `_staging`.
- Add test `test_staging_directory_is_excluded_from_active_catalog`.

- [ ] **Step 2: Run test to verify it passes with `skill-seeker` present**

Run: `python3 -m unittest tests/test_skills_structure.py`
Expected: PASS (21 skills asserted, `_staging` ignored).

- [ ] **Step 3: Update `AGENTS.md`**

Update skill counts from 20 to 21 in Section 5 (Skills & Documentation Routing).

- [ ] **Step 4: Update `README.md`**

Update skill counts from 20 to 21 in overview bullet and directory tree comment.

- [ ] **Step 5: Run full test suite**

Run: `python3 -m unittest discover tests -v`
Expected: All tests pass cleanly with exit code 0.

- [ ] **Step 6: Commit**

```bash
git add tests/test_skills_structure.py AGENTS.md README.md
git commit -m "feat(tests): update skills structure validation for 21 domain skills and staging exclusion"
```

---

### Task 6: Full Regression Verification & CLI Sanity Run

**Files:** None (Execution & validation only)

- [ ] **Step 1: Run CLI help check**

Run: `python3 .agents/skills/skill-seeker/scripts/seek.py --help`
Expected: Clean exit code 0 displaying all flags (`--url`, `--repo`, `--pdf`, `--name`, `--promote`, `--list-staged`).

- [ ] **Step 2: Run list-staged check**

Run: `python3 .agents/skills/skill-seeker/scripts/seek.py --list-staged`
Expected: Clean exit code 0 reporting "No staged skills found."

- [ ] **Step 3: Run git status verification**

Run: `git status`
Expected: Clean working tree, nothing uncommitted.
