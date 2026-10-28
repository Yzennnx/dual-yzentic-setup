#!/usr/bin/env node

/**
 * Baton Coordinator Runner (scripts/baton.mjs)
 * Coordinates dual-agent handoffs between Claude Code (Builder) and Antigravity (Gatekeeper).
 * Provides 3 execution tiers (Express / Scoped / Full) and circuit breaker protection.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, openSync, writeSync, closeSync, unlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';
import { isCosmeticFile, isSourceFile, isTestFile, resolveChangeSet, fingerprintChanges } from './changes.mjs';
import { gatekeeperDisabled, shouldWriteTests, writeTests, repairTests, shouldDiagnose, diagnoseFailure, writeHandoff } from './gatekeeper.mjs';
import { describeFailure } from './agy.mjs';
import { checkAll as checkMockups } from './mockups-check.mjs';

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
  files_modified: [],
  tests_owed: []
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
 * True when the repo-relative path starts with one of the prefixes.
 */
export function underAny(path, prefixes) {
  return prefixes.some(prefix => path.startsWith(prefix));
}

/**
 * Auto-detect the execution tier based on touched files.
 * Tier 1: Express Lane (Micro/Cosmetic: CSS, markdown, static assets, docs)
 * Tier 2: Scoped Lane (Single component/module and/or its test file)
 * Tier 3: Architectural Deep Lane (DB schema, migrations, auth, multi-file features)
 * No files at all is never Tier 1: with nothing to classify, run the full suite.
 * When the blueprint sets a non-empty `project.risky_paths`, the surface decides instead of the file count:
 * all cosmetic is 1, any file under a risky prefix is 3, anything else is 2.
 */
