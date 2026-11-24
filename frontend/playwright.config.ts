import { defineConfig, devices } from '@playwright/test'

/**
 * E2E contra el entorno ya levantado (http://localhost:8080).
 * No arranca un servidor propio: en este proyecto todo entra por el gateway
 * de nginx, así que el test corre contra esa URL.
 *
 *   ./dev.sh up && podman exec sistema-contable-frontend pnpm test:e2e
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: 'list',

  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8080',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
