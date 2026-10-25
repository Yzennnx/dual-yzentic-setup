# Session Handoff

- **Done:** Wayfinder is now the kickoff front door. `.agents/skills/wayfinder/SKILL.md` is adapted from mattpocock/skills (MIT). Merged to `main` and pushed (`621d1f9`).
- **How kickoff works now:**
  - The blueprint is uninitialized, so run wayfinder in kickoff mode. It does a breadth-first pass and tags each open decision as answerable now or fog (research, prototype, task, blocked-by).
  - Two or more fog items, or one that blocks other decisions, means it charts a map in `docs/wayfinder/` (`map.md` plus `tickets/NN-<slug>.md`). Otherwise it hands off to brainstorming, then a spec, then `tailor-setup`.
  - One ticket per session. When the map is clear, the decisions collapse into `docs/specs/<date>-<project>-design.md`, the map is archived, and `tailor-setup` runs.
  - `npm run init:project` is still the shortcut when the stack is known.
- **Decisions:**
  - Tracker is local markdown, not GitHub Issues.
  - The upstream "Notes may enable execution" override is removed: wayfinder never writes to `src/`.
  - For prototypes, the developer picks the variant.
- **Open:**
  - `ALWAYS_KEPT_SKILLS` in `scripts/tailor.mjs` does not include wayfinder, so `tailor` may archive it after kickoff. Fine for kickoff only; add it if wayfinder should also be used for big features mid-project.
  - The commit-hook baton took 15 to 20 minutes per commit on the builder's two commits (measured 56 s before). Investigate.
  - GitHub says the repo moved to `Yzennnx/dual-yzentic-setup`. Update `origin`.
  - No project has been started yet.
- **Open these first:** `.agents/skills/wayfinder/SKILL.md`, `CLAUDE.md`.
