import { expect, test } from "@playwright/test";
import { SYNCED } from "./helpers";

test.describe("Stock tab", () => {
  test("shows price, signal, chart and the analysis cards for a symbol", async ({ page }) => {
    await page.goto(`/stock/${SYNCED[0]}`);
    await expect(page.getByTestId("stock-symbol")).toHaveText(SYNCED[0]);
    await expect(page.getByTestId("ltp")).not.toHaveText("–");
    await expect(page.getByTestId("ltp")).toHaveText(/^[\d,]+\.\d{2}$/);
    await expect(page.getByTestId("signal")).toHaveText(/^(STRONG BUY|BUY|HOLD|SELL|STRONG SELL|AVOID)$/);
    await expect(page.getByTestId("price-chart").locator("canvas").first()).toBeVisible();
    for (const title of ["Trade plan", "Setup checklist", "Support / resistance", "Trend", "Indicators", "Fair value", "Fundamentals", "Announcements"]) {
      await expect(page.getByRole("heading", { name: title, level: 3 })).toBeVisible();
    }
    await expect(page.getByRole("heading", { name: "Volume-price analysis (daily)" })).toBeVisible();
    await expect(page).toHaveTitle(new RegExp(`${SYNCED[0]}`));
  });

  test("the live stream connects through the proxy and the market strip appears", async ({ page }) => {
    await page.goto(`/stock/${SYNCED[0]}`);
    await expect(page.getByTestId("feed-status")).toContainText("LIVE", { timeout: 20_000 });
    await expect(page.getByTestId("session")).toContainText(/Market (open|closed)/);
  });

  test("searching for another symbol navigates to it", async ({ page }) => {
    await page.goto(`/stock/${SYNCED[0]}`);
    await page.getByLabel("Trading code").fill(SYNCED[1].toLowerCase());
    await page.getByRole("button", { name: "Analyze" }).click();
    await expect(page).toHaveURL(new RegExp(`/stock/${SYNCED[1]}$`));
    await expect(page.getByTestId("stock-symbol")).toHaveText(SYNCED[1]);
  });

  test("an unknown trading code is reported clearly, not as a blank page", async ({ page }) => {
    await page.goto("/stock/NOTADSECODE");
    await expect(page.getByRole("main").getByRole("alert")).toContainText(/not a DSE trading code/i);
  });

  test("a malformed symbol is a 404 page", async ({ page }) => {
    const res = await page.goto("/stock/bad%20symbol!!");
    expect(res?.status()).toBe(404);
  });

  test("the sidebar offers the symbol on screen for the watchlist", async ({ page }) => {
    await page.goto("/stock/ORIONINFU");
    await expect(page.getByRole("button", { name: /add ORIONINFU/ })).toBeVisible();
  });
});
