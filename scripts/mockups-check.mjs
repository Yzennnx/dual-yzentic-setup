/**
 * Mockup map checker (scripts/mockups-check.mjs)
 * A design that references mockups ends with a map table: mockup file | task | target component | fingerprint.
 * The fingerprint is the first 8 hex of the file's sha256. This checks the map covers every file in the
 * linked mockup folders and that no mapped file changed since its fingerprint was recorded.
 *
 *   node scripts/mockups-check.mjs docs/design/x.md   one design
 *   node scripts/mockups-check.mjs                    every docs/design/*.md that has a map
 */

import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve, dirname, basename, posix } from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const MOCKUPS = 'docs/design/mockups';
const IGNORED = ['README.md', 'canvas.json'];
const TEXT_EXT = /\.(html|css|svg|js|json|md|txt)$/i;

/**
 * First 8 hex of the sha256 of a file. Text files are hashed with LF endings so a checkout does not change it.
 */
export function fingerprintFile(path) {
  let data = readFileSync(path);
  if (TEXT_EXT.test(path)) data = Buffer.from(data.toString('utf-8').replace(/\r\n/g, '\n'));
  return createHash('sha256').update(data).digest('hex').slice(0, 8);
}

function cellText(cell) {
  const link = cell.match(/\[([^\]]*)\]\(([^)]*)\)/);
  return (link ? link[2] : cell).replace(/`/g, '').trim();
}

/**
 * The rows of the design's map table: the table whose first header cell starts with "Mockup".
 * Returns null when the design has no such table. A row is a skip when any cell starts with `skip:`.
 */
export function parseMap(text) {
  const lines = text.split(/\r?\n/);
  const start = lines.findIndex(line => /^\s*\|\s*mockup\b/i.test(line));
  if (start === -1) return null;
  const rows = [];
  for (const line of lines.slice(start + 1)) {
    if (!/^\s*\|/.test(line)) break;
    const cells = line.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());
    if (cells.every(c => /^:?-+:?$/.test(c))) continue;
    rows.push({
      file: cellText(cells[0] ?? '').replace(/^.*?mockups\//, ''),
      task: cells[1] ?? '',
      component: cellText(cells[2] ?? ''),
      skip: cells.find(c => /^skip:/i.test(c)) ?? null,
      fingerprint: (cells[3] ?? '').replace(/`/g, '').trim().toLowerCase()
    });
  }
  return rows;
}

/**
 * The mockup folders a design links, as paths relative to docs/design/mockups ('' is the mockups root).
 * A link to a file means its folder.
 */
export function mockupFolders(text, root = REPO_ROOT) {
  const folders = new Set();
  for (const match of text.matchAll(/\bmockups\/([^\s)>\]`'"|]*)/g)) {
    let rel = posix.normalize(match[1] || '.').replace(/^\.$/, '').replace(/\/$/, '');
    const abs = resolve(root, MOCKUPS, rel);
    if (!existsSync(abs)) continue;
    if (!statSync(abs).isDirectory()) rel = posix.dirname(rel).replace(/^\.$/, '');
    folders.add(rel);
  }
  return [...folders];
}

function filesIn(folder, root) {
  return readdirSync(resolve(root, MOCKUPS, folder), { withFileTypes: true })
    .filter(e => e.isFile() && !IGNORED.includes(e.name))
    .map(e => posix.join(folder, e.name));
}

/**
 * Check one design. `hasMap` is false when it has no map table (then it is not otherwise checked).
 */
export function checkDesign(designPath, root = REPO_ROOT) {
  const text = readFileSync(designPath, 'utf-8');
  const folders = mockupFolders(text, root);
  const rows = parseMap(text);
  const files = folders.flatMap(folder => filesIn(folder, root));
  if (rows === null) return { hasMap: false, folders, files, problems: [] };

  const problems = [];
  const mapped = new Set();
  for (const row of rows) {
    const target = files.find(f => f === row.file) ?? files.find(f => !row.file.includes('/') && basename(f) === row.file);
    if (!target) {
      problems.push(`missing: ${row.file} (mapped to ${row.task || '?'}, not in the linked folders)`);
      continue;
    }
    mapped.add(target);
    if (row.skip) continue;
    const now = fingerprintFile(resolve(root, MOCKUPS, target));
    if (row.fingerprint !== now) {
      problems.push(row.fingerprint
        ? `stale: ${target} (changed since ${row.task || '?'}; now ${now})`
        : `stale: ${target} (no fingerprint recorded; now ${now})`);
    }
  }
  for (const file of files) {
    if (!mapped.has(file)) problems.push(`unmapped: ${file} (fingerprint ${fingerprintFile(resolve(root, MOCKUPS, file))})`);
  }
  return { hasMap: true, folders, files, problems };
}

/**
 * Check every docs/design/*.md. Designs with a map report their problems. Designs that link mockups
 * but have no map go to `noMap`; with `changed` (repo-relative paths), those whose folders hold a
 * changed mockup also become problems.
 */
export function checkAll(root = REPO_ROOT, changed = null) {
  const dir = resolve(root, 'docs/design');
  const problems = [];
  const noMap = [];
  if (!existsSync(dir)) return { problems, noMap };
  for (const name of readdirSync(dir).filter(n => n.endsWith('.md')).sort()) {
    const result = checkDesign(resolve(dir, name), root);
    if (result.hasMap) {
      problems.push(...result.problems.map(p => `${name}: ${p}`));
    } else if (result.folders.length > 0) {
      noMap.push(name);
      const touched = (changed ?? []).filter(f => result.files.some(m => `${MOCKUPS}/${m}` === f.replace(/\\/g, '/')));
      if (touched.length > 0) problems.push(`${name}: no mockup map, but it links changed mockups (${touched.join(', ')})`);
    }
  }
  return { problems, noMap };
}

export function main(argv = process.argv.slice(2), root = REPO_ROOT) {
  if (argv[0]) {
    const result = checkDesign(resolve(root, argv[0]), root);
    if (!result.hasMap) {
      console.error(`no mockup map table in ${argv[0]} (a table whose first column is "Mockup file")`);
      return 1;
    }
    for (const p of result.problems) console.error(p);
    if (result.problems.length === 0) console.log(`mockup map ok: ${result.files.length} files`);
    return result.problems.length > 0 ? 1 : 0;
  }
  const { problems, noMap } = checkAll(root);
  for (const p of problems) console.error(p);
  if (noMap.length > 0) console.log(`no mockup map: ${noMap.join(', ')}`);
  if (problems.length === 0) console.log('mockup maps ok');
  return problems.length > 0 ? 1 : 0;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exit(main());
}
