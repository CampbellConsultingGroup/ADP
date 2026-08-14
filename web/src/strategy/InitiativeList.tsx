import { useState } from "react";
import {
  useInitiatives,
  useCreateInitiative,
  useUpdateInitiative,
  useDeleteInitiative,
  useObjectives,
  type StrategyInitiative,
  type InitiativeStatus,
} from "../api/strategy";
import { Button } from "../ui";
import InitiativeObjectiveLinkEditor from "./InitiativeObjectiveLinkEditor";
import NavLinkButton from "./NavLinkButton";
import { useScrollHighlight } from "./useScrollHighlight";

const STATUSES: InitiativeStatus[] = ["planned", "in_progress", "blocked", "complete", "cancelled"];
const STATUS_LABEL: Record<InitiativeStatus, string> = {
  planned: "Planned",
  in_progress: "In progress",
  blocked: "Blocked",
  complete: "Complete",
  cancelled: "Cancelled",
};

function InitiativeEditForm({
  initiative,
  onDone,
  onNavigateToObjective,
}: {
  initiative: StrategyInitiative;
  onDone: () => void;
  onNavigateToObjective?: (objectiveId: string) => void;
}) {
  const updateMutation = useUpdateInitiative(initiative.id);
  const [name, setName] = useState(initiative.name);
  const [description, setDescription] = useState(initiative.description ?? "");
  const [owner, setOwner] = useState(initiative.owner ?? "");
  const [status, setStatus] = useState<InitiativeStatus>(initiative.status);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    updateMutation.mutate(
      {
        name: name.trim(),
        description: description.trim() || null,
        owner: owner.trim() || null,
        status,
      },
      { onSuccess: onDone },
    );
  }

  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 8, background: "var(--surface)" }}>
      <form onSubmit={handleSubmit}>
        <label style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} style={{ display: "block", width: "100%", marginTop: 2 }} />
        </label>
        <label style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
          Description
          <input value={description} onChange={(e) => setDescription(e.target.value)} style={{ display: "block", width: "100%", marginTop: 2 }} />
        </label>
        <label style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
          Owner
          <input value={owner} onChange={(e) => setOwner(e.target.value)} style={{ display: "block", width: "100%", marginTop: 2 }} />
        </label>
        <label style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value as InitiativeStatus)} style={{ display: "block", width: "100%", marginTop: 2 }}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{STATUS_LABEL[s]}</option>
            ))}
          </select>
        </label>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="submit" disabled={updateMutation.isPending}>
            {updateMutation.isPending ? "Saving…" : "Save"}
          </button>
          <button type="button" onClick={onDone}>Cancel</button>
        </div>
        {updateMutation.isError && (
          <div className="ui-alert crit" style={{ marginTop: 6, fontSize: 12 }}>
            {updateMutation.error.message}
          </div>
        )}
      </form>

      <h4 style={{ fontSize: 13, marginTop: 16, marginBottom: 0, color: "var(--ink)" }}>Linked Objectives</h4>
      <InitiativeObjectiveLinkEditor initiative={initiative} onNavigateToObjective={onNavigateToObjective} />
    </div>
  );
}

interface InitiativeListProps {
  /** Drill-through target: when set, the matching initiative row scrolls
   *  into view and briefly highlights. Initiatives have no dedicated detail
   *  view, so cross-navigation lands here rather than a new page (mirrors
   *  CapabilityTree's focusCapabilityId / ThemeList's focusThemeId). */
  focusInitiativeId?: string | null;
  /** Cross-navigation: jump to a linked Objective's own detail view
   *  (Objectives tab, drilled in -- Objective has a real detail page, so
   *  this uses the existing selectedObjectiveId mechanism rather than
   *  scroll-and-highlight). Threaded to both the read-mode "Linked
   *  objectives" list and the edit-mode InitiativeObjectiveLinkEditor. */
  onNavigateToObjective?: (objectiveId: string) => void;
}

