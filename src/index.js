import "dotenv/config";
import express from "express";
import cors from "cors";
import { auth } from "./auth.js";

const PORT = process.env.PORT ?? 3001;
const FRONTEND_URL = process.env.FRONTEND_URL ?? "http://localhost:5173";

const app = express();

app.use(
  cors({
    origin: FRONTEND_URL,
    credentials: true,
  })
);
app.use(express.json());

// Health check (no auth)
app.get("/api/health", (_req, res) => {
  res.json({ status: "ok" });
});

// Auth0-protected route: current user from JWT
app.get("/api/auth/me", auth, (req, res) => {
  const claims = req.auth?.payload ?? {};
  res.json({
    user: {
      id: claims.sub,
      email: claims.email ?? claims[`${process.env.AUTH0_AUDIENCE}email`],
      name: claims.name ?? claims[`${process.env.AUTH0_AUDIENCE}name`],
    },
  });
});

// Error handler (e.g. Auth0 not configured or invalid token)
app.use((err, _req, res, _next) => {
  if (err.message === "Auth0 not configured") {
    res.status(503).json({ error: "Auth0 not configured" });
    return;
  }
  if (err.code === "invalid_token" || err.status === 401) {
    res.status(401).json({ error: "Invalid or expired token" });
    return;
  }
  res.status(500).json({ error: err.message ?? "Internal server error" });
});

app.listen(PORT, () => {
  console.log(`Fulcrum AI backend listening on http://localhost:${PORT}`);
});
