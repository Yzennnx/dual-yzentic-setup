import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { checkRules, globToRegExp, changedRules, parseOwns, gitChange } from './rules-check.mjs';

let root;
let files;
const put = (rel, text) => {
  const path = join(root, rel);
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, text);
  if (!files.includes(rel)) files.push(rel);
};
const doc = (name, { owns = [], rules = [`- [${name}#1] It works.`], extra = '' } = {}) =>
  `---\nowns:\n${owns.map(o => `  - ${o}`).join('\n')}\n---\n# ${name}\n\n## What the user sees\nx\n\n## Rules\n${rules.join('\n')}\n\n## How it works\nx\n\n## Limits and out of scope\nx\n${extra}`
    .replace('owns:\n\n', 'owns: []\n');
const noChange = { changed: [], added: [], diff: '', messages: '' };
const run = (change = noChange) => checkRules(root, { files, change });
const problems = (change) => run(change).problems;

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'rules-'));
  files = [];
  put('docs/rules/features/sessions.md', doc('sessions', { owns: ['src/session*.ts'] }));
  put('src/session.ts', 'x');
});

describe('rules-check', () => {
  it('is skipped while features/ holds only _example.md', () => {
    root = mkdtempSync(join(tmpdir(), 'rules-'));
    files = [];
    put('docs/rules/features/_example.md', 'not a real doc');
    assert.equal(run().skipped, true);
  });

  it('passes a clean repo and summarises warnings', () => {
    const r = run();
    assert.deepEqual(r.problems, []);
    assert.match(r.summary, /^rules: ok · 0 orphan files · 1 rules without a test$/);
  });

  it('1. shape: owns, sections, rule ids', () => {
    put('docs/rules/features/a.md', '# a\n\n## Rules\n- [b#1] wrong prefix\n- [a#1] ok\n- [a#1] dup\n- [a#x] bad\n');
    const text = problems().join('\n');
    assert.match(text, /a\.md: front matter needs an "owns:"/);
    assert.match(text, /a\.md: missing section "## What the user sees"/);
    assert.match(text, /rule b#1 must start with "a#"/);
    assert.match(text, /rule a#1 is already defined/);
    assert.match(text, /malformed rule "- \[a#x\] bad"/);
  });

  it('2. dead paths: an owns pattern with no file', () => {
    put('docs/rules/features/billing.md', doc('billing', { owns: ['src/billing*.ts'] }));
    assert.match(problems().join('\n'), /billing\.md: owns "src\/billing\*\.ts" matches no file/);
  });

  it('3. double owners', () => {
    put('docs/rules/features/more.md', doc('more', { owns: ['src/*.ts'] }));
    assert.match(problems().join('\n'), /src\/session\.ts is owned by more and sessions/);
  });

  it('4. PLAN tags: open tasks need an existing feature or [arch]; done tasks are exempt', () => {
    put('docs/PLAN.md', [
      '- [ ] Task 1.1 [sessions]: ok',
      '- [ ] Task 1.2 [arch]: ok',
      '- [ ] Task 1.3: no tag',
      '- [ ] Task 1.4 [nope]: unknown',
      '- [x] Task 1.5: done and untagged'
    ].join('\n'));
    const list = problems();
    assert.equal(list.length, 2);
    assert.match(list[0], /open task names no feature: "Task 1\.3/);
    assert.match(list[1], /\(unknown: nope\)/);
  });

  it('5. dead rule links: a test cites a rule that does not exist', () => {
    put('src/session.test.ts', "it('sessions#1 works', () => {});\n// covers sessions#9\n");
    const list = problems();
    assert.equal(list.length, 1);
    assert.match(list[0], /session\.test\.ts cites sessions#9/);
  });

  it('6. drift: an owned file changed and its doc did not', () => {
    const change = { ...noChange, changed: ['src/session.ts'] };
    assert.match(problems(change)[0], /sessions\.md may be stale: src\/session\.ts changed/);
    assert.deepEqual(problems({ ...change, changed: ['src/session.ts', 'docs/rules/features/sessions.md'] }), []);
    assert.deepEqual(problems({ ...change, messages: 'fix\n\nDocs: no behaviour change (sessions)\n' }), []);
    put('src/session.css', 'x');
    assert.deepEqual(problems({ ...noChange, changed: ['src/session.test.ts'] }), []);
  });

  it('6. drift: style files do not count', () => {
    put('docs/rules/features/ui.md', doc('ui', { owns: ['src/ui/*'] }));
    put('src/ui/a.css', 'x');
    assert.deepEqual(problems({ ...noChange, changed: ['src/ui/a.css'] }), []);
  });

  it('7. new orphans fail; old orphans only warn', () => {
    put('project-blueprint.json', JSON.stringify({ rules: { source: ['src/**/*.ts'], ignore: ['src/gen/**'] } }));
    put('src/old.ts', 'x');
    put('src/fresh.ts', 'x');
    put('src/gen/out.ts', 'x');
    put('src/fresh.test.ts', 'x');
    const r = run({ ...noChange, changed: ['src/fresh.ts'], added: ['src/fresh.ts', 'src/gen/out.ts', 'src/fresh.test.ts'] });
    assert.equal(r.problems.length, 1);
    assert.match(r.problems[0], /^src\/fresh\.ts is a new source file no doc owns/);
    assert.match(r.summary, /1 orphan files/);
  });

  it('8. rule tests: an added rule needs a citing test, unless manual', () => {
    const diff = '+- [sessions#1] It works.\n+- [sessions#2] (manual) By hand.\n';
    assert.match(problems({ ...noChange, diff })[0], /rule sessions#1 was added or reworded but no test cites it/);
    put('src/session.test.ts', "it('sessions#1 works', () => {});\n");
    assert.deepEqual(problems({ ...noChange, diff }), []);
  });
});

describe('helpers', () => {
  it('globToRegExp handles **, * and ?', () => {
    assert.ok(globToRegExp('src/**/*.ts').test('src/a/b/c.ts'));
    assert.ok(globToRegExp('src/**/*.ts').test('src/c.ts'));
    assert.ok(!globToRegExp('src/*.ts').test('src/a/c.ts'));
    assert.ok(globToRegExp('a?.ts').test('ab.ts'));
  });
  it('changedRules reads added rule lines only', () => {
    const rules = changedRules('--- a/x\n+++ b/x\n-- [a#1] old\n+- [a#1] new text\n+- [a#2] (manual) by hand\n+prose\n');
    assert.deepEqual(rules, [{ id: 'a#1', manual: false, text: 'new text' }, { id: 'a#2', manual: true, text: 'by hand' }]);
  });
  it('parseOwns reads lists, empty lists and missing keys', () => {
    assert.deepEqual(parseOwns('---\nowns:\n  - a/*.ts\n  - b.ts\n---\n'), ['a/*.ts', 'b.ts']);
    assert.deepEqual(parseOwns('---\nowns: []\n---\n'), []);
    assert.equal(parseOwns('# no front matter'), null);
  });
  it('gitChange sees branch commits, the working tree and untracked docs', () => {
    const g = (...a) => execFileSync('git', a, { cwd: root, stdio: 'ignore' });
    g('init', '-q', '-b', 'main');
    g('config', 'user.email', 't@t'); g('config', 'user.name', 't');
    put('a.txt', '1');
    g('add', '-A'); g('commit', '-q', '-m', 'base');
    g('checkout', '-q', '-b', 'feat');
    put('b.txt', '2');
    g('add', '-A'); g('commit', '-q', '-m', 'work\n\nDocs: no behaviour change (x)');
    put('a.txt', '3');
    put('docs/rules/features/new.md', '- [new#1] Fresh.\n');
    const c = gitChange(root);
    assert.deepEqual(c.changed.sort(), ['a.txt', 'b.txt', 'docs/rules/features/new.md']);
    assert.ok(c.added.includes('b.txt') && !c.added.includes('a.txt'));
    assert.match(c.messages, /Docs: no behaviour change \(x\)/);
    assert.match(c.diff, /\+- \[new#1\] Fresh\./);
  });
});
