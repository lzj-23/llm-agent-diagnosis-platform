import importlib.util
import subprocess
from pathlib import Path


def load_scanner():
    script = Path(__file__).resolve().parents[2] / "scripts/check_repository.py"
    spec = importlib.util.spec_from_file_location("repository_scanner", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scan_uses_git_relative_paths_when_checkout_is_nested_under_runtime(tmp_path):
    root = tmp_path / "runtime" / "public-release"
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "safe.txt").write_text("public fixture", encoding="utf-8")
    subprocess.run(["git", "add", "safe.txt"], cwd=root, check=True)

    report = load_scanner().inspect_repository(root)

    assert report == {"files_checked": 1, "issues": []}
