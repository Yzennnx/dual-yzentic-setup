# Invariants

Promises that must never break. Every feature doc and every change is checked against these. Number them `inv#1`, `inv#2`, ...; IDs never change. Keep this file near 30 lines.

_Replace the three examples below at kickoff._

- [inv#1] User data is never lost silently: a failed write is reported and the previous state stays intact.
- [inv#2] Secrets (keys, tokens, passwords) never appear in logs, errors, or committed files.
- [inv#3] Every input from outside the app (forms, URLs, files, network) is validated before it is used.