export default function InitiativeList({ focusInitiativeId, onNavigateToObjective }: InitiativeListProps = {}) {
  const { data, isLoading, error } = useInitiatives();
  const { data: objectivesData } = useObjectives();
  const createMutation = useCreateInitiative();
  const deleteMutation = useDeleteInitiative();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const { registerRef } = useScrollHighlight(focusInitiativeId);

  if (isLoading) return <div style={{ padding: 16, color: "var(--ink-3)" }}>Loading initiatives…</div>;
  if (error) return <div className="ui-alert crit">Failed to load initiatives</div>;

  const items = data?.items ?? [];
  const objectiveStatements = new Map((objectivesData?.items ?? []).map((o) => [o.id, o.statement]));

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setFormError("Name is required");
      return;
    }
    setFormError(null);
    createMutation.mutate(
      { name: name.trim() },
      {
        onSuccess: () => {
          setShowForm(false);
          setName("");
        },
      },
    );
  }

  function handleDelete(initiative: StrategyInitiative) {
    if (!confirm(`Delete initiative "${initiative.name}"?`)) return;
    // FR-011: unconditional -- deleting an initiative is never blocked by
    // existing objective links, unlike theme delete.
    deleteMutation.mutate(initiative.id);
  }

  return (
    <div>
      <p style={{ fontSize: 13, color: "var(--ink-3)", margin: "0 0 16px", lineHeight: 1.5 }}>
        <strong style={{ color: "var(--ink-2)" }}>Initiative:</strong> A funded program of work that
        delivers progress toward one or more objectives — the &ldquo;how&rdquo; and &ldquo;who&rsquo;s
        building it.&rdquo; Where an objective states what will change and by when, an initiative is the
        actual project, system change, or transformation effort doing the work to get there.
      </p>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 15, color: "var(--ink)" }}>Strategy Initiatives</h3>
        <Button size="sm" variant={showForm ? "default" : "primary"} icon={showForm ? undefined : "plus"} onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "New Initiative"}
        </Button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 12, background: "var(--surface)" }}
        >
          {formError && <div style={{ color: "var(--crit)", fontSize: 13, marginBottom: 6 }}>{formError}</div>}
          <label style={{ fontSize: 13 }}>
            Name *
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{ display: "block", width: "100%", marginTop: 2 }}
              placeholder="Claims Automation Rollout"
            />
          </label>
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Saving…" : "Save"}
            </button>
            <button type="button" onClick={() => setShowForm(false)}>
              Cancel
            </button>
          </div>
          {createMutation.isError && (
            <div className="ui-alert crit" style={{ marginTop: 6, fontSize: 12 }}>
              {createMutation.error.message}
            </div>
          )}
        </form>
      )}

      {items.length === 0 && !showForm && (
        <div style={{ color: "var(--ink-3)", fontSize: 13 }}>No initiatives yet. Create one above.</div>
      )}

      {items.map((i) =>
        editingId === i.id ? (
          <InitiativeEditForm
            key={i.id}
            initiative={i}
            onDone={() => setEditingId(null)}
            onNavigateToObjective={onNavigateToObjective}
          />
        ) : (
          <div
            key={i.id}
            id={`initiative-${i.id}`}
            ref={registerRef(i.id)}
            data-focused={focusInitiativeId === i.id ? "true" : undefined}
            style={{
              display: "flex", justifyContent: "space-between", alignItems: "flex-start",
              border: focusInitiativeId === i.id ? "1px solid var(--accent)" : "1px solid var(--border)",
              borderRadius: 8, padding: "10px 12px", marginBottom: 8,
              background: focusInitiativeId === i.id ? "var(--accent-wash)" : "var(--surface)",
            }}
          >
            <div>
              <div style={{ fontWeight: 500, fontSize: 14, color: "var(--ink)" }}>
                {i.name}
                <span style={{ fontWeight: 400, fontSize: 12, color: "var(--ink-3)", marginLeft: 8 }}>
                  {STATUS_LABEL[i.status]}
                </span>
              </div>
              {i.description && (
                <div style={{ fontSize: 13, color: "var(--ink-2)", marginTop: 2 }}>{i.description}</div>
              )}
              {i.owner && (
                <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>Owner: {i.owner}</div>
              )}
              {i.objective_ids.length === 0 ? (
                <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>No linked objectives</div>
              ) : (
                <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>
                  Linked objectives:
                  {i.objective_ids.map((oid) => (
                    <div key={oid} style={{ marginTop: 1 }}>
                      {onNavigateToObjective ? (
                        <NavLinkButton onClick={() => onNavigateToObjective(oid)} title="Jump to this objective">
                          {objectiveStatements.get(oid) ?? oid}
                        </NavLinkButton>
                      ) : (
                        objectiveStatements.get(oid) ?? oid
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <Button size="sm" onClick={() => setEditingId(i.id)}>Edit</Button>
              <Button size="sm" variant="danger" onClick={() => handleDelete(i)}>Delete</Button>
            </div>
          </div>
        ),
      )}
    </div>
  );
}
