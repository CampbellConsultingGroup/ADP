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

export async function initKeycloak(): Promise<boolean> {
  return keycloak.init({
    onLoad: "login-required",
    pkceMethod: "S256",
    checkLoginIframe: false,
  });
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
