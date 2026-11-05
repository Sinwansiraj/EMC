"""Load config.yaml and the private profile."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("JOB_AGENT_ROOT", Path(__file__).resolve().parent.parent))
PRIVATE = ROOT / "private"


def load_env() -> None:
    """Read private/.env (KEY=VALUE lines) into os.environ without overriding existing vars."""
    env = PRIVATE / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_config(path: Path | None = None) -> dict:
    path = path or ROOT / "config" / "config.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_profile(path: Path | None = None) -> dict:
    path = path or PRIVATE / "profile.yaml"
    if not path.exists():
        raise SystemExit(f"Profile not found at {path}. Copy your details into private/profile.yaml first.")
    from .privacy import read_private_text
    return yaml.safe_load(read_private_text(path))


def load_companies(cfg: dict) -> dict:
    p = ROOT / cfg["sources"]["ats_boards_file"]
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
