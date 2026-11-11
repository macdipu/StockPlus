import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

/** Best effort: delete the accounts the suite created (cascades to their sessions, lists and saved scans). */
export default function teardown() {
  try {
    execFileSync(
      "docker",
      ["compose", "exec", "-T", "db", "psql", "-U", "dse", "-d", "dse", "-c", "DELETE FROM users WHERE email LIKE 'e2e-%@example.test'"],
      { cwd: resolve(__dirname, "../.."), stdio: "ignore", timeout: 20_000 },
    );
  } catch {
    console.warn("e2e teardown: could not remove test accounts (docker unavailable); delete users like 'e2e-%@example.test'");
  }
}
