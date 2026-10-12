import { build } from 'vite';
import tailwindcss from '@tailwindcss/vite';
import { mkdir, writeFile, copyFile, readFile } from 'node:fs/promises';

const url = new URL(process.env.WATCHSIFT_API_URL || 'http://127.0.0.1:8000');
const local = ['127.0.0.1', 'localhost'].includes(url.hostname);
if (!['http:', 'https:'].includes(url.protocol) || (!local && url.protocol !== 'https:')) throw new Error('Production API requires HTTPS');
if (url.pathname !== '/' || url.search || url.hash || url.username || url.password) {
  throw new Error('API URL must be an origin without credentials');
}
const apiOrigin = url.origin;
await build({
  configFile: false, publicDir: false,
  plugins: [tailwindcss()],
  define: { __API_ORIGIN__: JSON.stringify(apiOrigin) },
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: { popup: 'popup.html', worker: 'src/background/index.ts' },
      output: { entryFileNames: '[name].js', chunkFileNames: 'assets/[name]-[hash].js' },
    },
  },
});
await build({
  configFile: false, publicDir: false,
  build: {
    outDir: 'dist', emptyOutDir: false,
    lib: { entry: 'src/content/index.ts', name: 'WatchSift', formats: ['iife'], fileName: () => 'content.js' },
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
});
await copyFile('src/content/content.css', 'dist/content.css');
await copyFile('public/privacy.html', 'dist/privacy.html');
await copyFile('node_modules/zod/LICENSE', 'dist/ZOD-LICENSE.txt');
for (const [dependency, license] of [['p-limit', 'license'], ['yocto-queue', 'license'], ['lodash-es', 'LICENSE'], ['ky', 'license'], ['react', 'LICENSE'], ['react-dom', 'LICENSE'], ['scheduler', 'LICENSE']]) {
  await copyFile(`node_modules/${dependency}/${license}`, `dist/${dependency}-LICENSE.txt`);
}
await mkdir('dist/icons', { recursive: true });
for (const size of [16, 32, 48, 128]) await copyFile(`public/icons/${size}.png`, `dist/icons/${size}.png`);
const manifest = JSON.parse(await readFile('manifest.json', 'utf8'));
manifest.host_permissions = [`${apiOrigin}/*`];
manifest.content_security_policy.extension_pages =
  `script-src 'self'; object-src 'none'; connect-src ${apiOrigin}`;
await writeFile('dist/manifest.json', JSON.stringify(manifest, null, 2));
