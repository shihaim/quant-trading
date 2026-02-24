from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path


@contextmanager
def file_lock(lock_path: str):
    """락 파일을 생성해 중복 실행을 막고, 종료 시 자동 해제한다."""
    path = Path(lock_path)
    if path.exists():
        raise RuntimeError(f"Lock already exists: {lock_path}")
    path.write_text("locked", encoding="utf-8")
    try:
        yield
    finally:
        if path.exists():
            path.unlink()
