/**
 * ADP-dhx: React 18 StrictMode (main.tsx) double-invokes AuthProvider's init
 * effect in dev, so initKeycloak() gets called twice against the same
 * module-level `keycloak` singleton. Real keycloak-js throws "A Keycloak
 * instance can only be initialized once" if keycloak.init() is called a
 * second time -- initKeycloak() must memoize so a second call never re-enters
 * keycloak.init().
 */
import { describe, expect, it, vi } from "vitest";

const mockInit = vi.fn(() => Promise.resolve(true));

vi.mock("keycloak-js", () => ({
  default: vi.fn().mockImplementation(function MockKeycloak(this: { init: typeof mockInit }) {
    this.init = mockInit;
  }),
}));

describe("initKeycloak (ADP-dhx double-init guard)", () => {
  it("calls keycloak.init() only once across repeated calls", async () => {
    const { initKeycloak } = await import("./keycloak");

    // Mirrors StrictMode: two synchronous calls before either resolves.
    const first = initKeycloak();
    const second = initKeycloak();

    expect(mockInit).toHaveBeenCalledTimes(1);

    await expect(first).resolves.toBe(true);
    await expect(second).resolves.toBe(true);

    // A third call, after the first has already settled, must still reuse it.
    await initKeycloak();
    expect(mockInit).toHaveBeenCalledTimes(1);
  });
});
