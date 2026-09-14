"""Check staged public content without printing secrets or file contents."""

import json
import subprocess
from pathlib import Path

from diagnosis_agent.config import get_settings

root = Path(__file__).resolve().parents[1]
names = (
    subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
)
key = get_settings().llm_api_key
issues = []
checked = 0
for name in filter(None, names):
    path = root / name
    if path.name == ".env" or any(
        part in (".venv", "runtime", "models") for part in path.parts
    ):
        issues.append({"file": name, "reason": "private_path_tracked"})
    if not path.is_file():
        continue
    data = path.read_bytes()
    checked += 1
    if key and key.encode() in data:
        issues.append({"file": name, "reason": "configured_secret_found"})
    if b"C:\\Users\\lzj" in data or b"D:\\enterprise-rag" in data:
        issues.append({"file": name, "reason": "private_machine_path"})
print(json.dumps({"files_checked": checked, "issues": issues}))
raise SystemExit(bool(issues))
