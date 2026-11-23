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

  test("the chart's layers and style can be changed, and are remembered", async ({ page }) => {
    await page.goto(`/stock/${SYNCED[0]}`);
    const chart = () => page.getByTestId("price-chart").locator("canvas").first();
    await expect(chart()).toBeVisible();
    const layers = page.getByRole("group", { name: "Chart layers" });
    const layer = (name: string) => layers.getByRole("checkbox", { name });
    const plan = page.getByRole("complementary", { name: "Trade plan drawn on the chart" });
    await page.getByText(/^Layers/).click();
    await expect(layer("Support and resistance")).toBeChecked(); // default: candles plus the nearest levels
    await expect(layer("Trade plan")).not.toBeChecked();
    await expect(plan).toHaveCount(0);

    await layer("Trade plan").check(); // the trade plan is drawn on the chart and written beside it
    await expect(plan).toBeVisible();
    await layers.getByRole("button", { name: "Clean" }).click(); // candles and volume only
    await expect(plan).toHaveCount(0);
    await expect(page.getByText(/^Candles and volume only/)).toBeVisible();
    await page.getByText(/^Layers/).click();

    const styles = ["Hollow candles", "Bars", "HLC bars", "Line", "Line with markers", "Step line", "Area", "HLC area", "Baseline", "Columns", "High-low", "Heikin Ashi"];
    for (const style of styles) {
      await page.getByRole("button", { name: "Chart style" }).click();
      await page.getByRole("menuitemradio", { name: style, exact: true }).click();
      await expect(chart()).toBeVisible();
    }
    await page.getByRole("tab", { name: "5min" }).click(); // levels and styles apply to every timeframe
    await expect(chart()).toBeVisible();

    await page.reload(); // both choices are remembered in this browser
    await expect(page.getByText(/^Candles and volume only/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Chart style" })).toContainText("Heikin Ashi");
    await page.getByText(/^Layers/).click();
    await layers.getByRole("button", { name: "Everything" }).click();
    await expect(plan).toBeVisible();
  });

  test("indicators can be searched, added with settings, and removed", async ({ page }) => {
    await page.goto(`/stock/${SYNCED[0]}`);
    await expect(page.getByTestId("price-chart").locator("canvas").first()).toBeVisible();
    await page.getByRole("button", { name: /^Indicators/ }).click();
    const dialog = page.getByRole("dialog", { name: "Indicators" });
    await expect(dialog.getByRole("heading", { name: /Momentum/ })).toBeVisible(); // grouped when not searching
    await dialog.getByLabel("Search indicators").fill("relative strength");
    await dialog.locator('[data-indicator="rsi"]').click();
    await page.keyboard.press("Escape");
    const chip = page.locator('[data-indicator="rsi(14)"]');
    await expect(chip).toContainText("Relative Strength Index (14)");

    await page.getByRole("button", { name: "Settings for Relative Strength Index" }).click();
    await page.getByLabel("Relative Strength Index Length").fill("21");
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page.locator('[data-indicator="rsi(21)"]')).toBeVisible();
    await expect(page.locator('[data-indicator="rsi(14)"]')).toHaveCount(0);

    await page.getByRole("button", { name: "Remove Relative Strength Index" }).click();
    await expect(page.locator('[data-indicator="rsi(21)"]')).toHaveCount(0);
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
