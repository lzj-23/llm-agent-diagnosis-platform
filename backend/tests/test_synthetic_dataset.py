import json

import pytest

from diagnosis_agent.evaluation.synthetic import SCENARIOS, generate_split, validate_generated
from diagnosis_agent.tools.service import ToolService


@pytest.mark.parametrize("split,count", [("development", 48), ("validation", 24), ("frozen", 24)])
def test_split_is_deterministic_balanced_and_valid(split, count):
    first, second = generate_split(split), generate_split(split)
    assert len(first) == count
    assert [row.case.model_dump() for row in first] == [row.case.model_dump() for row in second]
    assert not validate_generated(first)
    assert {row.label["scenario"] for row in first} == set(SCENARIOS)
    frequencies = {name: sum(row.label["scenario"] == name for row in first) for name in SCENARIOS}
    assert len(set(frequencies.values())) == 1


def test_splits_have_disjoint_ids_and_values():
    rows = {split: generate_split(split) for split in ("development", "validation", "frozen")}
    ids = {split: {row.case.id for row in values} for split, values in rows.items()}
    assert not ids["development"] & ids["validation"]
    assert not ids["development"] & ids["frozen"]
    assert not ids["validation"] & ids["frozen"]
    assert rows["development"][0].case.model_dump() != rows["frozen"][0].case.model_dump()


def test_hidden_labels_are_not_returned_by_tools():
    row = generate_split("frozen")[0]
    assert row.case.expected == "unknown"
    service = ToolService(dataset={row.case.id: row.case})
    outputs = [
        service.call(name, {"case_id": row.case.id}).model_dump_json()
        for name in ("query_logs", "query_metrics", "compare_runs", "replay_case")
    ]
    hidden = (
        row.label["root_cause_rubric"],
        *row.label["supported_claims"],
        *row.label["forbidden_claims"],
    )
    assert all(value not in "".join(outputs) for value in hidden)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_case_round_trip_and_label_separation(scenario):
    row = next(row for row in generate_split("validation") if row.label["scenario"] == scenario)
    public = json.dumps(row.case.model_dump(), ensure_ascii=False)
    assert row.case.synthetic
    assert row.label["agent_visible"] is False
    assert "root_cause_rubric" not in public
    assert "forbidden_claims" not in public
