import React from "react";
import { entityHref, type EntityKind } from "./routing";

export { entityHref };

/**
 * A link to one entity on the screen that owns it (ADP-blp.57).
 *
 * Wherever an entity was shown it was either plain text or wired up by hand through one of
 * several navigation contexts. Because every entity now has an address (`#/applications/<id>`),
 * a link is just an anchor: it works with Back, middle-click and "copy link", and needs no
 * context provider. Use this wherever an entity's name is displayed.
 */
interface EntityLinkProps {
  kind: EntityKind;
  id: string;
  children: React.ReactNode;
  title?: string;
}

export function EntityLink({ kind, id, children, title }: EntityLinkProps): React.ReactElement {
  return (
    <a className="ui-entitylink" href={entityHref(kind, id)} title={title}>
      {children}
    </a>
  );
}

export default EntityLink;
