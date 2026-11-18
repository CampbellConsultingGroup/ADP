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
      // Generated from generated/openapi.json by `npm run gen:api`.
      "src/api/generated/**",
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
      // ADP-blp.46: a button styled by hand drifts from the others (six blues, five sizes).
      // Use <Button> or the ui-btn / ui-btn-link classes; a `style` beside a className is fine.
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "JSXOpeningElement[name.name='button']:has(JSXAttribute[name.name='style']):not(:has(JSXAttribute[name.name='className']))",
          message: "Give the button a ui-btn class (or use <Button>) instead of styling it by hand.",
        },
      ],
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
  {
    // ADP-blp.46 baseline: files that still style buttons by hand (147 buttons when the rule was
    // added). Convert a file and delete it from this list; do not add to it.
    files: [
      "src/agent-review/AgentReviewButton.tsx",
      "src/agent-review/SuggestionCard.tsx",
      "src/agentic/AgentDetail.tsx",
      "src/agentic/AgentsPage.tsx",
      "src/agentic/AutomatedBy.tsx",
      "src/agentic/SolutionAgentsPanel.tsx",
      "src/business/BusinessContextPanel.tsx",
      "src/business/BusinessPage.tsx",
      "src/business/CapabilityForm.tsx",
      "src/business/CapabilityNode.tsx",
      "src/business/CapabilityOrgPanel.tsx",
      "src/business/CapabilityTree.tsx",
      "src/business/DomainDetail.tsx",
      "src/business/DomainList.tsx",
      "src/business/GeographyTree.tsx",
      "src/business/OrgFindings.tsx",
      "src/business/OrgUnitFootprint.tsx",
      "src/business/OrgUnitTree.tsx",
      "src/business/OrganizationTab.tsx",
      "src/business/RegionalAssessmentEditor.tsx",
      "src/business/RegionalHeatMap.tsx",
      "src/business/StageCapsEditor.tsx",
      "src/business/UnmatchedList.tsx",
      "src/business/ValueStreamDetail.tsx",
      "src/business/ValueStreamForm.tsx",
      "src/business/ValueStreamList.tsx",
      "src/business/ValueStreamStageEditor.tsx",
      "src/chat/ChatButton.tsx",
      "src/chat/ChatPanel.tsx",
      "src/compliance/ControlMappingsEditor.tsx",
      "src/compliance/ControlTree.tsx",
      "src/compliance/FrameworkDetail.tsx",
      "src/compliance/FrameworkForm.tsx",
      "src/governance/ArchitectureHealthTab.tsx",
      "src/inspection/InspectionPanel.tsx",
      "src/inspection/TechnologyEditor.tsx",
      "src/intake/IntakeTextForm.tsx",
      "src/intake/LLMSettings.tsx",
      "src/links/LinkEditor.tsx",
      "src/links/NavLinkButton.tsx",
      "src/patterns/AdoptionsList.tsx",
      "src/patterns/PatternsPage.tsx",
      "src/portfolio/PortfolioPage.tsx",
      "src/recommend/AcceptDialog.tsx",
      "src/recommend/OptionCard.tsx",
      "src/recommend/ReasoningPanel.tsx",
      "src/recommend/RejectDialog.tsx",
      "src/recommend/RequirementSelector.tsx",
      "src/strategy/EditFrame.tsx",
      "src/strategy/InitiativeControlMappingEditor.tsx",
      "src/strategy/ObjectiveControlLinkEditor.tsx",
      "src/strategy/ObjectiveDependencyPanel.tsx",
      "src/strategy/ObjectiveDetail.tsx",
      "src/strategy/ObjectiveList.tsx",
      "src/ui/ErrorBoundary.tsx",
    ],
    rules: { "no-restricted-syntax": "off" },
  },
);
