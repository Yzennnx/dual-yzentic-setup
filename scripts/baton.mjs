#!/usr/bin/env node

/**
 * Baton Coordinator Runner (scripts/baton.mjs)
 * Coordinates dual-agent handoffs between Claude Code (Builder) and Antigravity (Gatekeeper).
 * Provides 3 execution tiers (Express / Scoped / Full) and circuit breaker protection.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';
import { isCosmeticFile, resolveChangeSet, fingerprintChanges } from './changes.mjs';
import { gatekeeperDisabled, shouldWriteTests, writeTests, shouldDiagnose, diagnoseFailure, writeHandoff } from './gatekeeper.mjs';
import { describeFailure } from './agy.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, '..');

/**
 * Sync file locations for a repo root.
 */
export function syncPaths(root = REPO_ROOT) {
  return {
    json: resolve(root, '.agents/sync/handoff.json'),
    md: resolve(root, '.agents/sync/handoff.md')
  };
}

export const SYNC_JSON_PATH = syncPaths().json;
export const SYNC_MD_PATH = syncPaths().md;
export const BLUEPRINT_PATH = resolve(REPO_ROOT, 'project-blueprint.json');

const DEFAULT_STATE = {
  version: '1.0',
  task_id: 'TASK-00',
  active_agent: 'claude',
  status: 'idle',
  turn_count: 0,
  max_turns: 5,
  last_updated: new Date().toISOString(),
  summary: 'Initialized',
  files_modified: []
};

/**
 * Read the current sync state, auto-healing with defaults if missing or corrupted.
 */
export function readSyncState(filePath = SYNC_JSON_PATH) {
  try {
    if (!existsSync(filePath)) {
      writeSyncState(DEFAULT_STATE, filePath);
      return { ...DEFAULT_STATE };
    }
    const raw = readFileSync(filePath, 'utf-8');
    return JSON.parse(raw);
  } catch {
    writeSyncState(DEFAULT_STATE, filePath);
    return { ...DEFAULT_STATE };
  }
}

/**
 * Write sync state atomically.
 */
export function writeSyncState(state, filePath = SYNC_JSON_PATH) {
  const content = JSON.stringify(state, null, 2) + '\n';
  mkdirSync(dirname(filePath), { recursive: true });
  writeFileSync(filePath, content, 'utf-8');
}

/**
 * Check if the ping-pong circuit breaker has been tripped.
 * Returns true if execution is permitted, false if tripped (turn_count >= max_turns).
 */
export function checkCircuitBreaker(state) {
  const max = state.max_turns ?? 5;
  const current = state.turn_count ?? 0;
  return current < max;
}

/**
 * Distill error outputs to a maximum of 25 lines to protect Claude Pro context window.
 */
export function distillDiagnostics(rawOutput) {
  if (!rawOutput) return 'No output captured.';
  const lines = rawOutput.split('\n').filter(line => line.trim().length > 0);
  
  if (lines.length <= 25) {
    return lines.join('\n');
  }

  // Look for error, fail, or traceback markers
  const errorLines = lines.filter(l => 
    /error|fail|exception|assert|traceback|expected|received|not ok|actual|location|✖/i.test(l)
  );

  const selected = errorLines.length > 0 ? errorLines.slice(0, 22) : lines.slice(-22);
  return [
    `... [Truncated ${lines.length - selected.length} lines of raw logs] ...`,
    ...selected
  ].join('\n');
}

/**
 * Auto-detect the execution tier based on touched files.
 * Tier 1: Express Lane (Micro/Cosmetic: CSS, markdown, static assets, docs)
 * Tier 2: Scoped Lane (Single component/module and/or its test file)
 * Tier 3: Architectural Deep Lane (DB schema, migrations, auth, multi-file features)
 * No files at all is never Tier 1: with nothing to classify, run the full suite.
 */
