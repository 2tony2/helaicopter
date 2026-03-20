import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    ".venv/**",
    ".oats-worktrees/**",
    "next-env.d.ts",
    // Local generated output and vendored schema bundles are not app source.
    "dev/**",
    "public/database-schemas/**",
  ]),
  {
    files: ["src/views/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/app/*"],
              message: "Views compose screens but must not import route-layer files from src/app.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/features/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/app/*"],
              message: "Features must not depend on route-layer files from src/app.",
            },
            {
              group: ["@/views/*"],
              message: "Features must not depend on screen composition files from src/views.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/shared/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/app/*"],
              message: "Shared code must not depend on route-layer files from src/app.",
            },
            {
              group: ["@/views/*"],
              message: "Shared code must not depend on screen composition files from src/views.",
            },
            {
              group: ["@/features/*"],
              message: "Shared code must not depend on feature-layer files from src/features.",
            },
          ],
        },
      ],
    },
  },
]);

export default eslintConfig;
