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

/** Ensure the token is valid for at least `minValidity` seconds; refresh if needed. */
export async function getValidToken(minValidity = 30): Promise<string> {
  await keycloak.updateToken(minValidity);
  return keycloak.token ?? "";
}
