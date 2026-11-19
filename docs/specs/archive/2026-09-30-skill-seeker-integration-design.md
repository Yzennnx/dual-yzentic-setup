# Design Specification: Skill Seeker Integration (On-Demand Knowledge Ingestion & Staging Pipeline)

- **Date:** 2026-09-30
- **Status:** Proposed (Brainstormed)
- **Execution Tier:** Tier 3 (Architectural Deep Lane)
- **Target Subsystem:** Universal Agent Skills & Workflow Ingestion

---

## 1. Executive Summary & Context

`Yzentic-setup` provides an AI-driven development environment with 20 modular domain skills, standardized operational gates, and tiered execution lanes. Currently, the repository relies on static domain skills authored in [`.agents/skills/`](../../../.agents/skills/) and external discovery via [`find-skills`](../../../.agents/skills/find-skills/SKILL.md) (which searches pre-built packages on `skills.sh`).

When developers adopt bleeding-edge frameworks (e.g. Next.js canary, new state managers), private internal company SDKs, or complex architectural PDF specifications, AI agents encounter knowledge cutoffs or lack specific domain knowledge, leading to API hallucinations and token waste.

This specification introduces **Skill Seeker** (`yusufkaraaslan/Skill_Seekers`) into `Yzentic-setup` through a **Hybrid Pipeline**:
1. An on-demand domain skill ([`.agents/skills/skill-seeker/`](../../../.agents/skills/skill-seeker/)) powered by an ephemeral `uvx` CLI runner (zero root repository dependency bloat).
2. A safe staging gate ([`.agents/skills/_staging/`](../../../.agents/skills/_staging/)) with automated frontmatter and link compliance validation before catalog promotion.
3. Integration with the existing meta-skills ([`find-skills`](../../../.agents/skills/find-skills/SKILL.md) and [`skill-creator`](../../../.agents/skills/skill-creator/SKILL.md)).
4. Model Context Protocol (MCP) server configuration guides for live tool-calling in Cursor, Claude Code, and Antigravity.

---