export function detectExecutionTier(modifiedFiles = []) {
  if (!modifiedFiles || modifiedFiles.length === 0) {
    return 3;
  }

  if (modifiedFiles.every(isCosmeticFile)) {
    return 1;
  }

  const isArchitectural = modifiedFiles.some(file => 
    /schema|migration|auth|middleware|config/i.test(file)
  ) || modifiedFiles.length > 3;

  if (isArchitectural) {
    return 3;
  }

  return 2;
}

/**
 * Read the project's verify commands from the blueprint.
 * Returns null until the project is initialized, or if the blueprint is missing or unreadable.
 */
export function readVerifyConfig(blueprintPath = BLUEPRINT_PATH) {
  try {
    const blueprint = JSON.parse(readFileSync(blueprintPath, 'utf-8'));
    const verify = blueprint.project?.verify;
    if (blueprint.status !== 'initialized') return null;
    if (typeof verify?.test !== 'string' || verify.test.trim().length === 0) return null;
    return verify;
  } catch {
    return null;
  }
}

/**
 * Determine the test command to run for a given tier.
 */
export function resolveTestExecution(tier, scope, verify = null) {
  if (tier === 1) {
    return { command: 'git diff --stat', isExpress: true };
  }

  if (scope && verify?.test_scoped) {
    return { command: verify.test_scoped.split('{scope}').join(scope), isExpress: false };
  }

  if (!scope && verify?.test) {
    return { command: verify.test, isExpress: false };
  }

  if (scope) {
    // If Python unittest scope
    if (scope.endsWith('.py')) {
      return { command: `python3 -m unittest ${scope}`, isExpress: false };
    }
    return { command: `npm test -- ${scope}`, isExpress: false };
  }

  // Default test command
  return { command: 'python3 tests/run_parallel.py', isExpress: false };
}

/**
 * Spec paths that PLAN.md links (`](specs/...)`) or the blueprint names as source_spec but that do not exist on disk.
 */
