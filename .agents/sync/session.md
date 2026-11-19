# Session Handoff

- Workflow switcher implemented on feat/workflow-switcher. Preset commits: 7671f1c, 750bb61, 793dcf6, d7ec6c5.
- Antigravity reviewed d7ec6c5. Scoped test follow-up now clears only explicitly covered paths, fallback assignment persists, and reset clears a local pin even with an invalid blueprint.
- The checkout follows classic by default. Run npm run workflow -- list or npm run workflow -- status for presets and ownership.
- Solo presets use the current interactive agent. Tier 3 still needs an independent check before merge.
- For Windows hook fixtures, put Git Bash's sh on PATH for npm verification.
- The blueprint is uninitialized. Wayfinder handles app kickoff, then the approved project rules feed tailor-setup.
- Separate open items from the prior session: investigate slow commit-hook verification and check whether origin needs the GitHub repository rename.
- Open first: docs/ai/workflows.md and docs/specs/archive/2026-11-19-workflow-switcher-plan.md.