export function detectExecutionTier(modifiedFiles = [], riskyPaths = null) {
  if (!modifiedFiles || modifiedFiles.length === 0) {
    return 3;
  }

  if (modifiedFiles.every(isCosmeticFile)) {
    return 1;
  }

  if (Array.isArray(riskyPaths) && riskyPaths.length > 0) {
    return modifiedFiles.some(file => underAny(file, riskyPaths)) ? 3 : 2;
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
 * The blueprint's optional `project.risky_paths`: an array of path prefixes, or null.
 */
export function readRiskyPaths(blueprintPath = BLUEPRINT_PATH) {
  try {
    const paths = JSON.parse(readFileSync(blueprintPath, 'utf-8')).project?.risky_paths;
    return Array.isArray(paths) && paths.length > 0 ? paths.filter(p => typeof p === 'string') : null;
  } catch {
    return null;
  }
}

/**
 * The commands to run for the changed files when `verify.routes` is set: the distinct setups, then the distinct
 * commands of every route whose paths match a changed file. `verify.test` is added when no route matches, or when a
 * changed non-cosmetic file belongs to no route. Returns null when no routes are configured.
 */
export function planRoutes(files, verify) {
  const routes = verify?.routes;
  if (!Array.isArray(routes) || routes.length === 0) return null;
  const matches = (route, file) => Array.isArray(route.paths) && underAny(file, route.paths);
  const matched = routes.filter(route => files.some(file => matches(route, file)));
  const uncovered = files.some(file => !isCosmeticFile(file) && !routes.some(route => matches(route, file)));
  const commands = [
    ...matched.map(route => route.setup),
    ...matched.map(route => route.command),
    ...(matched.length === 0 || uncovered ? [verify.test] : [])
  ].filter(cmd => typeof cmd === 'string' && cmd.trim().length > 0);
  return [...new Set(commands)];
}

/**
 * Test files under a folder listed in `verify.no_tests_in` (route folders that are bundled into the app).
 */
export function testsInForbidden(files, verify) {
  const folders = (verify?.no_tests_in ?? []).map(dir => (dir.endsWith('/') ? dir : `${dir}/`));
  return folders.length === 0 ? [] : files.filter(file => isTestFile(file) && underAny(file, folders));
}

/**
 * The command that runs just the given test files: the scoped command, the plain command with the files appended
 * for a known runner, or the plain command unchanged when it cannot take file arguments.
 */
export function selfCheckCommand(files, verify, fallback) {
  const list = files.join(' ');
  if (verify?.test_scoped) return verify.test_scoped.split('{scope}').join(list);
  const cmd = verify?.test || fallback;
  if (/^(npm|pnpm|yarn|bun)\s+(run\s+)?test\b/.test(cmd)) return `${cmd} -- ${list}`;
  if (/\b(vitest|jest|pytest|mocha|playwright|unittest)\b/.test(cmd)) return `${cmd} ${list}`;
  return cmd;
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

export const LOCK_PATH = resolve(tmpdir(), 'dual-yzentic-verify.lock');
export const LOCK_MAX_AGE_MS = 20 * 60 * 1000;

/**
 * True when the process exists (signal 0 only probes; EPERM means it exists but is not ours).
 */
export function pidAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    return err.code === 'EPERM';
  }
}

/**
 * The lock's contents, or null when it is missing or unreadable.
 */
export function readLock(lockPath = LOCK_PATH) {
  try {
    return JSON.parse(readFileSync(lockPath, 'utf-8'));
  } catch {
    return null;
  }
}

/**
 * A lock is stale when its pid is gone or it is older than maxAgeMs.
 */
export function lockIsStale(lock, { maxAgeMs = LOCK_MAX_AGE_MS, now = Date.now(), isAlive = pidAlive } = {}) {
  if (!lock || typeof lock.pid !== 'number') return true;
  const started = Date.parse(lock.startedAt);
  if (Number.isNaN(started) || now - started > maxAgeMs) return true;
  return !isAlive(lock.pid);
}

/**
 * Take the machine-wide verify lock, waiting while a live, recent one is held elsewhere.
 * Returns a release function (idempotent). Created with 'wx' so two takers cannot both win.
 */
export async function acquireLock(worktree, { lockPath = LOCK_PATH, pollMs = 2000, sleep = ms => new Promise(r => setTimeout(r, ms)), log = console.log, ...staleOpts } = {}) {
  let announced = false;
  for (;;) {
    try {
      const fd = openSync(lockPath, 'wx');
      writeSync(fd, JSON.stringify({ pid: process.pid, worktree, startedAt: new Date().toISOString() }));
      closeSync(fd);
      break;
    } catch (err) {
      if (err.code !== 'EEXIST') throw err;
    }
    const held = readLock(lockPath);
    if (lockIsStale(held, staleOpts)) {
      try { unlinkSync(lockPath); } catch { /* someone else took it over */ }
      continue;
    }
    if (!announced) {
      log(`[Baton] waiting for verify in ${held.worktree}`);
      announced = true;
    }
    await sleep(pollMs);
  }
  let released = false;
  const release = () => {
    if (released) return;
    released = true;
    if (readLock(lockPath)?.pid === process.pid) {
      try { unlinkSync(lockPath); } catch { /* already gone */ }
    }
  };
  process.once('exit', release);
  process.once('SIGINT', () => { release(); process.exit(130); });
  return release;
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
    const tier = detectExecutionTier(modified, readRiskyPaths(resolve(root, 'project-blueprint.json')));
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
    if ((state.tests_owed ?? []).length > 0) console.log(`Tests owed:   ${state.tests_owed.join(', ')}`);
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

    // One verify at a time on the machine; released on exit (every path below ends in process.exit)
    await acquireLock(root);

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
    if (tierOverride !== null && ![1, 2, 3].includes(tierOverride)) {
      console.error('[Baton] --tier must be 1, 2 or 3');
      process.exit(1);
    }
    const debug = args.includes('--debug') || process.env.BATON_DEBUG === '1';

    const { files: modified, source } = resolveChangeSet(root);
    if (source === 'last-commit') console.log(CLEAN_TREE_NOTE);
    const tier = tierOverride || detectExecutionTier(modified, readRiskyPaths(resolve(root, 'project-blueprint.json')));
    // A changed mockup must leave its design's map complete and current
    if (modified.some(f => f.replaceAll('\\', '/').startsWith('docs/design/mockups/'))) {
      const { problems } = checkMockups(root, modified);
      if (problems.length > 0) {
        console.error('\n[Baton] FAIL: mockup map out of date (npm run mockups:check -- <design.md>):');
        for (const problem of problems) console.error(`  ${problem}`);
        process.exit(1);
      }
    }
    const { command: testCmd, isExpress } = resolveTestExecution(tier, scopeOverride, verifyConfig);
    const disabled = gatekeeperDisabled(args);
    // An explicit --scope wins over routes; otherwise routes pick the commands for the changed files
    const commands = isExpress ? [] : (scopeOverride ? null : planRoutes(modified, verifyConfig)) ?? [testCmd];
    const verifiedCommand = isExpress ? 'express' : commands.join(' && ');

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

    console.log(`\n[Baton] Verifying changes (Tier ${tier}${tierOverride ? ' - set by --tier' : ' - auto-detected'})...`);
    state.gatekeeper = { result: 'not_needed', tests_written: [], out_of_scope: [] };
    state.e2e = 'not_run';

    // Test files under a no-tests folder (an Expo Router routes dir, say) would be bundled into the app
    const failForbidden = (paths) => {
      settle('verification_failed');
      console.error('\n[Baton] FAIL: test files under a folder that verify.no_tests_in marks as bundled into the app:');
      for (const path of paths) console.error(`  ${path}`);
      console.error('Move them beside that folder, in its parent. Nothing was moved.\n');
      process.exit(1);
    };
    const forbiddenNow = testsInForbidden(modified, verifyConfig);
    if (forbiddenNow.length > 0) failForbidden(forbiddenNow);

    let commandStarted = Date.now();
    const runCommand = (cmd) => {
      commandStarted = Date.now();
      try {
        return { success: true, output: execSync(cmd, { cwd: root, encoding: 'utf-8', stdio: 'pipe' }) };
      } catch (err) {
        return { success: false, output: (err.stdout || '') + '\n' + (err.stderr || '') };
      }
    };

    if (isExpress) {
      console.log('[Baton] Tier 1 Express Lane: Cosmetic/asset changes detected. Full tests bypassed.');
      if (!wantE2e) {
        settle('verified');
        console.log('[Baton] PASS: Verified.\n');
        process.exit(0);
      }
    }

    // An explicit --scope names the test that covers the change, so no tests are owed
    const owesTests = shouldWriteTests({ tier, files: modified, disabled: disabled || Boolean(scopeOverride) });
    if (owesTests && debug) {
      const sources = modified.filter(isSourceFile);
      state.tests_owed = [...new Set([...(state.tests_owed ?? []), ...sources])];
      console.log(`[Baton] Debug mode: tests not written; owed for: ${sources.join(', ')}`);
    } else if (owesTests) {
      console.log('[Baton] Source changed with no test changes: asking the Gatekeeper to write tests...');
      const owed = (state.tests_owed ?? []).filter(path => existsSync(resolve(root, path)));
      const outcome = writeTests({ root, state, files: [...new Set([...modified, ...owed])], saveState });
      if (outcome.testsWritten.length > 0) state.tests_owed = [];
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
        // Run only the new tests once; if they fail, the Gatekeeper gets one round to fix its own tests
        const check = selfCheckCommand(outcome.testsWritten, verifyConfig, testCmd);
        console.log(`[Baton] Checking the new tests: ${check}`);
        const checked = runCommand(check);
        if (!checked.success) {
          console.log('[Baton] The new tests fail: asking the Gatekeeper to repair them (once)...');
          const repair = repairTests({ root, state, tests: outcome.testsWritten, output: distillDiagnostics(checked.output), saveState });
          state.gatekeeper.tests_written = [...new Set([...outcome.testsWritten, ...repair.testsWritten])];
          state.gatekeeper.out_of_scope = repair.outOfScope;
          state.gatekeeper.repaired = repair.result === 'ran';
          if (repair.outOfScope.length > 0) {
            settle('gatekeeper_out_of_scope');
            console.error('\n[Baton] FAIL: The Gatekeeper changed files other than tests:');
            for (const path of repair.outOfScope) console.error(`  ${path}`);
            console.error('Nothing was reverted. Inspect these files before continuing.\n');
            process.exit(1);
          }
          if (repair.result === 'skipped') console.log(`[Baton] Repair skipped (${describeFailure(repair.reason, repair.detail)}).`);
          else if (repair.reply) console.log(`[Baton] Gatekeeper repair note:\n${repair.reply.split('\n').slice(0, 8).join('\n')}`);
        }
        const forbiddenWritten = testsInForbidden(state.gatekeeper.tests_written, verifyConfig);
        if (forbiddenWritten.length > 0) failForbidden(forbiddenWritten);
      }
    }

    let testSuccess = true;
    let testOutput = '';
    let failedCommand = null;

    for (const cmd of commands) {
      console.log(`[Baton] Executing test command: ${cmd}`);
      ({ success: testSuccess, output: testOutput } = runCommand(cmd));
      if (!testSuccess) {
        failedCommand = cmd;
        break;
      }
    }
    if (testSuccess && wantE2e) {
      console.log(`[Baton] Executing e2e command: ${verifyConfig.e2e}`);
      ({ success: testSuccess, output: testOutput } = runCommand(verifyConfig.e2e));
      state.e2e = testSuccess ? 'passed' : 'failed';
      if (!testSuccess) failedCommand = verifyConfig.e2e;
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
      if (failedCommand && (commands.length > 1 || wantE2e)) console.error(`Failed command: ${failedCommand}`);
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
