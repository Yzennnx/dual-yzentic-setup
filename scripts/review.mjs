#!/usr/bin/env node

/**
 * Review command (scripts/review.mjs)
 * Asks Antigravity, read only, to review the branch diff against the spec and plan.
 * Usage: node scripts/review.mjs [--base <ref>] [--spec <path>] [--plan <path>] [--root <path>]
 */

import { execFileSync } from 'node:child_process';
import { readFileSync, readdirSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve, relative, dirname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { launchAgy, appendDelegation, describeFailure, PLAIN_PATHS_RULE } from './agy.mjs';
import { snapshotChanges, checkScope } from './changes.mjs';
import { readSyncState, writeSyncState, syncPaths } from './baton.mjs';

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const USAGE = 'Usage: node scripts/review.mjs [--base <ref>] [--spec <path>] [--plan <path>] [--root <path>]';
const FLAGS = ['--base', '--spec', '--plan', '--root'];
const DIFF_FILE = '.agents/sync/review.diff';

/**
 * Read the four `--flag <value>` options; anything else is an error.
 * `npm run review --base x` (no `--`) is swallowed by npm and arrives as npm_config_base, so the environment
 * fills in --base, --spec and --plan when their flags are absent.
 */
function parseArgs(args) {
  const options = { root: REPO_ROOT, base: null, spec: null, plan: null };
  for (let i = 0; i < args.length; i++) {
    const value = args[i + 1];
    if (!FLAGS.includes(args[i])) return { error: `[Review] Unknown argument: ${args[i]}\n${USAGE}` };
    if (!value || value.startsWith('--')) return { error: `[Review] ${args[i]} requires a value` };
    options[args[i].slice(2)] = value;
    i++;
  }
  for (const name of ['base', 'spec', 'plan']) {
    options[name] ??= process.env[`npm_config_${name}`] || null;
  }
  options.root = resolve(options.root);
  return options;
}

/**
 * Stdout of a git command, or null when git fails.
 */
function gitOut(root, args) {
  try {
    return execFileSync('git', args, { cwd: root, encoding: 'utf-8', stdio: ['ignore', 'pipe', 'ignore'], maxBuffer: 256 * 1024 * 1024 });
  } catch {
    return null;
  }
}

/**
 * The commit to diff from: the merge base with main, else HEAD~1, else null (a repo with one commit or none).
 */
function defaultBase(root) {
  const mergeBase = gitOut(root, ['merge-base', 'HEAD', 'main'])?.trim();
  if (mergeBase && mergeBase !== gitOut(root, ['rev-parse', 'HEAD'])?.trim()) return mergeBase;
  return gitOut(root, ['rev-parse', '--verify', '--quiet', 'HEAD~1']) ? 'HEAD~1' : null;
}

/**
 * A path as the prompt shows it: relative to the repo root, with forward slashes.
 */
function repoPath(root, path) {
  return relative(root, resolve(root, path)).split(sep).join('/');
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

/**
 * The lexically last docs/specs/*-plan.md, or null when there is none.
 */
function lastPlan(root) {
  try {
    const plans = readdirSync(resolve(root, 'docs/specs')).filter(name => name.endsWith('-plan.md')).sort();
    return plans.length > 0 ? `docs/specs/${plans[plans.length - 1]}` : null;
  } catch {
    return null;
  }
}

function buildPrompt(base, spec, plan) {
  return [
    `Review the changes in ${DIFF_FILE} (git diff ${base}..HEAD).`,
    ...(spec ? [`Spec: ${spec}`] : []),
    ...(plan ? [`Plan: ${plan}`] : []),
    'Report findings under three headings, in this order: Critical, Important, Minor.',
    'For each finding give the file and line, what is wrong, and why it matters.',
    'Give line numbers from the file itself, not positions in the diff file.',
    'End with a one-line verdict. Answer in at most 60 lines.',
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
  const options = parseArgs(process.argv.slice(2));
  if (options.error) {
    console.error(options.error);
    process.exitCode = 1;
    return;
  }
  const { root } = options;

  const base = options.base ?? defaultBase(root);
  const diff = base ? gitOut(root, ['diff', `${base}..HEAD`]) : '';
  if (diff === null) {
    console.error(`[Review] git diff ${base}..HEAD failed. Is "${base}" a valid ref?`);
    process.exitCode = 1;
    return;
  }
  if (!diff.trim()) {
    console.log('[Review] Nothing to review.');
    return;
  }

  console.log(`[Review] Reviewing ${base}..HEAD`);
  const diffPath = resolve(root, DIFF_FILE);
  mkdirSync(dirname(diffPath), { recursive: true });
  writeFileSync(diffPath, diff, 'utf-8');

  const specPath = options.spec ?? readSourceSpec(root);
  const planPath = options.plan ?? lastPlan(root);
  const prompt = buildPrompt(
    base,
    specPath && repoPath(root, specPath),
    planPath && repoPath(root, planPath)
  );

  const before = snapshotChanges(root);
  const result = launchAgy({ job: 'review', prompt, root });
  const { outOfScope } = checkScope(before, snapshotChanges(root));
  recordLaunch(root, result.entry);

  if (outOfScope.length > 0) {
    console.error('[Review] Antigravity changed files during a read-only launch:');
    for (const path of outOfScope) console.error(`  ${path}`);
    process.exitCode = 1;
    return;
  }
  if (!result.ok) {
    console.error(`[Review] Antigravity unavailable (${describeFailure(result.reason, result.detail)}).`);
    process.exitCode = 1;
    return;
  }

  writeFileSync(resolve(root, '.agents/sync/review.md'), result.response.endsWith('\n') ? result.response : `${result.response}\n`, 'utf-8');
  console.log(result.response);
}

// Auto-run if executed directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch(err => {
    console.error('[Review] Unexpected error:', err);
    process.exit(1);
  });
}
