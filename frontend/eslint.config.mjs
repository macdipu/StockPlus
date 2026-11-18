import { defineConfig, globalIgnores } from "eslint/config";
import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

/**
 * Architecture rules (ARCHITECTURE.md §4, rule 6), enforced by lint:
 *   - app/ is routing only and may import a feature ONLY through its public index;
 *   - a feature never imports another feature's internals (only its public index) and never imports app/;
 *   - shared/ never imports features or app/.
 */
const FEATURES = ["auth", "live", "watchlist", "stock", "market", "scanner", "data", "tools", "company", "picks"];

const restrict = (patterns) => ({
  "no-restricted-imports": ["error", { patterns }],
});

const deepFeature = (name, message) => ({ group: [`@/features/${name}/*`], message });

export default defineConfig([
  ...coreWebVitals,
  ...typescript,
  globalIgnores([".next/**", "node_modules/**", "next-env.d.ts", "playwright-report/**", "test-results/**"]),
  {
    rules: {
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      "@typescript-eslint/consistent-type-imports": ["error", { prefer: "type-imports" }],
      eqeqeq: ["error", "always", { null: "ignore" }],
    },
  },
  {
    files: ["src/app/**/*.{ts,tsx}"],
    rules: restrict([
      { group: ["@/features/*/*"], message: "app/ may import a feature only through its public index." },
    ]),
  },
  {
    files: ["src/shared/**/*.{ts,tsx}"],
    rules: restrict([
      { group: ["@/features/*", "@/app/*"], message: "shared/ must not depend on features or app/." },
    ]),
  },
  ...FEATURES.map((feature) => ({
    files: [`src/features/${feature}/**/*.{ts,tsx}`],
    rules: restrict([
      { group: ["@/app/*"], message: "features must not import app/." },
      ...FEATURES.filter((other) => other !== feature).map((other) =>
        deepFeature(other, `Import "@/features/${other}" (its public index), not its internals.`),
      ),
    ]),
  })),
]);
