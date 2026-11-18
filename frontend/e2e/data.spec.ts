import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test.describe("Data tab", () => {
  test("shows the fundamentals matrix and switches to TA values", async ({ page }) => {
    await page.goto("/find/table");
    const table = page.getByRole("region", { name: "Data" });
    await expect(table.getByRole("columnheader", { name: /P\/E/ })).toBeVisible();
    await expect(table.getByRole("row")).not.toHaveCount(1);
    await table.getByRole("button", { name: "TA values" }).click();
    await expect(table.getByRole("columnheader", { name: /RSI/ })).toBeVisible();
    await expect(table.getByRole("button", { name: "TA values" })).toHaveAttribute("aria-pressed", "true");
  });

  test("filters to a sector from the URL and can clear the filter", async ({ page }) => {
    await page.goto("/find/table?sector=Bank");
    await expect(page.getByText("Sector: Bank")).toBeVisible();
    await page.getByRole("link", { name: "Show all sectors" }).click();
    await expect(page.getByText("All sectors")).toBeVisible();
  });

  test("exports exactly what is on screen as CSV", async ({ page }) => {
    await page.goto("/find/table");
    await expect(page.getByRole("region", { name: "Data" }).getByRole("row")).not.toHaveCount(1);
    const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Export CSV" }).click()]);
    expect(download.suggestedFilename()).toBe("dse-data-matrix.csv");
    const csv = await readFile((await download.path()) ?? "", "utf8");
    const [header = "", ...lines] = csv.trim().split("\n");
    expect(header.split(",")).toEqual(expect.arrayContaining(["symbol", "pe", "pb"]));
    expect(lines.length).toBeGreaterThan(0);
  });

  test("a row opens the stock page", async ({ page }) => {
    await page.goto("/find/table");
    const link = page.getByRole("region", { name: "Data" }).getByRole("link").first();
    const symbol = (await link.textContent()) ?? "";
    await link.click();
    await expect(page).toHaveURL(new RegExp(`/stock/${symbol}`));
  });
});
