import { defineConfig, devices } from '@playwright/test'

const live = process.env.LIVE === '1'

export default defineConfig({
  testDir: './tests',
  timeout: 45_000,
  expect: { timeout: 10_000, toHaveScreenshot: { animations: 'disabled', maxDiffPixelRatio: 0.01 } },
  fullyParallel: true,
  workers: process.env.CI ? 2 : 4,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  snapshotPathTemplate: '{testDir}/__screenshots__/{projectName}/{testFilePath}/{arg}{ext}',
  use: {
    baseURL: live ? 'http://localhost:8001' : 'http://localhost:8000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    viewport: { width: 1280, height: 800 },
  },
  webServer: {
    command: 'node helpers/serve.mjs',
    url: `http://localhost:${live ? 8001 : 8000}/healthz`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: { PORT: live ? '8001' : '8000', LIVE: live ? '1' : '0' },
  },
  projects: [
    {
      name: 'chromium-ar',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 }, locale: 'ar-EG' },
      metadata: { lang: 'ar' },
      grepInvert: /@mobile|@demo/,
    },
    {
      name: 'chromium-en',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 }, locale: 'en-US' },
      metadata: { lang: 'en' },
      grepInvert: /@mobile|@demo|@live/,
    },
    {
      name: 'mobile-ar',
      use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 }, locale: 'ar-EG', hasTouch: true },
      metadata: { lang: 'ar' },
      grep: /@mobile/,
    },
    {
      name: 'demo',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 720 },
        video: { mode: 'on', size: { width: 1280, height: 720 } },
        launchOptions: { slowMo: 250 },
      },
      metadata: { lang: 'ar' },
      grep: /@demo/,
      timeout: 240_000,
    },
  ],
})
