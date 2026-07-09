import React, { useState } from "react";
import { NavBar, type AppView } from "../shell";
import { usePortfolioTechnologies, usePortfolioDesigns } from "../api/portfolio";
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
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <NavBar currentView="portfolio" onNavigate={onNavigate} designId={null} />

      <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px", maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        {/* Summary header */}
        <PortfolioSummaryHeader onStatusSelect={handleStatusSelect} />

        {/* Filter bar */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
          <select
            value={activeStatus}
            onChange={(e) => setActiveStatus(e.target.value)}
            style={{
              padding: "6px 10px",
              borderRadius: 8,
              border: "1px solid #D1D5DB",
              fontSize: 14,
              color: "#374151",
            }}
            aria-label="Filter by lifecycle status"
          >
            {LIFECYCLE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>

          <button
            onClick={() => setSearchMode(!searchMode)}
            style={{
              padding: "6px 14px",
              borderRadius: 8,
              border: "1px solid #D1D5DB",
              backgroundColor: searchMode ? "#EDE9FE" : "#fff",
              color: searchMode ? "#5B21B6" : "#374151",
              fontSize: 14,
              cursor: "pointer",
              fontWeight: searchMode ? 600 : 400,
            }}
          >
            {searchMode ? "← Browse" : "Search"}
          </button>

          <button
            onClick={() => onNavigate("governance")}
            style={{
              marginLeft: "auto",
              padding: "6px 14px",
              borderRadius: 8,
              border: "1px solid #D1D5DB",
              backgroundColor: "#fff",
              color: "#374151",
              fontSize: 14,
              cursor: "pointer",
            }}
          >
            Governance Report
          </button>
        </div>

        {searchMode ? (
          /* Search mode */
          <DependencySearch onSelectDesign={handleSelectDesign} />
        ) : (
          /* Browse mode */
          <>
            {/* Technology landscape */}
            <div style={{ marginBottom: 20 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: "#374151", marginBottom: 10 }}>
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
              <h3 style={{ fontSize: 14, fontWeight: 600, color: "#374151", marginBottom: 10 }}>
                Designs
                {(activeTechnology || activeStatus) && (
                  <button
                    onClick={() => { setActiveTechnology(null); setActiveStatus(""); }}
                    style={{
                      marginLeft: 8,
                      fontSize: 12,
                      color: "#6B7280",
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
