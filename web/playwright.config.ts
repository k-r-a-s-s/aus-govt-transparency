// Browser tests for the public site (SPEC ADR-W12, AC-B6, B9, B10). `npm test` builds the
// JS bundle, then tests/global-setup.ts builds the mini site from the committed fixture
// (tests/fixtures/web/mini.db) with the Python build and serves it with `python -m
// http.server` on a free 127.0.0.1 port. Tests read the URL from process.env.SITE_URL.
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: /.*\.spec\.ts$/,
  globalSetup: "./tests/global-setup.ts",
  fullyParallel: true,
  workers: 2,
  retries: 0,
  reporter: [["list"]],
  outputDir: "test-results",
  use: { ...devices["Desktop Chrome"], trace: "off" },
});
