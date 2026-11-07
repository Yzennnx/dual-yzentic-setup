#!/usr/bin/env node

/**
 * global-skills.mjs
 * Checks that the skills listed in global-skills.json are installed globally for both agents,
 * and with --install copies missing ones from the skill library and links them.
 *
 * Layout: real folders in ~/.agents/skills; ~/.claude/skills/<name> links to each (Claude Code);
 * ~/.gemini/config/skills links to ~/.agents/skills as a whole (Antigravity).
 *
 * Usage: node scripts/global-skills.mjs [--install] [--json] [--root <repo>] [--home <dir>]
 */

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const REPO_ROOT = path.resolve(path.dirname(__filename), '..');

function expandHome(p, home) {
  return p === '~' || p.startsWith('~/') ? path.join(home, p.slice(2)) : p;
}

function hasSkill(dir, name) {
  return fs.existsSync(path.join(dir, name, 'SKILL.md'));
}

function dirs(home) {
  return {
    store: path.join(home, '.agents', 'skills'),
    claude: path.join(home, '.claude', 'skills'),
    antigravity: path.join(home, '.gemini', 'config', 'skills')
  };
}

export function readManifest(root = REPO_ROOT, home = os.homedir()) {
  const file = path.join(root, 'global-skills.json');
  if (!fs.existsSync(file)) return null;
  const manifest = JSON.parse(fs.readFileSync(file, 'utf-8'));
  return {
    skills: [...new Set(manifest.skills ?? [])],
    library: expandHome(manifest.library ?? '~/skill-library', home)
  };
}

/** Which listed skills each agent cannot see. Null when the repo has no global-skills.json. */
export function checkGlobalSkills({ root = REPO_ROOT, home = os.homedir() } = {}) {
  const manifest = readManifest(root, home);
  if (!manifest) return null;
  const d = dirs(home);
  const claude = manifest.skills.filter(name => !hasSkill(d.claude, name));
  const antigravity = manifest.skills.filter(name => !hasSkill(d.antigravity, name));
  return { claude, antigravity, ok: claude.length === 0 && antigravity.length === 0 };
}

function link(target, at) {
  fs.mkdirSync(path.dirname(at), { recursive: true });
  // 'junction' needs no admin rights on Windows; other platforms ignore the type and make a symlink.
  fs.symlinkSync(target, at, 'junction');
}

/** Copies missing skills from the library into the store and links them for both agents. */
export function installGlobalSkills({ root = REPO_ROOT, home = os.homedir() } = {}) {
  const manifest = readManifest(root, home);
  if (!manifest) return null;
  const d = dirs(home);
  const result = { copied: [], linked: [], notInLibrary: [] };

  for (const name of manifest.skills) {
    if (!hasSkill(d.store, name)) {
      if (!hasSkill(manifest.library, name)) {
        result.notInLibrary.push(name);
        continue;
      }
      fs.mkdirSync(d.store, { recursive: true });
      fs.cpSync(path.join(manifest.library, name), path.join(d.store, name), { recursive: true });
      result.copied.push(name);
    }
    if (!hasSkill(d.claude, name) && !fs.existsSync(path.join(d.claude, name))) {
      link(path.join(d.store, name), path.join(d.claude, name));
      result.linked.push(`claude:${name}`);
    }
  }

  if (!fs.existsSync(d.antigravity)) {
    link(d.store, d.antigravity);
    result.linked.push('antigravity:skills');
  } else if (!fs.lstatSync(d.antigravity).isSymbolicLink()) {
    for (const name of manifest.skills) {
      if (hasSkill(d.store, name) && !fs.existsSync(path.join(d.antigravity, name))) {
        link(path.join(d.store, name), path.join(d.antigravity, name));
        result.linked.push(`antigravity:${name}`);
      }
    }
  }
  return result;
}

/** One session-start line when something is missing; nothing when all is installed. */
export function globalSkillsLine(root = REPO_ROOT, home = os.homedir()) {
  try {
    const res = checkGlobalSkills({ root, home });
    if (!res || res.ok) return [];
    const missing = [...new Set([...res.claude, ...res.antigravity])];
    return [`Global skills missing: ${missing.join(', ')} (run npm run skills:global -- --install)`];
  } catch {
    return [];
  }
}

function argValue(args, flag) {
  const i = args.indexOf(flag);
  return i >= 0 ? args[i + 1] : undefined;
}

export function main(args = process.argv.slice(2)) {
  const root = path.resolve(argValue(args, '--root') ?? REPO_ROOT);
  const home = path.resolve(argValue(args, '--home') ?? os.homedir());
  const json = args.includes('--json');

  if (args.includes('--install')) {
    const res = installGlobalSkills({ root, home });
    if (!res) return console.error('[Skills] global-skills.json not found.'), 1;
    if (json) console.log(JSON.stringify(res));
    else {
      if (res.copied.length) console.log(`[Skills] copied: ${res.copied.join(', ')}`);
      if (res.linked.length) console.log(`[Skills] linked: ${res.linked.join(', ')}`);
      if (res.notInLibrary.length) console.log(`[Skills] not in library, install by hand: ${res.notInLibrary.join(', ')}`);
    }
  }

  const check = checkGlobalSkills({ root, home });
  if (!check) return console.error('[Skills] global-skills.json not found.'), 1;
  if (json && !args.includes('--install')) console.log(JSON.stringify(check));
  if (!json) {
    if (check.ok) console.log('[Skills] all global skills installed for Claude and Antigravity.');
    if (check.claude.length) console.log(`[Skills] missing for Claude: ${check.claude.join(', ')}`);
    if (check.antigravity.length) console.log(`[Skills] missing for Antigravity: ${check.antigravity.join(', ')}`);
  }
  return check.ok ? 0 : 1;
}

if (process.argv[1] && path.resolve(process.argv[1]) === __filename) {
  process.exitCode = main();
}
