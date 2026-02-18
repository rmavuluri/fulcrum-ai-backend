# Fulcrum AI Backend

Express backend for Fulcrum AI: Auth0 JWT validation and (later) MCP proxy.

## Auth0 setup

1. **Auth0 tenant**
   - Create an [Auth0 account](https://auth0.com) and a tenant.

2. **Application (SPA)**
   - In Auth0 Dashboard: Applications → Create Application → Single Page Application.
   - Note the **Domain** and **Client ID** (used by the frontend).
   - Settings:
     - **Allowed Callback URLs**: `http://localhost:5173` (and your production URL).
     - **Allowed Logout URLs**: `http://localhost:5173` (and production).
     - **Allowed Web Origins**: `http://localhost:5173` (and production).
   - Save.

3. **API (backend)**
   - APIs → Create API.
   - Name and **Identifier** (e.g. `https://fulcrum-ai-api`). This is your **Audience**.
   - Enable "Allow Offline Access" if you need refresh tokens.
   - Save.

4. **Environment variables**
   - Copy `.env.example` to `.env`.
   - Set:
     - `AUTH0_DOMAIN` = your tenant domain (e.g. `tenant.us.auth0.com`).
     - `AUTH0_ISSUER_BASE_URL` = `https://<AUTH0_DOMAIN>` (or leave unset to derive from `AUTH0_DOMAIN`).
     - `AUTH0_AUDIENCE` = your API Identifier.
     - `FRONTEND_URL` = frontend origin (e.g. `http://localhost:5173`).
     - `PORT` = backend port (e.g. `3001`).

## Run

```bash
npm install
npm run dev
```

Backend runs at `http://localhost:3001`. Frontend should use `VITE_API_URL=http://localhost:3001`.

## Endpoints

- `GET /api/health` – health check (no auth).
- `GET /api/auth/me` – current user from JWT (requires `Authorization: Bearer <access_token>`).

MCP routes will be added later.
