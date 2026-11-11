import { defineConfig, devices } from "@playwright/test";

// The e2e suite runs against the REAL stack: start it first (`docker compose up -d` at the repo root, API on
// :8001) and make sure a few instruments are synced. Next itself is started here.
const API_ORIGIN = process.env.E2E_API_ORIGIN ?? "http://localhost:8001";
const PORT = Number(process.env.E2E_PORT ?? 3100);

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  globalTeardown: "./e2e/global-teardown.ts",
  reporter: [["list"]],
  use: { baseURL: `http://localhost:${PORT}`, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npm run build && npx next start --port ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 240_000,
    env: { API_ORIGIN },
  },
});
