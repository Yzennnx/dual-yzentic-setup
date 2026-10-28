---
name: tailor-setup
description: Tailors the whole repository setup (active skills, docs/PLAN.md roadmap with feature tags, rules.source, agent docs, src/ scaffold, and the baton's verify commands) to the project design written in docs/rules at kickoff. Use when docs/rules holds the invariants, architecture and a feature doc per feature, and the user says "tailor the setup", "set up the repo for this design", "configure the workspace", or invokes /tailor-setup.
version: 1.0.0
---

# Tailor-Setup Skill (Design-Driven Repository Tailoring)

The project's design lives in [`docs/rules/`](../../../docs/rules/README.md): `invariants.md`, `architecture.md` and one `features/<feature>.md` per feature. **Tailor-Setup** reads it, you decide what the project needs and record it in a manifest; `npm run tailor` applies the manifest deterministically.

---

## 1. When to Use

- `docs/rules/` holds the project design (invariants, architecture, a full feature doc per feature with `owns: []`) and [`project-blueprint.json`](../../../project-blueprint.json) has `status: "uninitialized"`.

## 2. When NOT to Use

- ❌ **No project design in `docs/rules/` yet.** Stop. Run `wayfinder` (kickoff mode) first; it hands off to `superpowers:brainstorming` or charts a decision map. Brainstorming writes the design straight into `docs/rules/` (invariants, architecture, one feature doc per feature); there is no separate `docs/specs/<project>-design.md`. Specs about this template itself (`*-setup-*`, `*-tailoring-*`, `skill-seeker-*`) are not project designs.
- ❌ **Blueprint already `initialized`.** Stop and tell the developer. Re-tailoring overwrites `docs/PLAN.md`, including checked-off tasks. Only proceed with `--force` if the developer explicitly asks.
- ❌ **Mid-project plan changes.** Edit `docs/PLAN.md` and toggle skills with `npm run skill:enable` / `npm run skill:disable` instead.

---

## 3. The 8-Step Flow

```text
1. READ THE RULES         docs/rules/README.md, invariants.md, architecture.md and every
                          features/*.md, in full
2. READ THE CATALOGUE     npm run skill:list -- --json, then ONLY the name/description
                          frontmatter of each SKILL.md (active and archived)
3. WRITE THE MANIFEST     into the "project" block of project-blueprint.json (Section 4)
                          plus rules.source at the top level. Leave "status" untouched
4. DRY RUN                npm run tailor -- --dry-run
5. GET APPROVAL           Show the developer: skills kept / archived, stack, developer,
                          roadmap tasks, verify commands. STOP until they approve
6. APPLY                  npm run tailor
7. DOCS & SCAFFOLD       Agent docs (Section 6), then src/ and its ownership (Section 7)
8. VERIFY                 npm run verify:agent
```

After step 6 the baton runs the project's own commands from `verify`. Until the scaffold exists, a failing `npm run verify:agent` in step 8 is expected to point at the missing project tests, not at the template.

---

## 4. The Manifest

Extend the existing `project` block and set the top-level `rules.source`.

```json
"project": {
  "name": "ai-flow-canvas",
  "description": "One-sentence mission",
  "archetype": "custom",
  "source_rules": "docs/rules/README.md",
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
    { "id": "1.1", "title": "…", "priority": "P0", "description": "…", "features": ["canvas"] }
  ]
},
"rules": { "source": ["src/**/*.ts", "src/**/*.tsx"] }
```

| Field | Required | Rule |
| :--- | :--- | :--- |
| `name`, `description` | yes | Non-empty strings. |
| `archetype` | yes | Must be `"custom"`. |
| `source_rules` | yes | Repo-relative path to `docs/rules/README.md`. |
| `stack` | yes | Object of free-form strings. Keys are not fixed; a CLI tool may have only `runtime`. |
| `developer` | no | The developer's name, a non-empty string when present. The roadmap says "the developer" when absent. |
| `skills` | yes | Names that exist in `.agents/skills/` or `.agents/skills-archive/`. |
| `verify.test` | yes | Shell command for the fast suite: unit and component tests. It runs on every verify and every commit, so keep browser tests out of it. |
| `verify.test_scoped` | no | Shell command containing `{scope}`. |
| `verify.e2e` | no | Shell command for the slow browser or end-to-end suite. It runs only with `npm run verify:agent -- --e2e`. |
| `verify.build` | no | Production build command. Recorded for agents; the baton does not run it. |
| `roadmap` | yes | At least one task. `id` unique; `priority` is `P0`, `P1`, or `P2`; `features` lists the feature names it belongs to (each needs `docs/rules/features/<name>.md`) or `arch`. They become `[feature]` tags on the PLAN line. |
| `rules.source` (top level) | yes | Globs of where the project's code lives. `npm run tailor` keeps it and fills `rules.ignore` and `rules.tests` with defaults; `npm run rules:check` flags a new source file no doc owns. |

**Always kept, listed or not:** `tailor-setup`, `fast-track`, `caveman`, `ponytail`.

---

## 5. Choosing Skills

- Include a skill **only when a roadmap task needs it**. Name the task when you present the list for approval.
- Choose from frontmatter `name` and `description` alone. Do not load whole skill bodies while choosing.
- When unsure, leave it out. `npm run skill:enable <name>` restores any archived skill in one command.

---

## 6. Agent Docs

Rewrite only what is stack-specific:

| File | Rewrite |
| :--- | :--- |
| `docs/ai/agent-handbook.md` | The skills quick-selection table: list only skills that are now active. |
| `CLAUDE.md` | Remove the "Frontend Polish" bullet when the project has no frontend. Name this project's risky-surface files in section 3.1. |

Step 7 no longer rewrites stack rule files: the design is already in `docs/rules/`. **Do not touch:** `AGENTS.md`, `GEMINI.md`, `.cursorrules`, `docs/ai/workflows.md`, `docs/ai/architecture.md`. They hold process rules, not stack rules.

**Fixed anchors.** Tests assert these strings; keep them verbatim:
- `Builder`, `verify:agent`, `caveman`, `ponytail`, `project-blueprint.json` in `CLAUDE.md`.
- `project-blueprint.json` in `docs/ai/agent-handbook.md`.
- The `<!-- rules:map -->` markers in `docs/rules/README.md`.

---

## 7. Scaffolding

- Run the stack's **official generator** non-interactively (for example `create-next-app`, `npm create vite`, `uv init`), targeting `src/` or the repo root where the generator requires it. Do not hand-write boilerplate a generator provides.
- If `src/` already contains files, skip scaffolding and say so.
- If the generator would overwrite the template's `package.json`, merge the template's `scripts` entries back in afterwards. The baton and `npm run tailor` depend on them.
- Put the generator's files into `architecture.md`'s `owns`, run `npm run rules:map`, then `npm run rules:check`: it must pass (features own nothing yet, so nothing can drift). A feature's first task adds its new files to that feature's `owns`.
- Record the exact generator command in the handoff summary.

---

## 8. Errors

| `npm run tailor` reports | Do this |
| :--- | :--- |
| A list of `project.<field>: …` problems | Fix every listed field in the manifest and re-run. Nothing was written. A feature with no doc: write `docs/rules/features/<name>.md` first. |
| `already initialized … --force` | Stop and ask the developer. Do not add `--force` on your own. |
| `project-blueprint.json is not valid JSON` | Repair the JSON you wrote and re-run. |
| A failure after skills have moved | Re-run `npm run tailor`; it converges. The blueprint stays `uninitialized` until the run completes. |

---

## 9. Key Rules

- **Approval before apply.** Never run `npm run tailor` without showing the dry run and getting a yes.
- **One source of truth.** The manifest lives in `project-blueprint.json`; do not hand-edit `docs/PLAN.md` or move skill folders as part of tailoring.
- **Relative links.** In files you write, link with relative Markdown paths, never absolute machine paths.
