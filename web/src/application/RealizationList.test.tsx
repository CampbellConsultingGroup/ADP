// 943-mapping-rationale US1: the "Realized by applications" editor. Choosing a rationale or a
// geography on a row saves at once (the ADP-w7z convention); the add row sends them with the link.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as acApi from "../api/appCapabilities";
import * as orgApi from "../api/organization";
import type { AppRef } from "../api/appCapabilities";
import type { Geography } from "../api/organization";
import RealizationList from "./RealizationList";

vi.mock("../api/appCapabilities", async (orig) => ({
  ...(await orig<typeof import("../api/appCapabilities")>()),
  useAddRealization: vi.fn(),
  useUpdateRealization: vi.fn(),
  useRemoveAppCapLink: vi.fn(),
}));
vi.mock("../api/organization", async (orig) => ({
  ...(await orig<typeof import("../api/organization")>()),
  useGeographies: vi.fn(),
}));

const ac = vi.mocked(acApi);
const org = vi.mocked(orgApi);
const geo = (id: string, name: string, kind: Geography["kind"], code: string | null = null): Geography => ({
  id, name, code, m49: null, parent_id: null, level: kind === "global" ? 1 : kind === "region" ? 2 : 3, kind, path: [], org_unit_count: 0,
});
const GEOS = [geo("g", "Global", "global"), geo("am", "Americas", "region"), geo("eu", "Europe", "region"), geo("de", "Germany", "country", "DE")];
const LINKED: AppRef[] = [
  { id: "pos", name: "Store POS", rationale: "target", geography: null, hint: null },
  { id: "ecom", name: "Commerce Cloud", rationale: null, geography: { id: "am", name: "Americas", code: null }, hint: null },
  { id: "old", name: "Legacy POS", rationale: "target", geography: null, hint: "TIME says Eliminate" },
];
const APPS = [
  { id: "pos", label: "Store POS" },
  { id: "ecom", label: "Commerce Cloud" },
  { id: "old", label: "Legacy POS" },
  { id: "new", label: "Order Hub" },
];

let update: ReturnType<typeof vi.fn>;
let add: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  update = vi.fn().mockResolvedValue({});
  add = vi.fn().mockResolvedValue({});
  ac.useUpdateRealization.mockReturnValue({ mutateAsync: update, isPending: false } as never);
  ac.useAddRealization.mockReturnValue({ mutateAsync: add, isPending: false } as never);
  ac.useRemoveAppCapLink.mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue(undefined), isPending: false } as never);
  org.useGeographies.mockReturnValue({ data: { items: GEOS, total: GEOS.length } } as never);
});

const list = (canWrite = true) => render(<RealizationList acId="ac1" linked={LINKED} options={APPS} canWrite={canWrite} />);
const row = (name: string) => screen.getByRole("listitem", { name });

describe("RealizationList", () => {
  it("shows each realization's rationale and geography", () => {
    list();
    expect((within(row("Store POS")).getByLabelText("Rationale for Store POS") as HTMLSelectElement).value).toBe("target");
    expect((within(row("Commerce Cloud")).getByLabelText("Rationale for Commerce Cloud") as HTMLSelectElement).value).toBe("");
    expect((within(row("Commerce Cloud")).getByLabelText("Geography for Commerce Cloud") as HTMLSelectElement).value).toBe("am");
  });

  it("saves a rationale as soon as it is chosen; Unclassified clears it", async () => {
    list();
    await userEvent.selectOptions(screen.getByLabelText("Rationale for Commerce Cloud"), "tactical");
    expect(update).toHaveBeenCalledWith({ id: "ac1", appId: "ecom", attrs: { rationale: "tactical" } });
    await userEvent.selectOptions(screen.getByLabelText("Rationale for Store POS"), "");
    expect(update).toHaveBeenCalledWith({ id: "ac1", appId: "pos", attrs: { rationale: null } });
  });

  it("saves a geography as soon as it is chosen; Everywhere clears it, and Global is not offered", async () => {
    list();
    const pick = screen.getByLabelText("Geography for Store POS") as HTMLSelectElement;
    expect(Array.from(pick.options).map((o) => o.textContent)).toEqual(["Everywhere", "Americas", "Europe", "Germany (DE)"]);
    await userEvent.selectOptions(pick, "de");
    expect(update).toHaveBeenCalledWith({ id: "ac1", appId: "pos", attrs: { geography_id: "de" } });
    await userEvent.selectOptions(screen.getByLabelText("Geography for Commerce Cloud"), "");
    expect(update).toHaveBeenCalledWith({ id: "ac1", appId: "ecom", attrs: { geography_id: null } });
  });

  it("shows the TIME hint", () => {
    list();
    expect(within(row("Legacy POS")).getByText(/TIME says Eliminate/)).toBeTruthy();
  });

  it("adds a realization with an optional rationale and geography", async () => {
    list();
    await userEvent.selectOptions(screen.getByLabelText("Add application"), "new");
    await userEvent.selectOptions(screen.getByLabelText("Rationale for the new application"), "transitional");
    await userEvent.selectOptions(screen.getByLabelText("Geography for the new application"), "eu");
    await userEvent.click(screen.getByRole("button", { name: "Link" }));
    expect(add).toHaveBeenCalledWith({ id: "ac1", appId: "new", attrs: { rationale: "transitional", geography_id: "eu" } });
  });

  it("shows the server's message when a save fails", async () => {
    update.mockRejectedValueOnce(new Error("No geography already means everywhere"));
    list();
    await userEvent.selectOptions(screen.getByLabelText("Geography for Store POS"), "de");
    expect((await screen.findByRole("alert")).textContent).toMatch(/everywhere/);
  });

  it("is read-only text for readers", () => {
    list(false);
    expect(screen.queryByLabelText("Rationale for Store POS")).toBeNull();
    expect(screen.queryByLabelText("Add application")).toBeNull();
    expect(within(row("Store POS")).getByText("Target")).toBeTruthy();
    expect(within(row("Commerce Cloud")).getByText("Unclassified")).toBeTruthy();
    expect(within(row("Commerce Cloud")).getByText(/Americas/)).toBeTruthy();
  });
});
