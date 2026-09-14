"""Export the exact validated import format, containing no private evidence."""

from pathlib import Path

from diagnosis_agent.tools.fixtures import cases

folder = Path("data/fixtures")
folder.mkdir(parents=True, exist_ok=True)
case = cases()["oom-0"]
case.id = "example-import"
(folder / "example-case.json").write_text(case.model_dump_json(indent=2), encoding="utf-8")
print("Exported synthetic example-case.json")
