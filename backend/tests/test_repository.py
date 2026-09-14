import pytest

from diagnosis_agent.storage.repository import Conflict, Repository


def test_idempotency_and_restart(tmp_path):
    url = "sqlite:///" + str(tmp_path / "tasks.sqlite")
    repo = Repository(url)
    payload = {"session_id": "test", "question": "hello"}
    task_id, created = repo.create(payload, "key")
    assert created
    assert repo.create(payload, "key") == (task_id, False)
    with pytest.raises(Conflict):
        repo.create({"session_id": "test", "question": "other"}, "key")
    assert repo.claim("worker1") == task_id
    assert repo.claim("worker2") is None
    repo.append_event(task_id, "worker1", {"action": "tool", "evidence": {"a": 1}})
    assert Repository(url).trace(task_id)[0]["action"] == "tool"
    repo.finish(task_id, "worker1", {"status": "needs_attention", "error": "injected"})
    assert repo.resume(task_id)
    assert repo.claim("worker2") == task_id
    with pytest.raises(Conflict):
        repo.append_event(task_id, "worker1", {})
    repo.finish(task_id, "worker2", {"status": "completed", "diagnosis": {"conclusion": "ok"}})
    assert "ok" in repo.recall("test", "hello")
    assert Repository(url).get(task_id)["status"] == "completed"
