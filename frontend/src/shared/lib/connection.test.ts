import { afterEach, describe, expect, it, vi } from "vitest";
import { connection } from "./connection";

afterEach(() => connection.markOnline());

describe("connection", () => {
  it("starts online, flips on a failure and back on any answer", () => {
    expect(connection.get()).toBe(false);
    connection.markOffline();
    expect(connection.get()).toBe(true);
    connection.markOnline();
    expect(connection.get()).toBe(false);
  });
  it("tells subscribers only when the state really changes", () => {
    const fn = vi.fn();
    const off = connection.subscribe(fn);
    connection.markOffline();
    connection.markOffline();
    connection.markOnline();
    off();
    connection.markOffline();
    expect(fn).toHaveBeenCalledTimes(2);
  });
});
