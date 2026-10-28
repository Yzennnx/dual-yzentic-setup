import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { featureFacts, mapTable, featureView, replaceMap, main } from './rules-map.mjs';

let root;
const put = (rel, text) => {
  const path = join(root, rel);
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, text);
};
const feature = `---\nowns:\n  - src/session*.ts\n---\n# Sessions\n\n## What the user sees\nx\n\n## Rules\n- [sessions#1] Works.\n- [sessions#2] Also works.\n\n## How it works\nx\n\n## Limits and out of scope\nx\n`;

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'rules-map-'));
  execFileSync('git', ['init', '-q'], { cwd: root });
  put('docs/rules/features/sessions.md', feature);
  put('docs/rules/README.md', '# Rules\n<!-- rules:map -->\nold\n<!-- /rules:map -->\ntail\n');
  put('src/session.ts', 'x');
  put('src/session.test.ts', "it('sessions#1 works', () => {});\n");
  put('docs/PLAN.md', '- [ ] Task 1 [sessions]: open\n- [x] Task 2 [sessions]: done\n- [ ] Task 3 [arch]: other\n');
  put('docs/design/d.md', '# D\n| Mockup file | Task | Component | Fingerprint |\n| --- | --- | --- | --- |\n| pc/start.html | 1 | session | abcd1234 |\n| pc/x.css | 1 | skip: tokens | |\n');
});

describe('rules-map', () => {
  it('collects tasks, boards, rules and tests per feature', () => {
    const [f] = featureFacts(root);
    assert.equal(f.name, 'sessions');
    assert.deepEqual(f.owned.sort(), ['src/session.test.ts', 'src/session.ts']);
    assert.equal(f.tasks.length, 2);
    assert.equal(f.boards.length, 1);
    assert.deepEqual(f.rules.map(r => r.tests.length), [1, 0]);
  });

  it('renders the table row', () => {
    assert.match(mapTable(featureFacts(root)), /\| sessions \| \[sessions\.md\]\(features\/sessions\.md\) \| 1\/1 \| 1 \| 2 \| 1 \|/);
  });

  it('prints one feature with its rules and tests', () => {
    const view = featureView(featureFacts(root)[0]);
    assert.match(view, /owns: src\/session\*\.ts/);
    assert.match(view, /sessions#1: src\/session\.test\.ts/);
    assert.match(view, /sessions#2: no test/);
  });

  it('rewrites only between the markers', () => {
    assert.equal(main([], root), 0);
    const readme = readFileSync(join(root, 'docs/rules/README.md'), 'utf-8');
    assert.match(readme, /<!-- rules:map -->\n\| Feature/);
    assert.match(readme, /<!-- \/rules:map -->\ntail\n$/);
    assert.equal(replaceMap('no markers', 'x'), null);
  });
});
