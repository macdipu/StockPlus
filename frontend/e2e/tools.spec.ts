import { expect, test } from "@playwright/test";
import { SYNCED } from "./helpers";

test.describe("Tools tab", () => {
  test("return calculator computes a result and shows its assumptions", async ({ page }) => {
    await page.goto("/tools");
    const card = page.getByRole("region", { name: "Return calculator" });
    await card.getByLabel("Symbol").fill(SYNCED[0]);
    await card.getByRole("button", { name: "Calculate" }).click();
    const result = page.getByTestId("return-result");
    await expect(result).toContainText("Bought");
    await expect(result).toContainText(/Return/);
    await expect(result).toContainText("dividends not included");
  });

  test("return calculator explains an impossible range", async ({ page }) => {
    await page.goto("/tools");
    const card = page.getByRole("region", { name: "Return calculator" });
    await card.getByLabel("Symbol").fill(SYNCED[0]);
    await card.getByLabel("Buy date").fill("2099-01-01");
    await card.getByRole("button", { name: "Calculate" }).click();
    await expect(card.getByRole("alert")).toContainText(/No bars between/);
  });

  test("correlation heatmap has one cell per pair", async ({ page }) => {
    await page.goto("/tools");
    const card = page.getByRole("region", { name: "Correlation of daily returns" });
    await card.getByLabel("Symbols (comma separated)").fill(SYNCED.join(","));
    await card.getByRole("button", { name: "Compute" }).click();
    const heat = page.getByTestId("heatmap");
    await expect(heat.getByRole("cell")).toHaveCount(SYNCED.length * SYNCED.length);
    await expect(heat.getByRole("columnheader")).toHaveCount(SYNCED.length);
    await expect(heat.getByRole("cell").first()).toHaveText("1.00"); // a series correlates perfectly with itself
  });

  test("correlation needs two symbols", async ({ page }) => {
    await page.goto("/tools");
    const card = page.getByRole("region", { name: "Correlation of daily returns" });
    await card.getByLabel("Symbols (comma separated)").fill(SYNCED[0]);
    await card.getByRole("button", { name: "Compute" }).click();
    await expect(card.getByRole("alert")).toContainText(/at least two/);
  });

  test("the CSV link serves a real CSV for the symbol", async ({ page, request }) => {
    await page.goto("/tools");
    const card = page.getByRole("region", { name: "Data download" });
    await card.getByLabel("Symbol to download").fill(SYNCED[1]);
    const href = await card.getByTestId("csv-link").getAttribute("href");
    expect(href).toBe(`/api/v1/data/${SYNCED[1]}.csv`);
    const res = await request.get(href ?? "");
    expect(res.status()).toBe(200);
    expect(res.headers()["content-type"]).toContain("text/csv");
    expect((await res.text()).startsWith("date,open,high,low,close,volume,trades")).toBe(true);
  });
});
