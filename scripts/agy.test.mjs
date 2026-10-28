import { describe, it, expect, afterEach } from 'vitest';
import { modelsForJob, modelForJob, shouldTryNextModel } from './agy.mjs';
import { parseArgs, buildPrompt } from './agy-build.mjs';

const KEYS = ['BATON_AGY_MODEL', 'BATON_AGY_MODEL_DEEP', 'BATON_AGY_MODEL_FAST'];
afterEach(() => { for (const k of KEYS) delete process.env[k]; });

describe('modelsForJob', () => {
  it('uses the deep chain for build, review, write_tests, diagnose and qa', () => {
    for (const job of ['build', 'review', 'write_tests', 'diagnose', 'qa']) {
      expect(modelsForJob(job)).toEqual(['gemini-4-argon-medium', 'claude-sonnet-5-5-medium', 'gpt-oss-120b-medium']);
    }
  });
  it('uses the low chain for scout', () => {
    expect(modelsForJob('scout')).toEqual(['gemini-4-argon-low', 'claude-sonnet-5-5-low', 'gpt-oss-120b-medium']);
  });
  it('lets the DEEP and FAST variables replace the first entry', () => {
    process.env.BATON_AGY_MODEL_DEEP = 'm-deep';
    process.env.BATON_AGY_MODEL_FAST = 'm-fast';
    expect(modelForJob('build')).toBe('m-deep');
    expect(modelsForJob('build')).toHaveLength(3);
    expect(modelForJob('scout')).toBe('m-fast');
  });
  it('lets BATON_AGY_MODEL override everything with no fallback', () => {
    process.env.BATON_AGY_MODEL = 'only';
    expect(modelsForJob('build')).toEqual(['only']);
    expect(modelsForJob('scout')).toEqual(['only']);
  });
});

describe('shouldTryNextModel', () => {
  it('retries on quota, availability and model errors only', () => {
    expect(shouldTryNextModel({ ok: false, reason: 'failed', detail: 'Quota exhausted for model' })).toBe(true);
    expect(shouldTryNextModel({ ok: false, reason: 'failed', detail: 'model gemini-4 not found' })).toBe(true);
    expect(shouldTryNextModel({ ok: false, reason: 'failed', detail: 'status TIMEOUT' })).toBe(false);
    expect(shouldTryNextModel({ ok: false, reason: 'timeout', detail: 'quota' })).toBe(false);
    expect(shouldTryNextModel({ ok: true, reason: null, detail: null })).toBe(false);
  });
});

describe('agy-build parseArgs', () => {
  it('accepts a plan with tasks, a design, or a qa area', () => {
    expect(parseArgs(['--plan', 'p.md', '--tasks', '1,2']).tasks).toBe('1,2');
    expect(parseArgs(['--design', 'd.md']).design).toBe('d.md');
    expect(parseArgs(['--qa', 'lists']).qa).toBe('lists');
  });
  it('rejects a plan without tasks and unknown flags', () => {
    expect(parseArgs(['--plan', 'p.md']).error).toBeTruthy();
    expect(parseArgs(['--nope', 'x']).error).toBeTruthy();
    expect(parseArgs([]).error).toBeTruthy();
  });
  it('names the document and tasks in the build prompt', () => {
    const prompt = buildPrompt({ plan: 'docs/specs/x.md', tasks: '3,4' });
    expect(prompt).toContain('3,4');
    expect(prompt).toContain('docs/specs/x.md');
    expect(prompt).toContain('one commit per task');
  });
});
