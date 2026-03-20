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
              group: [
                "@/app/*",
                "@/app/**",
                "../app/**",
                "../../app/**",
                "../../../app/**",
                "../../../../app/**",
              ],
              message: "Views compose screens but must not import route-layer files from src/app.",
            },
            {
              group: ["@/components/*", "@/components/**", "@/hooks/*", "@/hooks/**"],
              message:
                "Views should import from src/features/* or src/shared/* layer paths, not temporary compatibility shims.",
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
              group: [
                "@/app/*",
                "@/app/**",
                "../app/**",
                "../../app/**",
                "../../../app/**",
                "../../../../app/**",
              ],
              message: "Features must not depend on route-layer files from src/app.",
            },
            {
              group: [
                "@/views/*",
                "@/views/**",
                "../views/**",
                "../../views/**",
                "../../../views/**",
                "../../../../views/**",
              ],
              message: "Features must not depend on screen composition files from src/views.",
            },
            {
              group: ["@/components/*", "@/components/**", "@/hooks/*", "@/hooks/**"],
              message:
                "Features should import from src/features/* or src/shared/* layer paths, not temporary compatibility shims.",
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
              group: [
                "@/app/*",
                "@/app/**",
                "../app/**",
                "../../app/**",
                "../../../app/**",
                "../../../../app/**",
              ],
              message: "Shared code must not depend on route-layer files from src/app.",
            },
            {
              group: [
                "@/views/*",
                "@/views/**",
                "../views/**",
                "../../views/**",
                "../../../views/**",
                "../../../../views/**",
              ],
              message: "Shared code must not depend on screen composition files from src/views.",
            },
            {
              group: [
                "@/features/*",
                "@/features/**",
                "../features/**",
                "../../features/**",
                "../../../features/**",
                "../../../../features/**",
              ],
              message: "Shared code must not depend on feature-layer files from src/features.",
            },
            {
              group: ["@/components/*", "@/components/**", "@/hooks/*", "@/hooks/**"],
              message:
                "Shared code should import from src/shared/* layer paths, not temporary compatibility shims.",
            },
          ],
        },
      ],
    },
  },
]);

export default eslintConfig;
