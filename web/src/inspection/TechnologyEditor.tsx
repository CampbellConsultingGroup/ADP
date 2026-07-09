/**
 * TechnologyEditor — inline form for adding/editing element technology metadata (ADP-SPEC-029).
 */
import React, { useState } from "react";
import type { TechnologyMetadata } from "../types";
import { useUpdateElementTags } from "../api/designs";

interface TechnologyEditorProps {
  designId: string;
  elementId: string;
  existing: TechnologyMetadata | null | undefined;
  existingTags: string[];
  onDone: () => void;
}

export default function TechnologyEditor({
  designId,
  elementId,
  existing,
  existingTags,
  onDone,
}: TechnologyEditorProps): React.ReactElement {
  const [technology, setTechnology] = useState(existing?.technology ?? "");
  const [vendor, setVendor] = useState(existing?.vendor ?? "");
  const [platform, setPlatform] = useState(existing?.platform ?? "");
  const [version, setVersion] = useState(existing?.version ?? "");
  const [ownerTeam, setOwnerTeam] = useState(existing?.owner_team ?? "");
  const [tags, setTags] = useState<string[]>(existingTags);
  const [tagInput, setTagInput] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const mutation = useUpdateElementTags(designId, elementId);

  const validate = (): boolean => {
    const e: Record<string, string> = {};
    if (technology.length > 200) e.technology = "Max 200 characters";
    if (vendor.length > 200) e.vendor = "Max 200 characters";
    if (platform.length > 200) e.platform = "Max 200 characters";
    if (version.length > 50) e.version = "Max 50 characters";
    if (ownerTeam.length > 200) e.owner_team = "Max 200 characters";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const addTag = () => {
    const t = tagInput.trim();
    if (!t) return;
    if (t.length > 50) { setErrors(e => ({ ...e, tags: "Tag max 50 characters" })); return; }
    if (!tags.includes(t)) setTags(prev => [...prev, t]);
    setTagInput("");
    setErrors(e => { const n = { ...e }; delete n.tags; return n; });
  };

  const removeTag = (tag: string) => setTags(prev => prev.filter(t => t !== tag));

  const handleSave = () => {
    if (!validate()) return;
    mutation.mutate({
      technology: technology.trim() || null,
      vendor: vendor.trim() || null,
      platform: platform.trim() || null,
      version: version.trim() || null,
      owner_team: ownerTeam.trim() || null,
      tags,
    }, { onSuccess: onDone });
  };

  const inputStyle = (field: string): React.CSSProperties => ({
    width: "100%",
    padding: "5px 8px",
    fontSize: 12,
    borderRadius: 4,
    border: `1px solid ${errors[field] ? "#DC2626" : "#D1D5DB"}`,
    boxSizing: "border-box",
    fontFamily: "inherit",
    marginBottom: 2,
  });

  const labelStyle: React.CSSProperties = { fontSize: 11, fontWeight: 600, color: "#6B7280", marginBottom: 2, display: "block" };
  const errorStyle: React.CSSProperties = { fontSize: 11, color: "#DC2626", marginBottom: 6 };

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Technology</label>
        <input style={inputStyle("technology")} value={technology} onChange={e => setTechnology(e.target.value)} placeholder="e.g. Apache Kafka" />
        {errors.technology && <div style={errorStyle}>{errors.technology}</div>}
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Vendor</label>
        <input style={inputStyle("vendor")} value={vendor} onChange={e => setVendor(e.target.value)} placeholder="e.g. Confluent" />
        {errors.vendor && <div style={errorStyle}>{errors.vendor}</div>}
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Platform</label>
        <input style={inputStyle("platform")} value={platform} onChange={e => setPlatform(e.target.value)} placeholder="e.g. AWS EKS" />
        {errors.platform && <div style={errorStyle}>{errors.platform}</div>}
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Version</label>
        <input style={inputStyle("version")} value={version} onChange={e => setVersion(e.target.value)} placeholder="e.g. 3.4.1" />
        {errors.version && <div style={errorStyle}>{errors.version}</div>}
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Owner Team</label>
        <input style={inputStyle("owner_team")} value={ownerTeam} onChange={e => setOwnerTeam(e.target.value)} placeholder="e.g. Platform Engineering" />
        {errors.owner_team && <div style={errorStyle}>{errors.owner_team}</div>}
      </div>

      <div style={{ marginBottom: 10 }}>
        <label style={labelStyle}>Tags</label>
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 4 }}>
          {tags.map(tag => (
            <span key={tag} style={{ background: "#EDE9FE", color: "#5B21B6", fontSize: 11, padding: "2px 6px", borderRadius: 3, display: "flex", alignItems: "center", gap: 4 }}>
              {tag}
              <button onClick={() => removeTag(tag)} style={{ background: "none", border: "none", cursor: "pointer", color: "#5B21B6", fontSize: 11, padding: 0, lineHeight: 1 }}>✕</button>
            </span>
          ))}
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          <input
            style={{ ...inputStyle("tags"), flex: 1, marginBottom: 0 }}
            value={tagInput}
            onChange={e => setTagInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && (e.preventDefault(), addTag())}
            placeholder="Type tag + Enter"
            maxLength={51}
          />
          <button onClick={addTag} style={{ padding: "5px 10px", background: "#EDE9FE", color: "#5B21B6", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 11 }}>Add</button>
        </div>
        {errors.tags && <div style={errorStyle}>{errors.tags}</div>}
      </div>

      {mutation.isError && (
        <div style={{ fontSize: 12, color: "#DC2626", marginBottom: 8 }}>{mutation.error?.message}</div>
      )}

      <div style={{ display: "flex", gap: 6 }}>
        <button
          onClick={handleSave}
          disabled={mutation.isPending}
          style={{ flex: 1, padding: "6px 0", background: mutation.isPending ? "#D1D5DB" : "#1168BD", color: "#fff", border: "none", borderRadius: 4, cursor: mutation.isPending ? "not-allowed" : "pointer", fontSize: 12, fontWeight: 600 }}
        >
          {mutation.isPending ? "Saving…" : "Save"}
        </button>
        <button
          onClick={onDone}
          disabled={mutation.isPending}
          style={{ flex: 1, padding: "6px 0", background: "#fff", color: "#374151", border: "1px solid #D1D5DB", borderRadius: 4, cursor: "pointer", fontSize: 12 }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
