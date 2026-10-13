import { UserManager, WebStorageStateStore } from "oidc-client-ts";
export const mode = import.meta.env.VITE_MODE || "demo";
if (!["demo", "local", "aws"].includes(mode))
  throw new Error("VITE_MODE must be demo, local, or aws");
const domain = import.meta.env.VITE_COGNITO_DOMAIN;
export const manager =
  mode === "aws" && domain
    ? new UserManager({
        authority: import.meta.env.VITE_COGNITO_AUTHORITY,
        client_id: import.meta.env.VITE_COGNITO_CLIENT_ID,
        redirect_uri:
          import.meta.env.VITE_COGNITO_REDIRECT_URI ||
          `${location.origin}/callback`,
        post_logout_redirect_uri: `${location.origin}/`,
        response_type: "code",
        scope: "openid email cloudforge-api/jobs",
        automaticSilentRenew: false,
        userStore: new WebStorageStateStore({ store: sessionStorage }),
        metadata: {
          issuer: import.meta.env.VITE_COGNITO_AUTHORITY,
          authorization_endpoint: `${domain}/oauth2/authorize`,
          token_endpoint: `${domain}/oauth2/token`,
          end_session_endpoint: `${domain}/logout`,
          jwks_uri: `${import.meta.env.VITE_COGNITO_AUTHORITY}/.well-known/jwks.json`,
        },
      })
    : null;
export async function token(): Promise<string | undefined> {
  const user = await manager?.getUser();
  return user && !user.expired ? user.access_token : undefined;
}
export async function signOut() {
  await manager?.removeUser();
  if (domain)
    location.assign(
      `${domain}/logout?client_id=${encodeURIComponent(import.meta.env.VITE_COGNITO_CLIENT_ID)}&logout_uri=${encodeURIComponent(`${location.origin}/`)}`,
    );
}
