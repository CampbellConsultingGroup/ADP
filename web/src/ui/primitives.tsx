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

/**
 * `compact` is for full-height list/detail screens (the registries), where a large header would
 * push the working area down: a smaller title on one line (ADP-blp.66).
 */
export function PageHeader({ eyebrow, eyebrowColor, title, lede, compact }: {
  eyebrow?: string; eyebrowColor?: string; title: React.ReactNode; lede?: React.ReactNode;
  compact?: boolean;
}): React.ReactElement {
  return (
    <header className={`ui-pagehead${compact ? " compact" : ""}`}>
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

/**
 * Shared feedback and form pieces (ADP-blp.46). Screens wrote these by hand: 38 separate
 * "Loading…" lines in six styles, error text in a dozen, and labels that were not tied to their
 * control. Use these in new and changed screens.
 */

/** "Loading…", announced politely. `pad` adds space around it for a panel-sized placeholder. */
export function Loading({ label = "Loading…", pad }: { label?: string; pad?: number }): React.ReactElement {
  return (
    <div className="ui-loading" role="status" style={pad ? { padding: pad } : undefined}>
      {label}
    </div>
  );
}

/** A boxed message. `crit` and `warn` are announced as alerts; the others as status. */
export function Alert({ tone = "info", children }: { tone?: "crit" | "warn" | "good" | "info"; children: React.ReactNode }): React.ReactElement {
  return (
    <div className={`ui-alert ${tone}`} role={tone === "crit" || tone === "warn" ? "alert" : "status"}>
      {children}
    </div>
  );
}

/**
 * Shown in place of content the signed-in user's role may not read (ADP-blp.65), so every
 * gated tab says the same thing in the same way. `what` names the content, e.g. "cost data".
 */
export function Restricted({ what }: { what: string }): React.ReactElement {
  return (
    <div className="ui-alert info" role="status">
      <strong>Restricted to your role.</strong> You don't have permission to view {what}. Ask an
      administrator if you need access.
    </div>
  );
}

/**
 * A labelled form control. The label, hint and error are tied to the control (htmlFor,
 * aria-describedby, aria-invalid), which a bare <label> next to an <input> is not.
 * `children` receives the props to spread onto the control.
 */
export function Field({ label, required, hint, error, children }: {
  label: string; required?: boolean; hint?: React.ReactNode; error?: React.ReactNode;
  children: (control: { id: string; "aria-describedby"?: string; "aria-invalid"?: boolean; "aria-required"?: boolean }) => React.ReactNode;
}): React.ReactElement {
  const id = React.useId();
  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(" ");
  return (
    <div className="ui-field">
      <label className="ui-label" htmlFor={id}>
        {label}
        {required && <span className="req" aria-hidden="true"> *</span>}
      </label>
      {children({
        id,
        "aria-describedby": describedBy || undefined,
        "aria-invalid": error ? true : undefined,
        // aria-required, not the native attribute: forms here validate themselves and show
        // their own message, which the browser's built-in "fill in this field" bubble would pre-empt.
        "aria-required": required || undefined,
      })}
      {hint && <div className="ui-hint" id={`${id}-hint`}>{hint}</div>}
      {error && <div className="ui-field-error" id={`${id}-error`} role="alert">{error}</div>}
    </div>
  );
}

/**
 * A data table with the shared header and cell style (ADP-blp.46). `columns` are the header
 * labels; the children are ordinary <tr>/<td> rows. Scrolls sideways on its own when it is wider
 * than its container. `caption` names the table for assistive technology.
 */
export function Table({ columns, caption, dense, children }: {
  columns: ReadonlyArray<string>; caption?: string; dense?: boolean; children: React.ReactNode;
}): React.ReactElement {
  return (
    <div className="ui-table-wrap">
      <table className={`ui-table${dense ? " dense" : ""}`} aria-label={caption}>
        <thead>
          <tr>{columns.map((c) => <th key={c} scope="col">{c}</th>)}</tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
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
