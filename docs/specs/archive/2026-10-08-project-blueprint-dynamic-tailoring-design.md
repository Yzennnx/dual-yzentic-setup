# Design Spec: Project Blueprint & Dynamic Repo Tailoring

- **Date:** 2026-10-08
- **Status:** Draft / Pending Review
- **Repository:** [`dual-yzentic-setup`](../../../)
- **Target Context:** Fresh Clone Onboarding, Token Optimization & Domain Rules Customization

---

## 1. Executive Summary & Objective

This specification defines the architecture, file formats, and execution logic for a **Project Blueprint & Dynamic Repo Tailoring Subsystem**.

### Problem Statement
1. **Agent Context Clutter:** The repository houses 34+ skills across UI/UX, pitch design, diagrams, security, email templates, and MCP authoring. Loading all 34 skills into an agent's context window burns unnecessary input tokens on every turn.
2. **Fresh Clone Setup Friction:** When developers clone this template repository for a new project or hackathon, placeholder roadmap items (`Task 0.1`, `Task 1.1`), outdated commit state, and generic rules in [`docs/rules/`](../../rules/README.md) remain until manually cleaned up.
3. **Missing Proactive Onboarding:** Currently, neither Claude Code nor Antigravity checks if the project has just been cloned, leaving teams without a structured initialization flow.

### Proposed Solution
- **Declarative Blueprint (`project-blueprint.json`):** A root configuration file tracking initialization status, project metadata, team members (`Dev 1`, `Dev 2`), selected tech stack, and pre-configured archetype presets.
- **Reversible Skill Soft-Deletion:** Moves non-essential skills to [`.agents/skills-archive/`](../../../.agents/skills-archive/), keeping only the 8–12 skills required for the chosen archetype, with zero-friction restoration via `npm run skill:enable <skill>`.
- **Dynamic Rules & Roadmap Customization:** Rewrites [`docs/rules/`](../../rules/README.md) to reflect the project's actual frontend/backend stack and generates a fresh, clean-slate [`docs/PLAN.md`](../../PLAN.md).
- **Dual Interface:** An interactive Node CLI wizard (`npm run init:project`) combined with an Agent First-Turn Gate in [`AGENTS.md`](../../../AGENTS.md) that prompts the developer if the repo is uninitialized.

---

## 2. Blueprint Schema & Archetypes (`project-blueprint.json`)

The file [`project-blueprint.json`](../../../project-blueprint.json) lives at the workspace root:

```json
{
  "status": "uninitialized",
  "project": {
    "name": "dual-yzentic-setup",
    "description": "Dual-agent pair programming setup template",
    "archetype": "fullstack-web",
    "stack": {
      "frontend": "Next.js (App Router) + Tailwind CSS",
      "backend": "Node.js / Route Handlers",
      "database": "Supabase / PostgreSQL",
      "auth": "Supabase Auth"
    },
    "team": {
      "dev1": { "name": "Dev 1", "role": "Fullstack & AI" },
      "dev2": { "name": "Dev 2", "role": "Frontend & Design" }
    }
  },
  "archetypes": {
    "fullstack-web": {
      "name": "Full-Stack Web Application (Next.js / Vite + Backend)",
      "keep_skills": [
        "caveman", "ponytail", "ui-ux-pro-max", "impeccable",
        "archify", "webapp-testing", "owasp-security", "varlock",
        "pitch-architect", "demo-seed-data", "fast-track"
      ],
      "rules_preset": "fullstack-web"
    },
    "ai-agent-app": {
      "name": "AI Agent / LLM Pipeline (FastAPI / Node + Multi-Agent)",
      "keep_skills": [
        "caveman", "ponytail", "prompt-engineer", "agentic-eval",
        "varlock", "owasp-security", "pitch-architect", "demo-seed-data",
        "archify", "fast-track"
      ],
      "rules_preset": "ai-agent"
    },
    "frontend-dashboard": {
      "name": "Frontend Dashboard / SPA (Vite + React + Tailwind)",
      "keep_skills": [
        "caveman", "ponytail", "ui-ux-pro-max", "impeccable",
        "design-system", "slides", "banner-design", "demo-seed-data",
        "pitch-architect", "webapp-testing", "fast-track"
      ],
      "rules_preset": "frontend-dashboard"
    },
    "minimal-hackathon": {
      "name": "Ultra-Lean Hackathon Sprint (Core Essentials Only)",
      "keep_skills": [
        "caveman", "ponytail", "ui-ux-pro-max", "impeccable",
        "pitch-architect", "demo-seed-data", "fast-track"
      ],
      "rules_preset": "minimal"
    }
  }
}
```

---

