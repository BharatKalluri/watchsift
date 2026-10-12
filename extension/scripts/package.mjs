import { readFile, mkdir, rm, rename } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';

const manifest = JSON.parse(await readFile('dist/manifest.json', 'utf8'));
if (manifest.host_permissions.some(host => {
  const url = new URL(host);
  return url.protocol !== 'https:' || ['localhost', '127.0.0.1'].includes(url.hostname);
})) {
  throw new Error('Build with the production HTTPS API before making a Web Store ZIP.');
}
await mkdir('artifacts', { recursive: true });
const pending = `../artifacts/.watchsift-${randomUUID()}.zip`;
try {
  execFileSync('zip', ['-r', pending, '.'], { cwd: 'dist', stdio: 'inherit' });
  await rename(`dist/${pending}`, `artifacts/watchsift-${manifest.version}.zip`);
} finally {
  await rm(`dist/${pending}`, { force: true });
}
