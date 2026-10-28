import { describe, it, expect, beforeEach } from 'vitest';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { parseMap, fingerprintFile, checkDesign, checkAll } from './mockups-check.mjs';

let root;
const put = (rel, text) => {
  const path = join(root, rel);
  mkdirSync(join(path, '..'), { recursive: true });
  writeFileSync(path, text);
  return path;
};
const design = (rows) => `# D\n[mockups](mockups/pc/README.md)\n\n| Mockup file | Task | Component | Fingerprint |\n| --- | --- | --- | --- |\n${rows}\n`;

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'mockups-'));
  put('docs/design/mockups/pc/a.html', '<a>');
  put('docs/design/mockups/pc/b.css', 'b{}');
  put('docs/design/mockups/pc/README.md', 'ignored');
  put('docs/design/mockups/pc/canvas.json', '{}');
});

describe('parseMap', () => {
  it('returns null without a map table', () => {
    expect(parseMap('# D\n| a | b |\n| - | - |\n')).toBeNull();
  });
  it('reads rows and skips', () => {
    const rows = parseMap(design('| `pc/a.html` | R.1 | Start | abcd1234 |\n| pc/b.css | R.1 | skip: shared | |'));
    expect(rows.map(r => [r.file, r.task, r.skip])).toEqual([['pc/a.html', 'R.1', null], ['pc/b.css', 'R.1', 'skip: shared']]);
    expect(rows[0].fingerprint).toBe('abcd1234');
  });
});

describe('checkDesign', () => {
  it('passes when every file is mapped with its fingerprint or skipped', () => {
    const fp = fingerprintFile(join(root, 'docs/design/mockups/pc/a.html'));
    const path = put('docs/design/d.md', design(`| pc/a.html | R.1 | Start | ${fp} |\n| pc/b.css | R.1 | skip: tokens | |`));
    expect(checkDesign(path, root).problems).toEqual([]);
  });
  it('lists unmapped files, ignoring README and canvas.json', () => {
    const path = put('docs/design/d.md', design('| pc/a.html | R.1 | skip: x | |'));
    const { problems } = checkDesign(path, root);
    expect(problems).toHaveLength(1);
    expect(problems[0]).toMatch(/^unmapped: pc\/b\.css/);
  });
  it('flags a changed file as stale with the task', () => {
    const path = put('docs/design/d.md', design('| pc/a.html | R.7 | Start | 00000000 |\n| pc/b.css | R.7 | skip: x | |'));
    expect(checkDesign(path, root).problems[0]).toMatch(/^stale: pc\/a\.html \(changed since R\.7/);
  });
  it('hashes the same with CRLF endings', () => {
    const a = fingerprintFile(put('x/one.html', 'a\nb\n'));
    const b = fingerprintFile(put('x/two.html', 'a\r\nb\r\n'));
    expect(a).toBe(b);
  });
});

describe('checkAll', () => {
  it('only checks designs with a map and names the rest', () => {
    put('docs/design/old.md', '# Old\n[m](mockups/pc/README.md)\n');
    put('docs/design/d.md', design('| pc/a.html | R.1 | skip: x | |\n| pc/b.css | R.1 | skip: x | |'));
    expect(checkAll(root)).toEqual({ problems: [], noMap: ['old.md'] });
  });
  it('fails a map-less design only when its mockups changed', () => {
    put('docs/design/old.md', '# Old\n[m](mockups/pc/README.md)\n');
    const { problems } = checkAll(root, ['docs/design/mockups/pc/a.html']);
    expect(problems[0]).toMatch(/^old\.md: no mockup map/);
    expect(checkAll(root, ['docs/design/mockups/other/z.html']).problems).toEqual([]);
  });
});
