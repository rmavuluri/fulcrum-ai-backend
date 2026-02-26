"""
Fulcrum AI Backend — Flask app: Auth0 JWT validation and API routes.
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# Use certifi CA bundle for HTTPS (Auth0 JWKS, Anthropic API); fixes SSL errors on macOS
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

from flask import Flask, jsonify, g, request
from flask_cors import CORS

from .auth import require_auth, Auth0NotConfiguredError, InvalidTokenError

PORT = int(os.getenv("PORT", "3001"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# MCP document server (for /api/chat)
MCP_SERVER_COMMAND = os.getenv("MCP_SERVER_COMMAND", "uv")
MCP_SERVER_ARGS = os.getenv("MCP_SERVER_ARGS", "run,src/mcp_server.py").split(",")

app = Flask(__name__)
CORS(app, origins=[FRONTEND_URL], supports_credentials=True)


def _use_ally_sandbox() -> bool:
    """Use Ally sandbox for chat when enabled and credentials are set."""
    if os.getenv("USE_ALLY_SANDBOX", "").lower() not in ("1", "true", "yes"):
        return False
    return bool(os.getenv("SANDBOX_CLIENT_KEY") and os.getenv("SANDBOX_CLIENT_SECRET"))


def _run_chat_turn_sandbox(query: str) -> str:
    """Run one chat turn using the Ally sandbox API (sync)."""
    from src.ally_sandbox import generate_bearer_token, call_sandbox

    token = generate_bearer_token()
    if not token:
        raise RuntimeError(
            "Ally sandbox not configured: set SANDBOX_CLIENT_KEY and SANDBOX_CLIENT_SECRET"
        )
    return call_sandbox(token, query)


async def _run_chat_turn(query: str) -> str:
    """Run one chat turn: Ally sandbox if enabled, else document MCP server + Claude."""
    if _use_ally_sandbox():
        return _run_chat_turn_sandbox(query)

    from src.mcp_client import MCPClient
    from src.core.claude import Claude
    from src.core.cli_chat import CliChat

    async with MCPClient(
        command=MCP_SERVER_COMMAND.strip(),
        args=[a.strip() for a in MCP_SERVER_ARGS],
    ) as client:
        clients = {"doc": client}
        claude = Claude()
        agent = CliChat(doc_client=client, clients=clients, claude_service=claude)
        return await agent.run(query)


async def _list_docs() -> list[str]:
    """Return list of document IDs from the MCP document server."""
    from src.mcp_client import MCPClient
    from src.core.claude import Claude
    from src.core.cli_chat import CliChat

    async with MCPClient(
        command=MCP_SERVER_COMMAND.strip(),
        args=[a.strip() for a in MCP_SERVER_ARGS],
    ) as client:
        claude = Claude()
        agent = CliChat(doc_client=client, clients={"doc": client}, claude_service=claude)
        return await agent.list_docs_ids()


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify(status="ok")


@app.route("/api/documents", methods=["GET"])
@require_auth
def list_documents():
    """Return list of document IDs (for @-mentions). Auth required."""
    try:
        doc_ids = asyncio.run(_list_docs())
        return jsonify(documents=doc_ids)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/api/chat", methods=["POST"])
@require_auth
def chat():
    """Accept { \"message\": \"...\" } or { \"query\": \"...\" }, return { \"response\": \"...\" }. Auth required."""
    body = request.get_json(silent=True) or {}
    message = body.get("message") or body.get("query") or ""
    message = message.strip()
    if not message:
        return jsonify(error="Missing message or query"), 400
    try:
        response = asyncio.run(_run_chat_turn(message))
        return jsonify(response=response)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/api/auth/me", methods=["GET"])
@require_auth
def auth_me():
    claims = g.auth_payload
    audience = os.getenv("AUTH0_AUDIENCE", "")
    email = claims.get("email") or claims.get(f"{audience}email")
    name = claims.get("name") or claims.get(f"{audience}name")
    return jsonify(
        user={
            "id": claims.get("sub"),
            "email": email,
            "name": name,
        }
    )


@app.errorhandler(Auth0NotConfiguredError)
def handle_auth0_not_configured(err):
    return jsonify(error="Auth0 not configured"), 503


@app.errorhandler(InvalidTokenError)
def handle_invalid_token(err):
    return jsonify(error="Invalid or expired token"), 401


@app.errorhandler(401)
def handle_401(err):
    return jsonify(error="Invalid or expired token"), 401


@app.errorhandler(Exception)
def handle_generic(err):
    if getattr(err, "code", None) == "invalid_token":
        return jsonify(error="Invalid or expired token"), 401
    message = getattr(err, "message", None) or str(err) or "Internal server error"
    return jsonify(error=message), 500


def main():
    app.run(host="0.0.0.0", port=PORT, debug=os.getenv("FLASK_DEBUG", "0") == "1")


if __name__ == "__main__":
    print(f"Fulcrum AI backend listening on http://localhost:{PORT}")
    main()
