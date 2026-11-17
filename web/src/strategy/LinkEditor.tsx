/**
 * The link editor shared by an objective's capability, value stream, design and application
 * links (ADP-blp.36). Those four were separate files of about 135 lines each that differed only
 * in the noun: the same list of linked items with a Remove button, the same "Link a …" picker
 * that saves as soon as a value is chosen, the same 409 handling and the same confirmation.
 * Each is now a few lines that hands this component its options, linked ids and mutations.
 */
import React, { useState } from "react";
import NavLinkButton from "./NavLinkButton";
import { useLinkFeedback } from "./useLinkFeedback";
import { EntityLink } from "../shell/EntityLink";
import type { EntityKind } from "../shell/routing";

export interface LinkOption {
  id: string;
  label: string;
}

/** The kinds of linked thing that have a screen of their own to open (ADP-blp.57). */
type LinkedKind = Extract<EntityKind, "business_capability" | "application">;

type LinkError = Error & { status?: number };

interface LinkMutation {
  mutate: (
    id: string,
    options?: { onSuccess?: () => void; onError?: (error: LinkError) => void },
  ) => void;
  isPending: boolean;
}

interface LinkEditorProps {
  /** Everything that could be linked. */
  options: LinkOption[];
  linkedIds: readonly string[];
  isLoading?: boolean;
  /** "capability" */
  noun: string;
  /** "capabilities" */
  plural: string;
  /** The picker's prompt. Default: "Link a <noun>…" */
  prompt?: string;
  link: LinkMutation;
  unlink: LinkMutation;
  /** When set, each linked item's name is a link to that entity on its own screen. */
  entityKind?: LinkedKind;
  /** When set, each linked item's name is a button that opens it within the current screen. */
  onOpen?: (id: string) => void;
  /** Tooltip for that button, e.g. "Jump to this objective". */
  openTitle?: string;
}

const muted: React.CSSProperties = { fontSize: "0.85rem", color: "var(--ink-2)" };

export default function LinkEditor({
  options, linkedIds, isLoading, noun, plural, prompt, link, unlink, entityKind, onOpen, openTitle,
}: LinkEditorProps): React.ReactElement {
  const [selectedId, setSelectedId] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const feedback = useLinkFeedback();

  const linkedSet = new Set(linkedIds);
  const linked = options.filter((o) => linkedSet.has(o.id));
  const available = options.filter((o) => !linkedSet.has(o.id));

  function handleAdd(chosenId: string) {
    if (!chosenId) return;
    setSelectedId(chosenId);
    setLinkError(null);
    const label = available.find((o) => o.id === chosenId)?.label ?? chosenId;
    link.mutate(chosenId, {
      onSuccess: () => {
        setSelectedId("");
        feedback.showLinked(label);
      },
      onError: (err) => {
        setSelectedId("");
        setLinkError(err.status === 409 ? "Already linked" : err.message || `Failed to link ${noun}`);
      },
    });
  }

  if (isLoading) return <p style={muted}>Loading {plural}…</p>;

  return (
    <div style={{ marginTop: "0.75rem" }}>
      <div style={{ marginBottom: "0.5rem" }}>
        {linked.length === 0 && <p style={{ ...muted, margin: "0 0 0.5rem" }}>No {plural} linked yet.</p>}
        {linked.map((o) => (
          <div
            key={o.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.35rem 0",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <span style={{ flex: 1, fontSize: "0.85rem" }}>
              {onOpen ? (
                <NavLinkButton onClick={() => onOpen(o.id)} title={openTitle}>
                  {o.label}
                </NavLinkButton>
              ) : entityKind ? (
                <EntityLink kind={entityKind} id={o.id}>{o.label}</EntityLink>
              ) : (
                o.label
              )}
            </span>
            <button
              onClick={() => unlink.mutate(o.id, { onSuccess: () => feedback.showRemoved(o.label) })}
              disabled={unlink.isPending}
              style={{
                background: "none",
                border: "1px solid var(--border)",
                borderRadius: "4px",
                cursor: "pointer",
                padding: "2px 8px",
                fontSize: "0.75rem",
                color: "var(--ink-2)",
              }}
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <select
          value={selectedId}
          onChange={(e) => handleAdd(e.target.value)}
          disabled={link.isPending}
          aria-label={prompt ?? `Link a ${noun}`}
          style={{
            flex: 1,
            minWidth: "160px",
            padding: "0.3rem 0.5rem",
            fontSize: "0.85rem",
            border: "1px solid var(--border)",
            borderRadius: "4px",
            background: "var(--bg)",
            color: "var(--ink)",
          }}
        >
          <option value="">{prompt ?? `Link a ${noun}…`}</option>
          {available.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      {linkError && (
        <p style={{ color: "var(--crit)", fontSize: "0.8rem", margin: "0.35rem 0 0" }}>{linkError}</p>
      )}
      {feedback.message && (
        <p style={{ color: "var(--good)", fontSize: "0.8rem", margin: "0.35rem 0 0" }}>{feedback.message}</p>
      )}
    </div>
  );
}
