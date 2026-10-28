#!/usr/bin/env node

/**
 * Antigravity build and QA jobs (scripts/agy-build.mjs)
 * agy-build mode: Antigravity implements the tasks of a plan or design on the current branch, writes the tests the
 * tasks name and commits one per task. When the branch added or reworded rules in docs/rules, a `rule-tests` job runs first
 * and writes one test per rule from the rule text alone. The same launcher runs the QA attack job for one area.
 * Usage:
 *   node scripts/agy-build.mjs [--root <path>] --plan <file> --tasks <list>
 *   node scripts/agy-build.mjs [--root <path>] --design <file>
 *   node scripts/agy-build.mjs [--root <path>] --qa <area>
 */

import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { launchAgy, appendDelegation, describeFailure, PLAIN_PATHS_RULE } from './agy.mjs';
import { readSyncState, writeSyncState, syncPaths } from './baton.mjs';
import { gitChange, changedRules, ruleTestLines } from './rules-check.mjs';

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const USAGE = 'Usage: node scripts/agy-build.mjs [--root <path>] (--plan <file> --tasks <list> | --design <file> | --qa <area>)';

/**
 * Read `--root`, `--plan`, `--tasks`, `--design` and `--qa` from argv.
 */
export function parseArgs(args) {
  const out = { root: REPO_ROOT };
  const flags = { '--root': 'root', '--plan': 'plan', '--tasks': 'tasks', '--design': 'design', '--qa': 'qa' };
  for (let i = 0; i < args.length; i++) {
    const key = flags[args[i]];
    const value = args[i + 1];
    if (!key) return { error: `Unknown argument ${args[i]}\n${USAGE}` };
    if (!value || value.startsWith('--')) return { error: `${args[i]} requires a value` };
    out[key] = key === 'root' ? resolve(value) : value;
    i++;
  }
  if (out.qa) return out.plan || out.design ? { error: USAGE } : out;
  if (out.design && !out.plan) return out;
  if (out.plan && out.tasks && !out.design) return out;
  return { error: USAGE };
}

/**
 * The prompt for the build job. It names the document and tasks and leaves the reading to Antigravity.
 */
export function buildPrompt({ plan, tasks, design, ruleTests = false }) {
  const source = plan
    ? `Implement task(s) ${tasks} from ${plan}. Read only the header, the Global Constraints and those tasks' sections.`
    : `Implement the tasks of the approved design in ${design}, in order.`;
  return [
    source,
    'Work on the current branch. Do not switch branches and do not push.',
    'Open every file and mockup the task names before coding, and match the surrounding code.',
    'Write the tests each task names (first, and watch them fail), then the code.',
    ...(ruleTests ? ['Tests for the changed rules already exist and were written without seeing the code. Make them pass; do not edit them, and report any that look wrong.'] : []),
    'Make one commit per task, staging only the files the task lists. Never bypass the commit hook.',
    'Do not change the design. When a task is ambiguous or cannot work as written, make the smallest change and record it.',
    'Reply in at most 12 lines: for each task the commit, the files changed, and the deviations (or none).',
    PLAIN_PATHS_RULE
  ].join('\n');
}

/**
 * The prompt for the rule-tests job: it sees the changed rules and the test layout, never the implementation.
 */
export function ruleTestsPrompt(rules) {
  return [
    'You write tests from rules. You have not seen the implementation and must not read it.',
    'Read only the existing test files and the test configuration, to match the runner, folders and naming.',
    ...ruleTestLines(rules),
    'Write test files only; change no application code. Commit them in one commit, staging only the test files. Never bypass the commit hook.',
    'Reply in at most 8 lines: the test files and the rule IDs each covers.',
    PLAIN_PATHS_RULE
  ].join('\n');
}

/**
 * The jobs one run launches, in order: `rule-tests` first when testable rules changed, then `build`; `qa` alone.
 */
export function jobsFor({ qa = false, rules = [] }) {
  if (qa) return ['qa'];
  return [...(rules.some(r => !r.manual) ? ['rule-tests'] : []), 'build'];
}

/**
 * The prompt for the QA job: attack one area, write findings and `*.qa.e2e.ts` tests, change no application code.
 */
export function qaPrompt(area) {
  return [
    `Break the "${area}" area of this app. Follow .agents/skills/qa-break/SKILL.md and its attack catalogue.`,
    `Write findings with repro steps to docs/qa/${area}-<today's date>.md and attack tests to *.qa.e2e.ts files next to the area's other e2e tests.`,
    'Change no application code. Do not edit any file except those two kinds.',
    'Reply in at most 12 lines: attacks tried, confirmed bugs, files written.',
    PLAIN_PATHS_RULE
  ].join('\n');
}

function git(root, args) {
  try {
    return execFileSync('git', args, { cwd: root, encoding: 'utf-8' }).trim();
  } catch {
    return '';
  }
}

function recordLaunch(root, entry) {
  const { json } = syncPaths(root);
  mkdirSync(dirname(json), { recursive: true });
  const state = readSyncState(json);
  appendDelegation(state, entry);
  writeSyncState(state, json);
}

export async function main() {
  const parsed = parseArgs(process.argv.slice(2));
  if (parsed.error) {
    console.error(parsed.error);
    process.exitCode = 1;
    return;
  }
  const { root } = parsed;
  const rules = parsed.qa ? [] : changedRules(gitChange(root).diff);
  const jobs = jobsFor({ qa: Boolean(parsed.qa), rules });
  for (const job of jobs) {
    const before = git(root, ['rev-parse', 'HEAD']);
    const prompt = job === 'qa' ? qaPrompt(parsed.qa)
      : job === 'rule-tests' ? ruleTestsPrompt(rules)
        : buildPrompt({ ...parsed, ruleTests: jobs.includes('rule-tests') });
    const result = launchAgy({ job, prompt, allowEdits: true, root });
    recordLaunch(root, result.entry);

    if (!result.ok) {
      console.log(`[Agy] ${job} job unavailable (${describeFailure(result.reason, result.detail)}).`);
      process.exitCode = 1;
      return;
    }
    console.log(result.response);
    console.log(`\n[Agy] model: ${result.entry.model}`);
    const commits = git(root, ['log', '--format=%h %s', `${before}..HEAD`]);
    if (job !== 'qa') console.log(commits ? `[Agy] commits:\n${commits}` : '[Agy] no commits were made; read git status and the diff.');
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch(err => {
    console.error('[Agy] Unexpected error:', err);
    process.exit(1);
  });
}
