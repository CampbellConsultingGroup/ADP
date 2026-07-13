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
