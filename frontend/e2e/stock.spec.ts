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
    await expect(page.getByRole("heading", { name: "Trade plan", level: 3 })).toBeVisible();
    await page.getByRole("tab", { name: "Technicals" }).click();
    for (const title of ["Setup checklist", "Support / resistance", "Trend", "Indicators"]) {
      await expect(page.getByRole("heading", { name: title, level: 3 })).toBeVisible();
    }
    await expect(page.getByRole("heading", { name: "Volume-price analysis (daily)" })).toBeVisible();
    await page.getByRole("tab", { name: "Company" }).click();
    for (const title of ["Fair value", "Fundamentals", "Financial health", "Company profile"]) {
      await expect(page.getByRole("heading", { name: title, level: 3 })).toBeVisible();
    }
    await expect(page).toHaveTitle(new RegExp(`${SYNCED[0]}`));
  });

  test("the Overview, Technicals and Company tabs switch views and are linkable by URL hash", async ({ page }) => {
    await page.goto(`/stock/${SYNCED[0]}`);
    const overview = page.getByRole("tab", { name: "Overview" });
    await expect(overview).toHaveAttribute("aria-selected", "true");
    await page.getByRole("tab", { name: "Company" }).click();
    await expect(page).toHaveURL(/#company$/);
    await expect(page.getByRole("heading", { name: "Trade plan", level: 3 })).toHaveCount(0);
    await page.getByRole("tab", { name: "Company" }).press("ArrowLeft");
    await expect(page.getByRole("tab", { name: "Technicals" })).toHaveAttribute("aria-selected", "true");
    await page.goto(`/stock/${SYNCED[0]}#technicals`);
    await expect(page.getByRole("tab", { name: "Technicals" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { name: "Setup checklist", level: 3 })).toBeVisible();
  });

  test("the chart's Analysis level and style can be changed, and are remembered", async ({ page }) => {
    await page.goto(`/stock/${SYNCED[0]}`);
    const chart = () => page.getByTestId("price-chart").locator("canvas").first();
    await expect(chart()).toBeVisible();
    const level = (name: string) => page.getByRole("group", { name: "Analysis on the chart" }).getByRole("button", { name });
    const plan = page.getByRole("complementary", { name: "Trade plan drawn on the chart" });
    await expect(level("Basic")).toHaveAttribute("aria-pressed", "true"); // default
    await expect(plan).toHaveCount(0);
    await expect(page.getByRole("tab", { name: "Advanced" })).toHaveCount(0); // one control, not two

    await level("Full").click(); // the trade plan is drawn on the chart and written beside it
    await expect(plan).toBeVisible();
    await level("Off").click(); // clean chart: no plan text, prices and volume only
    await expect(plan).toHaveCount(0);
    await expect(page.getByText("Prices and volume only.")).toBeVisible();

    for (const style of ["Hollow candles", "Bars (OHLC)", "Line (close)", "Area (close)", "Heikin Ashi (smoothed)"]) {
      await page.getByLabel("Chart style").selectOption({ label: style });
      await expect(chart()).toBeVisible();
    }
    await page.getByRole("tab", { name: "5min" }).click(); // levels and styles apply to every timeframe
    await expect(chart()).toBeVisible();

    await page.reload(); // both choices are remembered in this browser
    await expect(level("Off")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByLabel("Chart style")).toHaveValue("heikin");
    await level("Full").click();
    await expect(plan).toBeVisible();
  });

  test("/stock without a symbol offers search, suggestions and recently viewed stocks", async ({ page }) => {
    await page.goto(`/stock/${SYNCED[0]}`);
    await expect(page.getByTestId("stock-symbol")).toHaveText(SYNCED[0]);
    await page.goto("/stock");
    await expect(page.getByRole("heading", { name: "Recently viewed", level: 3 })).toBeVisible();
    await expect(page.getByRole("region", { name: "Recently viewed" }).getByRole("link", { name: new RegExp(SYNCED[0]) })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Most active today", level: 3 })).toBeVisible();
    await page.getByLabel("Trading code or sector").fill(SYNCED[1].slice(0, 2));
    await expect(page.getByRole("list", { name: "Matching symbols" }).getByRole("link").first()).toBeVisible();
    await page.getByLabel("Trading code or sector").fill(SYNCED[1]);
    await page.getByRole("button", { name: "Open" }).click();
    await expect(page).toHaveURL(new RegExp(`/stock/${SYNCED[1]}$`));
  });

  test("the live stream connects through the proxy and the market strip appears", async ({ page }) => {
    await page.goto(`/stock/${SYNCED[0]}`);
    await expect(page.getByTestId("feed-status")).toContainText("Live", { timeout: 20_000 });
    await expect(page.getByTestId("session")).toContainText(/Market (open|closed)/);
  });

  test("the Stock tab always opens the search page, and a share is reachable from it", async ({ page }) => {
    await page.goto(`/stock/${SYNCED[0]}`);
    await expect(page.getByRole("search")).toHaveCount(0); // no second search box in the header
    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Stock" }).click();
    await expect(page).toHaveURL(/\/stock$/);
    await page.getByLabel("Trading code or sector").fill(SYNCED[1].toLowerCase());
    await page.getByRole("button", { name: "Open" }).click();
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
