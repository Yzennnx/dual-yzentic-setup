#!/usr/bin/env node

/**
 * skills-manager.mjs
 * Reversible skill soft-delete and archival manager.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..');

const SKILL_NAME_PATTERN = /^[a-z0-9][a-z0-9-]*$/;

function skillPaths(root) {
  return {
    skillsDir: path.resolve(root, '.agents', 'skills'),
    archiveDir: path.resolve(root, '.agents', 'skills-archive')
  };
}

/**
 * Ensure archive directory exists
 */
export function ensureDirs({ root = REPO_ROOT } = {}) {
  const { skillsDir, archiveDir } = skillPaths(root);
  if (!fs.existsSync(skillsDir)) {
    fs.mkdirSync(skillsDir, { recursive: true });
  }
  if (!fs.existsSync(archiveDir)) {
    fs.mkdirSync(archiveDir, { recursive: true });
  }
}

/**
 * List all active and archived skills
 */
export function listSkills({ root = REPO_ROOT } = {}) {
  ensureDirs({ root });
  const { skillsDir, archiveDir } = skillPaths(root);

  const getSubdirs = (dir) => {
    if (!fs.existsSync(dir)) return [];
    return fs.readdirSync(dir, { withFileTypes: true })
      .filter(entry => entry.isDirectory() && !entry.name.startsWith('_'))
      .map(entry => entry.name)
      .sort();
  };

  return {
    active: getSubdirs(skillsDir),
    archived: getSubdirs(archiveDir)
  };
}

/**
 * Enable (restore) a skill from archive
 */
export function enableSkill(skillName, { root = REPO_ROOT } = {}) {
  ensureDirs({ root });
  const { skillsDir, archiveDir } = skillPaths(root);
  const source = path.join(archiveDir, skillName);
  const target = path.join(skillsDir, skillName);

  if (!fs.existsSync(source)) {
    if (fs.existsSync(target)) {
      return { success: true, message: `Skill '${skillName}' is already active.` };
    }
    throw new Error(`Skill '${skillName}' not found in archive: ${source}`);
  }

  if (fs.existsSync(target)) {
    throw new Error(`Skill '${skillName}' already exists in active skills: ${target}`);
  }

  fs.renameSync(source, target);
  return { success: true, message: `Skill '${skillName}' enabled (moved to active skills).` };
}

/**
 * Disable (soft-delete) a skill into archive
 */
export function disableSkill(skillName, { root = REPO_ROOT } = {}) {
  ensureDirs({ root });
  const { skillsDir, archiveDir } = skillPaths(root);
  const source = path.join(skillsDir, skillName);
  const target = path.join(archiveDir, skillName);

  if (!fs.existsSync(source)) {
    if (fs.existsSync(target)) {
      return { success: true, message: `Skill '${skillName}' is already archived.` };
    }
    throw new Error(`Skill '${skillName}' not found in active skills: ${source}`);
  }

  if (fs.existsSync(target)) {
    throw new Error(`Skill '${skillName}' already exists in archive: ${target}`);
  }

  fs.renameSync(source, target);
  return { success: true, message: `Skill '${skillName}' disabled (moved to archive).` };
}

/**
 * Sync skills against an explicit list: archive everything else, restore what is listed.
 * Throws before moving anything if a name is not a known skill.
 */
export function syncSkillsToList(names, { root = REPO_ROOT } = {}) {
  const keepSkills = new Set(names);
  const currentSkills = listSkills({ root });
  const known = new Set([...currentSkills.active, ...currentSkills.archived]);

  const unknown = [...keepSkills].filter(name => !SKILL_NAME_PATTERN.test(name) || !known.has(name));
  if (unknown.length > 0) {
    throw new Error(`Unknown skills: ${unknown.map(name => name || '(empty)').join(', ')}`);
  }

  const disabled = [];
  const enabled = [];

  // Archive any active skill not in the list
  for (const skill of currentSkills.active) {
    if (!keepSkills.has(skill)) {
      disableSkill(skill, { root });
      disabled.push(skill);
    }
  }

  // Restore any archived skill that is in the list
  for (const skill of currentSkills.archived) {
    if (keepSkills.has(skill)) {
      enableSkill(skill, { root });
      enabled.push(skill);
    }
  }

  return {
    active_count: keepSkills.size,
    archived_count: listSkills({ root }).archived.length,
    disabled,
    enabled
  };
}

/**
 * Pull `--root <path>` out of the CLI args. Returns the resolved root and the remaining args.
 */
function takeRoot(args) {
  const index = args.indexOf('--root');
  if (index === -1) return { root: REPO_ROOT, rest: args };
  const value = args[index + 1];
  if (!value || value.startsWith('--')) throw new Error('--root requires a path');
  return { root: path.resolve(value), rest: [...args.slice(0, index), ...args.slice(index + 2)] };
}

/**
 * CLI Entry point
 */
export async function main() {
  try {
    const { root, rest: args } = takeRoot(process.argv.slice(2));
    const command = args[0] || 'list';

    if (command === 'list') {
      const skills = listSkills({ root });
      if (args.includes('--json')) {
        console.log(JSON.stringify(skills, null, 2));
      } else {
        console.log('\n=== Skills Catalog ===');
        console.log(`Active (${skills.active.length}):`);
        skills.active.forEach(s => console.log(`  ✓ ${s}`));
        console.log(`\nArchived (${skills.archived.length}):`);
        skills.archived.forEach(s => console.log(`  - ${s} (use npm run skill:enable ${s})`));
        console.log('======================\n');
      }
      process.exit(0);
    }

    if (command === 'enable') {
      const name = args[1];
      if (!name) {
        console.error('Error: specify skill name to enable. Example: npm run skill:enable pitch-architect');
        process.exit(1);
      }
      const res = enableSkill(name, { root });
      console.log(`[Skills Manager] ${res.message}`);
      process.exit(0);
    }

    if (command === 'disable') {
      const name = args[1];
      if (!name) {
        console.error('Error: specify skill name to disable. Example: npm run skill:disable archify');
        process.exit(1);
      }
      const res = disableSkill(name, { root });
      console.log(`[Skills Manager] ${res.message}`);
      process.exit(0);
    }

    console.error(`Unknown command: ${command}. Use list, enable, or disable.`);
    process.exit(1);
  } catch (err) {
    console.error(`[Skills Manager Error] ${err.message}`);
    process.exit(1);
  }
}

// Execute if run directly
if (process.argv[1] && path.resolve(process.argv[1]) === __filename) {
  main();
}
