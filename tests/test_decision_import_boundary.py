"""Architectural guard: agents/ and engine/ must NEVER import execution/.

The only path to execution is from an approved decision via decisions/. This
test walks every .py under agents/ and engine/ with the ast module and fails on
any `import execution` / `from execution[...] import ...`.
"""
from __future__ import annotations

import ast
from pathlib import Path

GUARDED_DIRS = ("agents", "engine")
REPO_ROOT = Path(__file__).resolve().parent.parent


def _offending_imports(py_file: Path) -> list[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "execution" or alias.name.startswith("execution."):
                    offenders.append(f"{py_file}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "execution" or mod.startswith("execution."):
                offenders.append(f"{py_file}: from {mod} import ...")
    return offenders


def test_agents_and_engine_never_import_execution() -> None:
    violations: list[str] = []
    for dir_name in GUARDED_DIRS:
        for py_file in (REPO_ROOT / dir_name).rglob("*.py"):
            violations.extend(_offending_imports(py_file))
    assert not violations, "Import boundary violated:\n" + "\n".join(violations)
