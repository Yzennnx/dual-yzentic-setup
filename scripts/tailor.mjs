#!/usr/bin/env node

/**
 * tailor.mjs
 * Spec-driven setup tailoring: validates and applies the manifest in project-blueprint.json.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { syncSkillsToList } from './skills-manager.mjs';
import { generateRoadmap } from './roadmap.mjs';
import { installHooks } from './install-hooks.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..');

export const ALWAYS_KEPT_SKILLS = ['tailor-setup', 'fast-track', 'caveman', 'ponytail'];

const PRIORITIES = ['P0', 'P1', 'P2'];
const SKILL_NAME_PATTERN = /^[a-z0-9][a-z0-9-]*$/;

const isText = (value) => typeof value === 'string' && value.trim().length > 0;
const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

/**
 * Read installed skill names without creating directories
 */
function readSkillDirs(root) {
  const read = (folder) => {
    const dir = path.resolve(root, '.agents', folder);
    if (!fs.existsSync(dir)) return [];
    return fs.readdirSync(dir, { withFileTypes: true })
      .filter(entry => entry.isDirectory() && !entry.name.startsWith('_'))
      .map(entry => entry.name)
      .sort();
  };
  return { active: read('skills'), archived: read('skills-archive') };
}

function repoFileProblem(sourceSpec, root) {
  if (!isText(sourceSpec)) return 'must be a repo-relative path to docs/rules/README.md';
  if (path.isAbsolute(sourceSpec)) return 'must be relative to the repo root';
  const resolved = path.resolve(root, sourceSpec);
  const relative = path.relative(root, resolved);
  if (relative.startsWith('..') || path.isAbsolute(relative)) return 'must be inside the repo';
  if (!fs.existsSync(resolved) || !fs.statSync(resolved).isFile()) return `file not found: ${sourceSpec}`;
  return null;
}

/**
 * Validate the tailoring manifest. Returns a list of problems, each prefixed with its field path.
 */
export function validateManifest(blueprint, { root = REPO_ROOT } = {}) {
  const project = blueprint?.project;
  if (!isObject(project)) {
    return ['project: missing or not an object'];
  }

  const problems = [];
  const add = (field, message) => problems.push(`${field}: ${message}`);

  if (!isText(project.name)) add('project.name', 'must be a non-empty string');
  if (!isText(project.description)) add('project.description', 'must be a non-empty string');
  if (project.archetype !== 'custom') add('project.archetype', 'must be "custom"');

  const rulesProblem = repoFileProblem(project.source_rules, root);
  if (rulesProblem) add('project.source_rules', rulesProblem);

  const source = blueprint.rules?.source;
  if (!Array.isArray(source) || source.length === 0 || !source.every(isText)) {
    problems.push('rules.source: must be a non-empty array of globs where the code lives (for example "src/**/*.ts")');
  }

  if (!isObject(project.stack)) add('project.stack', 'must be an object');

  if (project.developer !== undefined && !isText(project.developer)) {
    add('project.developer', 'must be a non-empty string');
  }

  if (!Array.isArray(project.skills)) {
    add('project.skills', 'must be an array of skill names');
  } else {
    const installed = readSkillDirs(root);
    const known = new Set([...installed.active, ...installed.archived]);
    const unknown = [...new Set(project.skills)].filter(
      name => typeof name !== 'string' || !SKILL_NAME_PATTERN.test(name) || !known.has(name)
    );
    if (unknown.length > 0) {
      add('project.skills', `unknown skills: ${unknown.map(name => name || '(empty)').join(', ')}`);
    }
  }

  if (!isText(project.verify?.test)) add('project.verify.test', 'must be a non-empty command');
  const scoped = project.verify?.test_scoped;
  if (scoped !== undefined && (!isText(scoped) || !scoped.includes('{scope}'))) {
    add('project.verify.test_scoped', 'must be a command containing {scope}');
  }

  const e2e = project.verify?.e2e;
  if (e2e !== undefined && !isText(e2e)) add('project.verify.e2e', 'must be a non-empty command');

  if (!Array.isArray(project.roadmap) || project.roadmap.length === 0) {
    add('project.roadmap', 'must contain at least one task');
  } else {
    const seenIds = new Set();
    project.roadmap.forEach((task, index) => {
      const field = (name) => `project.roadmap[${index}].${name}`;
      if (!isObject(task)) {
        add(`project.roadmap[${index}]`, 'must be an object');
        return;
      }
      if (!isText(task.id)) add(field('id'), 'must be a non-empty string');
      else if (seenIds.has(task.id)) add(field('id'), `duplicate id "${task.id}"`);
      else seenIds.add(task.id);
      if (!isText(task.title)) add(field('title'), 'must be a non-empty string');
      if (!PRIORITIES.includes(task.priority)) add(field('priority'), `must be one of ${PRIORITIES.join(', ')}`);
      if (!isText(task.description)) add(field('description'), 'must be a non-empty string');
      if (!Array.isArray(task.features) || task.features.length === 0 || !task.features.every(isText)) {
        add(field('features'), 'must list at least one feature name (or "arch")');
      } else {
        for (const feature of task.features) {
          if (feature !== 'arch' && !fs.existsSync(path.resolve(root, 'docs', 'rules', 'features', `${feature}.md`))) {
            add(field('features'), `no feature doc docs/rules/features/${feature}.md`);
          }
        }
      }
    });
  }

  return problems;
}

const WRITTEN_FILES = [
  'docs/PLAN.md',
  'package.json',
  '.agents/sync/handoff.json',
  '.agents/sync/handoff.md',
  'project-blueprint.json'
];

