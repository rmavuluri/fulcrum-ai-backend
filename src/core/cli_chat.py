"""
CLI-specific chat: same as Chat but with doc_client set for document/MCP features.
All behavior (list_prompts, get_doc_content, @mentions, /commands) lives in Chat.
"""
from src.core.chat import Chat
from src.core.claude import Claude
from src.mcp_client import MCPClient


class CliChat(Chat):
    def __init__(
        self,
        doc_client: MCPClient,
        clients: dict[str, MCPClient],
        claude_service: Claude,
    ):
        super().__init__(
            claude_service=claude_service,
            clients=clients,
            doc_client=doc_client,
        )
