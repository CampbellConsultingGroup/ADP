// The cosmetic write gate for application screens. (The navigation contexts that used to live
// here are gone: entities are linked with shell/EntityLink, ADP-blp.57.)

import { useAuth } from "../auth/AuthProvider";
import { useCan, type Permission } from "../auth/permissions";

// Roles holding WRITE_APPLICATION (src/adp/authz/permissions.py). The server stays authoritative.
const APPLICATION_WRITER_ROLES = new Set([
  "enterprise_architect",
  "platform_admin",
  "solution_architect",
  "technical_architect",
]);
const AUTH_ENABLED = import.meta.env.VITE_AUTH_ENABLED !== "false";

/** With auth disabled the API treats every caller as Enterprise Architect. */
export function canWriteApplications(role: string | null | undefined, authEnabled = AUTH_ENABLED): boolean {
  if (!role) return !authEnabled;
  return APPLICATION_WRITER_ROLES.has(role);
}

/**
 * ADP-blp.65: the server's own answer (GET /api/v1/auth/permissions) once it has loaded, so this
 * cannot drift from the permission table. The role list above is only the guess used until then.
 */
export function useApplicationWrite(): Permission {
  const { user } = useAuth();
  return useCan("write_application", canWriteApplications(user?.role ?? null));
}

export function useCanWriteApplications(): boolean {
  return useApplicationWrite().allowed;
}

/** WRITE_BUSINESS_ARCH: business architecture, organization and strategy writes. */
export function useBusinessWrite(): Permission {
  const { user } = useAuth();
  return useCan("write_business_arch", canWriteApplications(user?.role ?? null));
}
