import sys
import asyncio
from typing import Any, Awaitable, Callable, Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

import json

# Optional callback types: server notifications and tool progress
LoggingCallback = Callable[[types.LoggingMessageNotificationParams], Awaitable[None]]
ProgressCallback = Callable[
    [float, Optional[float], Optional[str]], Awaitable[None]
]


async def default_logging_callback(params: types.LoggingMessageNotificationParams) -> None:
    """Print server log notifications (level/message or data). Use as logging_callback=default_logging_callback."""
    level = getattr(params, "level", "info")
    message = getattr(params, "message", None) or getattr(params, "data", str(params))
    print(f"[MCP {level}] {message}")


class MCPClient:
    """MCP client over stdio. Optional logging_callback for server notifications; pass progress_callback to call_tool for tool progress."""

    def __init__(
        self,
        command: str,
        args: list[str],
        env: Optional[dict] = None,
        *,
        logging_callback: Optional[LoggingCallback] = None,
    ):
        self._command = command
        self._args = args
        self._env = env
        self._logging_callback = logging_callback
        self._session: Optional[ClientSession] = None
        self._exit_stack: AsyncExitStack = AsyncExitStack()

    async def connect(self):
        server_params = StdioServerParameters(
            command=self._command,
            args=self._args,
            env=self._env,
        )
        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        _stdio, _write = stdio_transport
        session_kw: dict[str, Any] = {}
        if self._logging_callback is not None:
            session_kw["logging_callback"] = self._logging_callback
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(_stdio, _write, **session_kw)
        )
        await self._session.initialize()

    def session(self) -> ClientSession:
        if self._session is None:
            raise ConnectionError(
                "Client session not initialized. Call connect() first (or use async with MCPClient(...))."
            )
        return self._session


    async def list_tools(self) -> list[types.Tool]:
        result = await self.session().list_tools()
        return result.tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> types.CallToolResult:
        kwargs: dict[str, Any] = {}
        if progress_callback is not None:
            kwargs["progress_callback"] = progress_callback
        return await self.session().call_tool(tool_name, arguments, **kwargs)

    async def list_prompts(self) -> list[types.Prompt]:
        result = await self.session().list_prompts()
        return result.prompts

    async def get_prompt(self, prompt_name, args: dict[str, str]):
        result = await self.session().get_prompt(prompt_name, args)
        return result.messages

    async def read_resource(self, uri: str) -> Any:
        result = await self.session().read_resource(uri)
        if not result.contents:
            raise ValueError(f"Resource {uri} returned no contents")
        resource = result.contents[0]

        if isinstance(resource, types.TextResourceContents):
            if resource.mimeType == "application/json":
                return json.loads(resource.text)
            return resource.text
        return resource

    def _tool_result_json(self, result: types.CallToolResult) -> Any:
        """Parse tool result content as JSON or plain text. Raises if tool reported error."""
        if result.isError and result.content:
            text = result.content[0].text if hasattr(result.content[0], "text") else str(result.content[0])
            raise RuntimeError(f"Tool error: {text}")
        if not result.content:
            return None
        item = result.content[0]
        if not isinstance(item, types.TextContent):
            return None
        text = item.text.strip()
        if text.startswith("[") or text.startswith("{"):
            return json.loads(text)
        return text

    async def list_files(self) -> list[dict]:
        """List files in the MCP file store. Returns list of {id, filename}."""
        result = await self.call_tool("list_files", {})
        return self._tool_result_json(result) or []

    async def upload_file(self, file_path: str) -> dict:
        """Upload a file from path on the server. Returns {id, filename}."""
        result = await self.call_tool("upload_file", {"file_path": file_path})
        return self._tool_result_json(result)

    async def delete_file(self, id: str) -> str:
        """Delete a file by id. Returns success message."""
        result = await self.call_tool("delete_file", {"id": id})
        out = self._tool_result_json(result)
        return out if isinstance(out, str) else str(out)

    async def download_file(self, id: str, filename: Optional[str] = None) -> dict:
        """Download file by id. Returns {content_base64, filename, mime_type}. Caller can decode and write to disk."""
        result = await self.call_tool("download_file", {"id": id, "filename": filename})
        return self._tool_result_json(result)

    async def cleanup(self):
        await self._exit_stack.aclose()
        self._session = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()


# For testing (run from project root: python -m src.mcp_client)
async def main():
    async with MCPClient(
        command="uv",
        args=["run", "src/mcp_server.py"],
        logging_callback=default_logging_callback,
    ) as client:
        result = await client.list_tools()
        print(result)
        # Example with progress (if a tool supports it):
        # result = await client.call_tool(
        #     "add", {"a": 1, "b": 2},
        #     progress_callback=lambda p, t, m: print(f"Progress: {p}/{t}" if t else f"Progress: {p}"),
        # )


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
