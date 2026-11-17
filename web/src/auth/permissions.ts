import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { useAuth } from "./AuthProvider";

/**
 * What the signed-in user may do, from the server's own permission table (ADP-blp.62).
 *
 * `useCan("write_business_arch")` lets a screen disable a control and say why before the click,
 * instead of accepting a filled-in form and then refusing it. The answer comes from
 * GET /api/v1/auth/permissions, so it cannot drift from what the server enforces. Until it has
 * loaded -- or if it cannot be loaded -- everything is treated as allowed: the server still
 * checks every request, so the worst case is the old behaviour (a refusal after the click).
 */
interface MyPermissions {
  role: string;
  actions: string[];
}

let cache: Promise<MyPermissions | null> | null = null;

function load(): Promise<MyPermissions | null> {
  if (cache === null) {
    cache = apiGet<MyPermissions>("/api/v1/auth/permissions").catch(() => {
      cache = null; // try again next time
      return null;
    });
  }
  return cache;
}

/** For tests, and for a sign-out / role change. */
export function resetPermissionsCache(): void {
  cache = null;
}

export interface Permission {
  allowed: boolean;
  /** Why not, for a tooltip. Undefined when allowed. */
  reason?: string;
}

export function useCan(action: string): Permission {
  const { user } = useAuth();
  const [permissions, setPermissions] = useState<MyPermissions | null>(null);

  useEffect(() => {
    let live = true;
    void load().then((result) => {
      if (live) setPermissions(result);
    });
    return () => {
      live = false;
    };
  }, [user?.role]);

  if (permissions === null || permissions.actions.includes(action)) return { allowed: true };
  const role = user?.roleLabel ?? permissions.role.replace(/_/g, " ");
  return {
    allowed: false,
    reason: `Your role (${role}) cannot do this. Ask an administrator if you need access.`,
  };
}
