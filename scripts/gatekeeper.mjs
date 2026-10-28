/**
 * Gatekeeper steps for the baton (scripts/gatekeeper.mjs)
 * Launches Antigravity to write missing tests and to diagnose a failing test run, and renders the handoff ticket.
 * The baton imports this module, so it never imports the baton: state and a saveState callback come in as arguments.
 */

import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { launchAgy, appendDelegation, describeFailure, PLAIN_PATHS_RULE } from './agy.mjs';
import { isSourceFile, isTestFile, snapshotChanges, checkScope } from './changes.mjs';
import { gitChange, changedRules, ruleTestLines } from './rules-check.mjs';

const ARTIFACT_SLACK_MS = 2000; // coarse filesystem timestamps
const FAILURE_LOG = '.agents/sync/last-failure.log';
const FAILURE_FOLDERS = ['test-results', 'playwright-report'];

/**
 * True when the Gatekeeper is switched off: `--no-gatekeeper` on the command line or BATON_GATEKEEPER=0.
 */
export function gatekeeperDisabled(args, env = process.env) {
  return args.includes('--no-gatekeeper') || env.BATON_GATEKEEPER === '0';
}

/**
 * Tier 2 or 3, source files changed, and no test file changed (spec section 5.1).
 */
export function shouldWriteTests({ tier, files, disabled = false }) {
  if (disabled || (tier !== 2 && tier !== 3)) return false;
  return files.some(isSourceFile) && !files.some(isTestFile);
}

/**
 * The blueprint's source spec, test command, e2e command and no-tests folders; each is null (or empty) when absent or the blueprint is unreadable.
 */
function readProject(root) {
  try {
    const project = JSON.parse(readFileSync(resolve(root, 'project-blueprint.json'), 'utf-8')).project;
    const noTestsIn = project?.verify?.no_tests_in;
    return {
      spec: project?.source_rules || project?.source_spec || null,
      testCommand: project?.verify?.test || null,
      e2eCommand: project?.verify?.e2e || null,
      noTestsIn: Array.isArray(noTestsIn) ? noTestsIn : []
    };
  } catch {
    return { spec: null, testCommand: null, e2eCommand: null, noTestsIn: [] };
  }
}

/**
 * The prompt line that keeps test files out of folders the app bundles (empty when the blueprint lists none).
 */
function noTestsLine(noTestsIn) {
  return noTestsIn.length > 0
    ? [`Never create files under: ${noTestsIn.join(', ')}. They are route folders bundled into the app; put such tests beside them in the parent folder.`]
    : [];
}

function buildWritePrompt(sources, { spec, testCommand, e2eCommand, noTestsIn }, rules = []) {
  return [
    'You are the Gatekeeper of this repository (your role is defined in GEMINI.md).',
    'The Builder changed these source files and changed no tests:',
    ...sources.map(path => `- ${path}`),
    `Read ${spec ? `docs/PLAN.md and ${spec}` : 'docs/PLAN.md'} for the intended behaviour.`,
    'The docs in docs/rules (invariants.md and the feature docs) are current behaviour; older specs in docs/specs are history.',
    ...(testCommand ? [`The project runs its tests with: ${testCommand}. Write tests that suit that runner.`] : []),
    'Rules:',
    '- Write or update tests that cover the listed changes.',
    '- Touch test files only.',
    '- Run nothing.',
    ...noTestsLine(noTestsIn),
    '- Where the code contradicts the spec, test to the spec and say so in one line.',
    ...ruleTestLines(rules),
    e2eCommand
      ? 'Write unit or component tests. Write an end-to-end test only when the change adds or alters a user journey named in the spec, and put it under e2e/.'
      : 'Write unit or component tests only. Do not write end-to-end or browser tests.',
    PLAIN_PATHS_RULE
  ].join('\n');
}

function buildRepairPrompt(tests, output, { noTestsIn }) {
  return [
    'You are the Gatekeeper of this repository (your role is defined in GEMINI.md).',
    'You wrote these test files and they fail when run:',
    ...tests.map(path => `- ${path}`),
    'Distilled failure output:',
    output,
    'Rules:',
    '- Where the test is wrong (a bad mock, an import, a hoisting problem, a wrong expectation or comparison), fix the test.',
    '- Leave a test failing only if it exposes a real bug in the source, and say so in your reply in one line naming the file.',
    '- Touch test files only.',
    '- Run nothing.',
    ...noTestsLine(noTestsIn),
    PLAIN_PATHS_RULE
  ].join('\n');
}

function buildDiagnosePrompt(root) {
  const folders = FAILURE_FOLDERS.filter(name => existsSync(resolve(root, name)));
  return [
    'A test run failed in this repository. The full output is in .agents/sync/last-failure.log.',
    ...(folders.length > 0 ? [`Test artifacts are in ${folders.map(name => `${name}/`).join(' and ')}.`] : []),
    'Find the root cause. Answer in at most 15 lines with no introduction. Give:',
    '- the failing test',
    '- the file and line',
    '- expected against actual',
    '- the most likely cause in the source',
    'Read only. Edit nothing. Run nothing.',
    PLAIN_PATHS_RULE
  ].join('\n');
}

/**
 * Run one launch with active_agent set to antigravity, restore claude whatever happens, and log the delegation.
 */
function launchAsAntigravity(state, saveState, options) {
  state.active_agent = 'antigravity';
  saveState();
  try {
    const result = launchAgy(options);
    appendDelegation(state, result.entry);
    return result;
  } finally {
    state.active_agent = 'claude';
    saveState();
  }
}

/**
 * Ask Antigravity to write tests for the changed source files. The result is 'ran' when the launch was ok, else 'skipped'.
 * The scope guard runs whatever the launch result, since a killed run may have written files.
 */
