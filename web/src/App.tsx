import React, { lazy, useEffect, useRef, useState } from "react";
import OverviewPage from "./overview/OverviewPage";
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
import { ROUTE_EVENT, entityHref, formatRoute, parseRoute, type AppRoute, type EntityKind } from "./shell/routing";
import DesignFlowSteps from "./designs/DesignFlowSteps";

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
// The screens that show the design-flow steps. (Designs itself is the list, so it has none.)
const DESIGN_FLOW_VIEWS: AppView[] = ["intake", "canvas-v2"];
const DESIGN_ONLY_VIEW_LABELS: Record<string, string> = {
  "canvas-v2": "C4 Design",
};

// Search hit types that have an address of their own.
const SEARCH_ENTITY_KINDS: Record<string, EntityKind> = {
  business_capability: "business_capability",
  application: "application",
  application_capability: "application_capability",
  technical_capability: "technical_capability",
  agent: "agent",
};

// ADP-SPEC-025: Multi-design support.
// currentDesignId is null until the user selects or creates a design.
// Initial view is "overview" (the landing dashboard). All views render inside
// the shared AppShell (left-rail nav + top bar).
export default function App(): React.ReactElement {
  // ADP-blp.53: the starting location comes from the URL hash, so a reload or a pasted link
  // opens the same screen (and entity, and design) instead of always landing on Overview.
  const [initialRoute] = useState<AppRoute | null>(() => parseRoute(window.location.hash));
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
  // ADP-blp.56: a global search result opens on the screen that owns that kind of entity.
  // Kinds with no single-entity address yet open their screen.
  const onOpenSearchResult = (hit: SearchHit) => {
    const kind = SEARCH_ENTITY_KINDS[hit.entity_type];
    if (kind) window.location.hash = entityHref(kind, hit.entity_id);
    else onNavigate("business"); // value streams, stages, value chains, domains, org units
  };

  function onNavigate(nextView: AppView) {
    if (!currentDesignId && DESIGN_ONLY_VIEWS.includes(nextView)) {
      setPendingView(nextView);
      setView("designs");
      return;
    }
    if (nextView === view && parseRoute(window.location.hash)?.entity) {
      // The nav item of the screen already showing: close the open entity (ADP-blp.68).
      window.history.pushState(null, "", formatRoute({ view, entity: null, designId: null }));
      window.dispatchEvent(new Event(ROUTE_EVENT));
      return;
    }
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
  // The screen and the design are state here and mirrored into the hash; Back/Forward (or an
  // edited URL) is applied back onto the state. The open entity is not held here: each page
  // reads it from the hash itself (useRouteEntity, ADP-blp.68), so selecting something inside a
  // page is a history entry and does not remount the page.
  const designScoped = view === "intake" || DESIGN_ONLY_VIEWS.includes(view);
  const routeDesignId = designScoped ? currentDesignId : null;

  // ADP-blp.57: "Back to <screen>" in the top bar. The trail holds the places visited in this
  // session; returning to one of them (the browser's Back, or this control) shortens it.
  const trail = useRef<string[]>([]);
  const [back, setBack] = useState<{ view: AppView; hash: string } | null>(null);
  const noteLocation = useRef(() => {});
  noteLocation.current = () => {
    const here = parseRoute(window.location.hash);
    if (!here) return;
    const key = formatRoute(here);
    const visited = trail.current;
    const seen = visited.lastIndexOf(key);
    if (seen >= 0) visited.length = seen + 1;
    else visited.push(key);
    // The previous *screen*: selections made on this screen are not somewhere to go back to.
    let previous: { view: AppView; hash: string } | null = null;
    for (let i = visited.length - 2; i >= 0 && !previous; i--) {
      const route = parseRoute(visited[i]);
      if (route && route.view !== here.view) previous = { view: route.view, hash: visited[i] };
    }
    setBack(previous);
  };

  const firstSync = useRef(true);
  useEffect(() => {
    const first = firstSync.current;
    firstSync.current = false;
    // Already on this screen and design: leave the URL alone. It may carry the open entity and
    // a page's own parameters (?tab=...), which must survive a reload.
    const current = parseRoute(window.location.hash);
    if (!current || current.view !== view || current.designId !== routeDesignId) {
      const hash = formatRoute({ view, entity: null, designId: routeDesignId });
      // The first sync only fills in the address of the screen already showing.
      if (first) window.history.replaceState(null, "", hash);
      else window.history.pushState(null, "", hash);
    }
    noteLocation.current();
  }, [view, routeDesignId]);

  useEffect(() => {
    function applyLocation() {
      const next = parseRoute(window.location.hash);
      if (!next) return;
      if (next.designId) setCurrentDesignId(next.designId);
      setPendingView(null);
      setView(next.view);
      noteLocation.current();
    }
    const onRoute = () => noteLocation.current();
    window.addEventListener("popstate", applyLocation);
    window.addEventListener("hashchange", applyLocation);
    window.addEventListener(ROUTE_EVENT, onRoute);
    return () => {
      window.removeEventListener("popstate", applyLocation);
      window.removeEventListener("hashchange", applyLocation);
      window.removeEventListener(ROUTE_EVENT, onRoute);
    };
  }, []);

  const onBack = () => {
    if (back) window.location.hash = back.hash;
  };

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
        return <GovernancePage onNavigate={onNavigate} onSelectDesign={onSelectDesign} />;
      case "business":
        return (
          <BusinessPage
            onNavigate={onNavigate}
            designId={currentDesignId}
            onGenerateDiagram={onGenerateDiagram}
          />
        );
      case "applications":
        return <ApplicationPage />;
      case "agents":
        return <AgentsPage />;
      case "technical":
        return <TechCapPage />;
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
        return <PatternsPage onGenerateDiagram={onGenerateDiagram} />;
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
    <AppShell
      currentView={view}
      onNavigate={onNavigate}
      designId={currentDesignId}
      onStartNewDesign={onStartNewDesign}
      onOpenSearchResult={onOpenSearchResult}
      topActions={<AskAiLauncher />}
      backView={back?.view ?? null}
      onBack={onBack}
    >
      {/* ADP-blp.30: a page that fails must not take the nav down with it. */}
      <PageBoundary key={view}>
        {DESIGN_FLOW_VIEWS.includes(view) && (currentDesignId || view === "intake") ? (
          // ADP-blp.59: the steps of creating a design, above the screens that make it up.
          <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
            <DesignFlowSteps view={view} designId={currentDesignId} />
            <div style={{ flex: 1, minHeight: 0 }}>{renderPage()}</div>
          </div>
        ) : (
          renderPage()
        )}
      </PageBoundary>
    </AppShell>
  );
}
