"""Run with python -m diagnosis_agent.tools.mcp_server (stdio transport)."""

import faulthandler
import os
import sys
from contextlib import redirect_stdout

from mcp.server.fastmcp import FastMCP

from diagnosis_agent.tools.service import ToolService

mcp = FastMCP("diagnosis-tools")
service = ToolService()


@mcp.tool()
def query_logs(case_id: str) -> dict:
    """Return redacted logs and error counts for a registered case."""
    return service.call("query_logs", {"case_id": case_id}).model_dump()


@mcp.tool()
def query_metrics(case_id: str) -> dict:
    """Return baseline/current metrics with their measurement conditions."""
    return service.call("query_metrics", {"case_id": case_id}).model_dump()


@mcp.tool()
def compare_runs(case_id: str) -> dict:
    """Compare a case's runs and enumerate confounding condition changes."""
    return service.call("compare_runs", {"case_id": case_id}).model_dump()


@mcp.tool()
def replay_case(case_id: str) -> dict:
    """Replay offline rules on registered data, never run shell or production requests."""
    return service.call("replay_case", {"case_id": case_id}).model_dump()


@mcp.tool()
def search_docs(query: str, top_k: int = 3) -> dict:
    """Search troubleshooting notes and return source references."""
    return service.call("search_docs", {"query": query, "top_k": top_k}).model_dump()


@mcp.tool()
def generate_report(
    case_id: str, conclusion: str, evidence_ids: list[str], recommendations: list[str]
) -> dict:
    """Validate references and assemble a candidate report."""
    return service.call(
        "generate_report",
        {
            "case_id": case_id,
            "conclusion": conclusion,
            "evidence_ids": evidence_ids,
            "recommendations": recommendations,
        },
    ).model_dump()


if __name__ == "__main__":
    if os.environ.get("MCP_DEBUG_STACK") == "1":
        faulthandler.dump_traceback_later(30, repeat=False)
    from diagnosis_agent.config import get_settings

    if get_settings().rag_backend == "neural":
        # Load numerical libraries before stdio threads/event loop on Windows.
        # stdout belongs exclusively to JSON-RPC; model-loader messages go to stderr.
        with redirect_stdout(sys.stderr):
            service.call("search_docs", {"query": "warmup"})
    mcp.run(transport="stdio")