export function writeTests({ root, state, files, saveState = () => {}, rules = changedRules(gitChange(root).diff) }) {
  const before = snapshotChanges(root);
  const launch = launchAsAntigravity(state, saveState, {
    job: 'write_tests',
    prompt: buildWritePrompt(files.filter(isSourceFile), readProject(root), rules),
    allowEdits: true,
    root
  });
  const { testsWritten, outOfScope } = checkScope(before, snapshotChanges(root), { allowEdits: true });
  return { result: launch.ok ? 'ran' : 'skipped', testsWritten, outOfScope, reason: launch.reason, detail: launch.detail };
}

/**
 * One repair round after the new tests failed their own run: Antigravity fixes its tests, or says the source is at fault.
 * `output` is the distilled failure. The scope guard applies as it does for writing.
 */
export function repairTests({ root, state, tests, output, saveState = () => {} }) {
  const before = snapshotChanges(root);
  const launch = launchAsAntigravity(state, saveState, {
    job: 'write_tests',
    prompt: buildRepairPrompt(tests, output, readProject(root)),
    allowEdits: true,
    root
  });
  const { testsWritten, outOfScope } = checkScope(before, snapshotChanges(root), { allowEdits: true });
  return {
    result: launch.ok ? 'ran' : 'skipped',
    testsWritten,
    outOfScope,
    reply: launch.ok ? String(launch.response ?? '').trim() : '',
    reason: launch.reason,
    detail: launch.detail
  };
}

/**
 * Whether an artifact folder exists and, when `since` (ms since the epoch) is given, was touched by the failing run:
 * the folder or one of its direct children was modified at or after `since`, give or take the slack.
 */
function isFreshFolder(folder, since) {
  if (!existsSync(folder)) return false;
  if (since === null) return true;
  const cutoff = since - ARTIFACT_SLACK_MS;
  try {
    return [folder, ...readdirSync(folder).map(name => resolve(folder, name))].some(path => statSync(path).mtimeMs >= cutoff);
  } catch {
    return false;
  }
}

/**
 * A failure is worth a diagnosis launch only when it is not readable as it is: the output is longer than
 * BATON_DIAGNOSE_MIN_LINES non-empty lines (default 150, 0 always diagnoses), a browser run left its artifacts
 * in the project root during the run (see isFreshFolder), or the command that failed was the e2e command.
 */
export function shouldDiagnose({ root, output, isE2e = false, since = null, env = process.env }) {
  if (isE2e || FAILURE_FOLDERS.some(name => isFreshFolder(resolve(root, name), since))) return true;
  output = typeof output === 'string' ? output : '';
  const raw = (env.BATON_DIAGNOSE_MIN_LINES ?? '').trim();
  const threshold = raw !== '' && Number.isFinite(Number(raw)) && Number(raw) >= 0 ? Number(raw) : 150;
  return output.split('\n').filter(line => line.trim().length > 0).length > threshold;
}

/**
 * Ask Antigravity, read only, for a root-cause note on a failed test run.
 * Returns the note (null when the launch was not ok) and the files changed during the launch, which are never reverted.
 */
export function diagnoseFailure({ root, state, output, saveState = () => {} }) {
  const logPath = resolve(root, FAILURE_LOG);
  mkdirSync(dirname(logPath), { recursive: true });
  writeFileSync(logPath, output, 'utf-8');

  const before = snapshotChanges(root);
  const launch = launchAsAntigravity(state, saveState, { job: 'diagnose', prompt: buildDiagnosePrompt(root), root });
  const { outOfScope } = checkScope(before, snapshotChanges(root));

  if (!launch.ok) {
    console.error(`[Baton] Gatekeeper diagnosis unavailable (${describeFailure(launch.reason, launch.detail)}).`);
    return { note: null, outOfScope };
  }
  return { note: launch.response.trim(), outOfScope };
}

/**
 * The handoff ticket for the last verify, as Markdown.
 */
export function renderHandoff({ state, tier, files, diagnosis = null }) {
  const written = state.gatekeeper?.tests_written ?? [];
  const outOfScope = state.gatekeeper?.out_of_scope ?? [];
  const report = [];
  if (written.length > 0) report.push('Tests written:', ...written.map(path => `- ${path}`));
  if (diagnosis) report.push(...(report.length > 0 ? [''] : []), 'Diagnosis:', diagnosis);
  if (outOfScope.length > 0) {
    report.push(...(report.length > 0 ? [''] : []), 'Out of scope (not reverted):', ...outOfScope.map(path => `- ${path}`));
  }
  if (report.length === 0) {
    const result = state.gatekeeper?.result;
    if (result === 'ran') report.push('Launched; wrote no tests.');
    else if (result === 'skipped') report.push('Launch attempted; Antigravity was unavailable.');
    else report.push('Not launched.');
  }
  if (state.gatekeeper?.result === 'skipped') {
    report.push('', 'Gatekeeper skipped: tests for this change are still owed.');
  }

  report.push('', `E2E: ${{ passed: 'passed', failed: 'failed' }[state.e2e] ?? 'not run'}`);

  return [
    `# Agent Handoff Ticket: ${state.task_id ?? 'TASK-00'}`,
    '',
    `- Status: ${state.status}`,
    `- Tier: ${tier}`,
    '',
    '## Changes Implemented by Claude',
    ...(files.length > 0 ? files.map(path => `- ${path}`) : ['- (none)']),
    '',
    '## Verification Report by Antigravity',
    ...report,
    ''
  ].join('\n');
}

/**
 * Rewrite handoff.md for the last verify.
 */
export function writeHandoff(mdPath, details) {
  mkdirSync(dirname(mdPath), { recursive: true });
  writeFileSync(mdPath, renderHandoff(details), 'utf-8');
}
