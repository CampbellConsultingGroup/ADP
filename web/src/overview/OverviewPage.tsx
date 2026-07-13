/**
 * Overview dashboard — the landing page for ADP.
 *
 * Surfaces live portfolio KPIs and breaks the practice into four architecture
 * domains (Business, Enterprise, Solution, Technical). Every capability tile
 * routes into the existing views via onNavigate. All figures are fetched live
 * from the API through the shared TanStack Query hooks.
 */
import React from "react";
import type { AppView } from "../shell";
import { useApplications, useTechCaps, useIntegrations } from "../api/application";
import { useCapabilities, useValueStreams, useDomains } from "../api/business";
import { usePortfolioSummary } from "../api/portfolio";
import { useKnowledgeItems } from "../api/knowledge";
import "./overview.css";

interface OverviewPageProps {
  onNavigate: (view: AppView) => void;
}

// ── Inline icon set ───────────────────────────────────────────────────────────
const ICONS: Record<string, React.ReactNode> = {
  layers: <><polygon points="12,3 21,8 12,13 3,8" /><path d="M3 12l9 5 9-5M3 16l9 5 9-5" /></>,
  biz: <><path d="M4 20V9l8-5 8 5v11" /><path d="M9 20v-5h6v5" /><path d="M4 12h16" /></>,
  ent: <><rect x="3" y="4" width="6" height="6" rx="1" /><rect x="15" y="4" width="6" height="6" rx="1" /><rect x="9" y="14" width="6" height="6" rx="1" /><path d="M6 10v2h12v-2M12 12v2" /></>,
  sol: <><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" /><path d="M12 3v9l8 4.5M12 12L4 16.5" /></>,
  tec: <><path d="M6 8l-3 4 3 4M18 8l3 4-3 4M14 5l-4 14" /></>,
  stream: <><path d="M3 7h11l4 5-4 5H3" /><path d="M3 12h9" /></>,
  link: <><path d="M9 12h6" /><path d="M10 8H8a4 4 0 000 8h2M14 8h2a4 4 0 010 8h-2" /></>,
  grid: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
  plug: <><path d="M9 3v6M15 3v6M6 9h12v3a6 6 0 01-12 0zM12 18v3" /></>,
  chart: <><path d="M4 20V4M4 20h16" /><rect x="7" y="12" width="3" height="5" /><rect x="12" y="8" width="3" height="9" /><rect x="17" y="5" width="3" height="12" /></>,
  shield: <><path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" /><path d="M9.5 12l2 2 3.5-4" /></>,
  book: <><path d="M4 5a2 2 0 012-2h12v16H6a2 2 0 00-2 2z" /><path d="M4 19a2 2 0 012-2h12" /></>,
  tags: <><path d="M4 4h8l8 8-8 8-8-8z" /><circle cx="8.5" cy="8.5" r="1.4" /></>,
  image: <><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9.5" r="1.6" /><path d="M4 17l5-5 4 4 3-3 4 4" /></>,
  inbox: <><path d="M4 13l2-8h12l2 8v6H4z" /><path d="M4 13h5l1 2h4l1-2h5" /></>,
  spark: <><path d="M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" /></>,
  check: <><path d="M4 12l5 5L20 6" /><circle cx="12" cy="12" r="9" opacity=".35" /></>,
  cycle: <><path d="M4 12a8 8 0 0113-6l3 2M20 12a8 8 0 01-13 6l-3-2" /><path d="M20 4v4h-4M4 20v-4h4" /></>,
  doc: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4M9 12h6M9 16h6" /></>,
  go: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
};

function Icon({ name }: { name: string }): React.ReactElement {
  return (
    <svg className="ic" viewBox="0 0 24 24" aria-hidden="true">
      {ICONS[name]}
    </svg>
  );
}

const num = (v: number | undefined, fallback = "—"): string =>
  v === undefined || Number.isNaN(v) ? fallback : String(v);

interface DomainTile {
  name: string;
  icon: string;
  metric?: string;
  view: AppView;
}

interface Domain {
  key: string;
  eyebrow: string;
  title: string;
  desc: string;
  icon: string;
  hue: string;
  wash: string;
  metrics: { n: string; l: string }[];
  tiles: DomainTile[];
}

