/**
 * Rules map (scripts/rules-map.mjs)
 * Regenerates the feature map table in docs/rules/README.md between <!-- rules:map --> markers:
 * feature, doc, open/done tasks, boards, rules, rules with a test.
 *
 *   node scripts/rules-map.mjs             rewrite the table
 *   node scripts/rules-map.mjs <feature>   print one feature: owns, files, tasks, boards, rules with tests
 */

import { readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs';
import { resolve, dirname, basename, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkRules, globToRegExp } from './rules-check.mjs';
import { parseMap } from './mockups-check.mjs';

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const OPEN = '<!-- rules:map -->';
const CLOSE = '<!-- /rules:map -->';

/** Mockup map rows (not skipped) of every docs/design/*.md, as { file, component, design }. */
function boardRows(root) {
  const dir = resolve(root, 'docs/design');
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter(n => n.endsWith('.md')).flatMap(name =>
    (parseMap(readFileSync(resolve(dir, name), 'utf-8')) ?? []).filter(r => !r.skip).map(r => ({ file: r.file, component: r.component, design: name })));
}

/** A board belongs to a feature when its target component is one of the feature's files, by path or file name without extension. */
function boardsFor(feature, rows, owned) {
  return rows.filter(r => r.component && owned.some(f => f === r.component || basename(f, extname(f)) === basename(r.component, extname(r.component))));
}

/** The facts about each feature doc. */
export function featureFacts(root) {
  const result = checkRules(root, { change: { changed: [], added: [], diff: '', messages: '' } });
  if (result.skipped) return [];
  const rows = boardRows(root);
  return result.features.map(d => {
    const owned = result.files.filter(f => (d.owns ?? []).some(p => globToRegExp(p).test(f)));
    const tasks = result.tasks.filter(t => t.tags.includes(d.name));
    return {
      name: d.name, file: d.file, owns: d.owns ?? [], owned, tasks,
      boards: boardsFor(d, rows, owned),
      rules: d.rules.map(r => ({ ...r, tests: result.cited.get(r.id) ?? [] }))
    };
  });
}

export function mapTable(facts) {
  const lines = ['| Feature | Doc | Tasks open/done | Boards | Rules | With a test |', '| --- | --- | --- | --- | --- | --- |'];
  for (const f of facts) {
    const open = f.tasks.filter(t => !t.done).length;
    lines.push(`| ${f.name} | [${basename(f.file)}](features/${basename(f.file)}) | ${open}/${f.tasks.length - open} | ${f.boards.length} | ${f.rules.length} | ${f.rules.filter(r => r.tests.length > 0).length} |`);
  }
  return lines.join('\n');
}

export function featureView(f) {
  return [
    `${f.name} (${f.file})`,
    `owns: ${f.owns.join(', ') || '(nothing)'}`,
    `files (${f.owned.length}): ${f.owned.join(', ') || '(none)'}`,
    `tasks: ${f.tasks.map(t => `${t.done ? '[x]' : '[ ]'} ${t.text.slice(0, 60)}`).join(' | ') || '(none)'}`,
    `boards: ${f.boards.map(b => `${b.file} -> ${b.component}`).join(', ') || '(none)'}`,
    'rules:',
    ...f.rules.map(r => `  ${r.id}${r.manual ? ' (manual)' : ''}: ${r.tests.length > 0 ? [...new Set(r.tests)].join(', ') : 'no test'}`)
  ].join('\n');
}

/** Replace the text between the markers; null when the README lacks them. */
export function replaceMap(readme, table) {
  const a = readme.indexOf(OPEN);
  const b = readme.indexOf(CLOSE);
  if (a === -1 || b === -1 || b < a) return null;
  return `${readme.slice(0, a + OPEN.length)}\n${table}\n${readme.slice(b)}`;
}

export function main(argv = process.argv.slice(2), root = REPO_ROOT) {
  const facts = featureFacts(root);
  if (argv[0]) {
    const f = facts.find(x => x.name === argv[0]);
    if (!f) { console.error(`no feature doc "${argv[0]}" (have: ${facts.map(x => x.name).join(', ') || 'none'})`); return 1; }
    console.log(featureView(f));
    return 0;
  }
  const path = resolve(root, 'docs/rules/README.md');
  const next = replaceMap(readFileSync(path, 'utf-8'), mapTable(facts));
  if (next === null) { console.error(`docs/rules/README.md needs ${OPEN} and ${CLOSE} markers`); return 1; }
  writeFileSync(path, next);
  console.log(`feature map updated: ${facts.length} features`);
  return 0;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exit(main());
}
