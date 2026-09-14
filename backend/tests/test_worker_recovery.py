import asyncio
from unittest.mock import Mock, patch

from sqlalchemy.exc import OperationalError

from diagnosis_agent.storage.worker import work


def test_claimed_task_read_failure_does_not_kill_worker():
    async def scenario():
        stop = asyncio.Event()
        repo = Mock()
        repo.claim.return_value = "claimed-task"
        repo.get.side_effect = OperationalError("select", {}, Exception("offline"))

        async def backoff(_):
            stop.set()

        with patch("diagnosis_agent.storage.worker.asyncio.sleep", backoff):
            await work(repo, stop)
        repo.get.assert_called_once_with("claimed-task")
        repo.finish.assert_not_called()

    asyncio.run(scenario())
