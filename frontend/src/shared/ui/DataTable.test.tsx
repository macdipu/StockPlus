import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DataTable, type Column } from "./DataTable";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

interface R {
  symbol: string;
  ltp: number | null;
}
const rows: R[] = [
  { symbol: "BBB", ltp: 20 },
  { symbol: "AAA", ltp: null },
  { symbol: "CCC", ltp: 5 },
];
const columns: Column<R>[] = [
  { key: "symbol", label: "Symbol" },
  { key: "ltp", label: "LTP", align: "right" },
];
const order = () => screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0]?.textContent);

describe("DataTable", () => {
  it("renders rows in the given order until a sort is chosen", () => {
    render(<DataTable rows={rows} columns={columns} rowKey={(r) => r.symbol} caption="t" />);
    expect(order()).toEqual(["BBB", "AAA", "CCC"]);
  });

  it("sorts on header click, toggles direction, keeps missing values last and exposes aria-sort", async () => {
    render(<DataTable rows={rows} columns={columns} rowKey={(r) => r.symbol} caption="t" />);
    await userEvent.click(screen.getByRole("button", { name: "LTP" }));
    expect(order()).toEqual(["BBB", "CCC", "AAA"]); // descending first, null last
    expect(screen.getByRole("columnheader", { name: /LTP/ })).toHaveAttribute("aria-sort", "descending");
    await userEvent.click(screen.getByRole("button", { name: /LTP/ }));
    expect(order()).toEqual(["CCC", "BBB", "AAA"]);
    expect(screen.getByRole("columnheader", { name: /LTP/ })).toHaveAttribute("aria-sort", "ascending");
  });

  it("honours a default sort", () => {
    render(<DataTable rows={rows} columns={columns} rowKey={(r) => r.symbol} caption="t" defaultSort={{ key: "symbol", desc: false }} />);
    expect(order()).toEqual(["AAA", "BBB", "CCC"]);
  });

  it("navigates on click and on Enter, only when rows have an href", async () => {
    push.mockClear();
    const { rerender } = render(<DataTable rows={rows} columns={columns} rowKey={(r) => r.symbol} caption="t" rowHref={(r) => `/stock/${r.symbol}`} />);
    const first = screen.getAllByRole("row")[1]!;
    await userEvent.click(first);
    expect(push).toHaveBeenCalledWith("/stock/BBB");
    first.focus();
    await userEvent.keyboard("{Enter}");
    expect(push).toHaveBeenCalledTimes(2);
    rerender(<DataTable rows={rows} columns={columns} rowKey={(r) => r.symbol} caption="t" />);
    await userEvent.click(screen.getAllByRole("row")[1]!);
    expect(push).toHaveBeenCalledTimes(2);
  });

  it("shows an empty message and a caption for screen readers", () => {
    render(<DataTable rows={[]} columns={columns} rowKey={(r: R) => r.symbol} caption="Results" empty="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Results")).toHaveClass("sr-only");
  });
});
