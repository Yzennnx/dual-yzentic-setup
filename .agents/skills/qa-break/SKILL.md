---
name: qa-break
description: Attack one area of the app to find bugs, using Luna's attack catalogue, and record findings with repro steps plus Playwright attack tests. Use when the user invokes /qa-break <area> or asks to try to break, fuzz or stress an area (Lists, Start, Schedule, Settings, intro, sync).
version: 1.0.0
---

# QA Break Skill (Attack One Area)

Builds on [`webapp-testing`](../webapp-testing/SKILL.md) for driving the app. Input: one area, for example `lists` or `session-start`. Test the built desktop app through the existing Playwright launcher in `apps/desktop/e2e/launch.ts`; add extension or phone attacks only where an e2e launcher exists.

## Who runs it

- **agy-build mode** ([`workflow`](../workflow/SKILL.md)): Antigravity runs the attacks with `npm run agy:qa -- <area>` (the `qa` job, deep model chain). Claude triages the findings.
- **classic mode**: Claude runs the attacks itself.

## Attack catalogue

Try each that applies to the area:

1. Empty and whitespace-only input; leading and trailing spaces.
2. 10,000 characters in every text box and name.
3. Emoji, combining marks, and right-to-left text.
4. HTML and JS in names (`<img src=x onerror=...>`, `<script>`): the Electron renderer must show it as text and run nothing.
5. Number boxes: 0, negative, huge, decimal, `1e9`, empty.
6. Double submit, rapid toggles, Esc pressed mid-dialog, clicking behind a dialog.
7. Pasted duplicate sites and programs; malformed URLs; `javascript:` and `file:` URLs; links with ports, credentials and trailing dots.
8. Clock jumps and suspend/resume during a session timer (change the system or mocked clock mid-session).
9. Kill the app mid-session, then relaunch with the same data folder.
10. Offline in the middle of a sync, then back online.

## Output

- Findings in `docs/qa/<area>-<YYYY-MM-DD>.md`: one entry per finding with the attack, exact repro steps, expected, actual, and severity. List attacks that held up in one line.
- An attack test per finding or per notable attack in `apps/<app>/e2e/<area>.qa.e2e.ts`. They run in the separate Playwright `qa` project with `npm run e2e:qa`. They are not part of `verify.e2e` or `npm run e2e`.
- Change no application code while attacking.

## After the run

A confirmed bug becomes a normal task in `docs/PLAN.md` (tiered by its surface). Its `*.qa.e2e.ts` test moves into the regular suite, renamed `*.e2e.ts`, once the bug is fixed.
