/**
 * Playwright E2E Test Configuration
 * 
 * For the AI Portfolio Generative UI A2UI Dashboard
 * 
 * Run all tests: npx playwright test
 * Run with UI: npx playwright test --ui
 * Generate report: npx playwright show-report
 */

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
    testDir: './e2e',

    // Run tests in parallel
    fullyParallel: true,

    // Fail the build on CI if you accidentally left test.only in the source code
    forbidOnly: !!process.env.CI,

    // Retry on CI only
    retries: process.env.CI ? 2 : 0,

    // Opt out of parallel tests on CI
    workers: process.env.CI ? 1 : undefined,

    // Reporter to use
    reporter: [
        ['html', { open: 'never' }],
        ['list'],
    ],

    // Shared settings for all projects
    use: {
        // Base URL for tests
        baseURL: process.env.FRONTEND_URL || 'http://localhost:5173',

        // Collect trace when retrying the failed test
        trace: 'on-first-retry',

        // Take screenshot on failure
        screenshot: 'only-on-failure',

        // Record video on first retry
        video: 'on-first-retry',

        // Timeout for each action
        actionTimeout: 10000,

        // Navigation timeout
        navigationTimeout: 30000,
    },

    // Configure projects for major browsers
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },

        {
            name: 'firefox',
            use: { ...devices['Desktop Firefox'] },
        },

        {
            name: 'webkit',
            use: { ...devices['Desktop Safari'] },
        },

        // Test against mobile viewports
        {
            name: 'Mobile Chrome',
            use: { ...devices['Pixel 5'] },
        },

        {
            name: 'Mobile Safari',
            use: { ...devices['iPhone 12'] },
        },
    ],

    // Run local dev server before tests (optional)
    // Uncomment if you want Playwright to start the servers
    // webServer: [
    //   {
    //     command: 'npm run dev',
    //     url: 'http://localhost:5173',
    //     reuseExistingServer: !process.env.CI,
    //     timeout: 120 * 1000,
    //   },
    //   {
    //     command: 'cd backend && python -m uvicorn main:app --reload --port 8000',
    //     url: 'http://localhost:8000/health',
    //     reuseExistingServer: !process.env.CI,
    //     timeout: 120 * 1000,
    //   },
    // ],

    // Global timeout
    timeout: 60000,

    // Expect timeout
    expect: {
        timeout: 10000,
    },
});
