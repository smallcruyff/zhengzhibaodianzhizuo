#!/usr/bin/env python3
"""Read-only checks for the 6.0.3 release snapshot, not a production task gate.

This checks file integrity and static references. It does not establish that a
host has loaded the Skill, that a model follows it, or that any book is correct.
Python 3.9+; standard library only. Local edits require a new release manifest.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

RELEASE = "6.0.3-20260908"
FONT_SUFFIXES = {".ttf", ".otf", ".woff", ".woff2", ".ttc"}


def validate(root: Path) -> dict[str, object]:
    root = root.resolve()
    errors: list[str] = []
    manifest = json.loads((root / "migration/RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("release") != RELEASE:
        errors.append("Unexpected manifest release")
    records = manifest["files"]
    recorded: set[str] = set()
    checked_links = 0
    for record in records:
        name = record["path"]
        relative = Path(name)
        candidate = (root / relative).resolve()
        if relative.is_absolute() or not candidate.is_relative_to(root) or name.startswith("migration/"):
            errors.append(f"Unsafe or out-of-scope manifest path: {name}")
            continue
        if name in recorded:
            errors.append(f"Duplicate manifest path: {name}")
        recorded.add(name)
        if not candidate.is_file():
            errors.append(f"Missing file: {name}")
            continue
        content = candidate.read_bytes()
        if hashlib.sha256(content).hexdigest() != record["sha256"]:
            errors.append(f"Changed bytes: {name}")
        if len(content) != record["bytes"]:
            errors.append(f"Changed length: {name}")

    actual: set[str] = set()
    seen: dict[str, str] = {}
    for file in sorted(root.rglob("*")):
        if not file.is_file():
            continue
        name = file.relative_to(root).as_posix()
        if not name.startswith("migration/"):
            actual.add(name)
        if file.is_symlink():
            errors.append(f"Unexpected symbolic link: {name}")
        folded = name.casefold()
        if folded in seen:
            errors.append(f"Case collision: {seen[folded]}, {name}")
        seen[folded] = name
        if file.suffix.lower() in FONT_SUFFIXES:
            errors.append(f"Font binary: {name}")
        if file.suffix == ".md":
            text = file.read_text(encoding="utf-8")
            if len(re.findall(r"^```", text, re.MULTILINE)) % 2:
                errors.append(f"Unpaired code fence: {name}")
            for _, target in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text):
                if re.match(r"(?:https?|mailto|sandbox):", target) or target.startswith("#"):
                    continue
                local = target.split("#", 1)[0]
                if not local:
                    continue
                resolved = (file.parent / local).resolve()
                checked_links += 1
                if not resolved.is_relative_to(root) or not resolved.exists():
                    errors.append(f"Broken local reference: {name}: {target}")
    if actual != recorded:
        errors.append(f"Manifest coverage mismatch: extra={sorted(actual-recorded)}, missing={sorted(recorded-actual)}")
    skills = sorted(p.relative_to(root).as_posix() for p in root.rglob("SKILL.md"))
    if skills != ["SKILL.md"]:
        errors.append(f"Unexpected Skill entrypoints: {skills}")

    main = (root / "SKILL.md").read_text(encoding="utf-8")
    front = re.match(r"\A---\n(.*?)\n---\n", main, re.DOTALL)
    if front is None:
        errors.append("Missing YAML front matter")
    else:
        for field in ("name", "description"):
            if not re.search(rf"^{field}:\s*\S", front.group(1), re.MULTILINE):
                errors.append(f"Missing required metadata: {field}")
    if f"skill_revision: {RELEASE}" not in main:
        errors.append("Unexpected Skill release revision")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    constitution = (root / "references/project-constitution.md").read_text(encoding="utf-8")
    if f"execution_revision: {RELEASE}" not in agents or f"execution_compilation: {RELEASE}" not in constitution:
        errors.append("Execution/constitution compilation release mismatch")
    for label, text, phrases in [
        ("SKILL", main, ["每轮实质制书前", "主代理必须亲自全文读取"]),
        ("AGENTS", agents, ["不受上下文缓存豁免", "约束与自主空间"]),
        ("constitution", constitution, ["每轮实质制书前", "必须使用可用文件读取工具取得并亲自阅读全文", "同一轮内部连续工具调用", "事务性豁免", "两张示范图"]),
    ]:
        for phrase in phrases:
            if phrase not in text:
                errors.append(f"Missing release-specific clause in {label}: {phrase}")
    return {
        "status": "PASS" if not errors else "FAIL",
        "release": RELEASE,
        "manifest_files": len(records),
        "markdown_local_links": checked_links,
        "errors": errors,
        "scope": "Static release integrity; maintenance archive bytes are checked separately during packaging.",
        "not_tested": ["host installation", "model behavior", "book content accuracy", "runtime performance"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = validate(args.root)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
