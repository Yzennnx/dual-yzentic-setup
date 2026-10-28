/**
 * roadmap.mjs
 * Renders the living roadmap (docs/PLAN.md) from project info and a task list.
 */

const PRIORITY_SECTIONS = [
  { priority: 'P0', heading: 'P0: Must-Have' },
  { priority: 'P1', heading: 'P1: Should-Have' },
  { priority: 'P2', heading: 'P2: Later' }
];

const oneLine = (text) => String(text ?? '').replace(/\s+/g, ' ').trim();

function renderTask(task) {
  const tags = (task.features ?? []).map(feature => ` [${oneLine(feature)}]`).join('');
  return `- [ ] **Task ${oneLine(task.id)}${tags}: ${oneLine(task.title)}**
  - **Priority:** ${task.priority}
  - **Status:** Backlog
  - **Description:** ${oneLine(task.description)}
`;
}

function renderSection({ priority, heading }, tasks) {
  const matching = tasks.filter(task => task.priority === priority);
  const body = matching.length > 0 ? matching.map(renderTask).join('\n') : 'None yet.\n';
  return `## ${heading}\n\n${body}`;
}

/**
 * Generate fresh living roadmap.
 * tasks: [{ id, title, priority: 'P0'|'P1'|'P2', description, features? }]; features render as [tag] after the id
 */
export function generateRoadmap({ name, desc, developer = 'the developer', preset, tasks = [] }) {
  const dateStr = new Date().toISOString().split('T')[0];
  const sections = PRIORITY_SECTIONS.map(section => renderSection(section, tasks)).join('\n---\n\n');

  return `# Universal Living Roadmap & Feature Plan: ${name}

> **For ${developer} and the AI agents:** This document is the single source of truth for the project. No feature is implemented without an entry here. Keep it updated after every completed task.

- **Project:** ${name}
- **Objective:** ${desc}
- **Archetype:** ${preset}
- **Last Synchronized:** ${dateStr}
- **Verification:** [\`scripts/baton.mjs\`](../scripts/baton.mjs) via \`npm run verify:agent\`

---

## Mission & Objective

${desc}

---

## Rules for Adding Features

1. **Log it first:** Add every new idea below with a Priority and the status \`[ ] Backlog\` before any code is written.
2. **Priorities:**
   - **\`P0\` (Must-Have):** Required for the core user journey to work.
   - **\`P1\` (Should-Have):** Improves the core journey: polish, seed data, secondary flows.
   - **\`P2\` (Later):** Parked until P0 and P1 are done.
3. **One task at a time:** Finish, verify with \`npm run verify:agent\`, and commit a task before starting the next.

---

## Current Focus

Active milestone: **Core scaffolding and first feature loop**

---

${sections}`;
}
