/** Defense-in-depth alongside the backend's http(s)-only validators (compliance source_url,
 *  agent a2a_card_url): only render a stored URL as a clickable link if it actually parses to an
 *  http/https URL, so a value that predates a validator (or reached the database by some other
 *  path) can never render as a `javascript:`-executable href. Shared since 933-agent-registry;
 *  originally local to compliance/FrameworkDetail.tsx (923 security review). */
export function isHttpUrl(value: string): boolean {
  try {
    const scheme = new URL(value).protocol;
    return scheme === "http:" || scheme === "https:";
  } catch {
    return false;
  }
}
