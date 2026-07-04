import React, { useEffect, useState } from "react";
import type {
  KnowledgeItemDetail,
  KnowledgeItemCreateRequest,
  KnowledgeItemUpdateRequest,
  KnowledgeKind,
} from "../api/knowledge";
import { KNOWLEDGE_KINDS, useCreateKnowledgeItem, useUpdateKnowledgeItem } from "../api/knowledge";

interface KnowledgeItemFormProps {
  /** Editing an existing item — pre-fills form; undefined = create mode */
  existing?: KnowledgeItemDetail;
  onDone: () => void;
  onCancel: () => void;
}

type FormState = {
  id: string;
  kind: KnowledgeKind;
  title: string;
  full_text: string;
  source_ref: string;
  metadata: string;
};

const EMPTY_FORM: FormState = {
  id: "",
  kind: "principle",
  title: "",
  full_text: "",
  source_ref: "",
  metadata: "",
};

export default function KnowledgeItemForm({ existing, onDone, onCancel }: KnowledgeItemFormProps): React.ReactElement {
  const isEdit = !!existing;
  const [form, setForm] = useState<FormState>({ ...EMPTY_FORM });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const create = useCreateKnowledgeItem();
  const update = useUpdateKnowledgeItem(existing?.id ?? "");
  const isPending = create.isPending || update.isPending;
  const mutationError = create.error || update.error;

  useEffect(() => {
    if (existing) {
      setForm({
        id: existing.id,
        kind: existing.kind,
        title: existing.title,
        full_text: existing.full_text,
        source_ref: existing.source_ref,
        metadata: Object.keys(existing.metadata).length > 0
          ? JSON.stringify(existing.metadata, null, 2)
          : "",
      });
    } else {
      setForm({ ...EMPTY_FORM });
    }
    setErrors({});
  }, [existing]);

  const set = (field: keyof typeof EMPTY_FORM) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!form.title.trim()) errs.title = "Title is required";
    if (!form.full_text.trim()) errs.full_text = "Content is required";
    if (!form.source_ref.trim()) errs.source_ref = "Source reference is required";
    if (!isEdit && !form.id.trim()) errs.id = "ID is required (e.g. PRIN-007)";
    if (form.metadata.trim()) {
      try { JSON.parse(form.metadata); } catch { errs.metadata = "Must be valid JSON"; }
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = () => {
    if (!validate()) return;
    const metadata = form.metadata.trim() ? JSON.parse(form.metadata) : {};

    if (isEdit) {
      const body: KnowledgeItemUpdateRequest = {
        kind: form.kind,
        title: form.title.trim(),
        full_text: form.full_text.trim(),
        source_ref: form.source_ref.trim(),
        metadata,
      };
      update.mutate(body, { onSuccess: onDone });
    } else {
      const body: KnowledgeItemCreateRequest = {
        id: form.id.trim() || undefined,
        kind: form.kind,
        title: form.title.trim(),
        full_text: form.full_text.trim(),
        source_ref: form.source_ref.trim(),
        metadata,
      };
      create.mutate(body, { onSuccess: onDone });
    }
  };

  const field = (label: string, key: keyof typeof EMPTY_FORM, element: React.ReactNode) => (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 4 }}>
        {label}
      </label>
      {element}
      {errors[key] && <div style={{ fontSize: 12, color: "#DC2626", marginTop: 3 }}>{errors[key]}</div>}
    </div>
  );

  const inputStyle = (hasError: boolean): React.CSSProperties => ({
    width: "100%",
    padding: "7px 10px",
    fontSize: 13,
    borderRadius: 5,
    border: `1px solid ${hasError ? "#DC2626" : "#D1D5DB"}`,
    boxSizing: "border-box",
    fontFamily: "inherit",
  });

  return (
    <div style={{ background: "#F8FAFC", border: "1px solid #E5E7EB", borderRadius: 8, padding: 20, marginBottom: 16 }}>
      <h3 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700 }}>
        {isEdit ? `Edit: ${existing!.title}` : "Add Knowledge Item"}
      </h3>

      {!isEdit && field("ID *", "id",
        <input style={inputStyle(!!errors.id)} value={form.id} onChange={set("id")}
          placeholder="e.g. PRIN-007 or PAT-012" />
      )}

      {field("Kind *", "kind",
        <select style={inputStyle(false)} value={form.kind} onChange={set("kind")}>
          {KNOWLEDGE_KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
        </select>
      )}

      {field("Title *", "title",
        <input style={inputStyle(!!errors.title)} value={form.title} onChange={set("title")}
          placeholder="Concise name for this knowledge item" />
      )}

      {field("Content *", "full_text",
        <textarea style={{ ...inputStyle(!!errors.full_text), resize: "vertical" }}
          value={form.full_text} onChange={set("full_text")} rows={8}
          placeholder="Full knowledge content — this is what the AI reads to ground recommendations" />
      )}

      {field("Source Reference *", "source_ref",
        <input style={inputStyle(!!errors.source_ref)} value={form.source_ref} onChange={set("source_ref")}
          placeholder="https://example.com/source" />
      )}

      {field("Metadata (JSON, optional)", "metadata",
        <textarea style={{ ...inputStyle(!!errors.metadata), resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
          value={form.metadata} onChange={set("metadata")} rows={3}
          placeholder='{"domain": "security", "tags": ["auth"]}' />
      )}

      {mutationError && (
        <div style={{ marginBottom: 12, padding: 10, background: "#FEE2E2", border: "1px solid #FECACA", borderRadius: 5, fontSize: 13, color: "#B91C1C" }}>
          {mutationError.message}
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button onClick={onCancel} disabled={isPending}
          style={{ padding: "8px 18px", background: "#fff", color: "#374151", border: "1px solid #D1D5DB", borderRadius: 4, cursor: "pointer", fontSize: 14 }}>
          Cancel
        </button>
        <button onClick={handleSubmit} disabled={isPending}
          style={{ padding: "8px 18px", background: isPending ? "#D1D5DB" : "#1168BD", color: "#fff", border: "none", borderRadius: 4, cursor: isPending ? "not-allowed" : "pointer", fontSize: 14, fontWeight: 600 }}>
          {isPending ? "Saving..." : isEdit ? "Save Changes" : "Add Item"}
        </button>
      </div>
    </div>
  );
}
