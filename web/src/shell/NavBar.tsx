/**
 * Shared navigation bar used by all views (ADP-SPEC-025/026).
 * Shows "Designs" always; design-scoped tabs only when designId is set.
 * Displays signed-in user identity and role when ADP_AUTH_ENABLED=true (ADP-SPEC-026).
 */
import React from "react";
import { useAuth } from "../auth/AuthProvider";

export type AppView = "overview" | "designs" | "intake" | "recommend" | "canvas" | "knowledge" | "portfolio" | "governance" | "business" | "applications";

interface NavBarProps {
  currentView: AppView;
  onNavigate: (view: AppView) => void;
  designId?: string | null;
}

const DESIGN_TABS: { view: AppView; label: string }[] = [
  { view: "intake", label: "Intake" },
  { view: "recommend", label: "Recommendations" },
  { view: "canvas", label: "Canvas" },
  { view: "knowledge", label: "Knowledge" },
];

export default function NavBar({ currentView, onNavigate, designId }: NavBarProps): React.ReactElement {
  const inDesign = !!designId && currentView !== "designs";
  const { user, logout } = useAuth();

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      padding: "0 16px",
      background: "#1168BD",
      color: "#fff",
      flexShrink: 0,
      minHeight: 46,
    }}>
      {/* Wordmark */}
      <span style={{ fontWeight: 700, fontSize: 15, marginRight: 12, padding: "12px 0" }}>ADP</span>

      {/* Overview tab — always visible, the landing dashboard */}
      <button
        onClick={() => onNavigate("overview")}
        style={{
          padding: "12px 16px",
          background: currentView === "overview" ? "rgba(255,255,255,0.2)" : "transparent",
          color: "#fff",
          border: "none",
          borderBottom: currentView === "overview" ? "3px solid #fff" : "3px solid transparent",
          cursor: "pointer",
          fontSize: 14,
          fontWeight: currentView === "overview" ? 600 : 400,
        }}
      >
        Overview
      </button>

      {/* Designs tab — always visible */}
      <button
        onClick={() => onNavigate("designs")}
        style={{
          padding: "12px 16px",
          background: currentView === "designs" ? "rgba(255,255,255,0.2)" : "transparent",
          color: "#fff",
          border: "none",
          borderBottom: currentView === "designs" ? "3px solid #fff" : "3px solid transparent",
          cursor: "pointer",
          fontSize: 14,
          fontWeight: currentView === "designs" ? 600 : 400,
        }}
      >
        Designs
      </button>

      {/* Portfolio tab — always visible */}
      <button
        onClick={() => onNavigate("portfolio")}
        style={{
          padding: "12px 16px",
          background: currentView === "portfolio" || currentView === "governance" ? "rgba(255,255,255,0.2)" : "transparent",
          color: "#fff",
          border: "none",
          borderBottom: currentView === "portfolio" || currentView === "governance" ? "3px solid #fff" : "3px solid transparent",
          cursor: "pointer",
          fontSize: 14,
          fontWeight: currentView === "portfolio" || currentView === "governance" ? 600 : 400,
        }}
      >
        Portfolio
      </button>

      {/* Business tab — always visible */}
      <button
        onClick={() => onNavigate("business")}
        style={{
          padding: "12px 16px",
          background: currentView === "business" ? "rgba(255,255,255,0.2)" : "transparent",
          color: "#fff",
          border: "none",
          borderBottom: currentView === "business" ? "3px solid #fff" : "3px solid transparent",
          cursor: "pointer",
          fontSize: 14,
          fontWeight: currentView === "business" ? 600 : 400,
        }}
      >
        Business
      </button>

      {/* Applications tab — always visible */}
      <button
        onClick={() => onNavigate("applications")}
        style={{
          padding: "12px 16px",
          background: currentView === "applications" ? "rgba(255,255,255,0.2)" : "transparent",
          color: "#fff",
          border: "none",
          borderBottom: currentView === "applications" ? "3px solid #fff" : "3px solid transparent",
          cursor: "pointer",
          fontSize: 14,
          fontWeight: currentView === "applications" ? 600 : 400,
        }}
      >
        Applications
      </button>

      {/* Design-scoped tabs — only when a design is open */}
      {inDesign && DESIGN_TABS.map(({ view, label }) => (
        <button
          key={view}
          onClick={() => onNavigate(view)}
          style={{
            padding: "12px 16px",
            background: currentView === view ? "rgba(255,255,255,0.2)" : "transparent",
            color: "#fff",
            border: "none",
            borderBottom: currentView === view ? "3px solid #fff" : "3px solid transparent",
            cursor: "pointer",
            fontSize: 14,
            fontWeight: currentView === view ? 600 : 400,
          }}
        >
          {label}
        </button>
      ))}

      {/* Right side: design ID + user identity */}
      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
        {inDesign && (
          <span style={{ fontSize: 11, opacity: 0.6 }}>{designId}</span>
        )}

        {/* Signed-in user display (ADP-SPEC-026) */}
        {user && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                background: user.roleColors.bg,
                color: user.roleColors.text,
                fontSize: 10,
                fontWeight: 700,
                padding: "2px 7px",
                borderRadius: 10,
              }}
            >
              {user.roleLabel}
            </span>
            <span style={{ fontSize: 13, opacity: 0.9 }}>{user.username}</span>
            <button
              onClick={logout}
              title="Sign out"
              style={{
                padding: "3px 10px",
                background: "rgba(255,255,255,0.15)",
                color: "#fff",
                border: "1px solid rgba(255,255,255,0.3)",
                borderRadius: 4,
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
