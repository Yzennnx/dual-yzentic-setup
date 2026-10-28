#!/usr/bin/env node

/**
 * Scout command (scripts/scout.mjs)
 * Asks Antigravity, read only, which files a task touches and which patterns to follow.
 * Usage: node scripts/scout.mjs [--root <path>] "<task>"
 */

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { launchAgy, appendDelegation, describeFailure, PLAIN_PATHS_RULE } from './agy.mjs';
import { snapshotChanges, checkScope } from './changes.mjs';
import { readSyncState, writeSyncState, syncPaths } from './baton.mjs';

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const USAGE = 'Usage: node scripts/scout.mjs [--root <path>] "<task>"';

/**
 * Split argv into the repo root and the task text; every word that is not `--root <path>` is task text.
 */
function parseArgs(args) {
  let root = REPO_ROOT;
  const words = [];
  for (let i = 0; i < args.length; i++) {
    if (args[i] !== '--root') {
      words.push(args[i]);
      continue;
    }
    const value = args[++i];
    if (!value || value.startsWith('--')) return { error: '[Scout] --root requires a path' };
    root = resolve(value);
  }
  return { root, task: words.join(' ').trim() };
}

/**
 * The blueprint's project.source_rules (or the old source_spec), or null when there is no blueprint or no spec.
 */
function readSourceSpec(root) {
  try {
    return ((project) => project?.source_rules || project?.source_spec)(JSON.parse(readFileSync(resolve(root, 'project-blueprint.json'), 'utf-8')).project) || null;
  } catch {
    return null;
  }
}

function buildPrompt(task, spec) {
  const docs = spec ? `docs/PLAN.md and ${spec}` : 'docs/PLAN.md';
  return [
    `Scout this task for the engineer who will implement it: ${task}`,
    `Read ${docs} for context.`,
    'Answer in at most 40 lines with no introduction. Cover:',
    '- the files to change',
    '- the files to read first',
    '- for each file, the function or line range and one line on why',
    '- the existing patterns to follow',
    'Read only. Edit nothing. Run nothing.',
    PLAIN_PATHS_RULE
  ].join('\n');
}

/**
 * Add the launch to the repo's delegation log in handoff.json.
 */
function recordLaunch(root, entry) {
  const { json } = syncPaths(root);
  mkdirSync(dirname(json), { recursive: true });
  const state = readSyncState(json);
  appendDelegation(state, entry);
  writeSyncState(state, json);
}

/**
 * CLI Entry point
 */
export async function main() {
  const { root, task, error } = parseArgs(process.argv.slice(2));
  if (error) {
    console.error(error);
    process.exitCode = 1;
    return;
  }
  if (!task) {
    console.error(USAGE);
    process.exitCode = 1;
    return;
  }

  const before = snapshotChanges(root);
  const result = launchAgy({ job: 'scout', prompt: buildPrompt(task, readSourceSpec(root)), root });
  const { outOfScope } = checkScope(before, snapshotChanges(root));
  recordLaunch(root, result.entry);

  if (outOfScope.length > 0) {
    console.error('[Scout] Antigravity changed files during a read-only launch:');
    for (const path of outOfScope) console.error(`  ${path}`);
    process.exitCode = 1;
    return;
  }
  if (!result.ok) {
    console.log(`[Scout] Antigravity unavailable (${describeFailure(result.reason, result.detail)}).`);
    return;
  }

  const briefPath = resolve(root, '.agents/sync/scout.md');
  mkdirSync(dirname(briefPath), { recursive: true });
  writeFileSync(briefPath, result.response.endsWith('\n') ? result.response : `${result.response}\n`, 'utf-8');
  console.log(result.response);
}

// Auto-run if executed directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch(err => {
    console.error('[Scout] Unexpected error:', err);
    process.exit(1);
  });
}
