import asyncio
import logging
from uuid import uuid4

from sqlalchemy.exc import OperationalError

from diagnosis_agent.agents.engine import Engine
from diagnosis_agent.storage.repository import Conflict


async def work(repo, stop, cache=None):
    owner = str(uuid4())
    while not stop.is_set():
        try:
            task_id = await asyncio.to_thread(repo.claim, owner)
        except OperationalError:
            logging.getLogger(__name__).warning("database_claim_unavailable")
            await asyncio.sleep(1)
            continue
        if not task_id:
            try:
                await asyncio.wait_for(stop.wait(), 0.5)
            except asyncio.TimeoutError:
                pass
            continue
        try:
            task = await asyncio.to_thread(repo.get, task_id)
        except OperationalError:
            # The claimed lease expires naturally; never lose the worker loop.
            logging.getLogger(__name__).warning("database_read_unavailable")
            await asyncio.sleep(1)
            continue
        payload = task["payload"]

        async def pulse(task_id=task_id):
            while True:
                await asyncio.sleep(15)
                if not await asyncio.to_thread(repo.heartbeat, task_id, owner):
                    return

        heartbeat = asyncio.create_task(pulse())
        try:
            evidence = task["result"].get("evidence", {})
            for e in repo.trace(task_id):
                evidence.update(e.get("evidence", {}))
            result = await Engine().run(
                payload["question"],
                payload["case_id"],
                mode=payload["mode"],
                rag=payload["rag"],
                reviewer=payload["reviewer"],
                memory=repo.recall(payload["session_id"], payload["question"]),
                checkpoint={"evidence": evidence},
                on_event=lambda e, task_id=task_id: repo.append_event(task_id, owner, e),
            )
            await asyncio.to_thread(repo.finish, task_id, owner, result)
            if cache:
                try:
                    await cache.delete("task:" + task_id)
                except Exception:  # noqa: BLE001 -- optional cache cannot break persistence
                    logging.getLogger(__name__).warning("redis_invalidation_unavailable")
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 -- preserve failed task for operator resume
            try:
                repo.finish(
                    task_id, owner, {"status": "needs_attention", "error": "worker_failure"}
                )
            except (Conflict, OperationalError):
                pass  # A newer lease owner is authoritative; this worker must not overwrite it.
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
