/**
 * Rules checker (scripts/rules-check.mjs)
 * docs/rules/features/<feature>.md files own code paths (front matter `owns:`) and carry numbered rules
 * ([feature#1]). This checks the docs against the repo and against the branch's change set:
 * shape, dead paths, double owners, PLAN tags, dead rule links, drift, new orphans, rule tests.
 *
 *   node scripts/rules-check.mjs     prints problems and exits 1, or one summary line
 *
 * Skipped while docs/rules/features/ holds nothing but _*.md files (an uninitialized template).
 */

import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { isTestFile } from './changes.mjs';

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const FEATURES = 'docs/rules/features';
const SECTIONS = ['## What the user sees', '## Rules', '## How it works', '## Limits and out of scope'];
const DEFAULT_TESTS = ['**/*.test.*', '**/*.spec.*', '**/test_*.py'];
const RULE_LINE = /^\s*- \[[^\]]*#[^\]]*\]/;
const RULE = /^- \[([a-z][a-z0-9-]*)#(\d+)\] (\(manual\) )?(\S.*)$/;
const STYLE = /\.(css|scss)$/i;

/** A glob (`**`, `*`, `?`) as an anchored regular expression over posix paths. */
export function globToRegExp(glob) {
  let out = '';
  for (let i = 0; i < glob.length; i++) {
    const c = glob[i];
    if (c === '*' && glob[i + 1] === '*') {
      i++;
      if (glob[i + 1] === '/') { i++; out += '(?:.*/)?'; } else out += '.*';
    } else if (c === '*') out += '[^/]*';
    else if (c === '?') out += '[^/]';
    else out += c.replace(/[.+^${}()|[\]\\]/g, '\\$&');
  }
  return new RegExp(`^${out}$`);
}

const matchesAny = (globs, path) => globs.some(g => globToRegExp(g).test(path));
const norm = p => p.replace(/\\/g, '/');

const read = (root, rel) => { try { return readFileSync(resolve(root, rel), 'utf-8').replace(/\r\n/g, '\n'); } catch { return null; } };

/** The blueprint's rules.* keys, with the default test globs. */
export function readRules(root) {
  let rules = {};
  try { rules = JSON.parse(read(root, 'project-blueprint.json')).rules ?? {}; } catch { /* no blueprint */ }
  return { source: rules.source ?? [], ignore: rules.ignore ?? [], tests: rules.tests ?? DEFAULT_TESTS };
}

/** Every file git knows or would add (tracked plus untracked, minus ignored), posix paths. */
export function listFiles(root) {
  try {
    return execFileSync('git', ['ls-files', '-co', '--exclude-standard', '-z'], { cwd: root, encoding: 'utf-8', stdio: ['ignore', 'pipe', 'ignore'] })
      .split('\0').filter(Boolean).map(norm);
  } catch {
    return [];
  }
}

/** `owns` list from a doc's front matter: null without an `owns:` key. */
export function parseOwns(text) {
  const fm = text.match(/^---\n([\s\S]*?)\n---/);
  if (!fm) return null;
  const lines = fm[1].split('\n');
  const at = lines.findIndex(l => /^owns:/.test(l));
  if (at === -1) return null;
  const inline = lines[at].replace(/^owns:\s*/, '').trim();
  if (inline === '[]') return [];
  const owns = [];
  for (const line of lines.slice(at + 1)) {
    const m = line.match(/^\s+-\s+(.+?)\s*$/);
    if (!m) break;
    owns.push(m[1].replace(/^["']|["']$/g, ''));
  }
  return owns;
}

/** The rules of a doc: `- [feature#n] (manual) text` lines. Malformed rule-looking lines go to `bad`. */
export function parseRules(text) {
  const rules = [];
  const bad = [];
  for (const line of text.split('\n')) {
    if (!RULE_LINE.test(line)) continue;
    const m = line.match(RULE);
    if (m) rules.push({ id: `${m[1]}#${m[2]}`, prefix: m[1], n: Number(m[2]), manual: Boolean(m[3]), text: m[4].trim() });
    else bad.push(line.trim());
  }
  return { rules, bad };
}

/** The docs: every features/*.md not starting with `_`, then architecture.md; invariants.md only for its rule IDs. */
export function loadDocs(root) {
  const dir = resolve(root, FEATURES);
  const names = existsSync(dir) ? readdirSync(dir).filter(n => n.endsWith('.md') && !n.startsWith('_')).sort() : [];
  const docs = names.map(n => ({ name: n.slice(0, -3), file: `${FEATURES}/${n}`, arch: false }));
  if (existsSync(resolve(root, 'docs/rules/architecture.md'))) docs.push({ name: 'architecture', file: 'docs/rules/architecture.md', arch: true });
  for (const d of docs) {
    d.text = read(root, d.file) ?? '';
    d.owns = parseOwns(d.text);
    Object.assign(d, parseRules(d.text));
  }
  const inv = read(root, 'docs/rules/invariants.md');
  const invariants = inv === null ? [] : parseRules(inv).rules.filter(r => r.prefix === 'inv');
  return { docs, features: docs.filter(d => !d.arch), invariants };
}

/** PLAN.md tasks: `- [ ] Task 1.2 [auth]: ...` with the tags found before the first colon. */
export function planTasks(root) {
  const text = read(root, 'docs/PLAN.md') ?? '';
  const tasks = [];
  for (const line of text.split('\n')) {
    const m = line.match(/^\s*[-*] \[( |x|X)\] (.*)$/);
    if (!m) continue;
    const head = m[2].split(':')[0];
    tasks.push({ done: m[1] !== ' ', text: m[2], tags: [...head.matchAll(/\[([a-z][a-z0-9-]*)\]/g)].map(t => t[1]) });
  }
  return tasks;
}

/** Rule IDs cited by test files: id -> files. Counts `feature#n` for known prefixes and any `covers feature#n`. */
export function citations(root, files, tests, prefixes) {
  const cited = new Map();
  for (const file of files.filter(f => matchesAny(tests, f))) {
    const text = read(root, file);
    if (text === null) continue;
    for (const m of text.matchAll(/\b([a-z][a-z0-9-]*)#(\d+)\b/g)) {
      const covers = text.slice(Math.max(0, m.index - 8), m.index).endsWith('covers ');
      if (!covers && !prefixes.includes(m[1])) continue;
      const id = `${m[1]}#${m[2]}`;
      cited.set(id, [...(cited.get(id) ?? []), file]);
    }
  }
  return cited;
}

/** Rules added or reworded in a unified diff of docs/rules: the `+- [id#n] text` lines, manual flag included. */
export function changedRules(diffText) {
  const out = [];
  for (const line of (diffText ?? '').split('\n')) {
    if (!line.startsWith('+') || line.startsWith('+++')) continue;
    const m = line.slice(1).match(RULE);
    if (m) out.push({ id: `${m[1]}#${m[2]}`, manual: Boolean(m[3]), text: m[4].trim() });
  }
  return out;
}

/**
 * Prompt lines that hand changed rules to a test writer that has not written the code (empty without rules).
 * Manual rules are left out: only a hand test can prove them.
 */
export function ruleTestLines(rules) {
  const testable = (rules ?? []).filter(r => !r.manual);
  if (testable.length === 0) return [];
  return [
    'Rules added or reworded on this branch (docs/rules). Write one test per rule from the rule text alone, and cite the rule ID in the test name or a "covers <id>" comment:',
    ...testable.map(r => `- ${r.id}: ${r.text}`),
    'Where the code disagrees with a rule, leave that test failing and report the mismatch in one line. Never bend a test to fit the code.'
  ];
}

const git = (root, args) => execFileSync('git', args, { cwd: root, encoding: 'utf-8', stdio: ['ignore', 'pipe', 'ignore'] });

/**
 * The branch's change set: main...HEAD plus the working tree. `changed` is every touched path (not deleted),
 * `added` the new ones, `diff` the docs/rules diff (untracked docs count as all added), `messages` the branch's commit messages.
 */
export function gitChange(root) {
  try {
    let base = 'HEAD';
    try { base = git(root, ['merge-base', 'main', 'HEAD']).trim(); } catch { /* no main: working tree only */ }
    const changed = new Set();
    const added = new Set();
    for (const line of git(root, ['diff', '--name-status', '--no-renames', base]).split('\n').filter(Boolean)) {
      const [status, file] = line.split('\t');
      if (status === 'D') continue;
      changed.add(norm(file));
      if (status === 'A') added.add(norm(file));
    }
    const untracked = git(root, ['ls-files', '-o', '--exclude-standard', '-z']).split('\0').filter(Boolean).map(norm);
    for (const f of untracked) { changed.add(f); added.add(f); }
    let diff = git(root, ['diff', base, '--', 'docs/rules']);
    for (const f of untracked.filter(f => f.startsWith('docs/rules/') && f.endsWith('.md'))) {
      diff += (read(root, f) ?? '').split('\n').map(l => `+${l}`).join('\n') + '\n';
    }
    const messages = base === 'HEAD' ? '' : git(root, ['log', '--format=%B', `${base}..HEAD`]);
    return { changed: [...changed], added: [...added], diff, messages };
  } catch {
    return { changed: [], added: [], diff: '', messages: '' };
  }
}

/**
 * Run the checks. `change` is the branch's change set (see gitChange); `files` the repo's files.
 * Returns { skipped } for an uninitialized template, else { problems, warnings, summary, ... }.
 */
export function checkRules(root = REPO_ROOT, { change = gitChange(root), files = listFiles(root) } = {}) {
  const { docs, features, invariants } = loadDocs(root);
  if (features.length === 0) return { skipped: true, problems: [], ruleTestProblems: [], warnings: [], summary: null };
  const cfg = readRules(root);
  const problems = [];
  const names = features.map(f => f.name);

  // 1. Shape
  const seen = new Map();
  for (const d of docs) {
    if (d.owns === null) problems.push(`${d.file}: front matter needs an "owns:" list (may be empty: owns: [])`);
    if (!d.arch) {
      for (const s of SECTIONS) if (!d.text.includes(`\n${s}`)) problems.push(`${d.file}: missing section "${s}"`);
    }
    for (const line of d.bad) problems.push(`${d.file}: malformed rule "${line.slice(0, 60)}" (use "- [${d.name}#1] text")`);
    for (const r of d.rules) {
      if (r.prefix !== d.name) problems.push(`${d.file}: rule ${r.id} must start with "${d.name}#"`);
      if (seen.has(r.id)) problems.push(`${d.file}: rule ${r.id} is already defined in ${seen.get(r.id)}`);
      else seen.set(r.id, d.file);
    }
  }
  const known = new Set([...seen.keys(), ...invariants.map(r => r.id)]);

  // 2. Dead paths, 3. double owners
  const owners = new Map();
  for (const d of docs) {
    for (const pattern of d.owns ?? []) {
      const hits = files.filter(f => globToRegExp(pattern).test(f));
      if (hits.length === 0) problems.push(`${d.file}: owns "${pattern}" matches no file (fix or remove it)`);
      for (const f of hits) owners.set(f, [...new Set([...(owners.get(f) ?? []), d.name])]);
    }
  }
  for (const [f, who] of owners) if (who.length > 1) problems.push(`${f} is owned by ${[...who].sort().join(" and ")} (one owner per file)`);

  // 4. PLAN tags
  const tasks = planTasks(root);
  for (const t of tasks.filter(t => !t.done)) {
    if (!t.tags.some(tag => tag === 'arch' || names.includes(tag))) {
      const unknown = t.tags.length > 0 ? ` (unknown: ${t.tags.join(', ')})` : '';
      problems.push(`PLAN.md: open task names no feature${unknown}: "${t.text.slice(0, 50)}" (tag it [feature] or [arch])`);
    }
  }

  // 5. Dead rule links
  const cited = citations(root, files, cfg.tests, [...names, 'architecture', 'inv']);
  for (const [id, where] of cited) if (!known.has(id)) problems.push(`${where[0]} cites ${id}, which is not a rule in docs/rules`);

  // 6. Drift
  const docFiles = new Set(docs.map(d => d.file));
  const trailers = [...(change.messages ?? '').matchAll(/^Docs: no behaviour change \(([^)]*)\)/gm)].flatMap(m => m[1].split(',').map(s => s.trim()));
  const isTest = f => isTestFile(f) || matchesAny(cfg.tests, f);
  for (const d of docs) {
    if (change.changed.includes(d.file) || trailers.includes(d.name)) continue;
    const hit = change.changed.find(f => owners.get(f)?.includes(d.name) && !STYLE.test(f) && !isTest(f) && !docFiles.has(f));
    if (hit) problems.push(`${d.file.split('/').pop()} may be stale: ${hit} changed (edit the doc, or add "Docs: no behaviour change (${d.name})" to a commit)`);
  }

  // 7. New orphans, and the old ones as a warning
  const isSource = f => matchesAny(cfg.source, f) && !isTest(f) && !matchesAny(cfg.ignore, f);
  const orphans = cfg.source.length === 0 ? [] : files.filter(f => isSource(f) && !owners.has(f));
  for (const f of orphans.filter(f => change.added.includes(f))) problems.push(`${f} is a new source file no doc owns (add it to a feature's "owns" in docs/rules/features/)`);
  const oldOrphans = orphans.filter(f => !change.added.includes(f));

  // 8. Rule tests (kept apart: the baton checks them again after the Gatekeeper has written tests)
  const ruleTestProblems = [];
  const mine = new Map(docs.flatMap(d => d.rules).concat(invariants).map(r => [r.id, r]));
  for (const r of changedRules(change.diff)) {
    if (r.manual || !mine.has(r.id) || cited.has(r.id)) continue;
    ruleTestProblems.push(`rule ${r.id} was added or reworded but no test cites it (name the test "${r.id} ..." or add "// covers ${r.id}")`);
  }

  problems.push(...ruleTestProblems);
  const untested = [...mine.values()].filter(r => !r.manual && !cited.has(r.id)).length;
  const warnings = [`${oldOrphans.length} orphan files`, `${untested} rules without a test`];
  const summary = `rules: ${problems.length === 0 ? 'ok' : `${problems.length} problems`} · ${warnings.join(' · ')}`;
  return { skipped: false, problems, ruleTestProblems, warnings, summary, docs, features, tasks, owners, cited, files };
}

export function main(root = REPO_ROOT) {
  const result = checkRules(root);
  if (result.skipped) { console.log('rules: skipped (no feature docs yet)'); return 0; }
  for (const p of result.problems) console.error(p);
  console.log(result.summary);
  return result.problems.length > 0 ? 1 : 0;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exit(main());
}
