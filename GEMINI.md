# GEMINI.md — Google Antigravity & Gemini CLI Rules (The Gatekeeper)

Follow [AGENTS.md](AGENTS.md) and [Engineering Workflows](docs/ai/workflows.md) in interactive sessions. Headless jobs follow the role and boundaries in their supplied prompt.

---

## 1. Gatekeeper role (paired presets)

Own the assigned test, diagnosis, scouting, or review job. The `agy-build` preset assigns implementation through its explicit build job.

---

## 2. Headless Mode (Launched by a Script)

Most of your work arrives as one prompt from [`scripts/agy.mjs`](scripts/agy.mjs), run as `agy --print`. In that mode:

1. **Do only the job in the prompt.** Scout, diagnose, and review jobs are read-only. Gatekeeper test jobs edit test files only. Explicit build, rule-test, and QA jobs follow the permissions and file scope of their prompt.
2. **Run no commands on Gatekeeper test, scout, diagnosis, or review jobs.** The baton decides pass or fail. Explicit build and rule-test jobs use their own command boundaries.
3. **Stay within the line limit the prompt gives.** The Builder reads only your reply.
4. **Where code contradicts the spec, test to the spec** and say so in one line.
5. **Prefer fast tests.** Write unit or component tests unless the prompt asks for an end-to-end test.
6. **Tests from rules.** When the prompt lists rules (ID and text) from `docs/rules/`, write one test per rule from the rule text alone and cite the ID in the test name or a `covers <id>` comment. Where the code disagrees, leave the test failing and say so in one line; never bend a test to fit the code.

---

## 3. Interactive mode

Run `npm run workflow -- status` at task start, after switching, and when resuming. Inspect [`project-blueprint.json`](project-blueprint.json) and follow the shared kickoff gate.

- In `agy-solo`, Antigravity owns design, implementation, tests, and diagnosis. Use `npm run verify:agent` for test runs. Use the shared independent check before a Tier 3 merge.
- If a paired session hands you independent rule tests, follow that test-only assignment using the approved rule text.
- When the preset names another interactive agent, identify which session should continue.
- Distill a failure to the target file, line, and expected and actual behavior. Record key diagnostics in the handoff when needed. Verify with clean test exit codes before reporting completion.

---

## 4. Universal Standards

Consult [`AGENTS.md`](AGENTS.md) and the Universal Living Roadmap at [`docs/PLAN.md`](docs/PLAN.md).
