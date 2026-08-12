/**
 * AppShell — the application chrome: left navigation rail + top bar.
 * Rendered once at the App level; page components render as children inside
 * the scrollable content area. Replaces the old per-page NavBar.
 */
import React from "react";
import type { AppView } from "../shell";
import { useAuth } from "../auth/AuthProvider";
import { Icon } from "./Icon";
import { useTheme } from "./theme";

interface NavDef {
  view: AppView;
  label: string;
  icon: string;
  hue?: "biz" | "ent" | "sol" | "tec";
}

const PRIMARY: NavDef[] = [
  { view: "overview", label: "Overview", icon: "grid" },
  { view: "designs", label: "Designs", icon: "sol" },
];
const ARCHITECTURE: NavDef[] = [
  // ADP-d8u.1: strategic objectives are a distinct entity with their own
  // lifecycle (plan.md's Structure Decision) -- a new top-level section,
  // not nested under Business Architecture. Placed first, ahead of
  // Business, per explicit nav-ordering request.
  { view: "strategy", label: "Strategy", icon: "spark", hue: "biz" },
  { view: "business", label: "Business", icon: "biz", hue: "biz" },
  { view: "applications", label: "Applications", icon: "ent", hue: "ent" },
  { view: "portfolio", label: "Portfolio", icon: "chart", hue: "ent" },
  { view: "governance", label: "Governance", icon: "shield" },
  { view: "knowledge", label: "Knowledge", icon: "book", hue: "tec" },
  // ADP-SPEC-046 / ADP-914.5: standalone diagrams (flowchart/sequence/ERD/
  // UML/architecture) have no relationship to a Design (FR-011), so they sit
  // here alongside Business/Applications rather than under DESIGN_SCOPED.
  { view: "diagrams", label: "Diagrams", icon: "layers", hue: "tec" },
];
const DESIGN_SCOPED: NavDef[] = [
  { view: "intake", label: "Intake", icon: "inbox" },
  { view: "recommend", label: "Recommendations", icon: "spark" },
  { view: "canvas", label: "Canvas", icon: "sol" },
];
// ADP-SPEC-042: gated at the route/nav level on the distinct platform_admin
// role, not folded into ARCHITECTURE — this surface has its own permission
// (MANAGE_AGENT_PROMPTS), not implied by any architect role.
const ADMIN: NavDef[] = [
  { view: "admin", label: "Agent Prompts", icon: "shield" },
];

const TITLES: Record<AppView, string> = {
  overview: "Overview",
  designs: "Designs",
  business: "Business Architecture",
  applications: "Application Registry",
  portfolio: "Portfolio",
  governance: "Governance",
  knowledge: "Knowledge",
  intake: "Requirements Intake",
  recommend: "Recommendations",
  canvas: "Design Canvas",
  diagrams: "Diagrams",
  strategy: "Strategy",
  admin: "Agent Prompt Management",
};

const HUE_VARS: Record<string, string> = {
  biz: "var(--biz)",
  ent: "var(--ent)",
  sol: "var(--sol)",
  tec: "var(--tec)",
};

function NavItem({
  def,
  current,
  onNavigate,
}: {
  def: NavDef;
  current: AppView;
  onNavigate: (v: AppView) => void;
}): React.ReactElement {
  const active = current === def.view;
  const cls = `shell-navitem${active ? " active" : ""}${active && def.hue ? ` hue-${def.hue}` : ""}`;
  return (
    <button className={cls} onClick={() => onNavigate(def.view)}>
      <Icon name={def.icon} size={18} />
      {def.label}
      {def.hue && <span className="dot" style={{ background: HUE_VARS[def.hue] }} />}
    </button>
  );
}

interface AppShellProps {
  currentView: AppView;
  onNavigate: (view: AppView) => void;
  designId?: string | null;
  children: React.ReactNode;
}

export function AppShell({ currentView, onNavigate, designId, children }: AppShellProps): React.ReactElement {
  const { user, logout } = useAuth();
  const { cycle } = useTheme();
  const inDesign = !!designId;
  const initials = user ? user.username.slice(0, 2).toUpperCase() : "AD";

  return (
    <div className="shell">
      <nav className="shell-rail">
        <div className="shell-brand">
          <span className="mark"><Icon name="compass" size={19} style={{ stroke: "#fff" }} /></span>
          <span className="txt">
            <span className="name">ADP</span>
            <span className="sub">Architecture Platform</span>
          </span>
        </div>

        <div className="shell-navlabel">Workspace</div>
        {PRIMARY.map((d) => <NavItem key={d.view} def={d} current={currentView} onNavigate={onNavigate} />)}

        <div className="shell-navlabel">Architecture</div>
        {ARCHITECTURE.map((d) => <NavItem key={d.view} def={d} current={currentView} onNavigate={onNavigate} />)}

        {user?.role === "platform_admin" && (
          <>
            <div className="shell-navlabel">Administration</div>
            {ADMIN.map((d) => <NavItem key={d.view} def={d} current={currentView} onNavigate={onNavigate} />)}
          </>
        )}

        {inDesign && (
          <>
            <div className="shell-navlabel">Design · {designId}</div>
            {DESIGN_SCOPED.map((d) => <NavItem key={d.view} def={d} current={currentView} onNavigate={onNavigate} />)}
          </>
        )}

        <div className="shell-railspacer" />
        {user && (
          <div className="shell-user">
            <span className="av">{initials}</span>
            <span style={{ minWidth: 0 }}>
              <span className="who">{user.username}</span>
              <span className="role" style={{ display: "block" }}>{user.roleLabel}</span>
            </span>
            <button className="shell-signout" onClick={logout} title="Sign out">Sign out</button>
          </div>
        )}
      </nav>

      <div className="shell-main">
        <header className="shell-topbar">
          <div className="shell-crumb"><span>ADP</span><span>/</span><b>{TITLES[currentView]}</b></div>
          <div className="shell-search"><Icon name="search" size={15} /> Search… <span className="k">⌘K</span></div>
          <div className="shell-topactions">
            <span className="shell-envpill"><span className="led" /> Retail demo</span>
            <button className="shell-iconbtn" onClick={cycle} title="Toggle light / dark"><Icon name="moon" size={18} /></button>
            <button className="shell-iconbtn" title="Notifications"><Icon name="bell" size={18} /></button>
          </div>
        </header>
        <div className="shell-content">{children}</div>
      </div>
    </div>
  );
}
