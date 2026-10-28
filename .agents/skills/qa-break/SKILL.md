---
name: qa-break
description: Attack one area of the app to find bugs, using a standard attack catalogue plus the project's own invariants, and record findings with repro steps plus Playwright attack tests. Use when the user invokes /qa-break <area> or asks to try to break, fuzz or stress an area.
version: 1.0.0
---

# QA Break Skill (Attack One Area)

Builds on [`webapp-testing`](../webapp-testing/SKILL.md) for driving the app. Input: one area, for example `lists` or `checkout`. Drive the built app through the project's existing Playwright launcher; add other clients only where an e2e launcher exists.

## Setup (once per project)

The template ships no `playwright.config.ts`. Before the first run, add a second Playwright project named `qa` to the project's config, matching only `**/*.qa.e2e.ts`, and make the normal `e2e` project ignore those files:

```ts
projects: [
  { name: 'e2e', testMatch: '**/*.e2e.ts', testIgnore: '**/*.qa.e2e.ts' },
  { name: 'qa', testMatch: '**/*.qa.e2e.ts' },
]
```

`npm run e2e:qa` runs `playwright test --project=qa`. The project's `e2e` script should pass `--project=e2e` so attack tests stay out of `verify.e2e`.

## Who runs it

- **agy-build mode** ([`workflow`](../workflow/SKILL.md)): Antigravity runs the attacks with `npm run agy:qa -- <area>` (the `qa` job, deep model chain). Claude triages the findings.
- **classic mode**: Claude runs the attacks itself.

## Attack catalogue

Try each that applies to the area:

1. Inputs: empty and whitespace-only; 10,000 characters; emoji, combining marks, right-to-left text.
2. Numbers: 0, negative, huge, decimal, `1e9`, empty.
3. Clicks: double submit, rapid toggles, Esc pressed mid-dialog, clicking behind a dialog.
4. Pasted and malformed URLs: duplicates, `javascript:` and `file:` schemes, ports, credentials, trailing dots.
5. HTML and JS injection in every text field (`<img src=x onerror=...>`, `<script>`): it must show as text and run nothing.
6. Clock jumps and suspend/resume during any timer (change the system or a mocked clock mid-flow).
7. Kill the app mid-flow, then relaunch with the same data.
8. Offline in the middle of a sync, then back online.

Project-specific attacks come from `docs/rules/invariants.md` and the feature docs: try to break each promise and rule that applies to the area.

## Output

- Findings in `docs/qa/<area>-<YYYY-MM-DD>.md`: one entry per finding with the attack, exact repro steps, expected, actual, and severity. List attacks that held up in one line.
- An attack test per finding or per notable attack in `<app>/e2e/<area>.qa.e2e.ts`. They run only in the `qa` project (`npm run e2e:qa`), not in `verify.e2e` or `npm run e2e`.
- Change no application code while attacking.

## After the run

A confirmed bug becomes a normal task in `docs/PLAN.md` (tiered by its surface). Its `*.qa.e2e.ts` test moves into the regular suite, renamed `*.e2e.ts`, once the bug is fixed.