## 2. Architectural Design & Components

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        INGESTION SOURCES                               │
│      Documentation URL       GitHub Repo (AST)       Technical PDF     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│             .agents/skills/skill-seeker/scripts/seek.py                 │
│              (Executed non-interactively via uvx)                      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  STAGING GATE (.agents/skills/_staging/)               │
│  - Raw output: SKILL.md + references/                                  │
│  - Compliance check: YAML frontmatter, valid description, links        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                         python seek.py --promote <name>
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 ACTIVE CATALOG (.agents/skills/<name>/)                │
│  - Promoted skill active for all agents                                │
│  - Auto-registered in docs/ai/agent-handbook.md                        │
│  - Validated by tests/test_skills_structure.py                         │
└────────────────────────────────────────────────────────────────────────┘
```

### Component 1: Domain Skill Package (`.agents/skills/skill-seeker/`)
- **[`SKILL.md`](../../../.agents/skills/skill-seeker/SKILL.md):** Defines skill metadata, triggers (`ingest docs`, `create skill from repo`, `parse api pdf`, `skill seeker`), operational instructions, and safety rules.
- **[`scripts/seek.py`](../../../.agents/skills/skill-seeker/scripts/seek.py):** Orchestration CLI tool:
  - Invokes `skill-seekers` via `uvx --from skill-seekers skill-seekers`.
  - Arguments:
    - `--url <url>`: Target documentation website.
    - `--repo <owner/repo>`: GitHub repository for AST analysis.
    - `--pdf <path>`: Local PDF file.
    - `--name <skill-name>`: Identifier for the generated skill.
    - `--promote <skill-name>`: Validates and promotes a staged skill into active [`.agents/skills/`](../../../.agents/skills/).
    - `--list-staged`: Lists all draft skills currently in `_staging/`.

### Component 2: Staging Area & Compliance Validator
- **Directory:** [`.agents/skills/_staging/`](../../../.agents/skills/_staging/)
- **Isolation:** Staged skills are ignored by the standard test suite and git tracking (via `.gitignore` rule `.agents/skills/_staging/*` with `!.agents/skills/_staging/.gitkeep`).
- **Validation Rules (Enforced by `seek.py` prior to promotion):**
  1. `SKILL.md` must exist and contain valid YAML frontmatter between `---` delimiters.
  2. YAML frontmatter must include non-empty `name:` and `description:` keys.
  3. `description:` must be clear and contain trigger phrases.
  4. All internal Markdown links must use valid relative links or `file://` scheme.
  5. The target directory name must match `name:` in `SKILL.md`.

### Component 3: Meta-Skill Routing & Workflows
- **[`find-skills`](../../../.agents/skills/find-skills/SKILL.md):** Updated to add `skill-seeker` as the automated fallback when `npx skills find` yields no results.
- **[`skill-creator`](../../../.agents/skills/skill-creator/SKILL.md):** Can be run against any promoted skill to author evaluation test cases and benchmark triggering accuracy.
- **[`docs/ai/agent-handbook.md`](../../ai/agent-handbook.md):** Added to the domain skills quick-selection table under *"On-demand documentation ingestion & skill synthesis"*.

### Component 4: MCP Server Configuration
- In [`docs/ai/architecture.md`](../../ai/architecture.md), document standard MCP configuration snippets for assistants:
  - **Claude Code CLI:** `claude mcp add skill-seekers -- uvx skill-seekers mcp`
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

### Component 5: Test Suite & Documentation Verification
- **[`tests/test_skills_structure.py`](../../../tests/test_skills_structure.py):**
  - Update expected skill count to 21 (20 existing + `skill-seeker`).
  - Add `"skill-seeker"` to `required_skills`.
  - Add explicit test asserting `.agents/skills/_staging` is excluded from the domain skills catalog count.
- **Inventory Updates:**
  - Update skill count in [`AGENTS.md`](../../../AGENTS.md) and [`README.md`](../../../README.md) to 21.

---

## 3. Data Flow & Execution Scenarios

### Ingestion Data Flow
1. **User Request:** Agent is asked to build a feature with an unfamiliar library or internal SDK.
2. **Execution:** Agent runs:
   ```bash
   python .agents/skills/skill-seeker/scripts/seek.py --url https://docs.example.com --name example-lib
   ```
3. **Extraction & Packaging:**
   - `uvx` launches `skill-seekers` in an ephemeral environment.
   - `skill-seekers` scrapes pages, analyzes code snippets, and generates:
     - `.agents/skills/_staging/example-lib/SKILL.md`
     - `.agents/skills/_staging/example-lib/references/*.md`
4. **Validation & Promotion:**
   - Agent or user inspects the staged skill.
   - Run promotion:
     ```bash
     python .agents/skills/skill-seeker/scripts/seek.py --promote example-lib
     ```
   - Script validates frontmatter, moves folder to `.agents/skills/example-lib/`, updates `docs/ai/agent-handbook.md`, and runs the test suite.

---

## 4. Error Handling & Edge Cases

| Failure Mode | Root Cause | Handling Strategy |
| :--- | :--- | :--- |
| **Network Timeout / 403 Forbidden** | Doc site blocks scraping or connection drops | Script captures stderr, exits with code 1, and suggests supplying local HTML or PDF instead. |
| **Name Collision** | Target skill name already exists in active `.agents/skills/` | Promotion aborts with warning unless `--force` is explicitly provided. |
| **Invalid Frontmatter Generated** | Scraped source lacks structure for clean description | Validator flags missing/empty fields and outputs exact line errors for agent correction. |
| **Missing `uvx` Runtime** | System lacks `uv` package manager | Script falls back to checking `python3 -m pip install skill-seekers` in a virtualenv or outputs clear installation guidance. |

---

## 5. Security & Secret Exposure Guardrails

1. **GitHub Token Handling:** When scraping private GitHub repositories via `--repo`, the script reads `GITHUB_TOKEN` from the environment; it NEVER echoes, logs, or writes tokens to files.
2. **Untrusted Code Execution:** Scraped code snippets are treated strictly as documentation and reference markdown—never executed directly.
3. **No Secret Leaks:** In accordance with repository core tenets, generated skills undergo automated scans to ensure no API keys or credentials from doc pages are committed.

---

## 6. Implementation Stages & Verification Gates

- **Phase 1: Foundation & Staging Scaffold**
  - Create `.agents/skills/_staging/.gitkeep` and update `.gitignore`.
  - Create `.agents/skills/skill-seeker/scripts/seek.py` with CLI argument parsing, `uvx` runner, and validation logic.
- **Phase 2: Skill Definition & Procedural Documentation**
  - Author `.agents/skills/skill-seeker/SKILL.md`.
  - Update `docs/ai/agent-handbook.md` and `docs/ai/architecture.md` (MCP guide).
  - Update fallback instructions in `.agents/skills/find-skills/SKILL.md`.
- **Phase 3: Test Suite & Documentation Updates**
  - Update `tests/test_skills_structure.py` for 21 domain skills and staging exclusion.
  - Update skill inventory in `AGENTS.md` and `README.md`.
- **Phase 4: End-to-End Sanity Verification**
  - Run `python3 -m unittest discover tests -v` (confirm clean exit code 0).
  - Run a dry-run test of `seek.py --help` and `seek.py --list-staged`.
