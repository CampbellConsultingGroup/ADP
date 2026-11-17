import React, { useState } from "react";
import { useCreateValueStream, useUpdateValueStream } from "../api/business";
import type { ValueStream } from "../api/business";
import { Alert, Field } from "../ui/primitives";

interface ValueStreamFormProps {
  existing?: ValueStream;
  onDone: () => void;
  onCancel: () => void;
}

export default function ValueStreamForm({ existing, onDone, onCancel }: ValueStreamFormProps): React.ReactElement {
  const [name, setName] = useState(existing?.name ?? "");
  const [description, setDescription] = useState(existing?.description ?? "");
  const [stakeholder, setStakeholder] = useState(existing?.stakeholder ?? "");

  const create = useCreateValueStream();
  const update = useUpdateValueStream(existing?.id ?? "");
  const isPending = create.isPending || update.isPending;
  const error = create.error ?? update.error;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    const body = { name: name.trim(), description: description.trim() || null, stakeholder: stakeholder.trim() || null };
    if (existing) {
      update.mutate(body, { onSuccess: onDone });
    } else {
      create.mutate(body, { onSuccess: onDone });
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 6, padding: 16, marginBottom: 12 }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>{existing ? "Edit Value Stream" : "New Value Stream"}</div>
      {/* ADP-blp.46: Field ties each label to its control; the shared input classes replace
          three copies of the same inline style. */}
      <Field label="Name" required>
        {(control) => (
          <input
            {...control}
            className="ui-input"
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Order to Cash"
          />
        )}
      </Field>
      <Field label="Target Stakeholder">
        {(control) => (
          <input
            {...control}
            className="ui-input"
            value={stakeholder}
            onChange={(e) => setStakeholder(e.target.value)}
            placeholder="Customer"
          />
        )}
      </Field>
      <Field label="Description">
        {(control) => (
          <textarea
            {...control}
            className="ui-textarea"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description"
            rows={2}
          />
        )}
      </Field>
      {error && <Alert tone="crit">{error.message}</Alert>}
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button type="button" onClick={onCancel} style={{ padding: "6px 14px", fontSize: 13, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer" }}>
          Cancel
        </button>
        <button
          type="submit"
          disabled={!name.trim() || isPending}
          style={{ padding: "6px 14px", fontSize: 13, background: "var(--accent)", color: "var(--accent-ink)", border: "none", borderRadius: 4, cursor: name.trim() ? "pointer" : "not-allowed", opacity: name.trim() ? 1 : 0.5 }}
        >
          {isPending ? "Saving…" : existing ? "Save Changes" : "Create"}
        </button>
      </div>
    </form>
  );
}
