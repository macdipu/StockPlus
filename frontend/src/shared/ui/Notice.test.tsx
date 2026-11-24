import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/shared/api";
import { ErrorNotice, Loading, SLOW_AFTER_MS } from "./Notice";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("Loading", () => {
  it("shows what is loading right away, with a spinner", () => {
    render(<Loading what="Loading GP" />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading GP…");
    expect(document.querySelector(".spinner")).not.toBeNull();
    expect(screen.queryByText(/taking longer than usual/)).toBeNull();
  });
  it("says it is slow after a while, and offers a retry when it can", async () => {
    const retry = vi.fn();
    render(<Loading onRetry={retry} />);
    act(() => void vi.advanceTimersByTime(SLOW_AFTER_MS + 1));
    expect(screen.getByText(/taking longer than usual/)).toBeInTheDocument();
    vi.useRealTimers();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledTimes(1);
  });
  it("says it is slow without a retry button when there is nothing to retry", () => {
    render(<Loading />);
    act(() => void vi.advanceTimersByTime(SLOW_AFTER_MS + 1));
    expect(screen.getByText(/taking longer than usual/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("ErrorNotice", () => {
  it("shows the reason and a retry button", async () => {
    vi.useRealTimers();
    const retry = vi.fn();
    render(<ErrorNotice error={new ApiError(404, "Not found", "No such share", null)} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("No such share");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalled();
  });
  it("says a connection failure is the connection's fault", () => {
    render(<ErrorNotice error={new ApiError(0, "Network error", "Could not reach the server. Check your connection.", null)} />);
    expect(screen.getByRole("alert")).toHaveTextContent("This is a connection problem");
    expect(screen.queryByRole("button")).toBeNull();
  });
});
