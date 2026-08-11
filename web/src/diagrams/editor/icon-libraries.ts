/**
 * Local, static replacement for the sibling project's `api.getLibraryIcons()`
 * (canvas/apps/web/src/app/api.ts), which fetches icon artwork from that
 * project's own Fastify backend -- not portable (research.md Decision 1/2).
 *
 * ADP doesn't need the fetch: the built-in icon libraries (AWS, Azure,
 * generic shapes) are already vendored as static manifests in
 * `../core/libraries/`, loaded once via `loadLibrary()`. Admin-uploaded
 * *custom* icon libraries (a capability the sibling project's backend
 * supports) are out of scope for v1 -- no Standards/admin-library-upload
 * surface exists in ADP yet (spec.md FR-009).
 */
import { loadLibrary, type Icon } from '../core/index.js';
import { awsIconsManifest } from '../core/libraries/aws-icons.js';
import { azureIconsManifest } from '../core/libraries/azure-icons.js';
import { genericShapesManifest } from '../core/libraries/generic.js';

const _libraries = [awsIconsManifest, azureIconsManifest, genericShapesManifest].map((manifest) =>
  loadLibrary(manifest),
);

/** Mirrors the shape Canvas.tsx expects from the sibling project's
 * `api.getLibraryIcons(libraryId, libraryVersion)` -- an async function
 * returning `{ icons }`, so Canvas.tsx's `.then()` chain needs no change. */
export async function getLibraryIcons(
  libraryId: string,
  libraryVersion: string,
): Promise<{ icons: Icon[] }> {
  const library = _libraries.find((l) => l.id === libraryId && l.version === libraryVersion);
  return { icons: library?.icons ?? [] };
}