export default function OverviewPage({ onNavigate }: OverviewPageProps): React.ReactElement {
  const apps = useApplications();
  const caps = useCapabilities();
  const streams = useValueStreams();
  const domains = useDomains();
  const techCaps = useTechCaps();
  const knowledge = useKnowledgeItems();
  const integrations = useIntegrations();
  const summary = usePortfolioSummary();

  const appItems = apps.data?.items ?? [];
  const appCount = apps.data?.total ?? appItems.length;
  const healths = appItems.map((a) => a.health_score).filter((h): h is number => h != null);
  const avgHealth = healths.length ? (healths.reduce((s, h) => s + h, 0) / healths.length).toFixed(1) : "—";
  const healthDist = [5, 4, 3, 2, 1].map((score) => appItems.filter((a) => a.health_score === score).length);
  const maxHealth = Math.max(1, ...healthDist);
  const timeOf = (t: string) => appItems.filter((a) => a.time_classification === t).length;
  const atRisk = appItems.filter((a) => a.health_score === 1 || a.time_classification === "Eliminate").length;

  const byStatus = summary.data?.by_status ?? {};
  const designCount = summary.data?.total_designs;
  const lc = {
    current: byStatus["current"] ?? 0,
    proposed: byStatus["proposed"] ?? 0,
    draft: byStatus["draft"] ?? 0,
  };
  const lcTotal = Math.max(1, lc.current + lc.proposed + lc.draft);

  const capCount = caps.data?.total;
  const vsCount = streams.data?.total;
  const domainCount = domains.data?.total;
  const techCount = techCaps.data?.total;
  const knowledgeCount = knowledge.data?.total;
  const integrationCount = integrations.data?.total;

  const anyError = [apps, caps, streams, domains, techCaps, knowledge, integrations, summary].some((q) => q.isError);

  const DOMAINS: Domain[] = [
    {
      key: "business", eyebrow: "Business Architecture", title: "What the business does",
      desc: "Capabilities, value streams, and domains — the outcome view.",
      icon: "biz", hue: "var(--biz)", wash: "var(--biz-wash)",
      metrics: [
        { n: num(capCount), l: "Capabilities" },
        { n: num(domainCount), l: "Domains" },
        { n: num(vsCount), l: "Value streams" },
      ],
      tiles: [
        { name: "Capability Map", icon: "grid", metric: `${num(capCount)} capabilities`, view: "business" },
        { name: "Value Streams", icon: "stream", metric: `${num(vsCount)} streams`, view: "business" },
        { name: "Business Domains", icon: "biz", metric: `${num(domainCount)} domains`, view: "business" },
        { name: "Traceability", icon: "link", metric: "capability → design", view: "business" },
      ],
    },
    {
      key: "enterprise", eyebrow: "Enterprise Architecture", title: "The application landscape",
      desc: "Portfolio, integrations, and disposition across the estate.",
      icon: "ent", hue: "var(--ent)", wash: "var(--ent-wash)",
      metrics: [
        { n: num(appCount), l: "Applications" },
        { n: num(integrationCount), l: "Integrations" },
        { n: num(techCount), l: "Tech capabilities" },
      ],
      tiles: [
        { name: "Application Portfolio", icon: "layers", metric: `${num(appCount)} apps`, view: "applications" },
        { name: "Landscape & Integrations", icon: "plug", metric: `${num(integrationCount)} flows`, view: "applications" },
        { name: "Portfolio Analysis", icon: "chart", metric: "TIME · 7R", view: "portfolio" },
        { name: "Governance & Standards", icon: "shield", metric: `${atRisk} at risk`, view: "governance" },
      ],
    },
    {
      key: "solution", eyebrow: "Solution Architecture", title: "Designs in flight",
      desc: "C4 models, AI-assisted intake, recommendations, and reviews.",
      icon: "sol", hue: "var(--sol)", wash: "var(--sol-wash)",
      metrics: [
        { n: num(designCount), l: "Designs" },
        { n: num(lc.current), l: "Current" },
        { n: num(lc.proposed), l: "Proposed" },
      ],
      tiles: [
        { name: "C4 Design Workspace", icon: "sol", metric: `${num(designCount)} designs`, view: "designs" },
        { name: "Requirements Intake", icon: "inbox", metric: "AI-assisted", view: "designs" },
        { name: "Recommendations", icon: "spark", metric: "AI options", view: "designs" },
        { name: "Design Reviews", icon: "check", metric: "LLM-as-Judge", view: "designs" },
      ],
    },
    {
      key: "technical", eyebrow: "Technical Architecture", title: "The technology foundation",
      desc: "Technical capabilities, standards, patterns, and knowledge.",
      icon: "tec", hue: "var(--tec)", wash: "var(--tec-wash)",
      metrics: [
        { n: num(techCount), l: "Tech capabilities" },
        { n: num(knowledgeCount), l: "Knowledge items" },
        { n: "C4", l: "Locked theme" },
      ],
      tiles: [
        { name: "Technical Capability Map", icon: "tec", metric: `${num(techCount)} capabilities`, view: "applications" },
        { name: "Standards & Tags", icon: "tags", metric: "technology tags", view: "portfolio" },
        { name: "Knowledge Base", icon: "book", metric: `${num(knowledgeCount)} items`, view: "knowledge" },
        { name: "Rendering & Export", icon: "image", metric: "locked C4 theme", view: "designs" },
      ],
    },
  ];

  // Donut arc math (circumference on r=15.9 ≈ 100).
  const seg = (count: number) => (count / lcTotal) * 100;
  const currentLen = seg(lc.current);
  const proposedLen = seg(lc.proposed);
  const draftLen = seg(lc.draft);

  return (
    <div className="ovw-root">
      <div className="ovw-content">
          <header className="ovw-head">
            <div className="ovw-eyebrow"><span className="sw" /> Portfolio overview</div>
            <h1 className="ovw-h1">Architecture at a glance</h1>
            <p className="ovw-lede">
              One live view across the practice — business capabilities, the application landscape,
              in-flight designs, and the technology foundation. Jump into any of the four architecture
              domains below.
            </p>
            {anyError && (
              <p className="ovw-err">Some metrics failed to load — is the API running? Showing what's available.</p>
            )}
          </header>

          {/* KPI hero */}
          <div className="ovw-kpis">
            <div className="ovw-kpi">
              <div className="lab"><Icon name="layers" /> Applications</div>
              <div className="val">{num(appCount)}</div>
              <div className="delta"><span className="ovw-up">avg health {avgHealth}/5</span></div>
            </div>
            <div className="ovw-kpi">
              <div className="lab"><Icon name="sol" /> Designs</div>
              <div className="val">{num(designCount)}</div>
              <div className="delta">{lc.current} current · {lc.proposed} proposed</div>
            </div>
            <div className="ovw-kpi">
              <div className="lab"><Icon name="biz" /> Capabilities</div>
              <div className="val">{num(capCount)}</div>
              <div className="delta">across {num(domainCount)} domains</div>
            </div>
            <div className="ovw-kpi">
              <div className="lab"><Icon name="stream" /> Value streams</div>
              <div className="val">{num(vsCount)}</div>
              <div className="delta">business flows</div>
            </div>
            <div className="ovw-kpi">
              <div className="lab"><Icon name="book" /> Knowledge</div>
              <div className="val">{num(knowledgeCount)}</div>
              <div className="delta">patterns &amp; principles</div>
            </div>
            <div className={`ovw-kpi${atRisk > 0 ? " alert" : ""}`}>
              <div className="lab"><Icon name="shield" /> At risk</div>
              <div className="val">{num(atRisk)}</div>
              <div className="delta"><span className="ovw-down">Eliminate · health 1</span></div>
            </div>
          </div>

          {/* Visual band */}
          <div className="ovw-band">
            <div className="ovw-panel">
              <h3><Icon name="layers" /> Application health</h3>
              <div className="cap">Distribution of {num(appCount)} apps by health score</div>
              {[5, 4, 3, 2, 1].map((score, i) => {
                const n = healthDist[i];
                const color = score >= 4 ? "var(--good)" : score >= 3 ? "var(--warn)" : "var(--crit)";
                return (
                  <div className="ovw-hbar" key={score}>
                    <span className="tag">★ {score}</span>
                    <div className="track"><div className="fill" style={{ width: `${(n / maxHealth) * 100}%`, background: color }} /></div>
                    <span className="n">{n}</span>
                  </div>
                );
              })}
            </div>

            <div className="ovw-panel">
              <h3><Icon name="chart" /> TIME disposition</h3>
              <div className="cap">Tolerate · Invest · Migrate · Eliminate</div>
              <div className="ovw-quad">
                <div className="ovw-qcell invest"><div className="qn">{timeOf("Invest")}</div><div className="ql">Invest</div></div>
                <div className="ovw-qcell tolerate"><div className="qn">{timeOf("Tolerate")}</div><div className="ql">Tolerate</div></div>
                <div className="ovw-qcell migrate"><div className="qn">{timeOf("Migrate")}</div><div className="ql">Migrate</div></div>
                <div className="ovw-qcell eliminate"><div className="qn">{timeOf("Eliminate")}</div><div className="ql">Eliminate</div></div>
              </div>
            </div>

            <div className="ovw-panel">
              <h3><Icon name="cycle" /> Design lifecycle</h3>
              <div className="cap">{num(designCount)} designs by lifecycle state</div>
              <div className="ovw-donut-wrap">
                <svg width="104" height="104" viewBox="0 0 42 42" style={{ flexShrink: 0 }}>
                  <circle cx="21" cy="21" r="15.9" fill="none" stroke="var(--surface-3)" strokeWidth="7" />
                  <circle cx="21" cy="21" r="15.9" fill="none" stroke="var(--good)" strokeWidth="7"
                    strokeDasharray={`${currentLen} ${100 - currentLen}`} strokeDashoffset="25" transform="rotate(-90 21 21)" />
                  <circle cx="21" cy="21" r="15.9" fill="none" stroke="var(--accent)" strokeWidth="7"
                    strokeDasharray={`${proposedLen} ${100 - proposedLen}`} strokeDashoffset={`${25 - currentLen}`} transform="rotate(-90 21 21)" />
                  <circle cx="21" cy="21" r="15.9" fill="none" stroke="var(--ink-3)" strokeWidth="7"
                    strokeDasharray={`${draftLen} ${100 - draftLen}`} strokeDashoffset={`${25 - currentLen - proposedLen}`} transform="rotate(-90 21 21)" />
                  <text x="21" y="20.5" textAnchor="middle" fontSize="9" fontWeight="700" fill="var(--ink)" fontFamily="ui-monospace,monospace">{num(designCount)}</text>
                  <text x="21" y="27" textAnchor="middle" fontSize="3.4" fill="var(--ink-3)" fontFamily="ui-monospace,monospace">DESIGNS</text>
                </svg>
                <div className="ovw-legend">
                  <div className="li"><span className="sw" style={{ background: "var(--good)" }} /> Current <b>{lc.current}</b></div>
                  <div className="li"><span className="sw" style={{ background: "var(--accent)" }} /> Proposed <b>{lc.proposed}</b></div>
                  <div className="li"><span className="sw" style={{ background: "var(--ink-3)" }} /> Draft <b>{lc.draft}</b></div>
                </div>
              </div>
            </div>
          </div>

          {/* Domain cards */}
          <div className="ovw-sec-title"><h2>Architecture domains</h2><span className="rule" /></div>
          <div className="ovw-domains">
            {DOMAINS.map((d) => (
              <div className="ovw-dcard" key={d.key} style={{ ["--dc" as string]: d.hue, ["--dc-wash" as string]: d.wash }}>
                <div className="ovw-dc-head">
                  <div className="ovw-chip"><Icon name={d.icon} /></div>
                  <div>
                    <div className="ovw-d-eye">{d.eyebrow}</div>
                    <h3>{d.title}</h3>
                    <p className="ovw-d-desc">{d.desc}</p>
                  </div>
                </div>
                <div className="ovw-metric-row">
                  {d.metrics.map((m) => (
                    <div className="ovw-metric" key={m.l}><div className="m-n">{m.n}</div><div className="m-l">{m.l}</div></div>
                  ))}
                </div>
                <div className="ovw-tiles">
                  {d.tiles.map((t) => (
                    <button className="ovw-tile" key={t.name} onClick={() => onNavigate(t.view)}
                      title={`Open ${t.name}`}>
                      <span className="t-ic"><Icon name={t.icon} /></span>
                      <span>
                        <span className="t-name">{t.name}</span>
                        {t.metric && <span className="t-metric" style={{ display: "block" }}>{t.metric}</span>}
                      </span>
                      <span className="t-go"><Icon name="go" /></span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

        <div className="ovw-foot">ADP · Architecture Design Platform — live portfolio overview</div>
      </div>
    </div>
  );
}
