import asyncio
import base64
import uuid
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP, Context
from pydantic import Field

mcp = FastMCP("DocumentMCP", log_level="ERROR")

# MIME type map for file upload (by extension)
MIME_TYPE_MAP = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/plain",
    ".py": "text/plain",
    ".js": "text/plain",
    ".html": "text/plain",
    ".css": "text/plain",
    ".csv": "text/csv",
    ".json": "application/json",
    ".xml": "application/xml",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# In-memory file store: id -> {"filename": str, "content": bytes, "mime_type": str}
_file_store: dict[str, dict] = {}


docs = {
    "deposition.md": "This deposition covers the testimony of Angela Smith, P.E.",
    "report.pdf": "The report details the state of a 20m condenser tower.",
    "financials.docx": "These financials outline the project's budget and expenditures.",
    "outlook.pdf": "This document presents the projected future performance of the system.",
    "plan.md": "The plan outlines the steps for the project's implementation.",
    "spec.txt": "These specifications define the technical requirements for the equipment.",
}


from mcp.server.fastmcp.prompts import base


@mcp.tool(
    name="read_doc_contents",
    description="Read the contents of a document and return it as a string.",
)
def read_document(
    doc_id: str = Field(description="Id of the document to read"),
):
    if doc_id not in docs:
        raise ValueError(f"Doc with id {doc_id} not found")

    return docs[doc_id]


@mcp.tool(
    name="edit_document",
    description="Edit a document by replacing a string in the documents content with a new string",
)
def edit_document(
    doc_id: str = Field(description="Id of the document that will be edited"),
    old_str: str = Field(
        description="The text to replace. Must match exactly, including whitespace"
    ),
    new_str: str = Field(
        description="The new text to insert in place of the old text"
    ),
):
    if doc_id not in docs:
        raise ValueError(f"Doc with id {doc_id} not found")

    docs[doc_id] = docs[doc_id].replace(old_str, new_str)
    return f"Updated {doc_id}."


@mcp.tool(
    name="demo_progress",
    description="Demo tool that runs for a few seconds and sends progress so you can test progress_callback on the client. Pass steps (default 5) and delay_seconds (default 1).",
)
async def demo_progress(
    steps: int = Field(default=5, description="Number of steps"),
    delay_seconds: float = Field(default=1.0, description="Seconds to wait per step"),
    ctx: Context = None,  # Injected by FastMCP when client sends progress token; may be None on older clients
) -> str:
    """Run for steps * delay_seconds seconds, report progress each step, then return."""
    for i in range(steps):
        if ctx is not None:
            await ctx.report_progress(progress=i + 1, total=steps, message=f"Step {i + 1}/{steps}")
        await asyncio.sleep(delay_seconds)
    return f"Completed {steps} steps."


@mcp.tool(
    name="list_files",
    description="List all uploaded files. Returns a list of objects with id and filename.",
)
def list_files() -> list[dict]:
    """Return list of files in the store."""
    return [
        {"id": fid, "filename": meta["filename"]}
        for fid, meta in _file_store.items()
    ]


@mcp.tool(
    name="upload_file",
    description="Upload a file from a path on the server. Path is relative to server CWD or absolute. Returns the new file id.",
)
def upload_file(file_path: str = Field(description="Path to the file to upload")) -> dict:
    """Read file from disk and store it; return file id and filename."""
    path = Path(file_path)
    if not path.exists():
        raise ValueError(f"File not found: {file_path}")
    extension = path.suffix.lower()
    mime_type = MIME_TYPE_MAP.get(extension)
    if not mime_type:
        raise ValueError(f"Unknown mimetype for extension: {extension}")
    filename = path.name
    with open(path, "rb") as f:
        content = f.read()
    file_id = str(uuid.uuid4())
    _file_store[file_id] = {"filename": filename, "content": content, "mime_type": mime_type}
    return {"id": file_id, "filename": filename}


@mcp.tool(
    name="delete_file",
    description="Delete a file by its id.",
)
def delete_file(id: str = Field(description="Id of the file to delete")) -> str:
    """Remove file from store."""
    if id not in _file_store:
        raise ValueError(f"File with id {id} not found")
    del _file_store[id]
    return f"Deleted file {id}."


@mcp.tool(
    name="download_file",
    description="Download a file by id. Returns content as base64 and filename. Optional filename argument is the name to suggest when saving.",
)
def download_file(
    id: str = Field(description="Id of the file to download"),
    filename: Optional[str] = Field(default=None, description="Optional filename to save as"),
) -> dict:
    """Return file content (base64) and filename for the client to save."""
    if id not in _file_store:
        raise ValueError(f"File with id {id} not found")
    meta = _file_store[id]
    content_b64 = base64.b64encode(meta["content"]).decode("ascii")
    save_name = filename if filename else meta["filename"]
    return {
        "content_base64": content_b64,
        "filename": save_name,
        "mime_type": meta["mime_type"],
    }


@mcp.resource("docs://documents", mime_type="application/json")
def list_docs() -> list[str]:
    return list(docs.keys())


@mcp.resource("docs://documents/{doc_id}", mime_type="text/plain")
def fetch_doc(doc_id: str) -> str:
    if doc_id not in docs:
        raise ValueError(f"Doc with id {doc_id} not found")
    return docs[doc_id]


@mcp.prompt(
    name="format",
    description="Rewrites the contents of the document in Markdown format.",
)
def format_document(
    doc_id: str = Field(description="Id of the document to format"),
) -> list[base.Message]:
    prompt = f"""
    Your goal is to reformat a document to be written with markdown syntax.

    The id of the document you need to reformat is:
    <document_id>
    {doc_id}
    </document_id>

    Add in headers, bullet points, tables, etc as necessary. Feel free to add in extra text, but don't change the meaning of the report.
    Use the 'edit_document' tool to edit the document. After the document has been edited, respond with the final version of the doc. Don't explain your changes.
    """

    return [base.UserMessage(prompt)]


if __name__ == "__main__":
    mcp.run(transport="stdio")
