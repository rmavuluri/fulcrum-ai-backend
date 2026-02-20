import json
import os
from typing import Optional, Literal, List, Any
from mcp.types import CallToolResult, Tool, TextContent
from src.mcp_client import MCPClient, ProgressCallback
from anthropic.types import Message, ToolResultBlockParam

# Anthropic built-in web search; API executes it server-side. Used when MCP tools don't cover the query.
def _web_search_allowed_domains() -> list[str]:
    raw = os.getenv("WEB_SEARCH_ALLOWED_DOMAINS", "google.com")
    return [d.strip() for d in raw.split(",") if d.strip()]


WEB_SEARCH_SCHEMA: dict[str, Any] = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": int(os.getenv("WEB_SEARCH_MAX_USES", "5")),
    "allowed_domains": _web_search_allowed_domains(),
}


class ToolManager:
    @classmethod
    async def get_all_tools(cls, clients: dict[str, MCPClient]) -> list[Tool]:
        """Gets all tools from the provided clients."""
        tools = []
        for client in clients.values():
            tool_models = await client.list_tools()
            tools += [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.inputSchema,
                }
                for t in tool_models
            ]
        return tools

    @classmethod
    async def _find_client_with_tool(
        cls, clients: list[MCPClient], tool_name: str
    ) -> Optional[MCPClient]:
        """Finds the first client that has the specified tool."""
        for client in clients:
            tools = await client.list_tools()
            tool = next((t for t in tools if t.name == tool_name), None)
            if tool:
                return client
        return None

    @classmethod
    def _build_tool_result_part(
        cls,
        tool_use_id: str,
        text: str,
        status: Literal["success"] | Literal["error"],
    ) -> ToolResultBlockParam:
        """Builds a tool result part dictionary."""
        return {
            "tool_use_id": tool_use_id,
            "type": "tool_result",
            "content": text,
            "is_error": status == "error",
        }

    @classmethod
    async def execute_tool_requests(
        cls,
        clients: dict[str, MCPClient],
        message: Message,
        *,
        progress_callback: ProgressCallback = None,
    ) -> List[ToolResultBlockParam]:
        """Executes a list of tool requests against the provided clients.
        Pass progress_callback to receive MCP progress (e.g. for demo_progress).
        If omitted, a no-op callback is used so the client sends a progress token
        and the server can report progress when supported."""
        tool_requests = [
            block for block in message.content if block.type == "tool_use"
        ]
        tool_result_blocks: list[ToolResultBlockParam] = []

        async def _noop_progress(_p: float, _t: Optional[float], _m: Optional[str]) -> None:
            pass

        cb = progress_callback if progress_callback is not None else _noop_progress

        for tool_request in tool_requests:
            tool_use_id = tool_request.id
            tool_name = tool_request.name
            tool_input = tool_request.input

            client = await cls._find_client_with_tool(
                list(clients.values()), tool_name
            )

            if not client:
                tool_result_part = cls._build_tool_result_part(
                    tool_use_id, "Could not find that tool", "error"
                )
                tool_result_blocks.append(tool_result_part)
                continue

            try:
                tool_output: CallToolResult | None = await client.call_tool(
                    tool_name, tool_input, progress_callback=cb
                )
                items = []
                if tool_output:
                    items = tool_output.content
                content_list = [
                    item.text for item in items if isinstance(item, TextContent)
                ]
                content_json = json.dumps(content_list)
                tool_result_part = cls._build_tool_result_part(
                    tool_use_id,
                    content_json,
                    "error"
                    if tool_output and tool_output.isError
                    else "success",
                )
            except Exception as e:
                error_message = f"Error executing tool '{tool_name}': {e}"
                print(error_message)
                tool_result_part = cls._build_tool_result_part(
                    tool_use_id,
                    json.dumps({"error": error_message}),
                    "error",
                )

            tool_result_blocks.append(tool_result_part)
        return tool_result_blocks
