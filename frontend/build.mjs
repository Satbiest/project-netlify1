// Only the PUBLIC backend address is written to browser configuration.
// GEMINI_API_KEY must be configured on Render, never on Netlify.
import { copyFileSync, existsSync, mkdirSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
export const publicFiles = [
  'index.html', '_headers', 'static/css/app.css', 'static/js/app.js',
  'static/favicon.svg', 'data/demo.json', 'config.js',
];

export function publicApiUrl(value = '') {
  const input = value.trim();
  if (!input) return '';
  const url = new URL(input);
  const local = url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  if ((url.protocol !== 'https:' && !local) || url.username || url.password ||
      url.search || url.hash || url.pathname !== '/') {
    throw new Error('CVBOOST_API_URL must be the HTTPS backend origin, without /api, credentials, query, or fragment.');
  }
  return url.origin;
}

function filesUnder(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const child = join(directory, entry.name);
    return entry.isDirectory() ? filesUnder(child) : [child];
  });
}

export function build({ output = join(root, 'dist'), apiUrl = process.env.CVBOOST_API_URL || '' } = {}) {
  const address = publicApiUrl(apiUrl);
  output = resolve(output);
  // Fail if stale/unexpected files could be published. Do not delete user files.
  if (existsSync(output)) {
    for (const path of filesUnder(output)) {
      if (!publicFiles.includes(relative(output, path).replaceAll('\\', '/'))) {
        throw new Error('Unexpected file in publish directory; use an empty output folder.');
      }
    }
  }
  mkdirSync(output, { recursive: true });
  for (const name of publicFiles.filter(name => name !== 'config.js')) {
    const target = join(output, name);
    mkdirSync(dirname(target), { recursive: true });
    copyFileSync(join(root, 'public', name), target);
  }
  writeFileSync(join(output, 'config.js'), 'window.CVBOOST_CONFIG = ' +
    JSON.stringify({ staticMode: true, apiBaseUrl: address }) + ';\n');
  return { output, apiBaseUrl: address, files: [...publicFiles] };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = build();
  console.log(`Published ${result.files.length} public files to ${result.output}`);
  console.log(result.apiBaseUrl ? `Backend: ${result.apiBaseUrl}` :
    'Preview mode. Set CVBOOST_API_URL in Netlify, then rebuild to enable live analysis.');
}
