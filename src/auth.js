import { auth as jwtAuth } from "express-oauth2-jwt-bearer";

const AUTH0_AUDIENCE = process.env.AUTH0_AUDIENCE;
const AUTH0_ISSUER_BASE_URL =
  process.env.AUTH0_ISSUER_BASE_URL ||
  (process.env.AUTH0_DOMAIN && `https://${process.env.AUTH0_DOMAIN}`);

const isConfigured = AUTH0_AUDIENCE && AUTH0_ISSUER_BASE_URL;

if (!isConfigured) {
  console.warn(
    "Auth0 not configured: set AUTH0_AUDIENCE and AUTH0_ISSUER_BASE_URL (or AUTH0_DOMAIN). /api/auth/me will return 503 until then."
  );
}

export const auth = isConfigured
  ? jwtAuth({
      audience: AUTH0_AUDIENCE,
      issuerBaseURL: AUTH0_ISSUER_BASE_URL,
      tokenSigningAlg: "RS256",
    })
  : (_req, _res, next) => {
      next(new Error("Auth0 not configured"));
    };
