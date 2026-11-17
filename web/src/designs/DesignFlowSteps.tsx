import React from "react";
import type { AppView } from "../shell";
import { formatRoute, useHashParam } from "../shell/routing";

/**
 * Where you are in creating a design (ADP-blp.59).
 *
 * A design is made across several screens -- describe the requirements, review the
 * recommendations, shape the C4 model, validate it -- but nothing showed that these were steps
 * of one flow or which came next. This strip sits above those screens. Each step is a link to
 * its screen; steps that need a design are inactive until one exists.
 */
type StepId = "describe" | "recommend" | "design" | "validate";

interface Step {
  id: StepId;
  label: string;
  hint: string;
  view: AppView;
  tab?: string;
  needsDesign: boolean;
}

const STEPS: Step[] = [
  { id: "describe", label: "Describe", hint: "Capture the requirements", view: "intake", needsDesign: false },
  { id: "recommend", label: "Recommend", hint: "Review AI-proposed options", view: "intake", tab: "recommend", needsDesign: true },
  { id: "design", label: "Design", hint: "Shape the C4 model", view: "canvas-v2", needsDesign: true },
  { id: "validate", label: "Validate", hint: "Check it against the standards", view: "designs", needsDesign: true },
];

const INTAKE_TABS = ["intake", "recommend", "settings"] as const;

export function currentStep(view: AppView, intakeTab: string): StepId | null {
  if (view === "intake") return intakeTab === "recommend" ? "recommend" : "describe";
  if (view === "canvas-v2") return "design";
  if (view === "designs") return "validate";
  return null;
}

function hrefFor(step: Step, designId: string | null): string {
  const base = formatRoute({ view: step.view, entity: null, designId: step.view === "designs" ? null : designId });
  if (!step.tab) return base;
  return `${base}${base.includes("?") ? "&" : "?"}tab=${step.tab}`;
}

interface Props {
  view: AppView;
  designId: string | null;
}

export default function DesignFlowSteps({ view, designId }: Props): React.ReactElement | null {
  const [intakeTab] = useHashParam<(typeof INTAKE_TABS)[number]>("tab", INTAKE_TABS, "intake");
  const current = currentStep(view, intakeTab);
  if (current === null) return null;
  const currentIndex = STEPS.findIndex((s) => s.id === current);

  return (
    <nav className="ui-steps" aria-label="Design steps">
      <ol>
        {STEPS.map((step, index) => {
          const isCurrent = step.id === current;
          const available = !step.needsDesign || designId !== null;
          const state = isCurrent ? "current" : index < currentIndex ? "done" : "todo";
          const body = (
            <>
              <span className="n">{index + 1}</span>
              <span className="t">
                <span className="l">{step.label}</span>
                <span className="h">{step.hint}</span>
              </span>
            </>
          );
          return (
            <li key={step.id} className={`${state}${available ? "" : " off"}`}>
              {isCurrent || !available ? (
                <span
                  className="s"
                  aria-current={isCurrent ? "step" : undefined}
                  title={available ? undefined : "Create or open a design first"}
                >
                  {body}
                </span>
              ) : (
                <a className="s" href={hrefFor(step, designId)}>
                  {body}
                </a>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
