# AI Agent Handbook

This handbook serves as the operational onboarding manual and skills selection guide for all AI coding agents working within `dual-yzentic-setup`.

---

## 1. Initial Session Orientation

Whenever starting a new session in this repository:

0. **Start from the handoff:** Read [`.agents/sync/session.md`](../../.agents/sync/session.md). In Claude Code a hook injects it at session start. Open only the files it lists.
1. **Inspect Project Blueprint:** Check [`project-blueprint.json`](../../project-blueprint.json). If `status === "uninitialized"`, start with the [`wayfinder`](../../.agents/skills/wayfinder/SKILL.md) skill (kickoff mode) before editing project code. `npm run init:project` stays the shortcut when the developer already knows the stack and an archetype fits.
2. **Inspect Sync Bus:** Run `npm run sync:status` for the baton state and the working-tree change set.
3. **Check the Universal Living Roadmap:** Find the entry for the task at hand in [`docs/PLAN.md`](../PLAN.md).
4. **Load on demand:** Open a skill in [`.agents/skills/`](../../.agents/skills/) or a rule file in [`docs/rules/`](../rules/README.md) only when the task needs it.

Do not survey the repository, recent history, or the skills catalogue up front. When a task does not say where its code lives and a quick search does not find it, `npm run scout -- "<task>"` returns the files that matter. Skip it when the task or plan names the files.

---

## 2. CLI Execution & Platform Conventions

### Execution Guidelines
- Run non-interactively (`PAGER=cat`, non-blocking flags).
- In chat, format file paths and code symbols as clickable `file://` links for the current machine. In committed files, use relative links.
- Verification is performed via the Baton Coordinator. Never run a full test suite directly:
  ```bash
  npm run verify:agent
  ```
- Three commands hand work to the Gatekeeper (Antigravity), each returning a short result:

  | Command | Gatekeeper job | Returns |
  | :--- | :--- | :--- |
  | `npm run scout -- "<task>"` | Find the files and ranges a task touches, when they are not known | A brief of at most 40 lines |
  | `npm run verify:agent` | Write tests for untested changes; diagnose long or browser failures | Pass, an excerpt, or a root-cause note |
  | `npm run review` | Review the branch diff against its spec and plan | Findings, at most 60 lines |

---

## 3. Communication & Safety Guardrails
- **Destructive Actions:** Stop and request explicit user confirmation before deleting files, dropping tables, or force-pushing.
- **Zero Secret Exposure:** Never display, print, or leak contents of `.env` files or API credentials into logs or chat. Use [`varlock`](../../.agents/skills/varlock/SKILL.md).
- **Conciseness:** Keep responses concise, evidence-driven, and focused on working deliverables.

---

## 4. Skills Quick-Selection Guide ("When to Use What")

### Core Process Skills (Superpowers Framework)

| Scenario / Task | Process Skill | Purpose |
| :--- | :--- | :--- |
| **Tier 3 work only** | `superpowers:using-superpowers` | Process skills apply to Tier 3. Tier 1 uses `fast-track`; Tier 2 uses a short design in chat |
| **New subsystem or architectural change** | `superpowers:brainstorming` | Discovery of intent, requirements, and design, in chat |
| **Tier 3 design and plan** | `superpowers:writing-plans` | The task format: each task names its tests. The approved chat design is saved unchanged in `docs/specs/`; one `builder` run per branch |
| **Executing implementation plans** | `builder` agent (`.claude/agents/builder.md`) | All of a branch's plan tasks in one launch, on Sonnet, with a fresh context |
| **Writing a test yourself** | `superpowers:test-driven-development` | Red-Green-Refactor, when the Gatekeeper was skipped or a plan task names the test |
| **Bug fixing or troubleshooting** | `superpowers:systematic-debugging` | Root-cause investigation before proposing fixes (no guessing) |
| **Pre-completion claim** | `superpowers:verification-before-completion` | Pre-completion evidence gate (verify tests before claiming complete) |

---

### Domain Skills ([`.agents/skills/`](../../.agents/skills/))

| Scenario / Task | Recommended Skill | Purpose |
| :--- | :--- | :--- |
| **Token defense on Claude Pro** | [`caveman`](../../.agents/skills/caveman/SKILL.md) | Strips conversational filler, saves ~70% output tokens |
| **Minimalist coding & anti-over-engineering** | [`ponytail`](../../.agents/skills/ponytail/SKILL.md) | "Lazy senior developer" mode: smallest workable diff, no bloated libraries |
| **Design intelligence (React, Tailwind, Shadcn)** | [`ui-ux-pro-max`](../../.agents/skills/ui-ux-pro-max/SKILL.md) | Searchable design tokens, color palettes, typography, and UX patterns |
| **Award-winning UI polish & accessibility** | [`impeccable`](../../.agents/skills/impeccable/SKILL.md) | Precision commands: `/impeccable polish`, `bolder`, `quieter`, `audit` |
| **System architecture & sequence diagrams** | [`archify`](../../.agents/skills/archify/SKILL.md) | Generates interactive architecture and sequence diagrams |
| **Realistic mock & seed data for demos** | [`demo-seed-data`](../../.agents/skills/demo-seed-data/SKILL.md) | Populates dashboards with avatars, realistic names, dynamic metrics |
| **Kickoff of an uninitialized project: surfacing and mapping open decisions** | [`wayfinder`](../../.agents/skills/wayfinder/SKILL.md) | Tags open decisions, then hands off to brainstorming or charts a ticket map in `docs/wayfinder/` |
| **Tailoring the repo to a brainstormed spec at kickoff** | [`tailor-setup`](../../.agents/skills/tailor-setup/SKILL.md) | Derives skills, roadmap, rules, scaffold, and verify commands from the project spec |
| **Micro-tasks, cosmetic CSS & quick fixes** | [`fast-track`](../../.agents/skills/fast-track/SKILL.md) | Express-lane protocol for token-efficient edits without test ceremony |
| **Web application browser testing** | [`webapp-testing`](../../.agents/skills/webapp-testing/SKILL.md) | Headless Playwright automation and DOM verification |
| **Managing API keys & secrets safely** | [`varlock`](../../.agents/skills/varlock/SKILL.md) | Zero-leak secret management |
| **Security audit, auth, crypto** | [`owasp-security`](../../.agents/skills/owasp-security/SKILL.md) | Audit against OWASP Top 10 |

---

## 5. Web Development Domain Rules ([`docs/rules/`](../rules/README.md))

| Task / Scope | Rule File | Focus & Standards |
| :--- | :--- | :--- |
| **Feature Scoping & Acceptance Criteria** | [`requirements.md`](../rules/requirements.md) | Given/When/Then criteria, 4 UI states (loading, empty, error, success) |
| **Frontend Components & UX** | [`frontend.md`](../rules/frontend.md) | Server-first RSC, state boundaries, Tailwind tokens, WCAG 2.1 AA |
| **Backend APIs, DB & Security** | [`backend.md`](../rules/backend.md) | Zod schema validation, RFC error envelopes, transaction safety |
