import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const appDir = path.dirname(fileURLToPath(import.meta.url));
const frontendURL = "http://localhost:4321";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],
  outputDir: "test-results",
  use: {
    baseURL: frontendURL,
    browserName: "chromium",
    viewport: { width: 1440, height: 900 },
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: {
    command: "bun run dev:e2e",
    cwd: appDir,
    url: frontendURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
