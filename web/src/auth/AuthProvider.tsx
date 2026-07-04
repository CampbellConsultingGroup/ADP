/**
 * AuthProvider — wraps the React app with Keycloak auth context (ADP-SPEC-026).
 *
 * When VITE_AUTH_ENABLED=true:
 *   - Initialises keycloak-js; unauthenticated users are redirected to Keycloak login.
 *   - After login, exposes the signed-in user's name and role via useAuth().
 *
 * When VITE_AUTH_ENABLED=false (default in development/tests):
 *   - Skips Keycloak init; provides a null user context.
 *   - App works exactly as before — no redirects, no token required.
 */
import React, { createContext, useContext, useEffect, useState } from "react";
import { initKeycloak, keycloak } from "./keycloak";

// ── Role display labels ────────────────────────────────────────────────────────

const ROLE_LABELS: Record<string, string> = {
  enterprise_architect: "Enterprise Architect",
  solution_architect: "Solution Architect",
  technical_architect: "Technical Architect",
  reviewer: "Reviewer",
};

const ROLE_COLORS: Record<string, { bg: string; text: string }> = {
  enterprise_architect: { bg: "#EDE9FE", text: "#5B21B6" },
  solution_architect: { bg: "#DBEAFE", text: "#1E40AF" },
  technical_architect: { bg: "#D1FAE5", text: "#065F46" },
  reviewer: { bg: "#F3F4F6", text: "#374151" },
};

export interface AuthUser {
  username: string;
  email: string;
  role: string;
  roleLabel: string;
  roleColors: { bg: string; text: string };
  groups: string[];
}

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  isLoading: false,
  logout: () => {},
});

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}

// ── Group → ADP role mapping (mirrors server-side logic) ──────────────────────

function groupsToRole(groups: string[]): string {
  const priority = ["EnterpriseArchitect", "ADPAdministrator", "SolutionArchitect", "TechnicalArchitect"];
  const roleMap: Record<string, string> = {
    EnterpriseArchitect: "enterprise_architect",
    ADPAdministrator: "enterprise_architect",
    SolutionArchitect: "solution_architect",
    TechnicalArchitect: "technical_architect",
  };
  for (const g of priority) {
    if (groups.some((ug) => ug === g || ug.endsWith(`/${g}`))) {
      return roleMap[g];
    }
  }
  return "technical_architect";
}

function parseUser(): AuthUser | null {
  const parsed = keycloak.tokenParsed;
  if (!parsed) return null;
  const groups: string[] = (parsed as Record<string, unknown>)["groups"] as string[] ?? [];
  const role = groupsToRole(groups);
  return {
    username: (parsed as Record<string, unknown>)["preferred_username"] as string ?? "unknown",
    email: (parsed as Record<string, unknown>)["email"] as string ?? "",
    role,
    roleLabel: ROLE_LABELS[role] ?? role,
    roleColors: ROLE_COLORS[role] ?? { bg: "#F3F4F6", text: "#374151" },
    groups,
  };
}

// ── Provider ──────────────────────────────────────────────────────────────────

const AUTH_ENABLED = import.meta.env.VITE_AUTH_ENABLED !== "false";

interface AuthProviderProps {
  children: React.ReactNode;
}

export default function AuthProvider({ children }: AuthProviderProps): React.ReactElement {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(AUTH_ENABLED);

  useEffect(() => {
    if (!AUTH_ENABLED) {
      setIsLoading(false);
      return;
    }

    initKeycloak()
      .then((authenticated) => {
        if (authenticated) {
          setUser(parseUser());
        }
        setIsLoading(false);
      })
      .catch((err) => {
        console.error("Keycloak init failed:", err);
        setIsLoading(false);
      });

    // Refresh token when it's about to expire
    keycloak.onTokenExpired = () => {
      keycloak.updateToken(60).then(() => {
        setUser(parseUser());
      }).catch(() => {
        keycloak.login();
      });
    };
  }, []);

  const logout = () => {
    if (AUTH_ENABLED) {
      keycloak.logout({ redirectUri: window.location.origin });
    }
  };

  if (isLoading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", fontFamily: "Arial, sans-serif", color: "#6B7280" }}>
        Signing in…
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
