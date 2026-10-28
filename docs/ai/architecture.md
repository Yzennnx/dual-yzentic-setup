# System Architecture & Design Principles

This document defines the architectural guidelines and boundaries for `Yzentic-setup`.

---

## 1. Modular Decomposition Principles

To maintain high reasoning reliability and prevent context window exhaustion:
- **Single Responsibility Principle (SRP):** Each file, class, and skill should possess one unambiguous purpose.
- **Focused File Size:** Files should strive to stay under 300 lines of code. When a file exceeds this boundary, decompose it into sub-modules or helper components.
- **Decoupled Interfaces:** Components must communicate via well-defined contracts and avoid tight coupling to concrete implementations.

---

## 2. Specification & Implementation Lifecycle

All architectural changes progress through four formal stages:

```text
Requirement / Idea
       │
       ▼
1. Design with the task list (agreed with the developer in chat)
       │
       ▼
2. Human Review Gate (One Approval, in chat)
       │
       ▼
3. The approved design saved as the plan (`docs/specs/YYYY-MM-DD-<name>-plan.md`)
       │
       ▼
4. Builder Delivery, Gatekeeper Tests & Verification Gate
```

---

## 3. Directory Layout Standards

- `AGENTS.md`: Universal rule root.
- `.agents/skills/`: On-demand, self-contained procedural skills (`<skill>/SKILL.md`).
- `.agents/skills/_staging/`: Isolated staging gate for unverified scrape artifacts.
- `docs/ai/`: Agent operational guides, workflows, and architecture.
- `docs/rules/`: The project's design: invariants, architecture and one doc per feature, each owning its code paths (`npm run rules:check`).
- `docs/specs/`: Approved technical specs and plans.
- `tests/`: Automated unit and integration test suites. Script tests run against temp fixture repos, never this one.
- `scripts/`: The baton, the Antigravity launcher, and the scout, review, tailor, and init commands.
- `.agents/sync/`: `session.md` (committed handoff) plus local, uncommitted baton and Gatekeeper state.
- `.claude/`: The `builder` agent and the session and command-guard hooks.

---

## 4. Model Context Protocol (MCP) Integrations

Agents and IDEs can integrate external documentation scrapers and live toolsets via standard MCP configurations:

### Skill Seekers MCP Server
Enables live tool-calling (`scrape_docs`, `analyze_repo`, `generate_skill`) during interactive agent sessions:

- **Claude Code CLI:**
  ```bash
  claude mcp add skill-seekers -- uvx skill-seekers mcp
  ```

- **Cursor / Windsurf / Antigravity (`mcp.json`):**
  ```json
  {
    "mcpServers": {
      "skill-seekers": {
        "command": "uvx",
        "args": ["skill-seekers", "mcp"]
      }
    }
  }
  ```

