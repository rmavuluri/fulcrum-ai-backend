"""
Fulcrum AI Backend — Flask app: API routes. Frontend gets sandbox token and calls APIs with it.
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# Use certifi CA bundle for HTTPS (Ally API, etc.); fixes SSL errors on macOS
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

from flask import Flask, jsonify, request
from flask_cors import CORS

PORT = int(os.getenv("PORT", "3001"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# MCP document server (for /api/chat when not using sandbox)
MCP_SERVER_COMMAND = os.getenv("MCP_SERVER_COMMAND", "uv")
MCP_SERVER_ARGS = os.getenv("MCP_SERVER_ARGS", "run,src/mcp_server.py").split(",")

app = Flask(__name__)
CORS(app, origins=[FRONTEND_URL], supports_credentials=True)


def _use_ally_sandbox() -> bool:
    """Use Ally sandbox for chat when enabled and credentials are set."""
    if os.getenv("USE_ALLY_SANDBOX", "").lower() not in ("1", "true", "yes"):
        return False
    return bool(os.getenv("SANDBOX_CLIENT_KEY") and os.getenv("SANDBOX_CLIENT_SECRET"))


def _run_chat_turn_sandbox(query: str, token: str | None = None) -> str:
    """Run one chat turn using the Ally sandbox API. Uses token if provided, else generates one."""
    from src.ally_sandbox import generate_bearer_token, call_sandbox

    if not token:
        token = generate_bearer_token()
    if not token:
        raise RuntimeError(
            "Ally sandbox not configured: set SANDBOX_CLIENT_KEY and SANDBOX_CLIENT_SECRET"
        )
    return call_sandbox(token, query)


async def _run_chat_turn(query: str, sandbox_token: str | None = None) -> str:
    """Run one chat turn: Ally sandbox if enabled (using sandbox_token if provided), else MCP + Claude."""
    if _use_ally_sandbox():
        return _run_chat_turn_sandbox(query, token=sandbox_token)

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
    """Return list of document IDs. When using Ally sandbox, returns [] (no MCP docs)."""
    if _use_ally_sandbox():
        return []
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


@app.route("/api/sandbox-token", methods=["GET"])
def sandbox_token():
    """
    Return an Ally sandbox bearer token for the frontend.
    Frontend should call this first, then send Authorization: Bearer <token> on /api/chat and other endpoints.
    """
    from src.ally_sandbox import generate_bearer_token

    if not _use_ally_sandbox():
        return jsonify(error="Ally sandbox not enabled: set USE_ALLY_SANDBOX and credentials"), 503

    token = generate_bearer_token()
    if not token:
        return jsonify(error="Failed to get sandbox token; check SANDBOX_CLIENT_KEY and SANDBOX_CLIENT_SECRET"), 503

    # Ally typically returns expires_in (seconds); default 1 hour
    expires_in = 3600
    return jsonify(access_token=token, expires_in=expires_in)


@app.route("/api/documents", methods=["GET"])
def list_documents():
    """Return list of document IDs (for @-mentions). Optional: send Authorization: Bearer <sandbox_token>."""
    try:
        doc_ids = asyncio.run(_list_docs())
        return jsonify(documents=doc_ids)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Chat. Body: { "message": "..." } or { "query": "..." }. Returns { "response": "..." }.
    Send Authorization: Bearer <sandbox_token> (get token from GET /api/sandbox-token).
    """
    body = request.get_json(silent=True) or {}
    message = body.get("message") or body.get("query") or ""
    message = message.strip()
    if not message:
        return jsonify(error="Missing message or query"), 400

    auth_header = request.headers.get("Authorization")
    sandbox_token = None
    if auth_header and auth_header.startswith("Bearer "):
        sandbox_token = auth_header[7:].strip()

    try:
        response = asyncio.run(_run_chat_turn(message, sandbox_token=sandbox_token))
        return jsonify(response=response)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.errorhandler(Exception)
def handle_generic(err):
    message = getattr(err, "message", None) or str(err) or "Internal server error"
    return jsonify(error=message), 500


def main():
    app.run(host="0.0.0.0", port=PORT, debug=os.getenv("FLASK_DEBUG", "0") == "1")


if __name__ == "__main__":
    print(f"Fulcrum AI backend listening on http://localhost:{PORT}")
    main()
