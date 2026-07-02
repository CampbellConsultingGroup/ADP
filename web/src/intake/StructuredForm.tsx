import React, { useState } from "react";
import { useAddRequirement, type RequirementKind } from "../api/intake";

interface StructuredFormProps { designId: string; }

const KINDS: RequirementKind[] = ["functional", "non_functional", "constraint", "driver"];

export default function StructuredForm({ designId }: StructuredFormProps): React.ReactElement {
  const [statement, setStatement] = useState("");
  const [kind, setKind] = useState<RequirementKind>("functional");
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const add = useAddRequirement(designId);

  const canSubmit = statement.trim().length >= 10 && !add.isPending;

  const handleSubmit = () => {
    add.mutate({ statement: statement.trim(), kind }, {
      onSuccess: (data) => {
        setSuccessMsg(`${data.requirement_id} added`);
        setStatement("");
        setTimeout(() => setSuccessMsg(null), 3000);
      },
    });
  };

  return (
    <div>
      <div style={{ marginBottom: 10 }}>
        <label style={{ fontSize: 13, fontWeight: 600, display: "block", marginBottom: 4 }}>Requirement statement *</label>
        <input
          value={statement}
          onChange={(e) => setStatement(e.target.value)}
          placeholder="The system must..."
          style={{ width: "100%", padding: 8, fontSize: 13, border: "1px solid #ccc", borderRadius: 4, boxSizing: "border-box" }}
        />
        {statement.length > 0 && statement.trim().length < 10 && (
          <div style={{ fontSize: 12, color: "#c0392b", marginTop: 4 }}>Minimum 10 characters required.</div>
        )}
      </div>
      <div style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 13, fontWeight: 600, display: "block", marginBottom: 4 }}>Kind *</label>
        <select value={kind} onChange={(e) => setKind(e.target.value as RequirementKind)} style={{ padding: "7px 10px", fontSize: 13, border: "1px solid #ccc", borderRadius: 4 }}>
          {KINDS.map((k) => <option key={k} value={k}>{k.replace("_", " ")}</option>)}
        </select>
      </div>
      <button
        disabled={!canSubmit}
        onClick={handleSubmit}
        style={{ padding: "8px 18px", background: canSubmit ? "#166534" : "#ccc", color: "#fff", border: "none", borderRadius: 4, cursor: canSubmit ? "pointer" : "not-allowed", fontSize: 14, fontWeight: 600 }}
      >
        {add.isPending ? "Adding..." : "Add Requirement"}
      </button>
      {successMsg && <div style={{ marginTop: 8, color: "#166534", fontSize: 13, fontWeight: 600 }}>{successMsg}</div>}
      {add.isError && <div style={{ marginTop: 8, color: "#c0392b", fontSize: 13 }}>Failed to add requirement.</div>}
    </div>
  );
}
