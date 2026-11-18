/** Cosmetic UI gating for pattern authoring/governance (935 research D14). The server's
 * WRITE_PATTERN / GOVERN_PATTERN rules stay authoritative. */

import { useAuth } from "../auth/AuthProvider";
import { useCan } from "../auth/permissions";

const PATTERN_MANAGER_ROLES = new Set(["enterprise_architect", "platform_admin"]);
const AUTH_ENABLED = import.meta.env.VITE_AUTH_ENABLED !== "false";

/** With auth disabled the API treats every caller as Enterprise Architect, so a null user may
 * manage patterns only in that mode. */
export function canManagePatterns(role: string | null | undefined, authEnabled = AUTH_ENABLED): boolean {
  if (!role) return !authEnabled;
  return PATTERN_MANAGER_ROLES.has(role);
}

/** ADP-blp.65: the server's answer once loaded; the role list above is the guess until then. */
export function useCanManagePatterns(): boolean {
  const { user } = useAuth();
  return useCan("write_pattern", canManagePatterns(user?.role ?? null)).allowed;
}

/** Lifecycle transitions (propose, promote, deprecate, decommission) need GOVERN_PATTERN. */
export function useCanGovernPatterns(): boolean {
  const { user } = useAuth();
  return useCan("govern_pattern", canManagePatterns(user?.role ?? null)).allowed;
}
