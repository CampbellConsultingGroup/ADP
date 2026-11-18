import { useState } from "react";
import { useCapabilities } from "../api/business";
import { useAppCapLinks, useCreateAppCapLink, useDeleteAppCapLink } from "../api/application";
import LinkEditor from "../links/LinkEditor";

interface Props { appId: string; }

/**
 * An application's business capability links, each with a fit score. A wrapper over the shared
 * LinkEditor (ADP-blp.36): the score is the link's extra field, so linking keeps a Link button.
 */
export default function CapabilityLinksEditor({ appId }: Props) {
  const { data: links, isLoading } = useAppCapLinks(appId);
  const { data: caps } = useCapabilities();
  const createLink = useCreateAppCapLink(appId);
  const deleteLink = useDeleteAppCapLink(appId);
  const [fitScore, setFitScore] = useState("3");

  const score = parseInt(fitScore, 10);
  const linked = (links?.items ?? []).map((l) => ({
    id: l.capability_id,
    label: l.capability_name,
    detail: `fit ${l.fit_score}/5`,
  }));

  return (
    <LinkEditor
      title="Business Capabilities"
      action="write_application"
      noun="capability"
      plural="capabilities"
      entityKind="business_capability"
      isLoading={isLoading}
      options={(caps?.items ?? []).map((c) => ({ id: c.id, label: `${c.name} (L${c.level})` }))}
      linkedIds={linked.map((c) => c.id)}
      linkedItems={linked}
      validate={() => (score >= 1 && score <= 5 ? null : "Fit score must be 1–5")}
      addFields={
        <input
          type="number"
          min={1}
          max={5}
          value={fitScore}
          onChange={(e) => setFitScore(e.target.value)}
          className="ui-input"
          style={{ width: 64 }}
          aria-label="Fit score (1 to 5)"
          title="Fit score 1–5"
        />
      }
      link={{
        isPending: createLink.isPending,
        mutate: (id, options) =>
          createLink.mutate(
            { capability_id: id, fit_score: score },
            { ...options, onSuccess: () => { setFitScore("3"); options?.onSuccess?.(); } },
          ),
      }}
      unlink={deleteLink}
    />
  );
}
