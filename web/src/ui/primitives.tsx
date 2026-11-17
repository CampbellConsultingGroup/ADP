/** Shared UI primitives built on the tokens + ui.css classes. */
import React from "react";
import { Icon } from "./Icon";

export function Card({ className = "", style, children }: { className?: string; style?: React.CSSProperties; children: React.ReactNode }): React.ReactElement {
  return <div className={`ui-card ${className}`} style={style}>{children}</div>;
}

export function Panel({ title, icon, caption, className = "", style, children }: {
  title?: React.ReactNode; icon?: string; caption?: React.ReactNode; className?: string; style?: React.CSSProperties; children: React.ReactNode;
}): React.ReactElement {
  return (
    <div className={`ui-panel ${className}`} style={style}>
      {title && <h3 className="ui-panel-h">{icon && <Icon name={icon} size={16} />}{title}</h3>}
      {caption && <div className="ui-panel-cap">{caption}</div>}
      {children}
    </div>
  );
}

type BtnVariant = "default" | "primary" | "ghost" | "danger";
export function Button({ variant = "default", size, icon, className = "", children, ...rest }: {
  variant?: BtnVariant; size?: "sm"; icon?: string; className?: string; children?: React.ReactNode;
} & React.ButtonHTMLAttributes<HTMLButtonElement>): React.ReactElement {
  const v = variant === "default" ? "" : ` ui-btn-${variant}`;
  const s = size === "sm" ? " ui-btn-sm" : "";
  return (
    <button className={`ui-btn${v}${s} ${className}`} {...rest}>
      {icon && <Icon name={icon} size={16} />}{children}
    </button>
  );
}

export type BadgeTone = "good" | "warn" | "crit" | "info" | "neutral";
export function StatusBadge({ tone = "neutral", children }: { tone?: BadgeTone; children: React.ReactNode }): React.ReactElement {
  return <span className={`ui-badge ${tone}`}><span className="b-dot" />{children}</span>;
}

export function PageHeader({ eyebrow, eyebrowColor, title, lede }: {
  eyebrow?: string; eyebrowColor?: string; title: React.ReactNode; lede?: React.ReactNode;
}): React.ReactElement {
  return (
    <header className="ui-pagehead">
      {eyebrow && <div className="ui-eyebrow"><span className="sw" style={eyebrowColor ? { background: eyebrowColor } : undefined} />{eyebrow}</div>}
      <h1 className="ui-h1">{title}</h1>
      {lede && <p className="ui-lede">{lede}</p>}
    </header>
  );
}

/**
 * What to show when a list has nothing in it (ADP-blp.61): what belongs here and why it matters,
 * then the next step. Most lists showed one grey line ("No themes yet.") that explained neither.
 * `children` is the next-step sentence; `action` is an optional button.
 */
export function EmptyState({ icon, title, why, children, action, compact }: {
  icon?: string; title: string; why?: React.ReactNode; children?: React.ReactNode;
  action?: React.ReactNode; compact?: boolean;
}): React.ReactElement {
  return (
    <div className={`ui-empty${compact ? " compact" : ""}`}>
      {icon && <div className="em-ic"><Icon name={icon} size={compact ? 26 : 40} style={{ margin: "0 auto" }} /></div>}
      <h2>{title}</h2>
      {why && <p className="em-why">{why}</p>}
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export function KpiTile({ label, icon, value, delta, alert }: {
  label: React.ReactNode; icon?: string; value: React.ReactNode; delta?: React.ReactNode; alert?: boolean;
}): React.ReactElement {
  return (
    <div className={`ui-kpi${alert ? " alert" : ""}`}>
      <div className="lab">{icon && <Icon name={icon} size={15} />}{label}</div>
      <div className="val">{value}</div>
      {delta && <div className="delta">{delta}</div>}
    </div>
  );
}