function readBlueprint(root) {
  const blueprintPath = path.resolve(root, 'project-blueprint.json');
  if (!fs.existsSync(blueprintPath)) {
    throw new Error(`project-blueprint.json not found at ${blueprintPath}`);
  }
  try {
    return JSON.parse(fs.readFileSync(blueprintPath, 'utf-8'));
  } catch (err) {
    throw new Error(`project-blueprint.json is not valid JSON: ${err.message}`);
  }
}

const writeJson = (filePath, data) => fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');

/**
 * Validate the manifest, then apply it. Nothing is written unless validation passes.
 */
export function tailorProject({ root = REPO_ROOT, dryRun = false, force = false } = {}) {
  const blueprint = readBlueprint(root);

  if (blueprint.status === 'initialized' && !force) {
    throw new Error('Project is already initialized. Re-run with --force to overwrite docs/PLAN.md and re-sync skills.');
  }

  const problems = validateManifest(blueprint, { root });
  if (problems.length > 0) {
    const err = new Error('Manifest in project-blueprint.json is invalid:');
    err.problems = problems;
    throw err;
  }

  const project = blueprint.project;
  const installed = readSkillDirs(root);
  const known = new Set([...installed.active, ...installed.archived]);
  const keep = new Set([...project.skills, ...ALWAYS_KEPT_SKILLS.filter(name => known.has(name))]);
  const changes = {
    archive: installed.active.filter(name => !keep.has(name)),
    restore: installed.archived.filter(name => keep.has(name)),
    write: WRITTEN_FILES
  };

  if (dryRun) {
    return { dryRun: true, changes, project };
  }

  // 1. Sync skills to the manifest list
  syncSkillsToList([...keep], { root });

  // 2. Render docs/PLAN.md
  const roadmap = generateRoadmap({
    name: project.name,
    desc: project.description,
    developer: project.developer,
    preset: project.archetype,
    tasks: project.roadmap
  });
  fs.writeFileSync(path.resolve(root, 'docs', 'PLAN.md'), roadmap, 'utf-8');

  // 3. Update package.json
  const packagePath = path.resolve(root, 'package.json');
  if (fs.existsSync(packagePath)) {
    const pkg = JSON.parse(fs.readFileSync(packagePath, 'utf-8'));
    pkg.name = project.name.toLowerCase().replace(/[^a-z0-9_-]/g, '-');
    pkg.description = project.description;
    writeJson(packagePath, pkg);
  }

  // 4. Reset Sync Bus
  const syncDir = path.resolve(root, '.agents', 'sync');
  fs.mkdirSync(syncDir, { recursive: true });
  const timestamp = new Date().toISOString();
  const developerLine = project.developer ? `- **Developer:** ${project.developer}\n` : '';
  writeJson(path.join(syncDir, 'handoff.json'), {
    version: '1.0',
    task_id: 'INIT-01',
    active_agent: 'claude',
    status: 'idle',
    turn_count: 0,
    max_turns: 5,
    last_updated: timestamp,
    summary: `Project tailored (${project.name} - ${project.archetype})`,
    files_modified: []
  });
  fs.writeFileSync(path.join(syncDir, 'handoff.md'), `# Agent Handoff Ticket: INIT-01

- **Status:** idle
- **Active Agent:** claude
- **Turn:** 0 / 5
- **Timestamp:** ${timestamp}

## Project Tailored
- **Name:** ${project.name}
- **Source Rules:** ${project.source_rules}
- **Active Skills:** ${keep.size} (Archived: ${installed.archived.length + changes.archive.length - changes.restore.length})
${developerLine}`, 'utf-8');

  // 5. Install git pre-commit hook
  if (fs.existsSync(path.resolve(root, '.git'))) {
    installHooks({ root });
  }

  // 6. Mark initialized last, so a failure above leaves the command re-runnable
  blueprint.status = 'initialized';
  blueprint.rules = { ignore: [], tests: ['**/*.test.*', '**/*.spec.*', '**/test_*.py'], ...blueprint.rules };
  writeJson(path.resolve(root, 'project-blueprint.json'), blueprint);

  return { dryRun: false, changes, project };
}

/**
 * CLI Entry
 */
export function main() {
  const args = process.argv.slice(2);
  // `npm run tailor --dry-run` (without `--`) is swallowed by npm and only reaches us as this env var
  const options = { dryRun: process.env.npm_config_dry_run === 'true', force: false };

  try {
    for (let i = 0; i < args.length; i++) {
      if (args[i] === '--dry-run') options.dryRun = true;
      else if (args[i] === '--force') options.force = true;
      else if (args[i] === '--root') {
        if (!args[i + 1] || args[i + 1].startsWith('--')) throw new Error('--root requires a path');
        options.root = path.resolve(args[++i]);
      } else {
        throw new Error(`Unknown argument: ${args[i]}. Use --dry-run, --force, or --root <path>.`);
      }
    }

    const res = tailorProject(options);
    const list = (names) => (names.length > 0 ? names.join(', ') : '(none)');
    console.log(`[Tailor] archive: ${list(res.changes.archive)}`);
    console.log(`[Tailor] restore: ${list(res.changes.restore)}`);
    console.log(`[Tailor] write: ${list(res.changes.write)}`);
    console.log(res.dryRun ? '[Tailor] Dry run: nothing written.' : '[Tailor] Project tailored.');
    process.exit(0);
  } catch (err) {
    console.error(`[Tailor Error] ${err.message}`);
    (err.problems || []).forEach(problem => console.error(`  - ${problem}`));
    process.exit(1);
  }
}

// Execute if run directly
if (process.argv[1] && path.resolve(process.argv[1]) === __filename) {
  main();
}
