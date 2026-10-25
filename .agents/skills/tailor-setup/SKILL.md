---
name: tailor-setup
description: Tailors the whole repository setup (active skills, docs/PLAN.md roadmap, docs/rules, agent docs, src/ scaffold, and the baton's verify commands) to a brainstormed project spec at kickoff. Use when a design spec exists in docs/specs/ and the user says "tailor the setup", "set up the repo for this spec", "configure the workspace from the spec", or invokes /tailor-setup. Use instead of `npm run init:project` when no archetype preset fits the project.
version: 1.0.0
---

# Tailor-Setup Skill (Spec-Driven Repository Tailoring)

`npm run init:project` tailors the repo from one of four fixed archetypes. **Tailor-Setup** tailors it from the project's own design spec: you decide what the project needs and record it in a manifest; `npm run tailor` applies the manifest deterministically.

---

## 1. When to Use

- A project design spec exists in [`docs/specs/`](../../../docs/specs/) and [`project-blueprint.json`](../../../project-blueprint.json) has `status: "uninitialized"`.

## 2. When NOT to Use

- ❌ **No project spec yet.** Stop. Run `wayfinder` (kickoff mode) to produce one first; it hands off to `superpowers:brainstorming` or charts a decision map. Specs about this template itself (`*-setup-*`, `*-tailoring-*`, `skill-seeker-*`) are not project specs.
- ❌ **Blueprint already `initialized`.** Stop and tell the developer. Re-tailoring overwrites `docs/PLAN.md`, including checked-off tasks. Only proceed with `--force` if the developer explicitly asks.
- ❌ **Mid-project plan changes.** Edit `docs/PLAN.md` and toggle skills with `npm run skill:enable` / `npm run skill:disable` instead.

---

## 3. The 8-Step Flow

```text
1. READ THE SPEC          docs/specs/<project>-design.md, in full
2. READ THE CATALOGUE     npm run skill:list -- --json, then ONLY the name/description
                          frontmatter of each SKILL.md (active and archived)
3. WRITE THE MANIFEST     into the "project" block of project-blueprint.json (Section 4)
                          Leave "status" and "archetypes" untouched
4. DRY RUN                npm run tailor -- --dry-run
5. GET APPROVAL           Show the developer: skills kept / archived, stack, developer,
                          roadmap tasks, verify commands. STOP until they approve
6. APPLY                  npm run tailor
7. REWRITE & SCAFFOLD     Rules and agent docs (Section 6), then src/ (Section 7)
8. VERIFY                 npm run verify:agent
```

After step 6 the baton runs the project's own commands from `verify`. Until the scaffold exists, a failing `npm run verify:agent` in step 8 is expected to point at the missing project tests, not at the template.

---

## 4. The Manifest

Extend the existing `project` block. Do not remove `archetypes`.

```json
"project": {
  "name": "ai-flow-canvas",
  "description": "One-sentence mission",
  "archetype": "custom",
  "source_spec": "docs/specs/2026-10-11-ai-flow-canvas-design.md",
  "stack": { "frontend": "…", "backend": "…", "database": "…", "auth": "…" },
  "developer": "Steve",
  "skills": ["webapp-testing", "owasp-security", "varlock"],
  "verify": {
    "test": "npm test",
    "test_scoped": "npm test -- {scope}",
    "e2e": "npx playwright test",
    "build": "npm run build"
  },
  "roadmap": [
    { "id": "1.1", "title": "…", "priority": "P0", "description": "…" }
  ]
}
```

| Field | Required | Rule |
| :--- | :--- | :--- |
| `name`, `description` | yes | Non-empty strings. |
| `archetype` | yes | Must be `"custom"`. |
| `source_spec` | yes | Repo-relative path to the existing spec file. |
| `stack` | yes | Object of free-form strings. Keys are not fixed; a CLI tool may have only `runtime`. |
| `developer` | no | The developer's name, a non-empty string when present. The roadmap says "the developer" when absent. |
| `skills` | yes | Names that exist in `.agents/skills/` or `.agents/skills-archive/`. |
| `verify.test` | yes | Shell command for the fast suite: unit and component tests. It runs on every verify and every commit, so keep browser tests out of it. |
| `verify.test_scoped` | no | Shell command containing `{scope}`. |
| `verify.e2e` | no | Shell command for the slow browser or end-to-end suite. It runs only with `npm run verify:agent -- --e2e`. |
| `verify.build` | no | Production build command. Recorded for agents; the baton does not run it. |
| `roadmap` | yes | At least one task. `id` unique; `priority` is `P0`, `P1`, or `P2`. |

**Always kept, listed or not:** `tailor-setup`, `fast-track`, `caveman`, `ponytail`.

---

## 5. Choosing Skills

- Include a skill **only when a roadmap task needs it**. Name the task when you present the list for approval.
- Choose from frontmatter `name` and `description` alone. Do not load whole skill bodies while choosing.
- When unsure, leave it out. `npm run skill:enable <name>` restores any archived skill in one command.

---

## 6. Rewriting the Rules and Agent Docs

Rewrite only what is stack-specific:

| File | Rewrite |
| :--- | :--- |
| `docs/rules/frontend.md`, `docs/rules/backend.md` | Overview, `## Core Standards`, and `## Dos and Don'ts` bodies, for the real stack. If the project has no such layer, keep the three headings with a short "not applicable to this project" note under each. Never delete the file. |
| `docs/rules/README.md` | The stack sentence and the "When to Read What" table. |
| `docs/ai/agent-handbook.md` | The skills quick-selection table: list only skills that are now active. |
| `CLAUDE.md` | Remove the "Frontend Polish" bullet when the project has no frontend. |

**Do not touch:** `docs/rules/requirements.md`, `AGENTS.md`, `GEMINI.md`, `.cursorrules`, `docs/ai/workflows.md`, `docs/ai/architecture.md`. They hold process rules, not stack rules.

**Fixed anchors.** Tests assert these strings; keep them verbatim:
- `## Core Standards` and `## Dos and Don'ts` in every rule file.
- `When to Read What` in `docs/rules/README.md`.
- `Builder`, `verify:agent`, `caveman`, `ponytail`, `project-blueprint.json` in `CLAUDE.md`.
- `project-blueprint.json` in `docs/ai/agent-handbook.md`.

Keep rule files token-lean: principles, checklists, and Dos/Don'ts tables, not long code blocks.

---

## 7. Scaffolding

- Run the stack's **official generator** non-interactively (for example `create-next-app`, `npm create vite`, `uv init`), targeting `src/` or the repo root where the generator requires it. Do not hand-write boilerplate a generator provides.
- If `src/` already contains files, skip scaffolding and say so.
- If the generator would overwrite the template's `package.json`, merge the template's `scripts` entries back in afterwards. The baton and `npm run tailor` depend on them.
- Record the exact generator command in the handoff summary.

---

## 8. Errors

| `npm run tailor` reports | Do this |
| :--- | :--- |
| A list of `project.<field>: …` problems | Fix every listed field in the manifest and re-run. Nothing was written. |
| `already initialized … --force` | Stop and ask the developer. Do not add `--force` on your own. |
| `project-blueprint.json is not valid JSON` | Repair the JSON you wrote and re-run. |
| A failure after skills have moved | Re-run `npm run tailor`; it converges. The blueprint stays `uninitialized` until the run completes. |

---

## 9. Key Rules

- **Approval before apply.** Never run `npm run tailor` without showing the dry run and getting a yes.
- **One source of truth.** The manifest lives in `project-blueprint.json`; do not hand-edit `docs/PLAN.md` or move skill folders as part of tailoring.
- **Relative links.** In files you write, link with relative Markdown paths, never absolute machine paths.
