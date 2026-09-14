"""Build an allowlisted static replay; never package runtime, backend env, or user uploads."""

import csv
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = root / "runtime" / "public-demo"
output.mkdir(parents=True, exist_ok=True)
for name in ("index.html", "app.js"):
    shutil.copyfile(root / "demo" / name, output / name)


def load(name):
    return json.loads((root / "evaluation-results" / name).read_text(encoding="utf-8"))


def load_csv(name):
    with (root / "evaluation-results" / name).open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


records = {
    "cases": [
        {
            "title": "新增：逐条证据核对",
            "kind": "合成OOM案例，实际模型与神经检索；核对标签不代表结论已被证明",
            "result": load("grounding-neural/task.json")["result"],
        },
        {
            "title": "本机上下文超限：实测错误",
            "kind": "真实CPU小模型实验，不是生产事故",
            "result": load("measured-context/diagnosis.json"),
        },
        {
            "title": "显存不足：神经RAG取证",
            "kind": "合成OOM数据，实际模型调用与神经检索",
            "result": load("neural-compose-verified/task.json")["result"],
        },
    ],
    "retest": load("gpu-context-v2/retest.json"),
    "synthetic": {
        "manifest": load("synthetic-v2-frozen-smoke-v2/manifest.json"),
        "rows": load_csv("synthetic-v2-frozen-smoke-v2/results.csv"),
    },
}
(output / "records.json").write_text(
    json.dumps(records, ensure_ascii=False), encoding="utf-8"
)
print("Built static replay from allowlisted public evaluation files.")
