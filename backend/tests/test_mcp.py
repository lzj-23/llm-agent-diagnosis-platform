import asyncio

from diagnosis_agent.tools.mcp_client import call, connect


def test_real_stdio_roundtrip():
    async def check():
        async with connect() as session:
            tools = await session.list_tools()
            assert len(tools.tools) == 6
            r = await call(session, "replay_case", {"case_id": "oom-0"})
            assert r.ok and r.data["observations"] == ["oom"]

    asyncio.run(check())
