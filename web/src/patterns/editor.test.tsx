// 935-pattern-registry US5: draft YAML editing, "New version" and delete.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as patternsApi from "../api/patterns";
import * as auth from "../auth/AuthProvider";
import PatternVersion, { bumpMinor } from "./PatternVersion";
import YamlEditor from "./YamlEditor";
import { detail, mutation } from "./testFixtures";

vi.mock("../api/patterns", async (orig) => {
  const actual = await orig<typeof import("../api/patterns")>();
  return {
    ...actual,
    usePatternVersion: vi.fn(),
    usePatternFamily: vi.fn(),
    usePatternYaml: vi.fn(),
    usePatternView: vi.fn(),
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

const YAML = "pattern: ea.integration.domain-event-backbone\nversion: 1.2.3\nkind: reference-architecture\n";

beforeEach(() => {
  vi.clearAllMocks();
  useAuth.mockReturnValue({ user: { role: "enterprise_architect" } } as never);
  api.usePatternVersion.mockReturnValue({ data: detail(), isLoading: false, error: null } as never);
  api.usePatternFamily.mockReturnValue({ data: undefined } as never);
  api.usePatternYaml.mockReturnValue({ data: YAML, isLoading: false } as never);
  api.useValidatePattern.mockReturnValue(mutation(vi.fn().mockResolvedValue({ ok: true, digest: "d", issues: [] })));
  api.useRenderPattern.mockReturnValue(mutation());
  api.useUpdateDraft.mockReturnValue(mutation(vi.fn().mockResolvedValue({ version: {}, issues: [] })));
  api.useTransition.mockReturnValue(mutation());
  api.useDeleteDraft.mockReturnValue(mutation(vi.fn().mockResolvedValue(undefined)));
});

describe("bumpMinor", () => {
  it("bumps the minor version and resets patch", () => {
    expect(bumpMinor(YAML)).toContain("version: 1.3.0\n");
    expect(bumpMinor("version: 1.9.4")).toBe("version: 1.10.0");
  });
});

describe("YamlEditor", () => {
  it("blocks Save while the last validation of the current text failed", async () => {
    const validate = vi.fn().mockResolvedValue({
      ok: false, digest: null,
      issues: [{ path: "roles", code: "V2.unknown_role", message: "m", severity: "error" }],
    });
    api.useValidatePattern.mockReturnValue(mutation(validate));
    const save = vi.fn().mockResolvedValue({ version: {}, issues: [] });
    api.useUpdateDraft.mockReturnValue(mutation(save));
    render(<YamlEditor patternKey="ea.a.b" version="1.0.0" initialYaml={YAML} />);
    const saveBtn = screen.getByRole("button", { name: "Save draft" }) as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(true); // unchanged text
    await userEvent.type(screen.getByLabelText("Draft YAML"), "x");
    expect(saveBtn.disabled).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "Validate" }));
    expect(await screen.findByText("V2.unknown_role")).toBeTruthy();
    expect(saveBtn.disabled).toBe(true);
    await userEvent.type(screen.getByLabelText("Draft YAML"), "y");
    expect(saveBtn.disabled).toBe(false);
    await userEvent.click(saveBtn);
    expect(save).toHaveBeenCalledWith(`${YAML}xy`);
    expect(await screen.findByText("Draft saved.")).toBeTruthy();
  });

  it("previews the structure view of unsaved text", async () => {
    const renderFn = vi.fn().mockResolvedValue({
      view: "structure", flowchart: "flowchart LR\n    r_a[A]\n", digest: "d", generated_at: "", truncated: [],
    });
    api.useRenderPattern.mockReturnValue(mutation(renderFn));
    render(<YamlEditor patternKey="ea.a.b" version="1.0.0" initialYaml={YAML} />);
    await userEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(renderFn).toHaveBeenCalledWith(YAML);
    expect(await screen.findByRole("img", { name: "Structure preview" })).toBeTruthy();
  });
});

describe("PatternVersion draft actions", () => {
  const props = { patternKey: "ea.integration.domain-event-backbone", version: "1.0.0", onBack: vi.fn(), onSelectVersion: vi.fn(), onNewVersion: vi.fn() };

  it("opens the editor for a draft and prefills New version", async () => {
    render(<PatternVersion {...props} />);
    await userEvent.click(screen.getByRole("tab", { name: "YAML" }));
    expect(screen.getByLabelText("Draft YAML")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "New version" }));
    expect(props.onNewVersion).toHaveBeenCalledWith(bumpMinor(YAML));
  });

  it("is read-only for a proposed version and for reviewers", async () => {
    api.usePatternVersion.mockReturnValue({ data: detail({ lifecycle: "proposed", allowed_transitions: ["draft", "current"] }), isLoading: false, error: null } as never);
    const { unmount } = render(<PatternVersion {...props} />);
    await userEvent.click(screen.getByRole("tab", { name: "YAML" }));
    expect(screen.queryByLabelText("Draft YAML")).toBeNull();
    expect(screen.queryByRole("button", { name: "Delete draft" })).toBeNull();
    unmount();
    useAuth.mockReturnValue({ user: { role: "reviewer" } } as never);
    api.usePatternVersion.mockReturnValue({ data: detail(), isLoading: false, error: null } as never);
    render(<PatternVersion {...props} />);
    expect(screen.queryByRole("button", { name: "New version" })).toBeNull();
    await userEvent.click(screen.getByRole("tab", { name: "YAML" }));
    expect(screen.queryByLabelText("Draft YAML")).toBeNull();
  });

  it("deletes a draft after confirmation and goes back", async () => {
    const del = vi.fn().mockResolvedValue(undefined);
    api.useDeleteDraft.mockReturnValue(mutation(del));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<PatternVersion {...props} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete draft" }));
    expect(del).toHaveBeenCalled();
    expect(props.onBack).toHaveBeenCalled();
  });
});
