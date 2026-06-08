from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, UploadFile

from macaronys_backend.config import settings
from macaronys_backend.utils.time import new_id


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(filename: str) -> str:
    cleaned = _SAFE_FILENAME_RE.sub("_", Path(filename).name).strip("._")
    return cleaned or "upload.bin"


async def save_upload_file(upload: UploadFile) -> tuple[Path, int]:
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{new_id()}_{safe_filename(upload.filename or 'upload.bin')}"
    target = upload_dir / filename

    total = 0
    with target.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                output.close()
                target.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"Upload exceeds {settings.max_upload_size_mb}MB limit",
                )
            output.write(chunk)

    await upload.seek(0)
    return target, total