export function missingSpecs(root) {
  const missing = [];
  try {
    const plan = readFileSync(resolve(root, 'docs/PLAN.md'), 'utf-8');
    for (const match of plan.matchAll(/\]\((specs\/[^)#\s]+)/g)) missing.push(`docs/${match[1]}`);
  } catch { /* no plan */ }
  try {
    const spec = JSON.parse(readFileSync(resolve(root, 'project-blueprint.json'), 'utf-8')).project?.source_spec;
    if (spec) missing.push(spec);
  } catch { /* no blueprint */ }
  return [...new Set(missing)].filter(path => !existsSync(resolve(root, path)));
}

const CLEAN_TREE_NOTE = '[Baton] Working tree clean: classifying the last commit.';

/**
 * Pull `--root <path>` out of the CLI args. Returns the resolved root and the remaining args.
 */
function takeRoot(args) {
  const index = args.indexOf('--root');
  if (index === -1) return { root: REPO_ROOT, rest: args };
  const value = args[index + 1];
  if (!value || value.startsWith('--')) {
    console.error('[Baton] --root requires a path');
    process.exit(1);
  }
  return { root: resolve(value), rest: [...args.slice(0, index), ...args.slice(index + 2)] };
}

/**
 * CLI Entry point
 */
export async function main() {
  const { root, rest: args } = takeRoot(process.argv.slice(2));
  const command = args[0] || 'status';
  const syncJson = syncPaths(root).json;

  if (command === 'status') {
    const state = readSyncState(syncJson);
    const { files: modified, source } = resolveChangeSet(root);
    const tier = detectExecutionTier(modified);
    console.log('\n=== Baton Sync Status ===');
    if (source === 'last-commit') console.log(CLEAN_TREE_NOTE);
    console.log(`Status:       ${state.status}`);
    console.log(`Active Agent: ${state.active_agent}`);
    console.log(`Turn Count:   ${state.turn_count} / ${state.max_turns}`);
    console.log(`Detected Tier:${tier} (${tier === 1 ? 'Express' : tier === 2 ? 'Scoped' : 'Architectural'})`);
    console.log(`Modified:     ${modified.length} files`);
    if (modified.length > 0) {
      console.log(`              ${modified.slice(0, 5).join(', ')}${modified.length > 5 ? '...' : ''}`);
    }
    const delegations = state.delegations ?? [];
    const tokens = delegations.reduce((sum, d) => sum + (d.total_tokens || 0), 0);
    console.log(`Antigravity:  ${delegations.length} launches, ${tokens} tokens (last 20)`);
    console.log('=========================\n');
    process.exit(0);
  }

  if (command === 'reset') {
    writeSyncState(DEFAULT_STATE, syncJson);
    console.log('[Baton] State reset to idle.');
    process.exit(0);
  }

  if (command === 'verify') {
    const verifyConfig = readVerifyConfig(resolve(root, 'project-blueprint.json'));
    const wantE2e = args.includes('--e2e') || process.env.npm_config_e2e === 'true';
    if (wantE2e && !verifyConfig?.e2e) {
      console.error('[Baton] No e2e command configured (project.verify.e2e).');
      process.exit(1);
    }

    const state = readSyncState(syncJson);

    for (const path of missingSpecs(root)) console.warn(`[Baton] Warning: ${path} is linked from PLAN.md or the blueprint but missing.`);

    // Check circuit breaker
    if (!checkCircuitBreaker(state)) {
      console.error('\n[CIRCUIT BREAKER TRIPPED]');
      console.error(`Baton halted: reached max turns (${state.turn_count}/${state.max_turns}) without green test.`);
      console.error('Developer intervention required. Please inspect the code or run npm run sync:reset.\n');
      process.exit(1);
    }

    // Determine tier & scope: flags win, then npm's own config for `npm run verify:agent --tier 2` (no `--`)
    let tierOverride = null;
    let scopeOverride = null;

    for (let i = 1; i < args.length; i++) {
      if (args[i] === '--tier' && args[i + 1]) {
        tierOverride = parseInt(args[i + 1], 10);
      }
      if (args[i] === '--scope' && args[i + 1]) {
        scopeOverride = args[i + 1];
      }
    }
    if (!tierOverride && process.env.npm_config_tier) {
      tierOverride = parseInt(process.env.npm_config_tier, 10);
    }
    if (!scopeOverride && process.env.npm_config_scope) {
      scopeOverride = process.env.npm_config_scope;
    }

    const { files: modified, source } = resolveChangeSet(root);
    if (source === 'last-commit') console.log(CLEAN_TREE_NOTE);
    const tier = tierOverride || detectExecutionTier(modified);
    const { command: testCmd, isExpress } = resolveTestExecution(tier, scopeOverride, verifyConfig);
    const disabled = gatekeeperDisabled(args);
    const verifiedCommand = isExpress ? 'express' : testCmd;

    // The commit hook repeats nothing: the same command already passed on the same content
    if (process.env.BATON_HOOK === '1' && state.status === 'verified' && state.verified) {
      const { fingerprint, command: ranCommand } = state.verified;
      if (ranCommand === verifiedCommand && fingerprint === fingerprintChanges(root)) {
        console.log('[Baton] Already verified for this content; skipping.');
        process.exit(0);
      }
    }
    const saveState = () => writeSyncState(state, syncJson);

    // Record the verdict in handoff.json and rewrite handoff.md
    const settle = (status, diagnosis = null) => {
      state.status = status;
      state.last_updated = new Date().toISOString();
      state.files_modified = modified;
      state.verified = status === 'verified' ? { fingerprint: fingerprintChanges(root), command: verifiedCommand } : null;
      saveState();
      writeHandoff(syncPaths(root).md, { state, tier, files: modified, diagnosis });
    };

    console.log(`\n[Baton] Verifying changes (Tier ${tier}${tierOverride ? ' - manual override' : ' - auto-detected'})...`);
    state.gatekeeper = { result: 'not_needed', tests_written: [], out_of_scope: [] };
    state.e2e = 'not_run';

    if (isExpress) {
      console.log('[Baton] Tier 1 Express Lane: Cosmetic/asset changes detected. Full tests bypassed.');
      if (!wantE2e) {
        settle('verified');
        console.log('[Baton] PASS: Verified.\n');
        process.exit(0);
      }
    }

    // An explicit --scope names the test that covers the change, so no tests are owed
    if (shouldWriteTests({ tier, files: modified, disabled: disabled || Boolean(scopeOverride) })) {
      console.log('[Baton] Source changed with no test changes: asking the Gatekeeper to write tests...');
      const outcome = writeTests({ root, state, files: modified, saveState });
      state.gatekeeper = { result: outcome.result, tests_written: outcome.testsWritten, out_of_scope: outcome.outOfScope };
      if (outcome.outOfScope.length > 0) {
        settle('gatekeeper_out_of_scope');
        console.error('\n[Baton] FAIL: The Gatekeeper changed files other than tests:');
        for (const path of outcome.outOfScope) console.error(`  ${path}`);
        console.error('Nothing was reverted. Inspect these files before continuing.\n');
        process.exit(1);
      }
      if (outcome.result === 'skipped') {
        console.log(`[Baton] Gatekeeper skipped (${describeFailure(outcome.reason, outcome.detail)}): tests for this change are still owed.`);
      } else if (outcome.testsWritten.length > 0) {
        console.log(`[Baton] Gatekeeper wrote: ${outcome.testsWritten.join(', ')}`);
      }
    }

    const runCommand = (cmd) => {
      commandStarted = Date.now();
      try {
        return { success: true, output: execSync(cmd, { cwd: root, encoding: 'utf-8', stdio: 'pipe' }) };
      } catch (err) {
        return { success: false, output: (err.stdout || '') + '\n' + (err.stderr || '') };
      }
    };

    let testSuccess = true;
    let testOutput = '';
    let commandStarted = Date.now();

    if (!isExpress) {
      console.log(`[Baton] Executing test command: ${testCmd}`);
      ({ success: testSuccess, output: testOutput } = runCommand(testCmd));
    }
    if (testSuccess && wantE2e) {
      console.log(`[Baton] Executing e2e command: ${verifyConfig.e2e}`);
      ({ success: testSuccess, output: testOutput } = runCommand(verifyConfig.e2e));
      state.e2e = testSuccess ? 'passed' : 'failed';
    }

    if (testSuccess) {
      state.turn_count = 0; // reset turn count on success
      settle('verified');

      console.log('\n[Baton] PASS: All tests passed! Verification completed.');
      console.log('Status set to "verified".\n');
      process.exit(0);
    } else {
      state.turn_count = (state.turn_count || 0) + 1;
      const { note: diagnosis, outOfScope } = disabled || !shouldDiagnose({ root, output: testOutput, isE2e: state.e2e === 'failed', since: commandStarted })
        ? { note: null, outOfScope: [] }
        : diagnoseFailure({ root, state, output: testOutput, saveState });
      state.gatekeeper.out_of_scope = outOfScope;
      settle('verification_failed', diagnosis);

      console.error('\n[Baton] FAIL: Verification failed.');
      console.error(`Recorded Turn ${state.turn_count} / ${state.max_turns} in .agents/sync/handoff.json.`);
      if (diagnosis) {
        console.error('\n--- Gatekeeper Diagnosis ---');
        console.error(diagnosis);
        console.error('----------------------------\n');
      } else {
        console.error('\n--- Distilled Failure Diagnostic (For Claude Code) ---');
        console.error(distillDiagnostics(testOutput));
        console.error('------------------------------------------------------\n');
      }
      if (outOfScope.length > 0) {
        console.error('[Baton] The Gatekeeper changed files during a read-only diagnosis:');
        for (const path of outOfScope) console.error(`  ${path}`);
        console.error('Nothing was reverted. Inspect these files before continuing.\n');
      }
      process.exit(1);
    }
  }

  console.error(`Unknown command: ${command}`);
  process.exit(1);
}

// Auto-run if executed directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch(err => {
    console.error('[Baton] Unexpected error:', err);
    process.exit(1);
  });
}
