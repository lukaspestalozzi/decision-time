import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  workers: 1,
  use: {
    baseURL: 'http://localhost:9009',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
  webServer: [
    {
      command: 'cd ../backend && DATA_DIR=./data-e2e uv run uvicorn app.main:app --port 9010',
      port: 9010,
      reuseExistingServer: false,
    },
    {
      command: 'cd ../frontend && npx ng serve --proxy-config proxy.e2e.json --port 9009',
      port: 9009,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
