"""Privacy helpers: owner-only file permissions, log redaction, optional encryption at rest.

Encryption: set JOB_AGENT_KEY in your environment (generate with `python -m job_agent keygen`)
and run `python -m job_agent encrypt-profile`. The profile is then stored as profile.yaml.enc and
decrypted only in memory.
"""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s-]{8,}\d)")


def redact(text: str, profile: dict | None = None) -> str:
    """Remove email addresses, phone numbers and any profile identity values from text."""
    if not text:
        return text
    out = EMAIL_RE.sub("[email]", str(text))
    out = PHONE_RE.sub("[phone]", out)
    if profile:
        ident = profile.get("identity", {})
        for key in ("phone", "email"):
            val = ident.get(key)
            if val:
                out = out.replace(str(val), f"[{key}]")
    return out


def restrict(path: Path) -> None:
    """Make a file or directory readable by the owner only (best effort on Windows)."""
    try:
        if path.is_dir():
            os.chmod(path, stat.S_IRWXU)
        else:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def ensure_private_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    restrict(path)
    return path


def _fernet():
    key = os.environ.get("JOB_AGENT_KEY")
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode())


def read_private_text(path: Path) -> str:
    enc = path.with_suffix(path.suffix + ".enc")
    if enc.exists():
        f = _fernet()
        if f is None:
            raise SystemExit(f"{enc.name} is encrypted; set JOB_AGENT_KEY to read it.")
        return f.decrypt(enc.read_bytes()).decode("utf-8")
    return path.read_text(encoding="utf-8")


def encrypt_file(path: Path) -> Path:
    f = _fernet()
    if f is None:
        raise SystemExit("Set JOB_AGENT_KEY first (python -m job_agent keygen).")
    enc = path.with_suffix(path.suffix + ".enc")
    enc.write_bytes(f.encrypt(path.read_bytes()))
    restrict(enc)
    path.unlink()
    return enc


def keygen() -> str:
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()
