/**
 * Keycloak instance and initialisation helper (ADP-SPEC-026).
 * Import `keycloak` to access the current token; call `initKeycloak()` once at app startup.
 */
import Keycloak from "keycloak-js";

const keycloakUrl = import.meta.env.VITE_KEYCLOAK_URL ?? "http://127.0.0.1:8080";
const keycloakRealm = import.meta.env.VITE_KEYCLOAK_REALM ?? "ADPRealm";
const keycloakClientId = import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? "adp-frontend";

export const keycloak = new Keycloak({
  url: keycloakUrl,
  realm: keycloakRealm,
  clientId: keycloakClientId,
});

// ADP-dhx: React 18 StrictMode (main.tsx) intentionally double-invokes effects
// in dev, so AuthProvider's init effect calls initKeycloak() twice against the
// same module-level `keycloak` singleton. keycloak-js throws "A Keycloak
// instance can only be initialized once" on the second real call to
// keycloak.init() -- memoize the in-flight/settled promise so a second call
// (StrictMode's replay, or any other accidental re-invocation) reuses the
// first call's result instead of re-entering keycloak.init().
let initPromise: Promise<boolean> | null = null;

// ADP-blp.53: the app's own location now lives in the URL hash ("#/business/<id>"), and
// keycloak-js returns its login result in the hash too. A deep link is therefore set aside
// before the login redirect and put back once Keycloak has finished with the URL, so the two
// never share the fragment (an OAuth redirect URI may not carry one).
const ROUTE_STASH_KEY = "adp.route";

export function stashAppRoute(): void {
  const hash = window.location.hash;
  if (!hash.startsWith("#/")) return;
  try {
    window.sessionStorage.setItem(ROUTE_STASH_KEY, hash);
  } catch {
    return; // no storage: keep the hash where it is rather than lose it
  }
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
}

export function restoreAppRoute(): void {
  let saved: string | null = null;
  try {
    saved = window.sessionStorage.getItem(ROUTE_STASH_KEY);
    window.sessionStorage.removeItem(ROUTE_STASH_KEY);
  } catch {
    return;
  }
  if (saved && !window.location.hash) window.history.replaceState(null, "", saved);
}

export function initKeycloak(): Promise<boolean> {
  if (!initPromise) {
    stashAppRoute();
    initPromise = keycloak
      .init({
        onLoad: "login-required",
        pkceMethod: "S256",
        checkLoginIframe: false,
      })
      .then((authenticated) => {
        restoreAppRoute();
        return authenticated;
      });
  }
  return initPromise;
}

/** Ensure the token is valid for at least `minValidity` seconds; refresh if needed.
 *
 * Resilience (ADP-cm9): a refresh hiccup (clock skew, a transient network blip
 * through the /auth reverse proxy, etc.) must NOT cause us to send NO token --
 * that yields a 401 on every API call and, with the app's error boundary, an
 * error screen instead of data. So if updateToken() throws we fall back to the
 * current access token when one is still present, and only surface an empty
 * string when we genuinely have nothing to send. */
export async function getValidToken(minValidity = 30): Promise<string> {
  try {
    await keycloak.updateToken(minValidity);
  } catch (err) {
    // Keep going with the existing token if we have one; a failed *refresh*
    // shouldn't strip auth from a request the current token could still serve.
    console.warn("keycloak.updateToken failed; falling back to current token", err);
  }
  return keycloak.token ?? "";
}
