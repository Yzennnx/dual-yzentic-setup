/**
 * Headless Antigravity launcher (scripts/agy.mjs)
 * Runs `agy --print` for one job and reports what happened. It never writes files;
 * callers persist the returned entry with appendDelegation.
 */

import { spawnSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

// Each chain is tried in order: the next model runs when a launch fails on quota, availability or the model itself
const CHAIN_DEEP = ['gemini-4-argon-medium', 'claude-sonnet-5-5-medium', 'gpt-oss-120b-medium'];
const CHAIN_FAST = ['gemini-4-argon-low', 'claude-sonnet-5-5-low', 'gpt-oss-120b-medium'];
const FAST_JOBS = ['scout'];
const MODEL_ERROR = /quota|rate.?limit|exhaust|unavailable|overloaded|capacity|not found|unknown model|unsupported model|invalid model|no access|(429|503)/i;
const DEFAULT_TIMEOUT_SECONDS = 600;
const JOB_TIMEOUT_SECONDS = { review: 1200, build: 1800, qa: 1800 }; // a review reads the whole branch and outlasts the other jobs
const DEFAULT_KILL_GRACE_SECONDS = 15; // agy gets this long past its own --print-timeout before we kill it
const DELEGATION_LIMIT = 20;

/**
 * The closing line of every prompt, so replies carry plain repo-relative paths instead of Markdown links.
 */
export const PLAIN_PATHS_RULE =
  'Reply in plain text. Refer to files by repo-relative path with forward slashes. Do not use Markdown links or absolute paths.';

/**
 * The models to try for a job, in order. Scout uses the low chain; every other job (build, review, tests, diagnose, qa)
 * uses the deep chain. BATON_AGY_MODEL_FAST / BATON_AGY_MODEL_DEEP replace the first entry of their chain.
 * BATON_AGY_MODEL, when set, is the only model for every job.
 */
export function modelsForJob(job) {
  if (process.env.BATON_AGY_MODEL) return [process.env.BATON_AGY_MODEL];
  const fast = FAST_JOBS.includes(job);
  const [first, ...rest] = fast ? CHAIN_FAST : CHAIN_DEEP;
  const override = fast ? process.env.BATON_AGY_MODEL_FAST : process.env.BATON_AGY_MODEL_DEEP;
  return [override || first, ...rest];
}

/**
 * The first model for a job.
 */
export function modelForJob(job) {
  return modelsForJob(job)[0];
}

/**
 * True when a failed launch is worth retrying on the next model: a quota, availability or model error, not a timeout or a denial.
 */
export function shouldTryNextModel({ ok, reason, detail }) {
  return !ok && reason === 'failed' && MODEL_ERROR.test(detail ?? '');
}

/**
 * The launch timeout in seconds for a job: BATON_AGY_TIMEOUT when set, else 1200 for review and 600 for every other job.
 */
export function timeoutForJob(job) {
  return Number(process.env.BATON_AGY_TIMEOUT) || JOB_TIMEOUT_SECONDS[job] || DEFAULT_TIMEOUT_SECONDS;
}

/**
 * How long to let the agy process run before killing it: its own timeout plus BATON_AGY_GRACE seconds (default 15).
 */
export function processTimeoutMs(seconds) {
  const raw = (process.env.BATON_AGY_GRACE ?? '').trim();
  const grace = raw !== '' && Number.isFinite(Number(raw)) && Number(raw) >= 0 ? Number(raw) : DEFAULT_KILL_GRACE_SECONDS;
  return (seconds + grace) * 1000;
}

/**
 * The last stdout line that starts with `{` and parses as JSON, or null. agy may print a warning first.
 */
function parseResult(stdout) {
  const lines = stdout.split('\n').map(line => line.trim()).filter(line => line.startsWith('{'));
  for (let i = lines.length - 1; i >= 0; i--) {
    try {
      return JSON.parse(lines[i]);
    } catch {
      // not the JSON line; keep looking
    }
  }
  return null;
}

/**
 * A launch's reason followed by the first line of its detail, when there is one: `failed: status TIMEOUT`.
 */
export function describeFailure(reason, detail) {
  const first = (detail ?? '').split('\n').map(line => line.trim()).find(Boolean);
  return first ? `${reason}: ${first}` : reason;
}

function firstLines(text, count) {
  return text.split('\n').map(line => line.trim()).filter(Boolean).slice(0, count).join('\n');
}

/**
 * Launch one headless Antigravity job, moving down the job's model chain on quota, availability or model errors.
 * The entry records the model that ran last, and `tried` when more than one did.
 */
export function launchAgy(options) {
  const models = modelsForJob(options.job);
  const tried = [];
  let result;
  for (const model of models) {
    tried.push(model);
    result = launchOnce(model, options);
    if (!shouldTryNextModel(result)) break;
  }
  if (tried.length > 1) result.entry.tried = tried;
  return result;
}

/**
 * One launch on one model. Success is read from the JSON, never from the exit code.
 */
function launchOnce(model, { job, prompt, allowEdits = false, timeoutSeconds, root = REPO_ROOT }) {
  const cmd = process.env.BATON_AGY_CMD || 'agy';
  const seconds = timeoutSeconds ?? timeoutForJob(job);

  const agyArgs = ['--print', prompt, '--output-format', 'json', '--print-timeout', `${seconds}s`, '--model', model];
  if (allowEdits) agyArgs.push('--mode', 'accept-edits');
  const runsWithNode = cmd.endsWith('.mjs');

  const started = Date.now();
  const run = spawnSync(runsWithNode ? process.execPath : cmd, runsWithNode ? [cmd, ...agyArgs] : agyArgs, {
    cwd: root,
    encoding: 'utf-8',
    timeout: processTimeoutMs(seconds),
    windowsHide: true
  });
  const wallSeconds = (Date.now() - started) / 1000;

  const output = `${run.stdout || ''}\n${run.stderr || ''}`;
  const parsed = run.error ? null : parseResult(run.stdout || '');
  const response = typeof parsed?.response === 'string' ? parsed.response : '';
  const usage = parsed?.usage ?? null;
  const deniedActions = Array.isArray(parsed?.denied_actions) ? parsed.denied_actions : [];
  const ok = parsed?.status === 'SUCCESS' && response.trim().length > 0;

  let reason = null;
  let detail = null;
  if (!ok) {
    if (run.error?.code === 'ENOENT') reason = 'not_installed';
    else if (run.error?.code === 'ETIMEDOUT') reason = 'timeout';
    else if (deniedActions.length > 0) reason = 'denied';
    else {
      reason = 'failed';
      const status = parsed && typeof parsed.status === 'string' && parsed.status !== 'SUCCESS' ? `status ${parsed.status}` : null;
      detail = run.error ? run.error.message : [status, firstLines(output, 3)].filter(Boolean).join('\n');
    }
  }

  const duration = typeof parsed?.duration_seconds === 'number' ? parsed.duration_seconds : wallSeconds;
  const entry = {
    job: job ?? null,
    model,
    ok,
    reason,
    seconds: Math.round(duration * 10) / 10,
    total_tokens: usage?.total_tokens ?? 0,
    at: new Date().toISOString()
  };

  return { ok, response, usage, deniedActions, reason, detail, entry };
}

/**
 * Add a launch to the state's delegation log, keeping the last 20.
 */
export function appendDelegation(state, entry) {
  state.delegations = [...(state.delegations ?? []), entry].slice(-DELEGATION_LIMIT);
}
