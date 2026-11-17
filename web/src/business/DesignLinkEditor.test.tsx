// ADP-blp.36: the capability / value stream design link editor is now a wrapper over the
// shared link editor. These check what the wrapper is responsible for.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DesignLinkEditor from "./DesignLinkEditor";
import * as businessApi from "../api/business";

vi.mock("../api/business");
const api = vi.mocked(businessApi);

const linkMutate = vi.fn();
const unlinkMutate = vi.fn();

function mutation(mutate: ReturnType<typeof vi.fn>) {
  return { mutate, isPending: false } as never;
}

beforeEach(() => {
  vi.clearAllMocks();
  api.useDesigns.mockReturnValue({
    data: { designs: [{ id: "DSN-2", title: "Checkout redesign" }] },
  } as never);
  // DSN-9 is linked but is NOT in the picker's page of designs.
  api.useLinkedCapabilityDesigns.mockReturnValue({
    data: { items: [{ design_id: "DSN-9", title: "Legacy POS", lifecycle_status: "approved" }] },
    isLoading: false,
  } as never);
  api.useLinkedValueStreamDesigns.mockReturnValue({ data: undefined, isLoading: false } as never);
  api.useLinkDesignToCapability.mockReturnValue(mutation(linkMutate));
  api.useUnlinkDesignFromCapability.mockReturnValue(mutation(unlinkMutate));
  api.useLinkDesignToValueStream.mockReturnValue(mutation(vi.fn()));
  api.useUnlinkDesignFromValueStream.mockReturnValue(mutation(vi.fn()));
});

describe("business DesignLinkEditor", () => {
  it("lists a linked design with its status even when it is not among the picker's designs", () => {
    render(<DesignLinkEditor entityType="capability" entityId="cap-1" />);

    expect(screen.getByText("Legacy POS")).toBeTruthy();
    expect(screen.getByText("approved")).toBeTruthy();
    expect(api.useLinkedCapabilityDesigns).toHaveBeenCalledWith("cap-1");
    expect(api.useLinkedValueStreamDesigns).toHaveBeenCalledWith(null);
  });

  it("links a design as soon as it is chosen, and removes one", async () => {
    const user = userEvent.setup();
    render(<DesignLinkEditor entityType="capability" entityId="cap-1" />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Link a design" }), "DSN-2");
    expect(linkMutate).toHaveBeenCalledWith("DSN-2", expect.anything());

    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(unlinkMutate).toHaveBeenCalledWith("DSN-9", expect.anything());
  });
});
