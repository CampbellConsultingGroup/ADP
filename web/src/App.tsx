import React, { lazy, useEffect, useMemo, useRef, useState } from "react";
import OverviewPage from "./overview/OverviewPage";
import { AppCapNavContext, CapabilityNavContext, type CapabilityNav } from "./application/appCapNav";
import type { DiagramSeed } from "./diagrams/generators";

// ADP-blp.31: every page except the landing page is loaded on first visit. The app used to ship
// as one 1.78 MB script -- the diagram editor, its icon libraries and every registry screen --
// before anything could render. PageBoundary's Suspense shows "Loading…" while a page's chunk
// arrives, and its error boundary covers a chunk that fails to load.
const InsightsPage = lazy(() => import("./insights/InsightsPage"));
const DesignsPage = lazy(() => import("./designs/DesignsPage"));
const C4DesignView = lazy(() =>
  import("./canvas-v2/C4DesignView").then((m) => ({ default: m.C4DesignView })),
);
const IntakePage = lazy(() => import("./intake/IntakePage"));
const KnowledgePage = lazy(() => import("./knowledge/KnowledgePage"));
const PortfolioPage = lazy(() => import("./portfolio/PortfolioPage"));
const GovernancePage = lazy(() => import("./governance/GovernancePage"));
const BusinessPage = lazy(() => import("./business/BusinessPage"));
const ApplicationPage = lazy(() => import("./application/ApplicationPage"));
const TechCapPage = lazy(() => import("./application/TechCapPage"));
const DiagramsPage = lazy(() =>
  import("./diagrams/DiagramsPage").then((m) => ({ default: m.DiagramsPage })),
);
const StrategyPage = lazy(() => import("./strategy/StrategyPage"));
const CompliancePage = lazy(() => import("./compliance/CompliancePage"));
const PatternsPage = lazy(() => import("./patterns/PatternsPage"));
const AgentsPage = lazy(() => import("./agentic/AgentsPage"));
const AdminPage = lazy(() => import("./admin/AdminPage"));
const ScoringRubricsPage = lazy(() => import("./admin/ScoringRubricsPage"));
import { AppShell } from "./ui";
import { AskAiLauncher } from "./chat/AskAiLauncher";
import { PageBoundary } from "./ui/PageBoundary";
import type { SearchHit } from "./ui/SearchPalette";
import type { AppView } from "./shell";
import { formatRoute, parseRoute, type AppRoute, type EntityKind } from "./shell/routing";

// C4 Design has no meaning without a design (it operates on elements that only
// exist once one does) -- clicking it from the always-visible Design nav group
// with no design selected detours through the Designs list (to pick or create
// one) rather than silently landing on that same list with no explanation.
//
// Intake is deliberately NOT here: it's where a design starts (capturing the
// Business Problem), so it must be reachable directly with no detour at all --
// see IntakePage/IntakeTextForm, which create the design lazily on first submit.
// Recommendations is no longer a top-level view at all -- it's a tab inside
// IntakePage itself (the second step of Intake's own flow), so it needs no
// entry here either.
const DESIGN_ONLY_VIEWS: AppView[] = ["canvas-v2"];
const DESIGN_ONLY_VIEW_LABELS: Record<string, string> = {
  "canvas-v2": "C4 Design",
};

