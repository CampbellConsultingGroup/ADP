import React from "react";
import Workspace from "./canvas/Workspace";

function getDesignIdFromPath(): string {
  const match = window.location.pathname.match(/\/designs\/([^/]+)/);
  return match?.[1] ?? "DESIGN-001";
}

export default function App(): React.ReactElement {
  const designId = getDesignIdFromPath();
  return <Workspace designId={designId} />;
}
