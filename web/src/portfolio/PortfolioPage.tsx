import React, { useState } from "react";
import type { AppView } from "../shell";
import { usePortfolioTechnologies, usePortfolioDesigns } from "../api/portfolio";
import { Button } from "../ui";
import TechnologyLandscape from "./TechnologyLandscape";
import PortfolioDesignList from "./PortfolioDesignList";
import DependencySearch from "./DependencySearch";
import PortfolioSummaryHeader from "./PortfolioSummaryHeader";

interface PortfolioPageProps {
  onNavigate: (view: AppView) => void;
  onSelectDesign: (id: string) => void;
}

const LIFECYCLE_OPTIONS = [
  { value: "", label: "All Statuses" },
  { value: "draft", label: "Draft" },
  { value: "proposed", label: "Proposed" },
  { value: "current", label: "Current" },
  { value: "deprecated", label: "Deprecated" },
  { value: "decommissioned", label: "Decommissioned" },
];

export default function PortfolioPage({
  onNavigate,
  onSelectDesign,
}: PortfolioPageProps): React.ReactElement {
  const [activeTechnology, setActiveTechnology] = useState<string | null>(null);
  const [activeStatus, setActiveStatus] = useState<string>("");
  const [searchMode, setSearchMode] = useState(false);

  const techQuery = usePortfolioTechnologies();
  const designsQuery = usePortfolioDesigns(
    activeTechnology ?? undefined,
    activeStatus || undefined,
  );

  const handleSelectDesign = (id: string) => {
    onSelectDesign(id);
    onNavigate("intake");
  };

  const handleStatusSelect = (status: string | null) => {
    setActiveStatus(status ?? "");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>

      <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px", maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        {/* Summary header */}
        <PortfolioSummaryHeader onStatusSelect={handleStatusSelect} />

        {/* Filter bar */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <select
            className="ui-select"
            value={activeStatus}
            onChange={(e) => setActiveStatus(e.target.value)}
            aria-label="Filter by lifecycle status"
          >
            {LIFECYCLE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          <Button
            variant={searchMode ? "primary" : "default"}
            icon={searchMode ? undefined : "search"}
            onClick={() => setSearchMode(!searchMode)}
          >
            {searchMode ? "← Browse" : "Search"}
          </Button>

          <Button icon="shield" style={{ marginLeft: "auto" }} onClick={() => onNavigate("governance")}>
            Governance Report
          </Button>
        </div>

        {searchMode ? (
          /* Search mode */
          <DependencySearch onSelectDesign={handleSelectDesign} />
        ) : (
          /* Browse mode */
          <>
            {/* Technology landscape */}
            <div style={{ marginBottom: 20 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)", marginBottom: 10 }}>
                Technologies
              </h3>
              <TechnologyLandscape
                technologies={techQuery.data?.technologies ?? []}
                activeTechnology={activeTechnology}
                onSelect={setActiveTechnology}
                isLoading={techQuery.isLoading}
              />
            </div>

            {/* Design list */}
            <div>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)", marginBottom: 10 }}>
                Designs
                {(activeTechnology || activeStatus) && (
                  <button
                    onClick={() => { setActiveTechnology(null); setActiveStatus(""); }}
                    style={{
                      marginLeft: 8,
                      fontSize: 12,
                      color: "var(--ink-3)",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      textDecoration: "underline",
                    }}
                  >
                    Clear filters
                  </button>
                )}
              </h3>
              <PortfolioDesignList
                designs={designsQuery.data?.designs ?? []}
                isLoading={designsQuery.isLoading}
                onSelectDesign={handleSelectDesign}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
