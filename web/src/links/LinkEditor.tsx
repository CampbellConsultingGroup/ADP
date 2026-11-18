/**
 * The link editor shared across screens: an objective's capability, value stream, design,
 * application and initiative links, and a capability's or value stream's design links
 * (ADP-blp.36). Those four were separate files of about 135 lines each that differed only
 * in the noun: the same list of linked items with a Remove button, the same "Link a …" picker
 * that saves as soon as a value is chosen, the same 409 handling and the same confirmation.
 * Each is now a few lines that hands this component its options, linked ids and mutations.
 */
import React, { useState } from "react";
import NavLinkButton from "./NavLinkButton";
import { useLinkFeedback } from "./useLinkFeedback";
import { EntityLink } from "../shell/EntityLink";
import type { EntityKind } from "../shell/routing";
import { useCan } from "../auth/permissions";

export interface LinkOption {
  id: string;
  label: string;
  /** Shown beside a linked item's name, e.g. a design's lifecycle status. */
  detail?: string;
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
  /**
   * The linked items themselves, when the caller has them (with their own labels). Without
   * this they are looked up in `options`, so a linked item missing from `options` -- a
   * picker list is usually capped -- would not be shown.
   */
  linkedItems?: LinkOption[];
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
  /**
   * The permission linking needs, e.g. "write_business_arch" (ADP-blp.65). Without it the
   * picker and Remove are disabled, with the reason as a tooltip, instead of failing on use.
   */
  action?: string;
  /** A heading above the list, e.g. "Linked Designs". */
  title?: string;
  /**
   * Shown before the picker, for a choice that narrows its options: a framework before its
   * controls, a value stream before its stages.
   */
  pickerPrefix?: React.ReactNode;
  /**
   * More inputs that belong to the link (a fit score). With these the link is not saved on
   * choosing a value: a Link button appears, and the caller's `link` reads its own fields.
   */
  addFields?: React.ReactNode;
  /** The picker's accessible name when it should differ from `prompt`, e.g. "Control". */
  pickerLabel?: string;
  /** Hide the picker until `pickerPrefix` has a choice. */
  hidePicker?: boolean;
  /** A line under the picker, e.g. why it has nothing to offer. */
  hint?: React.ReactNode;
  /** With `addFields`: a message to show instead of linking, or null when the fields are valid. */
  validate?: () => string | null;
}

const muted: React.CSSProperties = { fontSize: "0.85rem", color: "var(--ink-2)" };

export default function LinkEditor({
  options, linkedIds, linkedItems, isLoading, noun, plural, prompt, link, unlink, entityKind, onOpen,
  openTitle, action, title, pickerPrefix, addFields, validate, pickerLabel,
  hidePicker, hint,
}: LinkEditorProps): React.ReactElement {
  const permission = useCan(action ?? "");
  const canEdit = !action || permission.allowed;
  const why = canEdit ? undefined : permission.reason;
  const [selectedId, setSelectedId] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const feedback = useLinkFeedback();

  const linkedSet = new Set(linkedIds);
  const linked = linkedItems ?? options.filter((o) => linkedSet.has(o.id));
  const available = options.filter((o) => !linkedSet.has(o.id));

  function handleAdd(chosenId: string) {
    if (!chosenId) return;
    setSelectedId(chosenId);
    setLinkError(null);
    const invalid = validate?.() ?? null;
    if (invalid) {
      setLinkError(invalid);
      return;
    }
    const label = available.find((o) => o.id === chosenId)?.label ?? chosenId;
    link.mutate(chosenId, {
      onSuccess: () => {
        setSelectedId("");
        feedback.showLinked(label);
      },
      onError: (err) => {
        setSelectedId("");
        setLinkError(
          err.status === 409
            ? "Already linked"
            : err.status === 404
              ? `No such ${noun}`
              : err.message || `Failed to link ${noun}`,
        );
      },
    });
  }

  if (isLoading) return <p style={muted}>Loading {plural}…</p>;

  return (
    <div style={{ marginTop: title ? 0 : "0.75rem" }}>
      {title && (
        <h4 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600, color: "var(--ink-2)" }}>{title}</h4>
      )}
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
            {o.detail && (
              <span style={{ fontSize: "0.75rem", color: "var(--ink-2)", textTransform: "capitalize" }}>
                {o.detail}
              </span>
            )}
            <button
              onClick={() => unlink.mutate(o.id, { onSuccess: () => feedback.showRemoved(o.label) })}
              disabled={unlink.isPending || !canEdit}
              title={why}
              className="ui-btn ui-btn-xs"
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        {pickerPrefix}
        {!hidePicker && (
          <select
            value={selectedId}
            onChange={(e) => (addFields ? setSelectedId(e.target.value) : handleAdd(e.target.value))}
            disabled={link.isPending || !canEdit}
            title={why}
            aria-label={pickerLabel ?? prompt ?? `Link a ${noun}`}
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
        )}
        {addFields}
        {addFields && (
          <button
            type="button"
            className="ui-btn ui-btn-primary ui-btn-sm"
            disabled={!selectedId || link.isPending || !canEdit}
            title={why}
            onClick={() => handleAdd(selectedId)}
          >
            Link
          </button>
        )}
      </div>
      {hint && <p style={{ ...muted, fontSize: "0.8rem", margin: "0.35rem 0 0" }}>{hint}</p>}
      {linkError && (
        <p style={{ color: "var(--crit)", fontSize: "0.8rem", margin: "0.35rem 0 0" }}>{linkError}</p>
      )}
      {feedback.message && (
        <p style={{ color: "var(--good)", fontSize: "0.8rem", margin: "0.35rem 0 0" }}>{feedback.message}</p>
      )}
    </div>
  );
}
