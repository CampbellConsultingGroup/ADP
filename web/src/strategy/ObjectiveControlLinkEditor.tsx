/** ObjectiveControlLinkEditor — 925-strategy-compliance-linkage (COMPLY-05): link a Strategic
 *  Objective to a Control, recording that the objective is regulatory-driven (US2, "why does this
 *  objective exist"). A bare link (no status).
 *
 *  A wrapper over the shared LinkEditor (ADP-blp.36). Controls are nested per framework (there is
 *  no flat list), so you pick a framework first, then a control from its tree; choosing a control
 *  links it at once (ADP-w7z). */

import React, { useState } from "react";
import { flattenControls, useAllControls, useFramework, useFrameworks } from "../api/compliance";
import {
  useLinkObjectiveControl,
  useUnlinkObjectiveControl,
  type StrategicObjective,
} from "../api/strategy";
import LinkEditor from "../links/LinkEditor";

interface Props {
  objective: StrategicObjective;
}

export default function ObjectiveControlLinkEditor({ objective }: Props): React.ReactElement {
  const [frameworkId, setFrameworkId] = useState("");
  const frameworks = useFrameworks();
  const framework = useFramework(frameworkId || null);
  const allControls = useAllControls();
  const link = useLinkObjectiveControl(objective.id);
  const unlink = useUnlinkObjectiveControl(objective.id);

  const linked = objective.control_ids.map((id) => {
    const c = allControls.byId.get(id);
    return { id, label: c ? `${c.code} — ${c.title}` : id, detail: c?.framework_name };
  });
  const inFramework = framework.data ? flattenControls(framework.data) : [];
  const options = inFramework.map((c) => ({ id: c.id, label: `${"\u00a0\u00a0".repeat(c.depth)}${c.code} — ${c.title}` }));
  const nothingLeft = inFramework.every((c) => objective.control_ids.includes(c.id));

  return (
    <LinkEditor
      action="write_business_arch"
      noun="control"
      plural="controls"
      prompt={framework.isLoading ? "Loading controls…" : "Link a control…"}
      pickerLabel="Control"
      hidePicker={!frameworkId}
      options={options}
      linkedIds={objective.control_ids}
      linkedItems={linked}
      pickerPrefix={
        <select
          aria-label="Framework"
          className="ui-select"
          style={{ flex: 1, minWidth: 160 }}
          value={frameworkId}
          onChange={(e) => setFrameworkId(e.target.value)}
        >
          <option value="">Choose a framework…</option>
          {(frameworks.data?.items ?? []).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
      }
      hint={
        frameworkId && framework.data && nothingLeft
          ? framework.data.controls.length === 0
            ? "This framework has no controls yet."
            : "Every control in this framework is already linked."
          : undefined
      }
      link={link}
      unlink={unlink}
    />
  );
}
