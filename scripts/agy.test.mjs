import { describe, it, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { modelsForJob, modelForJob, shouldTryNextModel } from './agy.mjs';
import { parseArgs, buildPrompt } from './agy-build.mjs';

const KEYS = ['BATON_AGY_MODEL', 'BATON_AGY_MODEL_DEEP', 'BATON_AGY_MODEL_FAST'];
afterEach(() => { for (const k of KEYS) delete process.env[k]; });

describe('modelsForJob', () => {
  it('uses the deep chain for build, review, write_tests, diagnose and qa', () => {
    for (const job of ['build', 'review', 'write_tests', 'diagnose', 'qa']) {
      assert.deepEqual(modelsForJob(job), ['gemini-4-argon-medium', 'claude-sonnet-5-5-medium', 'gpt-oss-120b-medium']);
    }
  });
  it('uses the low chain for scout', () => {
    assert.deepEqual(modelsForJob('scout'), ['gemini-4-argon-low', 'claude-sonnet-5-5-low', 'gpt-oss-120b-medium']);
  });
  it('lets the DEEP and FAST variables replace the first entry', () => {
    process.env.BATON_AGY_MODEL_DEEP = 'm-deep';
    process.env.BATON_AGY_MODEL_FAST = 'm-fast';
    assert.equal(modelForJob('build'), 'm-deep');
    assert.equal((modelsForJob('build')).length, 3);
    assert.equal(modelForJob('scout'), 'm-fast');
  });
  it('lets BATON_AGY_MODEL override everything with no fallback', () => {
    process.env.BATON_AGY_MODEL = 'only';
    assert.deepEqual(modelsForJob('build'), ['only']);
    assert.deepEqual(modelsForJob('scout'), ['only']);
  });
});

describe('shouldTryNextModel', () => {
  it('retries on quota, availability and model errors only', () => {
    assert.equal(shouldTryNextModel({ ok: false, reason: 'failed', detail: 'Quota exhausted for model' }), true);
    assert.equal(shouldTryNextModel({ ok: false, reason: 'failed', detail: 'model gemini-4 not found' }), true);
    assert.equal(shouldTryNextModel({ ok: false, reason: 'failed', detail: 'status TIMEOUT' }), false);
    assert.equal(shouldTryNextModel({ ok: false, reason: 'timeout', detail: 'quota' }), false);
    assert.equal(shouldTryNextModel({ ok: true, reason: null, detail: null }), false);
  });
});

describe('agy-build parseArgs', () => {
  it('accepts a plan with tasks, a design, or a qa area', () => {
    assert.equal(parseArgs(['--plan', 'p.md', '--tasks', '1,2']).tasks, '1,2');
    assert.equal(parseArgs(['--design', 'd.md']).design, 'd.md');
    assert.equal(parseArgs(['--qa', 'lists']).qa, 'lists');
  });
  it('rejects a plan without tasks and unknown flags', () => {
    assert.ok(parseArgs(['--plan', 'p.md']).error);
    assert.ok(parseArgs(['--nope', 'x']).error);
    assert.ok(parseArgs([]).error);
  });
  it('names the document and tasks in the build prompt', () => {
    const prompt = buildPrompt({ plan: 'docs/specs/x.md', tasks: '3,4' });
    assert.ok((prompt).includes('3,4'));
    assert.ok((prompt).includes('docs/specs/x.md'));
    assert.ok((prompt).includes('one commit per task'));
  });
});
