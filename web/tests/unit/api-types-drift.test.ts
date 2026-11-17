import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

/**
 * The checked-in API types must match the API (ADP-blp.37).
 *
 * `src/api/generated/schema.d.ts` is generated from `generated/openapi.json`, which the backend's
 * own drift gate (`adp-generate --check`) keeps in step with the Pydantic models. This closes the
 * other half: if the OpenAPI document changes and the types are not regenerated, this fails.
 * Fix with `npm run gen:api`.
 */
describe("generated API types", () => {
  it("are up to date with generated/openapi.json", async () => {
    const root = join(__dirname, "../../..");
    const ast = await openapiTS(pathToFileURL(join(root, "generated/openapi.json")));
    const fresh = astToString(ast);
    const committed = readFileSync(join(root, "web/src/api/generated/schema.d.ts"), "utf8");
    // Compare content, not line endings or the generator's banner.
    const normalise = (text: string) =>
      text.replace(/\r\n/g, "\n").replace(/^\/\*\*[\s\S]*?\*\/\n+/, "").trim();
    expect(normalise(committed) === normalise(fresh), "run `npm run gen:api`").toBe(true);
  }, 30_000);
});
