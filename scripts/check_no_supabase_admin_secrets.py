"""Fail CI when tracked files contain Supabase elevated credentials."""
from __future__ import annotations

import base64
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JWT_RE = re.compile(rb"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
SECRET_RE = re.compile(rb"sb_secret_[A-Za-z0-9_-]{20,}")
PAT_RE = re.compile(rb"sbp_[A-Za-z0-9]{20,}")


def _tracked_files() -> list[Path]:
    out = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [ROOT / p.decode("utf-8") for p in out.split(b"\0") if p]


def _is_service_role_jwt(token: bytes) -> bool:
    try:
        payload = token.split(b".", 2)[1]
        payload += b"=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return data.get("role") == "service_role"
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return False


def main() -> int:
    findings: list[tuple[str, str]] = []
    for path in _tracked_files():
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if len(data) > 2_000_000 or b"\0" in data:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if SECRET_RE.search(data):
            findings.append((rel, "Supabase secret API key"))
        if PAT_RE.search(data):
            findings.append((rel, "Supabase personal access token"))
        if any(_is_service_role_jwt(m.group(0)) for m in JWT_RE.finditer(data)):
            findings.append((rel, "legacy service_role JWT"))

    if findings:
        print("Blocked: elevated Supabase credential found in tracked content.")
        for rel, kind in sorted(set(findings)):
            print(f"- {rel}: {kind}")
        return 1

    print("Secret guard passed: no Supabase admin credentials found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
