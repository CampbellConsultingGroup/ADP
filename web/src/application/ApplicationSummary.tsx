/**
 * The scores for one application on a single screen (ADP-blp.59).
 *
 * An application's health, value, disposition, risk, cost and compliance were spread over fourteen
 * tabs, so answering "how is this application doing?" meant opening half of them. This sits at the
 * top of the Overview tab: one card per score, with the same colour meaning as everywhere else
 * (ui/tones.ts), and each card opens the tab that holds the detail.
 *
 * Risk, cost and compliance are restricted to some roles. A card whose data the caller may not
 * read says so instead of showing an error or an empty value.
 */
import React from "react";
import { useApplicationCost, useApplicationRisk, type Application } from "../api/application";
import { hasStatus } from "../api/client";
import { useApplicationComplianceMappings, type ComplianceStatus } from "../api/compliance";
import type { BadgeTone } from "../ui";
import { TIME_TONES } from "../ui/tones";

type Section = "risk" | "cost" | "compliance-mappings";

interface CardData {
  label: string;
  value: string;
  detail?: string;
  tone: BadgeTone;
  opens?: Section;
}

const TONE_COLOR: Record<BadgeTone, string> = {
  good: "var(--good)",
  warn: "var(--warn)",
  crit: "var(--crit)",
  info: "var(--accent)",
  neutral: "var(--border-strong)",
};

function scoreTone(score: number | null): BadgeTone {
  if (score === null) return "neutral";
  if (score >= 4) return "good";
  return score >= 3 ? "warn" : "crit";
}

const LIFECYCLE_TONE: Record<string, BadgeTone> = {
  planned: "info",
  active: "good",
  sunset: "warn",
  retired: "neutral",
};

const RESTRICTED: Pick<CardData, "value" | "detail" | "tone"> = {
  value: "Restricted",
  detail: "Not available to your role",
  tone: "neutral",
};
const LOADING: Pick<CardData, "value" | "tone"> = { value: "…", tone: "neutral" };
const UNAVAILABLE: Pick<CardData, "value" | "detail" | "tone"> = {
  value: "—",
  detail: "Could not be loaded",
  tone: "neutral",
};

function label(text: string): string {
  const spaced = text.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** Worst first: what the application's overall compliance comes down to. */
const COMPLIANCE_ORDER: ComplianceStatus[] = ["non_compliant", "partial", "not_assessed", "compliant", "not_applicable"];
const COMPLIANCE_TONE: Record<ComplianceStatus, BadgeTone> = {
  non_compliant: "crit",
  partial: "warn",
  not_assessed: "neutral",
  compliant: "good",
  not_applicable: "neutral",
};

function money(amount: string): string {
  const value = Number(amount);
  if (!Number.isFinite(value)) return amount;
  return value.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

interface Props {
  app: Application;
  onOpen: (section: Section) => void;
}

export default function ApplicationSummary({ app, onOpen }: Props): React.ReactElement {
  const risk = useApplicationRisk(app.id);
  const cost = useApplicationCost(app.id);
  const compliance = useApplicationComplianceMappings(app.id);

  const riskCard = (): Pick<CardData, "value" | "detail" | "tone"> => {
    if (risk.isLoading) return LOADING;
    if (risk.error) return hasStatus(risk.error, 403) ? RESTRICTED : UNAVAILABLE;
    const r = risk.data;
    if (!r || (!r.security_posture && !r.vulnerability_status)) {
      return { value: "Not assessed", tone: "neutral" };
    }
    const critical = r.vulnerability_status === "critical" || r.vulnerability_status === "open_high";
    const weak = r.security_posture === "weak";
    const tone: BadgeTone = critical || weak ? "crit" : r.security_posture === "strong" ? "good" : "warn";
    return {
      value: label(r.security_posture ?? "unknown"),
      detail: r.vulnerability_status ? `Vulnerabilities: ${label(r.vulnerability_status).toLowerCase()}` : undefined,
      tone,
    };
  };

  const costCard = (): Pick<CardData, "value" | "detail" | "tone"> => {
    if (cost.isLoading) return LOADING;
    if (cost.error) return hasStatus(cost.error, 403) ? RESTRICTED : UNAVAILABLE;
    if (!cost.data || Number(cost.data.tco) === 0) return { value: "Not recorded", tone: "neutral" };
    return { value: money(cost.data.tco), detail: "Total cost of ownership", tone: "info" };
  };

  const complianceCard = (): Pick<CardData, "value" | "detail" | "tone"> => {
    if (compliance.isLoading) return LOADING;
    if (compliance.error) return hasStatus(compliance.error, 403) ? RESTRICTED : UNAVAILABLE;
    const items = compliance.data?.items ?? [];
    if (items.length === 0) return { value: "None mapped", detail: "No controls mapped yet", tone: "neutral" };
    const worst = COMPLIANCE_ORDER.find((s) => items.some((m) => m.compliance_status === s))!;
    return {
      value: label(worst),
      detail: `${items.length} control${items.length === 1 ? "" : "s"} mapped`,
      tone: COMPLIANCE_TONE[worst],
    };
  };

  const cards: CardData[] = [
    {
      label: "Health",
      value: app.health_score === null ? "Not assessed" : `${app.health_score} / 5`,
      tone: scoreTone(app.health_score),
    },
    {
      label: "Business value",
      value: app.business_value === null ? "Not assessed" : `${app.business_value} / 5`,
      tone: scoreTone(app.business_value),
    },
    {
      label: "Disposition",
      value: app.time_classification ?? "Not classified",
      detail: app.r_strategy ?? undefined,
      tone: app.time_classification ? TIME_TONES[app.time_classification] : "neutral",
    },
    {
      label: "Lifecycle",
      value: label(app.lifecycle_status),
      tone: LIFECYCLE_TONE[app.lifecycle_status] ?? "neutral",
    },
    { label: "Risk", opens: "risk", ...riskCard() },
    { label: "Cost", opens: "cost", ...costCard() },
    { label: "Compliance", opens: "compliance-mappings", ...complianceCard() },
  ];

  return (
    <div className="ui-scorecards" aria-label="Application summary">
      {cards.map((card) => {
        const body = (
          <>
            <span className="lab">{card.label}</span>
            <span className="val">{card.value}</span>
            {card.detail && <span className="det">{card.detail}</span>}
          </>
        );
        const style = { borderTopColor: TONE_COLOR[card.tone] };
        return card.opens ? (
          <button
            key={card.label}
            type="button"
            className="ui-scorecard link"
            style={style}
            onClick={() => onOpen(card.opens!)}
            title={`Open ${card.label}`}
          >
            {body}
          </button>
        ) : (
          <div key={card.label} className="ui-scorecard" style={style}>
            {body}
          </div>
        );
      })}
    </div>
  );
}
