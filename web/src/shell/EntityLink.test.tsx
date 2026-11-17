import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { EntityLink, entityHref } from "./EntityLink";
import { parseRoute } from "./routing";

describe("EntityLink (ADP-blp.57)", () => {
  it("is a plain link to the entity's own address", () => {
    render(<EntityLink kind="application" id="APP-7">Billing</EntityLink>);
    const link = screen.getByRole("link", { name: "Billing" });
    expect(link.getAttribute("href")).toBe("#/applications/APP-7");
  });

  it("gives every kind an address the router understands", () => {
    const kinds = [
      "business_capability", "application", "application_capability", "technical_capability",
      "agent", "adoption",
    ] as const;
    for (const kind of kinds) {
      expect(parseRoute(entityHref(kind, "x 1"))?.entity).toEqual({ kind, id: "x 1" });
    }
  });
});
