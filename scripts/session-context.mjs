#!/usr/bin/env node

/**
 * session-context.mjs
 * Claude Code SessionStart hook: injects the session handoff, the blueprint status, and the
 * tier rules, so a new session starts from them without having to be told to read anything.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..');

const MAX_HANDOFF_LINES = 40;

function readText(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf-8');
  } catch {
    return null;
  }
}

function blueprintLine(root) {
  const raw = readText(path.resolve(root, 'project-blueprint.json'));
  if (raw === null) return 'Blueprint: project-blueprint.json not found.';
  try {
    const status = JSON.parse(raw).status;
    if (status === 'initialized') return 'Blueprint: initialized.';
    return `Blueprint: ${status ?? 'unknown'}. Before writing project code, ask what the developer is building, `
      + 'then use the tailor-setup skill (a spec exists) or `npm run init:project` (an archetype fits).';
  } catch {
    return 'Blueprint: project-blueprint.json is not valid JSON.';
  }
}

function handoffBlock(root) {
  const raw = readText(path.resolve(root, '.agents', 'sync', 'session.md'));
  if (raw === null || raw.trim().length === 0) {
    return 'No session handoff recorded (.agents/sync/session.md is missing or empty).';
  }
  const lines = raw.trimEnd().split(/\r?\n/);
  if (lines.length <= MAX_HANDOFF_LINES) return lines.join('\n');
  return [
    ...lines.slice(0, MAX_HANDOFF_LINES),
    `... [truncated ${lines.length - MAX_HANDOFF_LINES} lines; the handoff should stay under 20]`
  ].join('\n');
}

/**
 * The Orca repo id from blueprint workflow.orca_repo_id, or '' when unset or unreadable.
 */
export function orcaRepoId(root) {
  try {
    return JSON.parse(readText(path.resolve(root, 'project-blueprint.json'))).workflow?.orca_repo_id ?? '';
  } catch {
    return '';
  }
}

/**
 * One line per in-review Orca worktree of this repo, from `orca worktree list --json` output.
 * Empty for bad JSON, ok:false, no repo id, or no in-review cards.
 */
export function parseReadyToMerge(stdout, repoId) {
  if (!repoId) return [];
  try {
    const parsed = JSON.parse(stdout);
    if (parsed?.ok === false) return [];
    return (parsed?.result?.worktrees ?? [])
      .filter(wt => wt.repoId === repoId && wt.workspaceStatus === 'in-review')
      .map(wt => `${String(wt.branch ?? '').replace(/^refs\/heads\//, '')} @ ${String(wt.head ?? '').slice(0, 7)}: ${wt.comment ?? ''}`);
  } catch {
    return [];
  }
}

function readyToMergeBlock(root) {
  const repoId = orcaRepoId(root);
  if (!repoId) return [];
  // A missing CLI, a stopped Orca or a timeout all leave the exit status non-zero or an error set
  const run = spawnSync('orca', ['worktree', 'list', '--json'], { encoding: 'utf-8', timeout: 3000, shell: true });
  if (run.error || run.status !== 0) return [];
  const lines = parseReadyToMerge(run.stdout, repoId);
  return lines.length > 0 ? ['', 'Ready to merge:', ...lines.map(line => `- ${line}`)] : [];
}

export function buildContext(root = REPO_ROOT) {
  return [
    'Project session context (injected by .claude/settings.json):',
    blueprintLine(root),
    'Process by tier (the surface sets the tier, not the size): Tier 1 = fast-track only, no documents or agents. '
      + 'Tier 2 = no risky surface: design in chat, wait for a yes, no spec or plan file, no review. '
      + 'Tier 3 = a risky surface (schema, sync, shared domain rules, API, auth, app interfaces): design in chat ending '
      + 'with tasks that name their tests, one yes, save it unchanged as the plan, one builder run, '
      + '`npm run review` once, merge into local main.',
    'Tests: never run a full suite directly; use `npm run verify:agent`. '
      + 'Start from the handoff below and open only the files it lists.',
    '',
    '--- .agents/sync/session.md ---',
    handoffBlock(root),
    ...readyToMergeBlock(root)
  ].join('\n');
}

export function main() {
  const args = process.argv.slice(2);
  const rootIndex = args.indexOf('--root');
  const root = rootIndex !== -1 && args[rootIndex + 1] ? path.resolve(args[rootIndex + 1]) : REPO_ROOT;

  let additionalContext;
  try {
    additionalContext = buildContext(root);
  } catch (err) {
    additionalContext = `Project session context unavailable: ${err.message}`;
  }

  console.log(JSON.stringify({ hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext } }));
}

// Execute if run directly
if (process.argv[1] && path.resolve(process.argv[1]) === __filename) {
  main();
}
