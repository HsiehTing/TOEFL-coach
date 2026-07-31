import hashlib
import os
import tempfile
from pathlib import Path

import yaml


def canonical_source_hash(prompt: str, response: str) -> str:
    canonical = prompt.replace("\r\n", "\n").strip() + "\n---\n" + response.replace("\r\n", "\n").strip()
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
