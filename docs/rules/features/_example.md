---
owns:
  - src/session*.ts
  - src/pages/Session*.tsx
---
# Sessions

_Sample only: files starting with `_` are skipped by the checks. Copy this shape for each real feature._

## What the user sees
Plain words, 5-15 lines, no code names. The user picks a length, presses Start, and sees a countdown. A break shows when the length is reached.

## Rules
- [sessions#1] A session has a target length between 10 and 240 minutes.
- [sessions#2] A break cannot be skipped.
- [sessions#3] (manual) The countdown stays readable on a small screen.

## How it works
Data flow, file by file: Start button -> SessionStart.tsx -> bridge -> main/session.ts -> db.

## Limits and out of scope
No shared sessions between users.