// ADP-SPEC-025: Multi-design support.
// currentDesignId is null until the user selects or creates a design.
// Initial view is "overview" (the landing dashboard). All views render inside
// the shared AppShell (left-rail nav + top bar).
export default function App(): React.ReactElement {
  // ADP-blp.53: the starting location comes from the URL hash, so a reload or a pasted link
  // opens the same screen (and entity, and design) instead of always landing on Overview.
  const [initialRoute] = useState<AppRoute | null>(() => parseRoute(window.location.hash));
  const initialEntity = (kind: EntityKind): string | null =>
    initialRoute?.entity?.kind === kind ? initialRoute.entity.id : null;
  const [view, setView] = useState<AppView>(initialRoute?.view ?? "overview");
  const [currentDesignId, setCurrentDesignId] = useState<string | null>(initialRoute?.designId ?? null);
  // Set when a design-only view is requested with no design selected yet --
  // consumed by onSelectDesign below so the user lands on the screen they
  // actually asked for (e.g. Recommendations) instead of always defaulting
  // to Intake once they pick or create a design.
  const [pendingView, setPendingView] = useState<AppView | null>(null);
  // ADP-914.7: a diagram generated from a value stream/capability elsewhere in
  // the app, waiting to be opened in the Diagrams editor -- mirrors
  // currentDesignId/onSelectDesign below exactly (research.md Decision 3).
  const [pendingDiagramSeed, setPendingDiagramSeed] = useState<DiagramSeed | null>(null);
  // 933-agent-registry: an application to open when an agent's solution link is followed.
  const [pendingAppId, setPendingAppId] = useState<string | null>(initialEntity("application"));
  // 937-application-capabilities: an application capability to open in Applications ->
  // Capabilities, when one is followed from a business/technical capability or an application.
  const [pendingAppCapId, setPendingAppCapId] = useState<string | null>(
    initialEntity("application_capability"),
  );
  const openAppCapability = (id: string) => {
    setPendingAppId(null);
    setPendingAppCapId(id);
    setView("applications");
  };
  // 938-capability-model-analysis: the analysis lists navigate to business capabilities,
  // applications and technical capabilities on their own screens.
  const [pendingBusinessCapId, setPendingBusinessCapId] = useState<string | null>(
    initialEntity("business_capability"),
  );
  const [pendingTechCapId, setPendingTechCapId] = useState<string | null>(
    initialEntity("technical_capability"),
  );
  // 939-governance-architecture-health: an adoption to open on the Patterns screen.
  const [pendingAdoptionId, setPendingAdoptionId] = useState<string | null>(initialEntity("adoption"));
  const openAdoption = (id: string) => {
    setPendingAdoptionId(id);
    setView("patterns");
  };
  // 944-agent-traceability: an agent to open on the Agents screen.
  const [pendingAgentId, setPendingAgentId] = useState<string | null>(initialEntity("agent"));
  const capabilityNav: CapabilityNav = {
    openBusinessCapability: (id) => {
      setPendingBusinessCapId(id);
      setView("business");
    },
    openApplication: (id) => {
      setPendingAppCapId(null);
      setPendingAppId(id);
      setView("applications");
    },
    openTechnicalCapability: (id) => {
      setPendingTechCapId(id);
      setView("technical");
    },
    openAgent: (id) => {
      setPendingAgentId(id);
      setView("agents");
    },
  };

  // ADP-blp.56: a global search result opens on the screen that owns that kind of entity.
  // Kinds with no single-entity deep link yet open their screen.
  const onOpenSearchResult = (hit: SearchHit) => {
    switch (hit.entity_type) {
      case "business_capability":
        capabilityNav.openBusinessCapability(hit.entity_id);
        break;
      case "application":
        capabilityNav.openApplication(hit.entity_id);
        break;
      case "application_capability":
        openAppCapability(hit.entity_id);
        break;
      case "technical_capability":
        capabilityNav.openTechnicalCapability(hit.entity_id);
        break;
      case "agent":
        capabilityNav.openAgent?.(hit.entity_id);
        break;
      default:
        // value streams, stages, value chains, domains, org units
        onNavigate("business");
    }
  };

  function onNavigate(nextView: AppView) {
    if (!currentDesignId && DESIGN_ONLY_VIEWS.includes(nextView)) {
      setPendingView(nextView);
      setView("designs");
      return;
    }
    setPendingAppId(null);
    setPendingAppCapId(null);
    setPendingBusinessCapId(null);
    setPendingTechCapId(null);
    setPendingAdoptionId(null);
    setPendingAgentId(null);
    setView(nextView);
  }

  const onSelectDesign = (id: string) => {
    setCurrentDesignId(id);
    setView(pendingView ?? "intake");
    setPendingView(null);
  };

  // Nav bar "Intake" click == "New Design": always resets to a blank Intake
  // form, even if a design is currently selected. Deliberately distinct from
  // onNavigate("intake") -- that generic path is also used by onSelectDesign
  // (Open a design -> populated Intake) and by the governance tabs'
  // onSelectDesign(id); onNavigate("intake") pattern, both of which must keep
  // landing on the *selected* design's data, not a blank one. This handler is
  // wired only to the nav bar's Intake button (see AppShell's onStartNewDesign
  // prop), so none of those other call sites are affected.
  const onStartNewDesign = () => {
    setCurrentDesignId(null);
    setPendingView(null);
    setView("intake");
  };

  const onGenerateDiagram = (seed: DiagramSeed) => {
    setPendingDiagramSeed(seed);
    setView("diagrams");
  };

  // ── URL hash <-> state (ADP-blp.53) ─────────────────────────────────────────
  // The state above stays the source of truth; the hash mirrors it. Every change of screen,
  // open entity or design becomes a history entry, and Back/Forward (or an edited URL) is
  // applied back onto the state.
  const route: AppRoute = useMemo(() => {
    let entity: AppRoute["entity"] = null;
    const pick = (kind: EntityKind, id: string | null) => (id ? { kind, id } : null);
    if (view === "business") entity = pick("business_capability", pendingBusinessCapId);
    else if (view === "applications") {
      entity = pick("application_capability", pendingAppCapId) ?? pick("application", pendingAppId);
    } else if (view === "technical") entity = pick("technical_capability", pendingTechCapId);
    else if (view === "agents") entity = pick("agent", pendingAgentId);
    else if (view === "patterns") entity = pick("adoption", pendingAdoptionId);
    const designScoped = view === "intake" || DESIGN_ONLY_VIEWS.includes(view);
    return { view, entity, designId: designScoped ? currentDesignId : null };
  }, [
    view, currentDesignId, pendingBusinessCapId, pendingAppCapId, pendingAppId, pendingTechCapId,
    pendingAgentId, pendingAdoptionId,
  ]);

  const firstSync = useRef(true);
  useEffect(() => {
    const hash = formatRoute(route);
    const first = firstSync.current;
    firstSync.current = false;
    // Already at this route: leave the URL alone. It may carry a page's own parameters
    // (?tab=...), which are not part of the route and must survive a reload (ADP-blp.68).
    const current = parseRoute(window.location.hash);
    if (current && formatRoute(current) === hash) return;
    // The first sync only fills in the address of the screen already showing.
    if (first) window.history.replaceState(null, "", hash);
    else window.history.pushState(null, "", hash);
  }, [route]);

  // ADP-blp.57: "Back to <screen>" in the top bar. Following a link to another screen used to
  // leave no way back except finding the original screen in the nav again. The trail holds the
  // routes visited in this session; stepping back to the previous one shortens it.
  const trail = useRef<string[]>([]);
  const [backView, setBackView] = useState<AppView | null>(null);
  useEffect(() => {
    const here = formatRoute(route);
    const visited = trail.current;
    if (visited[visited.length - 1] !== here) {
      if (visited.length >= 2 && visited[visited.length - 2] === here) visited.pop();
      else visited.push(here);
    }
    const previous = visited.length >= 2 ? parseRoute(visited[visited.length - 2]) : null;
    setBackView(previous && previous.view !== route.view ? previous.view : null);
  }, [route]);

  useEffect(() => {
    function applyLocation() {
      const next = parseRoute(window.location.hash);
      if (!next) return;
      const id = (kind: EntityKind) => (next.entity?.kind === kind ? next.entity.id : null);
      setPendingBusinessCapId(id("business_capability"));
      setPendingAppId(id("application"));
      setPendingAppCapId(id("application_capability"));
      setPendingTechCapId(id("technical_capability"));
      setPendingAgentId(id("agent"));
      setPendingAdoptionId(id("adoption"));
      if (next.designId) setCurrentDesignId(next.designId);
      setPendingView(null);
      setView(next.view);
    }
    window.addEventListener("popstate", applyLocation);
    window.addEventListener("hashchange", applyLocation);
    return () => {
      window.removeEventListener("popstate", applyLocation);
      window.removeEventListener("hashchange", applyLocation);
    };
  }, []);

  function renderPage(): React.ReactElement {
    // Global views — independent of design selection.
    switch (view) {
      case "overview":
        return <OverviewPage onNavigate={onNavigate} />;
      case "insights":
        return <InsightsPage />;
      case "portfolio":
        return <PortfolioPage />;
      case "governance":
        return <GovernancePage onNavigate={onNavigate} onSelectDesign={onSelectDesign} onOpenAdoption={openAdoption} />;
      case "business":
        return (
          <BusinessPage
            key={pendingBusinessCapId ?? "business"}
            onNavigate={onNavigate}
            designId={currentDesignId}
            onGenerateDiagram={onGenerateDiagram}
            initialFocusCapabilityId={pendingBusinessCapId}
          />
        );
      case "applications":
        return (
          <ApplicationPage
            key={pendingAppCapId ?? pendingAppId ?? "registry"}
            initialAppId={pendingAppId}
            initialAppCapId={pendingAppCapId}
          />
        );
      case "agents":
        return (
          <AgentsPage
            key={pendingAgentId ?? "agents"}
            initialAgentId={pendingAgentId}
            onOpenSolution={(appId) => {
              setPendingAppId(appId);
              setPendingAppCapId(null);
              setView("applications");
            }}
          />
        );
      case "technical":
        return <TechCapPage key={pendingTechCapId ?? "technical"} focusTechCapId={pendingTechCapId} />;
      case "diagrams":
        return (
          <DiagramsPage
            seed={pendingDiagramSeed}
            onSeedConsumed={() => setPendingDiagramSeed(null)}
          />
        );
      case "strategy":
        return <StrategyPage />;
      case "compliance":
        return <CompliancePage />;
      case "patterns":
        return (
          <PatternsPage
            key={pendingAdoptionId ?? "patterns"}
            onGenerateDiagram={onGenerateDiagram}
            initialAdoptionId={pendingAdoptionId}
          />
        );
      case "admin":
        return <AdminPage />;
      case "scoring-rubrics":
        return <ScoringRubricsPage />;
      case "knowledge":
        return <KnowledgePage onNavigate={onNavigate} designId={currentDesignId} />;
      case "intake":
        // Always reachable, design or no design -- see the DESIGN_ONLY_VIEWS
        // comment above.
        return (
          <IntakePage
            designId={currentDesignId}
            onNavigate={onNavigate}
            onDesignCreated={setCurrentDesignId}
          />
        );
      default:
        break;
    }

    // No design selected → always show the Designs screen.
    if (!currentDesignId || view === "designs") {
      return (
        <DesignsPage
          onSelectDesign={onSelectDesign}
          onNavigate={onNavigate}
          continueTo={pendingView ? DESIGN_ONLY_VIEW_LABELS[pendingView] : null}
        />
      );
    }

    // Design-scoped views.
    // ADP-914.13: C4DesignView is now the sole design-editing surface -- the legacy
    // Workspace/C4Canvas ("canvas") fallback it replaced is deleted. Every remaining
    // design-scoped view falls through to it (matches the pre-914.13 fallback shape,
    // which defaulted unmatched design-scoped views to Workspace).
    return <C4DesignView designId={currentDesignId} />;
  }

  return (
    <AppCapNavContext.Provider value={openAppCapability}>
      <CapabilityNavContext.Provider value={capabilityNav}>
        <AppShell
          currentView={view}
          onNavigate={onNavigate}
          designId={currentDesignId}
          onStartNewDesign={onStartNewDesign}
          onOpenSearchResult={onOpenSearchResult}
          topActions={<AskAiLauncher />}
          backView={backView}
          onBack={() => window.history.back()}
        >
          {/* ADP-blp.30: a page that fails must not take the nav down with it. */}
          <PageBoundary key={view}>{renderPage()}</PageBoundary>
        </AppShell>
      </CapabilityNavContext.Provider>
    </AppCapNavContext.Provider>
  );
}
