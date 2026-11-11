import { expect, test } from "@playwright/test";
import { PASSWORD, register, signOut, uniqueEmail } from "./helpers";

test.describe("Accounts and watchlists", () => {
  test("a visitor has a local watchlist that survives a reload", async ({ page }) => {
    await page.goto("/stock/GP");
    const list = page.getByRole("region", { name: "Watchlist" });
    await expect(list.getByText(/Saved in this browser/)).toBeVisible();
    await list.getByRole("button", { name: "Remove ROBI" }).click();
    await expect(list.getByTestId("watch-ROBI")).toHaveCount(0);
    await page.reload();
    await expect(list.getByTestId("watch-GP")).toBeVisible();
    await expect(list.getByTestId("watch-ROBI")).toHaveCount(0); // the removal persisted in this browser
  });

  test("register → signed in → session survives a reload → sign out", async ({ page }) => {
    const email = await register(page);
    await page.goto("/market");
    await page.reload();
    await expect(page.getByTestId("user-menu")).toContainText(email); // restored from the refresh cookie
    await signOut(page);
    await page.reload();
    await expect(page.getByRole("banner").getByRole("link", { name: "Sign in" })).toBeVisible();
  });

  test("the refresh token is an HttpOnly cookie scoped to /auth, and never in storage", async ({ page, context }) => {
    await register(page);
    const cookie = (await context.cookies()).find((c) => c.name === "dse_refresh");
    expect(cookie).toBeDefined();
    expect(cookie?.httpOnly).toBe(true);
    expect(cookie?.sameSite).toBe("Lax");
    expect(cookie?.path).toBe("/api/v1/auth");
    const stored = await page.evaluate(() => JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }));
    expect(stored).not.toContain("access_token");
    expect(stored).not.toContain(cookie?.value ?? "§");
    expect(await page.evaluate(() => document.cookie)).not.toContain("dse_refresh");
  });

  test("a signed-in user's watchlist lives on the account, across a fresh browser session", async ({ page, browser }) => {
    const email = await register(page);
    await page.goto("/stock/ORIONINFU");
    const list = page.getByRole("region", { name: "Watchlist" });
    await list.getByRole("button", { name: /add ORIONINFU/ }).click();
    await expect(list.getByTestId("watch-ORIONINFU")).toBeVisible();
    await expect(list.getByText(/Saved to your account/)).toBeVisible();

    const other = await (await browser.newContext()).newPage(); // a different browser: only the account links them
    await other.goto("/login");
    await other.getByLabel("Email").fill(email);
    await other.getByLabel("Password").fill(PASSWORD);
    await other.getByRole("button", { name: "Sign in" }).click();
    await expect(other.getByTestId("user-menu")).toBeVisible();
    await other.goto("/market");
    await expect(other.getByRole("region", { name: "Watchlist" }).getByTestId("watch-ORIONINFU")).toBeVisible();
    await other.context().close();
  });

  test("a customised guest list is carried into the account at first sign-in", async ({ page }) => {
    await page.goto("/stock/GP");
    const list = page.getByRole("region", { name: "Watchlist" });
    await list.getByRole("button", { name: "Remove BRACBANK" }).click();
    await expect(list.getByTestId("watch-BRACBANK")).toHaveCount(0);
    await register(page);
    await page.goto("/market");
    const mine = page.getByRole("region", { name: "Watchlist" });
    await expect(mine.getByText(/Saved to your account/)).toBeVisible();
    await expect(mine.getByTestId("watch-GP")).toBeVisible();
    await expect(mine.getByTestId("watch-BRACBANK")).toHaveCount(0); // the customisation came along
  });

  test("wrong password and duplicate registration are explained", async ({ page }) => {
    const email = await register(page);
    await signOut(page);
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("not the password at all");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText("Invalid email or password");

    await page.goto("/register");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel(/^Password/).fill(PASSWORD);
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText(/already exists/);
  });

  test("a weak password is refused", async ({ page }) => {
    await page.goto("/register");
    await page.getByLabel("Email").fill(uniqueEmail("weak"));
    await page.getByLabel(/^Password/).fill("short");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByTestId("user-menu")).toHaveCount(0);
  });

  test("sign-in redirects only to same-site paths", async ({ page }) => {
    const email = await register(page);
    await signOut(page);
    await page.goto("/login?next=//evil.example/steal");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByTestId("user-menu")).toBeVisible();
    expect(new URL(page.url()).origin).toBe(new URL(page.url()).origin);
    expect(page.url()).not.toContain("evil.example");
  });
});
