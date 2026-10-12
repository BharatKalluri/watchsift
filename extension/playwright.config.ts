import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/integration', workers: 1, timeout: 30000,
  use: { trace: 'retain-on-failure' },
});
