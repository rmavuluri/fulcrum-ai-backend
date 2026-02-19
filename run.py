#!/usr/bin/env python3
"""Run the Fulcrum AI backend (Flask)."""
import os
from dotenv import load_dotenv

load_dotenv()

# Use certifi's CA bundle so HTTPS (Auth0 JWKS, Anthropic API) works on macOS
import certifi
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

PORT = int(os.getenv("PORT", "3001"))

if __name__ == "__main__":
    from src.app import app
    print(f"Fulcrum AI backend listening on http://localhost:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=os.getenv("FLASK_DEBUG", "0") == "1")
