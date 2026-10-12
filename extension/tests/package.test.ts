import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { expect, it } from 'vitest';

it('packages HTTPS builds without a confirmation flag and replaces ZIPs without stale files', async () => {
  const folder = await mkdtemp(join(tmpdir(), 'watchsift-package-test-'));
  const script = resolve('scripts/package.mjs');
  const manifest = { version: '0.1.0', host_permissions: ['https://api.example.invalid/*'] };
  try {
    await mkdir(join(folder, 'dist'));
    await writeFile(join(folder, 'dist/manifest.json'), JSON.stringify(manifest));
    await writeFile(join(folder, 'dist/old.js'), 'synthetic old file');
    const options = { cwd: folder };
    execFileSync(process.execPath, [script], options);
    await rm(join(folder, 'dist/old.js'));
    await writeFile(join(folder, 'dist/new.js'), 'synthetic new file');
    execFileSync(process.execPath, [script], options);
    const archive = join(folder, 'artifacts/watchsift-0.1.0.zip');
    const names = execFileSync('unzip', ['-Z1', archive], { encoding: 'utf8' });
    expect(names).toContain('new.js');
    expect(names).not.toContain('old.js');
    expect((await readFile(archive)).length).toBeGreaterThan(0);
    await writeFile(join(folder, 'dist/manifest.json'), JSON.stringify({ ...manifest, host_permissions: ['http://127.0.0.1:8000/*'] }));
    const local = spawnSync(process.execPath, [script], { ...options, encoding: 'utf8' });
    expect(local.status).toBe(1);
    expect(local.stderr).toContain('production HTTPS API');
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});
