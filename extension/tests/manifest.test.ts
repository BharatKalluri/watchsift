import { readFile } from 'node:fs/promises';
import { expect, it } from 'vitest';

it('ships an MV3 manifest, narrow permissions, packaged scripts and correctly sized PNG icons', async () => {
  const manifest = JSON.parse(await readFile('dist/manifest.json', 'utf8'));
  expect(manifest.manifest_version).toBe(3);
  expect(manifest.permissions).toEqual(['storage']);
  expect(manifest.host_permissions).toHaveLength(1);
  expect(manifest.background).toEqual({ service_worker: 'worker.js', type: 'module' });
  expect(manifest.content_scripts[0].matches).toEqual(['https://www.netflix.com/*', 'https://netflix.com/*', 'https://www.primevideo.com/*', 'https://primevideo.com/*']);
  expect(manifest.content_scripts[0].run_at).toBe('document_idle');
  expect(manifest.content_security_policy.extension_pages).toContain("object-src 'none'");
  for (const file of ['worker.js', 'content.js', 'content.css', 'popup.html', 'privacy.html', 'ZOD-LICENSE.txt', 'p-limit-LICENSE.txt', 'yocto-queue-LICENSE.txt', 'lodash-es-LICENSE.txt', 'ky-LICENSE.txt', 'react-LICENSE.txt', 'react-dom-LICENSE.txt', 'scheduler-LICENSE.txt'])
    expect((await readFile(`dist/${file}`)).length).toBeGreaterThan(0);
  for (const [size, file] of Object.entries(manifest.icons)) {
    const png = await readFile(`dist/${file}`);
    expect(png.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a');
    expect([png.readUInt32BE(16), png.readUInt32BE(20)]).toEqual([Number(size), Number(size)]);
  }
});
