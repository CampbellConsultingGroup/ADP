// 935-pattern-registry: component tests for the Patterns screen. Mirrors agentic.test.tsx's
// vi.mock(hooks-module) convention; plain Testing Library queries only.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as patternsApi from "../api/patterns";
import type { PatternIssue } from "../api/patterns";
import * as auth from "../auth/AuthProvider";
import IssueList from "./IssueList";
import { detail, mutation, summary } from "./testFixtures";
import ImportPanel from "./ImportPanel";
import PatternsPage from "./PatternsPage";
import { canManagePatterns } from "./permissions";

vi.mock("../api/patterns", async (orig) => {
  const actual = await orig<typeof import("../api/patterns")>();
  return {
    ...actual,
    usePatterns: vi.fn(),
    usePatternFamily: vi.fn(),
    usePatternVersion: vi.fn(),
    usePatternYaml: vi.fn(),
    usePatternView: vi.fn(),
    useImportPattern: vi.fn(),
    useValidatePattern: vi.fn(),
    useRenderPattern: vi.fn(),
    useUpdateDraft: vi.fn(),
    useTransition: vi.fn(),
    useDeleteDraft: vi.fn(),
  };
});
vi.mock("../auth/AuthProvider", () => ({ useAuth: vi.fn() }));

const api = vi.mocked(patternsApi);
const useAuth = vi.mocked(auth.useAuth);

function asRole(role: string | null) {
  useAuth.mockReturnValue({ user: role ? { role } : null } as never);
}

beforeEach(() => {
  vi.clearAllMocks();
  asRole("enterprise_architect");
  api.usePatterns.mockReturnValue({ data: { items: [summary()], total: 1 }, isLoading: false } as never);
  api.useImportPattern.mockReturnValue(mutation());
  api.usePatternFamily.mockReturnValue({ data: undefined } as never);
  api.usePatternVersion.mockReturnValue({ data: detail(), isLoading: false, error: null } as never);
  api.usePatternYaml.mockReturnValue({ data: "pattern: x\n", isLoading: false } as never);
  api.useDeleteDraft.mockReturnValue(mutation());
  api.useTransition.mockReturnValue(mutation());
  api.useValidatePattern.mockReturnValue(mutation());
  api.useRenderPattern.mockReturnValue(mutation());
  api.useUpdateDraft.mockReturnValue(mutation());
});

describe("canManagePatterns", () => {
  it("allows only EA and Platform Admin, and a null user only when auth is disabled", () => {
    expect(canManagePatterns("enterprise_architect")).toBe(true);
    expect(canManagePatterns("platform_admin")).toBe(true);
    expect(canManagePatterns("solution_architect")).toBe(false);
    expect(canManagePatterns("reviewer")).toBe(false);
    expect(canManagePatterns(null, true)).toBe(false);
    expect(canManagePatterns(null, false)).toBe(true);
  });
});

describe("PatternsPage", () => {
  it("lists versions and passes filters to the query", async () => {
    render(<PatternsPage />);
    expect(screen.getByText("Domain Event Backbone")).toBeTruthy();
    await userEvent.selectOptions(screen.getByLabelText("Kind"), "anti-pattern");
    expect(api.usePatterns).toHaveBeenLastCalledWith({ kind: "anti-pattern" });
    await userEvent.selectOptions(screen.getByLabelText("Lifecycle"), "current");
    expect(api.usePatterns).toHaveBeenLastCalledWith({ kind: "anti-pattern", lifecycle: "current" });
  });

  it("hides Import for a reviewer", () => {
    asRole("reviewer");
    render(<PatternsPage />);
    expect(screen.queryByRole("button", { name: "Import pattern" })).toBeNull();
  });

  it("opens a version", async () => {
    render(<PatternsPage />);
    await userEvent.click(screen.getByRole("button", { name: "Domain Event Backbone" }));
    expect(api.usePatternVersion).toHaveBeenLastCalledWith("ea.integration.domain-event-backbone", "1.0.0");
    expect(screen.getByText("Context.")).toBeTruthy();
    await userEvent.click(screen.getByRole("tab", { name: "YAML" }));
    // An EA on a draft gets the editor, prefilled with the canonical YAML (US5).
    expect((screen.getByLabelText("Draft YAML") as HTMLTextAreaElement).value).toBe("pattern: x\n");
  });
});

describe("ImportPanel", () => {
  it("shows the issues of a rejected import", async () => {
    const issues: PatternIssue[] = [
      { path: "relationships[0].target", code: "V2.unknown_role", message: "role 'x' is not declared", severity: "error" },
    ];
    const mutateAsync = vi.fn().mockRejectedValue(new patternsApi.PatternIssuesError(422, issues, "Import rejected"));
    api.useImportPattern.mockReturnValue(mutation(mutateAsync));
    const onImported = vi.fn();
    render(<ImportPanel onImported={onImported} onCancel={() => {}} />);
    await userEvent.type(screen.getByLabelText("Pattern YAML"), "pattern: x");
    await userEvent.click(screen.getByRole("button", { name: "Import" }));
    const region = await screen.findByRole("region", { name: "Import rejected" });
    expect(within(region).getByText("V2.unknown_role")).toBeTruthy();
    expect(within(region).getByText("relationships[0].target")).toBeTruthy();
    expect(onImported).not.toHaveBeenCalled();
  });

  it("opens the created version", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ status: "created", version: summary(), issues: [] });
    api.useImportPattern.mockReturnValue(mutation(mutateAsync));
    const onImported = vi.fn();
    render(<ImportPanel initialYaml="pattern: x" onImported={onImported} onCancel={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Import" }));
    expect(mutateAsync).toHaveBeenCalledWith("pattern: x");
    expect(onImported).toHaveBeenCalledWith("ea.integration.domain-event-backbone", "1.0.0");
  });
});

describe("IssueList", () => {
  it("renders nothing for no issues and counts errors", () => {
    const { container } = render(<IssueList issues={[]} />);
    expect(container.textContent).toBe("");
    render(
      <IssueList
        title="Problems"
        issues={[
          { path: "", code: "I1.version_exists_use_update", message: "m", severity: "error" },
          { path: "motivation.principles[0]", code: "R1.unresolved_principle", message: "m", severity: "warning" },
        ]}
      />,
    );
    expect(screen.getByText(/Problems — 1 error, 1 other/)).toBeTruthy();
    expect(screen.getByText("(document)")).toBeTruthy();
  });
});
