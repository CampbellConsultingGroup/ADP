// ESLint flat config (ADP-blp.32). The repo had `eslint` and a `lint` script but no config and
// no plugins, so linting never ran -- including the react-hooks rules that several
// `eslint-disable` comments in the source refer to.
import js from "@eslint/js";
import globals from "globals";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "dist/**",
      "coverage/**",
      "node_modules/**",
      "playwright-report/**",
      "test-results/**",
      // Vendored from the Canvas diagram-core library; linted in its own repo.
      "src/diagrams/core/**",
      "src/diagrams/editor/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: { "react-hooks": reactHooks, "jsx-a11y": jsxA11y },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      ...jsxA11y.flatConfigs.recommended.rules,
      // A label counts when it wraps its control or points at it with htmlFor.
      "jsx-a11y/label-has-associated-control": ["error", { assert: "either", depth: 3 }],
      // Focus is only moved into a form or dialog the user has just opened.
      "jsx-a11y/no-autofocus": "off",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" },
      ],
    },
  },
  {
    // Playwright fixtures are destructured from an object, and `({}, testInfo)` is its own idiom.
    files: ["tests/e2e/**", "e2e/**", "**/*.spec.ts"],
    rules: { "no-empty-pattern": "off" },
  },
  {
    // Tests build fixtures and mocks loosely on purpose.
    files: ["**/*.test.{ts,tsx}", "tests/**", "e2e/**"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
    },
  },
);
