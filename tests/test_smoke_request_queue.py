import asyncio

from maya.llm.request_queue import RequestQueue


def test_smoke_request_queue() -> None:
    q = RequestQueue()

    async def _run() -> None:
        await q.throttle("frida_run_script")
        await q.throttle("llm_call")

    asyncio.run(_run())
