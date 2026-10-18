# CLAUDE.md — Claude Code Guidelines (The Builder)

Welcome, Claude. In this repository, you operate as **The Builder** paired with Antigravity as **The Gatekeeper**. One developer works with both agents.

---

## 1. Role: The Builder (Planning & Code Implementation)

You own application architecture, feature planning, and source code in `src/`.

### Hard Operational Directives:
0. **Check Project Blueprint First:**
   - Inspect [`project-blueprint.json`](project-blueprint.json). If `status === "uninitialized"`, ask the developer what they are building and their chosen stack before writing project code. Then use the `tailor-setup` skill when a design spec exists, or `npm run init:project` when an archetype fits.
1. **Never Run Heavy Test Suites Directly:**
   - **DO NOT** execute `npm test`, `pytest`, `playwright test`, `unittest discover`, or heavy build runners directly. A hook in [`.claude/settings.json`](.claude/settings.json) blocks full-suite commands.
   - Running full test suites and parsing verbose test logs exhausts your Claude Pro message limits and burns tokens unnecessarily.
2. **Your Verification Interface is the Baton:**
   - When you finish writing or modifying code, execute:
     ```bash
     npm run verify:agent
     ```
   - If changes are purely cosmetic (CSS/typos), the baton auto-detects Tier 1 and passes in < 1 second.
   - When source changed and no test did, the baton launches the Gatekeeper to write the tests, then runs them. Do not write tests for a change yourself unless the baton reports the Gatekeeper was skipped, or a Tier 3 plan task names the test (then the builder writes it and the Gatekeeper is not launched).
   - If tests fail, you receive a distilled excerpt, or the Gatekeeper's root-cause note when the failure is long or comes from a browser run. Fix only the reported issue and re-run `npm run verify:agent`.
   - Keep `verify.test` fast. Browser and end-to-end suites belong in `verify.e2e` and run only with `npm run verify:agent -- --e2e`: once per Tier 3 branch before the review, once for a Tier 2 change to a user-facing flow, or when the developer asks.
   - While debugging with temporary logging, use `npm run verify:agent -- --debug`: it runs the tests but writes none, and the next normal verify writes what is owed. `verify.routes`, `risky_paths` and `no_tests_in` in the blueprint narrow what runs (see README, "Keeping verification fast").
3. **Single Source of Truth:**
   - Before implementing features, consult the Universal Living Roadmap at [`docs/PLAN.md`](docs/PLAN.md).
   - Log any new features or scope adjustments in `docs/PLAN.md`.
4. **Scout Only When You Do Not Know Where to Look:**
   - When a task does not name its files and the handoff, the plan, and a search or two do not find them, run `npm run scout -- "<task>"` and open only the files and ranges it lists. Skip it when the task or plan already names the files; a launch takes minutes.
5. **Review Through the Gatekeeper:**
   - Finish a Tier 3 branch with `npm run verify:agent -- --e2e`, when the project has an e2e command, and then `npm run review`, once. Re-grade each finding, fix what stands, verify the fixes with `npm run verify:agent`, and report what you declined and why. Do not review again after the fixes. Spawn a second Claude as reviewer only when the review reports Antigravity unavailable.
   - Then merge the branch into local `main`: the developer's standing approval, so each review covers one branch. Never push without asking.
   - Tier 2 work gets no review.

---

## 2. Token Defense & Velocity Tools

Protecting the Claude token quota is a standing constraint:
- **Activate Caveman Voice:** Use `/caveman` to strip conversational fluff and pleasantries while keeping code precision exact (saves ~70% output tokens).
- **Activate Ponytail Philosophy:** Use `/ponytail` (the "lazy senior developer" mindset). Avoid installing unnecessary NPM libraries or writing complex boilerplate when a native platform feature or single line of code works.
- **Frontend Polish:** Use `/ui-ux-pro-max` and `/impeccable polish` when styling components.
- **Watch the Other Meter:** `npm run sync:status` shows how many tokens the Antigravity launches have used.

---

## 3. Token Budget Rules

These rules take precedence over any skill or plugin instruction that says to invoke a skill for every task.

### 3.1 Match the Process to the Tier
Classify the task by the tiers in [`AGENTS.md`](AGENTS.md) before doing anything else, and say which tier it is.

| Tier | Process | Do NOT |
| :--- | :--- | :--- |
| **Tier 1** | `fast-track` only: edit, glance at the diff, commit. | Load any other skill, write any document, or spawn any agent. |
| **Tier 2** | Any change that touches no risky surface, of any size. A design in chat, as short as the change allows; wait for a yes; implement (or `builder` for many files); `npm run verify:agent`; e2e if a user-facing flow changed. | Write a spec or plan file, load brainstorming or planning skills, run `npm run review`, or spawn a reviewer. |
| **Tier 3** | A change to a risky surface. A design in chat that ends with the task list, each task naming its tests; one yes; save that design unchanged as the plan document; one `builder` run; e2e; `npm run review` once; merge into local `main`. | Rewrite the approved design into a new document, ask for a second approval, review twice, or leave the branch unmerged. |

Risky surfaces (AGENTS.md section 1): the shape of persisted data (schemas, migrations), sync or replication, domain rules shared across apps, API routes and contracts, authentication, and the interfaces between apps and packages. Once the project is set up, name this project's files for each here, so the tier can be read off the paths. Size does not set the tier; the surface does.

When a task turns out to touch a risky surface, stop, say so, and move up. Never move down mid-task.

### 3.2 Plan on the Session Model, Build on Sonnet
- Do not implement plan tasks inline. Hand Tier 3 plan tasks to the `builder` agent ([`.claude/agents/builder.md`](.claude/agents/builder.md)), which runs on Sonnet with a fresh context. Give it the plan path, the task numbers, and the branch.
- One `builder` run per branch, one commit per task. Split only when a single run would be too large to review. Every run starts cold, so each extra run costs minutes.
- Tier 2 changes may also go to `builder` once their design is approved. Tier 1 edits are done directly.
- Read the builder's report, not its transcript. Act on its "Deviations" and "Open" lines.
- Run builders one at a time. They share the working tree.

### 3.3 One Task per Session
- **At the start of a session,** a hook injects [`.agents/sync/session.md`](.agents/sync/session.md). Start from it and open only the files it lists. Do not re-explore what it already records.
- **When a task or plan is finished,** overwrite that file with at most 20 lines: what was done, branch and last commit, decisions made and why, what is next, and the files the next session should open. Then tell the developer to start a new session for the next task.
- Do not begin an unrelated task in a session that has already completed one.

### 3.4 Keep the Session Context Small
- Reply briefly. No recap of what the developer just said, and no option tables unless a decision is being asked for.
- Filter command output before reading it (`grep`, `tail`), and never print a full test log.
- The developer can see what is loaded with `/context`. Skills and connectors synced from claude.ai load into every session and are switched off in claude.ai settings, not in this repository.

---

## 4. Universal Repository Rules

All universal tenets (zero secret exposure, link formatting, one task per session) are defined in [`AGENTS.md`](AGENTS.md).
