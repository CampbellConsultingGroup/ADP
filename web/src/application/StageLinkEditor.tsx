import { useState } from "react";
import { useValueStream, useValueStreams } from "../api/business";
import { useAppStageLinks, useCreateAppStageLink, useDeleteAppStageLink } from "../api/application";
import LinkEditor from "../links/LinkEditor";

interface Props { appId: string; }

/**
 * The value stream stages an application supports. A wrapper over the shared LinkEditor
 * (ADP-blp.36). Stages belong to a value stream, so you choose the stream first and then one of
 * its stages. (The old picker listed the streams as empty groups and offered no stage at all.)
 */
export default function StageLinkEditor({ appId }: Props) {
  const { data: links, isLoading } = useAppStageLinks(appId);
  const { data: streams } = useValueStreams();
  const [streamId, setStreamId] = useState("");
  const stream = useValueStream(streamId || null);
  const createLink = useCreateAppStageLink(appId);
  const deleteLink = useDeleteAppStageLink(appId);

  const linked = (links?.items ?? []).map((l) => ({ id: l.stage_id, label: l.stage_name }));
  const stages = (stream.data?.stages ?? []).map((s) => ({ id: s.id, label: s.name }));
  const unlinkedCount = stages.filter((s) => !linked.some((l) => l.id === s.id)).length;

  return (
    <LinkEditor
      title="Value Stream Stages"
      action="write_application"
      noun="stage"
      plural="stages"
      isLoading={isLoading}
      options={stages}
      linkedIds={linked.map((s) => s.id)}
      linkedItems={linked}
      pickerLabel="Stage"
      hidePicker={!streamId}
      pickerPrefix={
        <select
          aria-label="Value stream"
          className="ui-select"
          style={{ flex: 1, minWidth: 160 }}
          value={streamId}
          onChange={(e) => setStreamId(e.target.value)}
        >
          <option value="">Choose a value stream…</option>
          {(streams?.items ?? []).map((vs) => <option key={vs.id} value={vs.id}>{vs.name}</option>)}
        </select>
      }
      hint={
        streamId && stream.data && unlinkedCount === 0
          ? stages.length === 0 ? "This value stream has no stages yet." : "Every stage of this value stream is already linked."
          : undefined
      }
      link={createLink}
      unlink={deleteLink}
    />
  );
}
