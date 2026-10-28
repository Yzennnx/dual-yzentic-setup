# Rules

The design of this project lives here, split by feature. Read [`invariants.md`](invariants.md) and the one feature doc your task names (about 150 lines together), not everything.

## Mission

_Replace: one or two sentences on what this project is for and who uses it._

## Principles

1. **One owner per file.** Each feature doc lists the code it owns in its `owns:` front matter; `architecture.md` owns the cross-cutting files.
2. **Docs change with code.** `npm run rules:check` fails verify when an owned file changes without its doc, when a new source file has no owner, and when a changed rule has no test citing its ID.
3. **Rule IDs never change.** `[feature#3]` stays `[feature#3]`; a deleted rule leaves a gap and a new rule takes the next number. `(manual)` marks a rule only a hand test can prove.
4. **Tests cite rules.** A test name or a `// covers feature#3` comment links a test to its rule.

## Layout

| File | What it holds |
| :--- | :--- |
| [`invariants.md`](invariants.md) | Promises that must never break (`inv#1`, `inv#2`, ...) |
| [`architecture.md`](architecture.md) | Stack, apps, how they talk, data model, conventions, testing |
| `features/<feature>.md` | One per feature: what the user sees, rules, how it works, limits ([`_example.md`](features/_example.md) shows the format) |

## Feature map

`npm run rules:map` regenerates this table; `npm run rules:map -- <feature>` prints one feature.

<!-- rules:map -->
| Feature | Doc | Tasks open/done | Boards | Rules | With a test |
| --- | --- | --- | --- | --- | --- |
<!-- /rules:map -->
