import { useDesign } from "../api/designs";

/**
 * A design's title, for places that only hold its id (ADP-blp.63). The side rail used to show
 * "Design · DSN-014", which says nothing about which design is open. Falls back to the id while
 * the design loads or if it cannot be read.
 */
export default function DesignName({ designId }: { designId: string }) {
  const { data } = useDesign(designId);
  return <>{data?.title ?? designId}</>;
}
