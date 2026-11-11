import { expect, type Page } from "@playwright/test";

export const PASSWORD = "correct horse battery staple";

/** Test accounts all use this domain so the global teardown can remove them. */
export const uniqueEmail = (label = "user") => `e2e-${label}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}@example.test`;

export async function register(page: Page, email = uniqueEmail()): Promise<string> {
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel(/^Password/).fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByTestId("user-menu")).toContainText(email);
  return email;
}

export async function signOut(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("banner").getByRole("link", { name: "Sign in" })).toBeVisible();
}

/** The synced instruments the suite relies on (the dev database has these after a few `/stocks/X` reads). */
export const SYNCED = ["GP", "BATBC", "SQURPHARMA"] as const;