## 3. Skill Management Engine (`scripts/skills-manager.mjs`)

To keep agent context lean without permanently losing any installed capabilities:

### Directory Conventions
- **Active Skills:** [`.agents/skills/<skill_name>/`](../../../.agents/skills/) — Agents scan only this directory.
- **Archived Skills:** [`.agents/skills-archive/<skill_name>/`](../../../.agents/skills-archive/) — Preserved offline on disk, omitted from agent discovery.

### CLI Commands (`package.json`)
1. `npm run skill:enable <skill-name>`: Moves `.agents/skills-archive/<name>` $\rightarrow$ `.agents/skills/<name>`.
2. `npm run skill:disable <skill-name>`: Moves `.agents/skills/<name>` $\rightarrow$ `.agents/skills-archive/<name>`.
3. `npm run skill:list`: Prints categorized list of active vs. archived skills.
4. `npm run skill:sync`: Synchronizes `.agents/skills/` against the archetype defined in `project-blueprint.json`.

---

## 4. Tailoring & Customization Logic (`scripts/init-project.mjs`)

When tailoring executes (either via CLI or agent trigger), the following transformations occur deterministically:

### A. Skill Soft-Delete
- Reads `keep_skills` for the chosen archetype from [`project-blueprint.json`](../../../project-blueprint.json).
- Moves every folder in [`.agents/skills/`](../../../.agents/skills/) not present in `keep_skills` to [`.agents/skills-archive/`](../../../.agents/skills-archive/).
- Leaves active skills untouched.

### B. Rules Configuration
- Updates [`docs/rules/frontend.md`](../../rules/frontend.md) and [`docs/rules/backend.md`](../../rules/backend.md) with specific framework, ORM, and styling standards matching the chosen stack.

### C. Roadmap Generation
- Generates a fresh [`docs/PLAN.md`](../../PLAN.md):
  - Injects project name, 1-line mission pitch, and sprint deadline.
  - Replaces old setup boilerplate with standard starter milestones:
    - `Task 1.1: Core Application Shell & Navigation` (Assigned to Dev 1)
    - `Task 1.2: Core Data Models & API Endpoints` (Assigned to Dev 2)
    - `Task 1.3: Hero Interactive Value Loop` (Assigned to Dev 1)

### D. Sync Bus Reset
- Resets [`.agents/sync/handoff.json`](../../../.agents/sync/handoff.json):
  ```json
  {
    "version": "1.0",
    "task_id": "INIT-01",
    "active_agent": "claude",
    "status": "idle",
    "turn_count": 0,
    "max_turns": 5,
    "summary": "Project initialized via project-blueprint",
    "files_modified": []
  }
  ```
- Resets [`.agents/sync/handoff.md`](../../../.agents/sync/handoff.md) to clean ready state.

### E. Package.json Metadata
- Updates `name` and `description` in [`package.json`](../../../package.json).

---

## 5. Dual Onboarding Interfaces

### 1. Interactive CLI Wizard
Command:
```bash
npm run init:project
```
- Interactive prompts built with native Node.js `readline` (no heavy third-party CLI dependencies).
- Supports flags for scripted non-interactive execution:
  ```bash
  node scripts/init-project.mjs --preset fullstack-web --name "my-app" --desc "AI Canvas" --dev1 "Steve" --dev2 "Partner"
  ```

### 2. Agent First-Turn Gate
- Governed in [`AGENTS.md`](../../../AGENTS.md) and [`docs/ai/agent-handbook.md`](../../ai/agent-handbook.md):
- On session start, both Claude and Antigravity inspect [`project-blueprint.json`](../../../project-blueprint.json).
- If `"status": "uninitialized"`:
  - Agent halts feature coding and prompts:
    > *"Welcome to your project! This repository has just been cloned and is currently uninitialized. Let's set up your project name, tech stack, and developer roles so we can customize your tools and roadmap."*
  - After user response, agent runs `node scripts/init-project.mjs` non-interactively with the user's choices.

---

## 6. Verification & Test Plan

1. **Unit Test for Skills Manager (`tests/test_skills_manager.py`):**
   - Verifies moving skills to `.agents/skills-archive/` and back to `.agents/skills/`.
   - Validates that active skills lock matches filesystem.
2. **Unit Test for Project Initializer (`tests/test_project_init.py`):**
   - Verifies `--preset` flag non-interactive execution.
   - Validates that `docs/PLAN.md`, `package.json`, and `.agents/sync/handoff.json` update correctly.
   - Verifies status changes from `uninitialized` to `initialized`.
3. **Regression Test Suite:**
   - Ensures all existing 33 tests continue to pass after skill soft-delete.
