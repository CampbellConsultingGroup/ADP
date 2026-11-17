// 937-application-capabilities: cross-screen navigation to an application capability, plus the
// cosmetic write gate. A context (rather than a prop threaded through BusinessPage ->
// CapabilityTree -> CapabilityNode, TechCapPage -> TechCapTree and ApplicationDetail) because the
// read-only "application capabilities" sections live several levels deep on three screens.

import { createContext, useContext } from "react";
import { useAuth } from "../auth/AuthProvider";
import { useCan } from "../auth/permissions";

/** Opens Applications -> Capabilities with the given capability selected. */
export const AppCapNavContext = createContext<((id: string) => void) | null>(null);

export function useOpenAppCapability(): ((id: string) => void) | null {
  return useContext(AppCapNavContext);
}

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
export function useCanWriteApplications(): boolean {
  const { user } = useAuth();
  return useCan("write_application", canWriteApplications(user?.role ?? null)).allowed;
}

// 938-capability-model-analysis (FR-018): every item in the impact, exposure, gap, overlap and
// shared lists navigates to that item on its own screen. Provided by App.tsx; null in isolation
// (tests, or a screen rendered outside the shell), where items render as plain text.
export interface CapabilityNav {
  /** Business -> Capabilities, scrolled to and highlighting the capability. */
  openBusinessCapability: (id: string) => void;
  /** Applications -> Registry with the application open. */
  openApplication: (id: string) => void;
  /** Technical Architecture, scrolled to and highlighting the capability. */
  openTechnicalCapability: (id: string) => void;
  /** 944: Agents, with the agent open. Optional so screens that predate it need no change. */
  openAgent?: (id: string) => void;
}

export const CapabilityNavContext = createContext<CapabilityNav | null>(null);

export function useCapabilityNav(): CapabilityNav | null {
  return useContext(CapabilityNavContext);
}
