import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import timedelta

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from diagnosis_agent.tools.contracts import ToolResult


@asynccontextmanager
async def connect():
    from diagnosis_agent.config import get_settings

    settings = get_settings()
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "diagnosis_agent.tools.mcp_server"],
        env={
            "RUNTIME_DIR": settings.runtime_dir,
            "RAG_BACKEND": settings.rag_backend,
            "EMBEDDING_MODEL": settings.embedding_model,
            "RERANKER_MODEL": settings.reranker_model,
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        },
    )
    if os.environ.get("MCP_DEBUG_STACK") == "1":
        params.env["MCP_DEBUG_STACK"] = "1"
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write, read_timeout_seconds=timedelta(seconds=90)) as session,
    ):
        await session.initialize()
        yield session


async def call(session, name, args):
    response = await session.call_tool(name, args)
    if response.isError:
        return ToolResult(ok=False, error="mcp_tool_error")
    structured = response.structuredContent
    if structured and "ok" in structured:
        return ToolResult.model_validate(structured)
    for item in response.content:
        if item.type == "text":
            return ToolResult.model_validate(json.loads(item.text))
    return ToolResult(ok=False, error="empty_mcp_result")
