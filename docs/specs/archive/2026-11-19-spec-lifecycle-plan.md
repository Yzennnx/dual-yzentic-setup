# Implementation plan for active and archived specs

**One approved spec per feature or meaningful change. Every task created from that spec links to it in `docs/PLAN.md`.** A feature can have several tasks, each pointing to the relevant section of the same document. The roadmap tracks work and status, the spec records what you approved, and `docs/rules/features/` describes the app’s current behavior.

## Design

### 1. Use one spec from approval through completion

```text
docs/
  PLAN.md
  specs/
    README.md
    active/
      YYYY-MM-DD-saved-searches-plan.md
    archive/
      YYYY-MM-DD-workflow-switcher-plan.md
  rules/
    features/
      saved-searches.md
```

- **Draft the spec for review.** Start with what the feature should do, what’s out of scope, the behavior rules it changes, and how you’ll know it works. End with the implementation tasks and their verification. A Tier 3 spec names the tests for each task and includes the existing mockup map when applicable.
- **Approve once.** Save the approved draft in `docs/specs/active/`, then add the approved tasks to `PLAN.md` before coding. Each row keeps its title, priority, and status, plus a link such as `specs/active/YYYY-MM-DD-saved-searches-plan.md#task-1-save-a-search`. Keep the existing feature tags so the rules map still works.
- **Build from the linked spec.** Use it for implementation, handoff, and review. Update the live feature rules and tests as required. If the agreed behavior changes during implementation, bring that change back for approval and record it in the same spec.
- **Archive when the last linked task is verified and closed.** Move the spec and update all its roadmap links in the same commit. For Tier 3, do this after addressing review findings and before full verification of the final branch tip. The archived spec lands on `main` with the finished work. If any linked task is still open, keep the spec active.

### 2. Apply the policy by tier

| Tier | Spec policy |
|---|---|
| **Tier 1 · Express** | Keep the fast path. A cosmetic task can link to an existing spec or feature rule when relevant. |
| **Tier 2 · Standard** | Keep short fixes in chat. For a new feature or a behavior change worth preserving, use a short spec and link its tasks after approval. This replaces the current blanket rule against Tier 2 spec files. The Tier 2 verification and review rules still apply. |
| **Tier 3 · Risky Surface** | Require one combined spec with the approved design, tasks, and named tests. Every task created from it links back to it. Existing approval, verification, review, and merge gates still apply. |

Existing backlog placeholders can stay as ideas until their scope is approved. Project kickoff continues through Wayfinder and `docs/rules/`, where the initial product design already lives.

### 3. Point review at the spec for the work

Make the roadmap-linked path the documented input to review:

```powershell
npm run review -- --plan docs/specs/active/YYYY-MM-DD-saved-searches-plan.md
```

Keep explicit `--plan` paths working for active, archived, and legacy documents. For automatic selection, use a single active spec added or changed by the branch. If the branch changes multiple active specs, ask for `--plan` before launching review. If the relevant spec is already on `main`, pass its roadmap link explicitly. Replace the current latest-date fallback so review cannot silently pick an unrelated plan.

The baton already checks roadmap spec links for missing files. Extend the tests to cover both folders and make the repository’s integrity checks catch broken roadmap links after a move. Archiving stays a Git move and link update, with completion determined by the linked tasks.

## Implementation phases and tests

| Phase | Work | Tests |
|---|---|---|
| **1. Document the lifecycle** | Add `docs/specs/README.md` with a reusable spec outline, a roadmap link example, and the approval and archive steps. Update `AGENTS.md`, the workflow guide, the handbook, and the roadmap generator so new projects inherit the same process. Teach the generator to render a spec link when a task supplies one. | Extend `test_root_rules.py` and `test_docs_integrity.py` to check consistent tier guidance and valid guide links. Extend `test_roadmap.py` to verify that multiple tasks can link to sections of one spec and that existing backlog entries still render. |
| **2. Update review and link checks** | Replace the date-based review lookup with branch-aware selection. Preserve explicit paths and existing blueprint feature-rule inputs. Cover nested active and archived links in the baton and roadmap checks. | Extend `test_review.py` for explicit active, archived, and legacy paths, one branch candidate, two candidates, and a branch with no candidate. Use the existing Antigravity stub to confirm ambiguous selection stops before delegation. Extend `test_baton_runner.py` and `test_plan_integrity.py` for nested paths, links with section anchors, and missing targets. |
| **3. Organize the existing specs** | Inventory the flat `docs/specs/` files and their references. Move completed specs to `archive/` and any still-open specs to `active/`. Repair incoming links and relative links inside moved documents. Keep the historical wording and filenames. Preserve Wayfinder’s existing archive convention. | Extend `test_docs_integrity.py` and `test_plan_integrity.py` to verify the new layout and migrated links, including the workflow switcher’s completed roadmap entry. Run the mockup check for any moved spec that defines a mockup map. |
| **4. Verify the full lifecycle** | Walk through approving one feature with two roadmap tasks, reviewing against its active spec, completing the tasks, and moving it to archive with both links intact. Check that the other preset and tier behaviors still apply. | Add a fixture case in `test_plan_integrity.py` for two tasks sharing one spec and retaining valid links after archival. Use `test_review.py` to verify explicit archived review still works. Run the repo’s Tier 3 verification, one branch review, and final full baton verification before merging locally. |
