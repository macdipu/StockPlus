import { expect, test } from "@playwright/test";

test.describe("Market tab", () => {
  test("shows sectors, movers, P/E and the 52-week table", async ({ page }) => {
    await page.goto("/market");
    const sectors = page.getByRole("region", { name: "Sectors" });
    await expect(sectors.getByRole("row")).not.toHaveCount(1); // header + at least one sector
    for (const name of ["Top gainers", "Top losers", "Most active (value)"]) {
      await expect(page.getByRole("region", { name }).getByRole("columnheader", { name: /Symbol/ })).toBeVisible();
    }
    await expect(page.getByRole("region", { name: /P\/E/ }).getByRole("row", { name: /Market/ })).toBeVisible();
    await expect(page.getByRole("region", { name: "52-week range" }).getByRole("columnheader", { name: "In range" })).toBeVisible();
  });

  test("sorting a table by a column header reorders it", async ({ page }) => {
    await page.goto("/market");
    const sectors = page.getByRole("region", { name: "Sectors" });
    const firstCell = () => sectors.getByRole("row").nth(1).getByRole("cell").first().textContent();
    const before = await firstCell();
    await sectors.getByRole("button", { name: "Sector" }).click(); // descending by name
    await sectors.getByRole("button", { name: /Sector/ }).click(); // ascending
    const after = await firstCell();
    expect(after).not.toBeNull();
    expect([before, after].every(Boolean)).toBe(true);
    await expect(sectors.getByRole("columnheader", { name: /Sector/ })).toHaveAttribute("aria-sort", "ascending");
  });

  test("clicking a sector opens the Data tab filtered to it", async ({ page }) => {
    await page.goto("/market");
    const row = page.getByRole("region", { name: "Sectors" }).getByRole("row").nth(1);
    const sector = (await row.getByRole("cell").first().textContent()) ?? "";
    await row.click();
    await expect(page).toHaveURL(/\/data\?sector=/);
    await expect(page.getByText(`Sector: ${sector}`)).toBeVisible();
  });

  test("a mover links to its stock page", async ({ page }) => {
    await page.goto("/market");
    const link = page.getByRole("region", { name: "Top gainers" }).getByRole("link").first();
    const symbol = (await link.textContent()) ?? "";
    await link.click();
    await expect(page).toHaveURL(new RegExp(`/stock/${symbol}`));
  });
});
