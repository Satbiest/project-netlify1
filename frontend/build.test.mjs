import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import vm from 'node:vm';
import { build, publicApiUrl } from './build.mjs';

const outputDirectory = () => mkdtempSync(join(tmpdir(), 'cvboost-netlify-test-'));

test('preview build has rendered HTML, public assets, and no live endpoint', () => {
  const { output, files } = build({ output: outputDirectory(), apiUrl: '' });
  assert.equal(files.length, 7);
  const html = readFileSync(join(output, 'index.html'), 'utf8');
  assert(!html.includes('{%') && !html.includes('{{'));
  assert(html.includes('/config.js') && html.includes('data-max-mb="5"'));
  const context = { window: {} };
  vm.runInNewContext(readFileSync(join(output, 'config.js'), 'utf8'), context);
  assert.equal(context.window.CVBOOST_CONFIG.staticMode, true);
  assert.equal(context.window.CVBOOST_CONFIG.apiBaseUrl, '');
  assert.equal(JSON.parse(readFileSync(join(output, 'data/demo.json'))).metadata.mode, 'demo');
});

test('connected build writes only the public backend origin', () => {
  const { output } = build({ output: outputDirectory(), apiUrl: 'https://cvboost.example.com/' });
  const context = { window: {} };
  vm.runInNewContext(readFileSync(join(output, 'config.js'), 'utf8'), context);
  assert.equal(context.window.CVBOOST_CONFIG.apiBaseUrl, 'https://cvboost.example.com');
  assert(!readFileSync(join(output, 'config.js'), 'utf8').includes('GEMINI_API_KEY'));
});

test('rejects private HTTP and malformed addresses before building', () => {
  for (const url of ['http://10.150.237.220:8000', 'https://x.example/api',
    'https://user:password@x.example', 'https://x.example?key=secret', 'not-a-url']) {
    assert.throws(() => publicApiUrl(url));
  }
  assert.equal(publicApiUrl('http://127.0.0.1:8000/'), 'http://127.0.0.1:8000');
});

test('refuses an output folder containing files outside the publish allowlist', () => {
  const output = outputDirectory();
  writeFileSync(join(output, '.env'), 'private-placeholder');
  assert.throws(() => build({ output, apiUrl: '' }), /Unexpected file/);
});
