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
  // Overrides the default onNavigate(view) call -- used by the Design
  // section's "Intake" entry to reset to a blank/new-design state instead of
  // the generic per-view navigation (see AppShell's onStartNewDesign prop).
  onClick?: () => void;
}

const PRIMARY: NavDef[] = [
  { view: "overview", label: "Overview", icon: "grid" },
  // 919-insights-dashboard: general-audience, cross-domain visualizations --
  // sibling to Overview, deliberately not folded into ARCHITECTURE below
  // (that group is entirely architect-facing domain editors).
  { view: "insights", label: "Insights", icon: "target" },
];
const ARCHITECTURE: NavDef[] = [
  // ADP-d8u.1: strategic objectives are a distinct entity with their own
  // lifecycle (plan.md's Structure Decision) -- a new top-level section,
  // not nested under Business Architecture. Placed first, ahead of
  // Business, per explicit nav-ordering request.
  { view: "strategy", label: "Strategy", icon: "spark", hue: "biz" },
  { view: "business", label: "Business", icon: "biz", hue: "biz" },
  { view: "applications", label: "Applications", icon: "ent", hue: "ent" },
  // ADP-61l: mirrors Business's own top-level structure (a new top-level
  // nav item, not a tab bolted onto Applications) -- placed beside
  // Applications, the other "ent"-adjacent registry-style screen.
  { view: "technical", label: "Technical Architecture", icon: "tec", hue: "tec" },
  // ADP-SPEC-046 / ADP-914.5: standalone diagrams (flowchart/sequence/ERD/
  // UML/architecture) have no relationship to a Design (FR-011), so they sit
  // here alongside Business/Applications rather than under DESIGN_SCOPED.
  { view: "diagrams", label: "Diagrams", icon: "layers", hue: "tec" },
];
const OVERSIGHT: NavDef[] = [
  { view: "portfolio", label: "APM", icon: "chart", hue: "ent" },
  { view: "governance", label: "Governance", icon: "shield" },
  // COMPLY-01: placed beside Governance, per the source doc's own framing of
  // Compliance as governance-adjacent (plan.md Project Structure).
  { view: "compliance", label: "Compliance", icon: "shield", hue: "biz" },
  { view: "knowledge", label: "Knowledge", icon: "book", hue: "tec" },
];
// ADP-SPEC-042: gated at the route/nav level on the distinct platform_admin
// role, not folded into ARCHITECTURE — this surface has its own permission
// (MANAGE_AGENT_PROMPTS), not implied by any architect role.
const ADMIN: NavDef[] = [
  { view: "admin", label: "Agent Prompts", icon: "shield" },
  // ADP-68z: sibling admin surface, same platform_admin-only gate.
  { view: "scoring-rubrics", label: "Scoring Rubrics", icon: "shield" },
];

const TITLES: Record<AppView, string> = {
  overview: "Overview",
  insights: "Insights",
  designs: "Designs",
  business: "Business Architecture",
  applications: "Application Registry",
  technical: "Technical Architecture",
  portfolio: "APM",
  governance: "Governance",
  knowledge: "Knowledge",
  intake: "Requirements Intake",
  "canvas-v2": "C4 Design",
  diagrams: "Diagrams",
  strategy: "Strategy",
  compliance: "Compliance",
  admin: "Agent Prompt Management",
  "scoring-rubrics": "Scoring Rubric Management",
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
    <button className={cls} onClick={def.onClick ?? (() => onNavigate(def.view))}>
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
  // "Intake" nav click == "New Design": resets to a blank Intake form even if
  // a design is currently selected. Optional -- falls back to plain
  // onNavigate("intake") if omitted (e.g. in tests that don't wire it up).
  onStartNewDesign?: () => void;
  children: React.ReactNode;
}

export function AppShell({ currentView, onNavigate, designId, onStartNewDesign, children }: AppShellProps): React.ReactElement {
  const { user, logout } = useAuth();
  const { cycle } = useTheme();
  const inDesign = !!designId;
  const initials = user ? user.username.slice(0, 2).toUpperCase() : "AD";

  // Defined inside the component (unlike PRIMARY/ARCHITECTURE/OVERSIGHT above)
  // because "Intake" needs to close over the onStartNewDesign prop. Always
  // rendered (not gated on a design being selected) -- it's the entry point
  // into any design in the first place, as well as the home for per-design
  // views once inside one. Recommendations is no longer a top-level entry --
  // it's a tab inside IntakePage itself (the second step of Intake's own
  // flow). See the render logic below for how the section label adapts to
  // whether a design is currently selected.
  const DESIGN_SCOPED: NavDef[] = [
    { view: "designs", label: "Designs", icon: "sol" },
    { view: "intake", label: "Intake", icon: "inbox", onClick: onStartNewDesign },
    // ADP-914.13: the legacy "Canvas" item (C4Canvas/Workspace, ADP-SPEC-054's research.md
    // Decision 8 called it "canvas") is retired -- this is now the sole design-editing entry
    // point, so it drops the "(Preview)" qualifier that distinguished it from the alternative.
    { view: "canvas-v2", label: "C4 Design", icon: "sol" },
  ];

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

        <div className="shell-navlabel">Oversight</div>
        {OVERSIGHT.map((d) => <NavItem key={d.view} def={d} current={currentView} onNavigate={onNavigate} />)}

        {user?.role === "platform_admin" && (
          <>
            <div className="shell-navlabel">Administration</div>
            {ADMIN.map((d) => <NavItem key={d.view} def={d} current={currentView} onNavigate={onNavigate} />)}
          </>
        )}

        <div className="shell-navlabel">{inDesign ? `Design · ${designId}` : "Design"}</div>
        {DESIGN_SCOPED.map((d) => <NavItem key={d.view} def={d} current={currentView} onNavigate={onNavigate} />)}

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
