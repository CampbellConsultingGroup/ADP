import { describe, expect, it } from "vitest";
import { groupsToRole } from "../../src/auth/AuthProvider";

// ADP-SPEC-042: ADPAdministrator now maps to "platform_admin", not
// "enterprise_architect" -- Clarification Session 2026-07-24 Q1 requires a
// distinct Administrator permission, not implied by any architect role.

describe("groupsToRole", () => {
  it("maps ADPAdministrator to platform_admin", () => {
    expect(groupsToRole(["ADPAdministrator"])).toBe("platform_admin");
  });

  it("maps EnterpriseArchitect to enterprise_architect", () => {
    expect(groupsToRole(["EnterpriseArchitect"])).toBe("enterprise_architect");
  });

  it("platform_admin outranks enterprise_architect when both groups present", () => {
    expect(groupsToRole(["EnterpriseArchitect", "ADPAdministrator"])).toBe("platform_admin");
  });

  it("defaults to technical_architect for no recognized group", () => {
    expect(groupsToRole([])).toBe("technical_architect");
    expect(groupsToRole(["UnknownGroup"])).toBe("technical_architect");
  });
});
