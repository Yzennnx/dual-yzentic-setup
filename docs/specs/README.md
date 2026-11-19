# Spec lifecycle

Use one spec for a feature or meaningful behavior change. The [roadmap](../PLAN.md) tracks tasks and status. The [feature rules](../rules/README.md) describe current behavior.

## Draft and approve

1. **Goal and scope** — Describe what changes and where the work stops.
2. **Behavior and rules** — Describe expected behavior and include exact changed rule text and IDs.
3. **Acceptance and verification** — Explain how to demonstrate the approved behavior.
4. **Tasks** — Give each task a heading, scope, and checks. Name each task's tests for Tier 3. Include a mockup map when applicable.

After approval, save the draft as `active/YYYY-MM-DD-<name>-plan.md` and link each approved task before coding. Keep its feature tags, priority, and status.

```markdown
- [ ] **Task 1.1 [search]: Save a search**
  - **Priority:** P1
  - **Status:** Backlog
  - **Spec:** [Approved spec](specs/active/YYYY-MM-DD-saved-searches-plan.md#task-1-save-a-search)
```

For generated roadmaps, set each task's optional `spec` field to the same path relative to `docs/PLAN.md`. Include the task heading anchor when several tasks share a spec.

Tier 1 keeps the fast path and can link to existing guidance. Tier 2 keeps short fixes in chat and uses a short spec for a new feature or meaningful behavior change. Tier 3 requires one approved spec with design, tasks, and named tests. Project kickoff keeps its [Wayfinder workflow](../../.agents/skills/wayfinder/SKILL.md).

## Implement and review

Use the linked spec for implementation and handoff. Update live rules and tests as required. If agreed behavior changes, approve the change and update the same spec.

For paired Tier 3 review, pass the roadmap-linked spec file path from the repo root without its task heading anchor:

```powershell
npm run review -- --plan docs/specs/active/YYYY-MM-DD-saved-searches-plan.md
```

Review can select the sole active spec added or changed by the branch. Pass `--plan` when multiple active specs changed or the relevant spec already lives on `main`. Explicit paths also work for archived and legacy specs.

## Archive

Once the final linked task is verified and closed, move the spec into `archive/` with its filename intact. Update every roadmap link in the same commit and keep the heading anchors. If any linked task remains open, keep the spec in `active/`.

Automatic mockup checks include active specs. Archived specs retain the fingerprints from their approval and implementation. Pass the archived path to `npm run mockups:check -- <spec-path>` to check one explicitly.

For Tier 3, archive after addressing review findings and before full verification of the final branch tip. Wayfinder ticket maps keep the `archive/wayfinder-<date>/` convention.
