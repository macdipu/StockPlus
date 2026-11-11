import { expect, test } from "@playwright/test";
import { register, signOut, uniqueEmail } from "./helpers";

test.describe("Scanner tab", () => {
  test("runs the default preset and reports what it scanned", async ({ page }) => {
    await page.goto("/scanner");
    await expect(page.getByTestId("scan-meta")).toContainText(/\d+ of \d+ instruments/);
    await expect(page.getByRole("heading", { name: "Short-term long setup ≥ 5/6" })).toBeVisible();
  });

  test("lists every preset group and switches preset from the URL", async ({ page }) => {
    await page.goto("/scanner");
    for (const g of ["Trend", "Momentum", "Volatility", "Breakout", "Volume", "Candles", "Setup", "Fundamental"]) {
      await expect(page.getByText(g, { exact: true }).first()).toBeVisible();
    }
    await page.getByRole("link", { name: "RSI oversold" }).click();
    await expect(page).toHaveURL(/\/scanner\/rsi_oversold$/);
    await expect(page.getByRole("heading", { name: "RSI oversold" })).toBeVisible();
    await expect(page.getByRole("link", { name: "RSI oversold" })).toHaveAttribute("aria-current", "true");
  });

  test("pre-market presets now return results with the default filters", async ({ page }) => {
    await page.goto("/scanner/bullish_candles"); // legacy returned nothing for every pre-market preset
    await expect(page.getByTestId("scan-meta")).toContainText("last completed session");
  });

  test("the rule builder runs a custom scan", async ({ page }) => {
    await page.goto("/scanner");
    await page.getByLabel("Value").first().fill("0,100");
    await page.getByRole("button", { name: "Run custom scan" }).click();
    await expect(page.getByRole("heading", { name: "Custom scan", exact: true })).toBeVisible();
    await expect(page.getByTestId("scan-meta")).toContainText(/\d+ of \d+ instruments/);
    await expect(page.getByRole("link", { name: "RSI oversold" })).not.toHaveAttribute("aria-current", "true");
  });

  test("a rule that cannot work is explained before any request", async ({ page }) => {
    await page.goto("/scanner");
    await page.getByLabel("Value").first().fill("5"); // `between` needs two numbers
    await page.getByRole("button", { name: "Run custom scan" }).click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText(/two numbers/);
    await expect(page.getByRole("heading", { name: "Custom scan", exact: true })).toHaveCount(0);
  });

  test("rules can be added and removed", async ({ page }) => {
    await page.goto("/scanner");
    await page.getByRole("button", { name: "+ rule" }).click();
    await expect(page.getByRole("group", { name: "Rule 2" })).toBeVisible();
    await page.getByRole("button", { name: "Remove rule 2" }).click();
    await expect(page.getByRole("group", { name: "Rule 2" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Remove rule 1" })).toBeDisabled(); // always at least one
  });

  test("saved scans ask visitors to sign in", async ({ page }) => {
    await page.goto("/scanner");
    await expect(page.getByRole("region", { name: "Saved scans" }).getByRole("link", { name: "Sign in" })).toBeVisible();
  });

  test("a signed-in user can save, reload and delete a scan", async ({ page }) => {
    await register(page, uniqueEmail("scan"));
    await page.goto("/scanner");
    await page.getByLabel("Value").first().fill("20,60");
    await page.getByLabel("Name for this scan").fill("Mid RSI");
    await page.getByRole("button", { name: "Save current" }).click();
    const saved = page.getByRole("region", { name: "Saved scans" });
    await expect(saved.getByText("Mid RSI")).toBeVisible();

    await page.reload();
    await expect(saved.getByText("Mid RSI")).toBeVisible(); // persisted on the account

    await page.getByLabel("Value").first().fill("1,2");
    await saved.getByRole("button", { name: "Load" }).click();
    await expect(page.getByLabel("Value").first()).toHaveValue("20,60"); // the editor is restored from the definition
    await expect(page.getByRole("heading", { name: "Custom scan", exact: true })).toBeVisible();

    await saved.getByRole("button", { name: "Delete Mid RSI" }).click();
    await expect(saved.getByText("No saved scans yet.")).toBeVisible();
    await signOut(page);
  });
});
