---
name: wayfinder
description: Project kickoff front door. When project-blueprint.json is uninitialized, surfaces the open decisions, then either hands off to brainstorming (no fog) or charts a map of decision tickets in docs/wayfinder/ and resolves them one per session until the project spec is clear. Use at kickoff, or when the user says "wayfinder", "chart a map", or "work the map". Planning only; never writes src/.
version: 1.0.0
---

# Wayfinder (kickoff and decision mapping)

Adapted from Matt Pocock's `wayfinder` skill (MIT, https://github.com/mattpocock/skills), revised for local files and this repo's kickoff flow.

A project too big or too foggy for one session: the way to the **destination** is not visible yet. Wayfinding finds the way by resolving **decision tickets** (questions whose answer is a decision), not by building.

## Hard rules

- **Plan, don't do.** Wayfinder never writes `src/`, never scaffolds, never installs packages. No Notes entry can enable execution. Produce decisions, not deliverables.
- Local markdown only: no GitHub Issues or tracker, no `setup-matt-pocock-skills`, `grilling`, `domain-modeling`, `research`, `prototype`, or `to-spec` skill calls.
- **Refer by name.** Tell the developer a ticket's title (a link wrapping the name), never a bare number or slug.
- **One ticket per session**, except research tickets (run in parallel).
- Never record secrets in a ticket or the map (AGENTS.md rules).

## Concepts

- **Map** (`docs/wayfinder/map.md`) is an *index*, not a store: it gists decisions and links the ticket that holds the detail. A decision lives in one place, its ticket.
- **Fog of war** ("Not yet specified"): in-scope decisions you can see coming but cannot phrase sharply yet. Ticket it when you can state the question precisely, even if you cannot answer it; otherwise leave it as fog. Resolving a ticket graduates fog into new tickets.
- **Out of scope**: work beyond the destination. Never fog, never graduates.
- **Frontier**: tickets that are `open`, have every `blocked_by` ticket `closed`, and are unclaimed.
- **Claim**: set `claimed` in the ticket first, before any work, so parallel sessions skip it.

## Files

`docs/wayfinder/map.md` sections: `## Destination`, `## Notes`, `## Decisions so far` (one line per closed ticket: `- [Title](tickets/NN-slug.md): gist`), `## Not yet specified`, `## Out of scope`. Open tickets are not listed; find them in `tickets/`.

`docs/wayfinder/tickets/NN-<slug>.md`:

```markdown
---
type: grilling        # grilling | prototype | research | task
status: open          # open | closed | out-of-scope
blocked_by: []        # ticket slugs
claimed:              # session/date, empty when free
---
## Question
<the decision this ticket resolves, sized to one session>
```

Resolution adds `## Answer` (research also `## Findings`).

## Mode 1: Kickoff (blueprint `status: "uninitialized"`)

1. **Name the destination.** At kickoff it is always "the project spec".
2. **Breadth-first pass.** Ask the developer what they are building, then show a tagged list of the open decisions, each either *answerable now* or fog tagged `research` (needs outside facts), `prototype` (needs something to react to), `task` (manual work first), or `blocked-by <other decision>`.
3. **Verdict.** Two or more fog items, or any fog item that blocks other decisions: **chart a map**. Exactly one non-blocking fog item: resolve it inline, then brainstorm. Zero fog: no map. The developer may override either way.
4. **No map:** stop and hand off to `superpowers:brainstorming` to produce a spec in `docs/specs/`, then `tailor-setup`.
5. **Map:** write `docs/wayfinder/map.md` (Destination, Notes, empty Decisions so far, fog in Not yet specified, Out of scope) and a ticket file for each sharply specifiable question. Create tickets first, then wire `blocked_by` in a second pass. Fire each `research` ticket as a parallel subagent (Explore or general-purpose) that writes `## Findings` into the ticket; no branch.
6. **Stop.** Charting is one session. Update `.agents/sync/session.md` naming the first frontier ticket, and tell the developer to start a new session.

## Mode 2: Work (`docs/wayfinder/map.md` exists)

1. Load `map.md` only (low resolution); open other tickets on demand.
2. Pick the ticket the developer named, else the first frontier ticket. **Claim it.**
3. Resolve by type:
   - **grilling** (HITL): inline Q&A, one question at a time, recommending an answer for each. The agent never answers for the human.
   - **research** (AFK): a subagent reads docs, APIs, or local resources and writes `## Findings`; you distil the `## Answer`.
   - **prototype** (HITL): build cheap throwaway variants under `docs/wayfinder/prototypes/`. **The developer picks, never the agent.** Do not choose a variant and close the ticket.
   - **task**: do what you can; give the developer a precise checklist for the rest; record resulting facts (locations and URLs, never secrets).
4. Write `## Answer`, set `status: closed`, append one line to Decisions so far.
5. Graduate fog the answer made specifiable into new tickets (create, then wire), clearing it from Not yet specified. A ticket found to sit past the destination: set `status: out-of-scope` and add one line to Out of scope (gist and why). Update or delete tickets the decision invalidated.
6. Update `.agents/sync/session.md` with the next frontier ticket, then stop.

## Exit

No open tickets and no fog left: collapse Decisions so far (reading the tickets for detail) into `docs/specs/YYYY-MM-DD-<project>-design.md`, move `docs/wayfinder/` to `docs/specs/archive/wayfinder-<date>/`, and hand off to `tailor-setup`.

---

Credit: concept and structure by Matt Pocock (MIT License), https://github.com/mattpocock/skills.
