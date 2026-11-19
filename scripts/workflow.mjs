import { randomUUID } from 'node:crypto';
import { mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const LOCAL = '.agents/workflow.local.json';
const BLUEPRINT = 'project-blueprint.json';
const PRESETS = {
  classic: { agent: 'Claude', implementation: 'Claude (Sonnet builder for Tier 3)' },
  'agy-build': { agent: 'Claude', implementation: 'Antigravity build job', buildsWithAgy: true },
  'codex-agy': { agent: 'Codex', implementation: 'Codex' },
  'codex-solo': { agent: 'Codex', implementation: 'Codex', solo: true },
  'claude-solo': { agent: 'Claude', implementation: 'Claude', solo: true },
  'agy-solo': { agent: 'Antigravity', implementation: 'Antigravity (interactive)', solo: true },
};

function readConfig(root, name) {
  let raw;
  try {
    raw = readFileSync(resolve(root, name), 'utf-8');
  } catch (err) {
    if (err.code === 'ENOENT') return undefined;
    throw new Error(`Cannot read ${name} (${err.code}).`);
  }
  try {
    const config = JSON.parse(raw);
    if (config && typeof config === 'object' && !Array.isArray(config)) return config;
  } catch {
    // JSON parse errors can include local file contents.
  }
  throw new Error(`Invalid JSON object in ${name}.`);
}

function validateMode(mode, source) {
  if (typeof mode !== 'string' || !Object.hasOwn(PRESETS, mode)) {
    throw new Error(`Unknown workflow preset in ${source}. Run npm run workflow -- list.`);
  }
}

function readBlueprintMode(root) {
  const defaultMode = readConfig(root, BLUEPRINT)?.workflow?.mode;
  if (defaultMode !== undefined) validateMode(defaultMode, BLUEPRINT);
  return defaultMode;
}

export function resolveWorkflow(root, defaultMode = readBlueprintMode(root)) {
  const local = readConfig(root, LOCAL);
  if (local) validateMode(local.mode, LOCAL);
  const mode = local?.mode ?? defaultMode ?? 'classic';
  const source = local ? 'local override' : defaultMode ? 'blueprint default' : 'built-in default';
  return { ...PRESETS[mode], mode, source, defaultMode: defaultMode ?? 'classic' };
}

export function workflowSummary(workflow) {
  return `Workflow: ${workflow.mode} (${workflow.source})`;
}

export function soloJobMessage(workflow, job) {
  return `[${job}] ${workflow.mode} disables headless ${job.toLowerCase()}. Continue with ${workflow.agent} in the interactive session.`;
}

export function workflowStatusLines(workflow) {
  const { agent, solo, mode, source, defaultMode, implementation, buildsWithAgy } = workflow;
  const lines = [workflowSummary(workflow)];
  if (source === 'local override') lines.push(`Default: ${defaultMode}`);
  lines.push(`Interactive agent: ${agent}`, `Implementation: ${implementation}`);
  if (solo) {
    lines.push(`Tests and diagnosis: ${agent}`, 'Tier 3 review: developer or explicitly selected paired workflow', 'Headless agent launches: disabled');
  } else {
    lines.push(buildsWithAgy
      ? 'Tests: Antigravity build and rule-test jobs'
      : `Tests: Antigravity for eligible Gatekeeper work; ${mode === 'classic' ? 'Claude builder' : agent} for named Tier 3 tests`);
    lines.push('Eligible diagnosis, scouting, and Tier 3 review: Antigravity');
  }
  return lines;
}

function writePreference(file, mode) {
  mkdirSync(dirname(file), { recursive: true });
  const pending = `${file}.${randomUUID()}.tmp`;
  try {
    writeFileSync(pending, `${JSON.stringify({ mode })}\n`, { flag: 'wx' });
    renameSync(pending, file);
  } finally {
    rmSync(pending, { force: true });
  }
}

function main(args, root) {
  const command = args[0] ?? 'status';
  if (args.length > 1) throw new Error('Usage: npm run workflow -- <preset|status|list|reset>');
  if (command === 'list') {
    console.log(Object.keys(PRESETS).join('\n'));
    return;
  }
  const defaultMode = readBlueprintMode(root);
  const local = resolve(root, LOCAL);
  if (command === 'reset') {
    rmSync(local, { force: true });
  } else if (command !== 'status') {
    validateMode(command, 'command arguments');
    writePreference(local, command);
  }
  console.log(workflowStatusLines(resolveWorkflow(root, defaultMode)).join('\n'));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    main(process.argv.slice(2), process.cwd());
  } catch (err) {
    console.error(`[Workflow] ${err.message}`);
    process.exitCode = 1;
  }
}
