from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Union

import requests


def _guess_mime(source: str, data: bytes | None = None) -> str:
    """Guess MIME type from a path/URL or fallback to image/jpeg."""
    mime, _ = mimetypes.guess_type(source)
    if mime:
        return mime
    # For URLs without extension, try to infer from Content-Type if data fetch already happened.
    if source.startswith(("http://", "https://")) and data is not None:
        return "image/jpeg"
    return "image/jpeg"


def image_to_base64_url(image_source: str) -> str:
    """Convert a local image path or an image URL to a base64 data URL.

    Args:
        image_source: Local file path or HTTP(S) URL.

    Returns:
        A ``data:image/...;base64,...`` string.

    Raises:
        ValueError: If the source cannot be read.
    """
    if image_source.startswith(("http://", "https://")):
        try:
            resp = requests.get(image_source, timeout=30)
            resp.raise_for_status()
            data = resp.content
            content_type = resp.headers.get("Content-Type", "")
            mime = content_type.split(";")[0].strip() or _guess_mime(image_source, data)
        except requests.RequestException as exc:
            raise ValueError(f"Failed to fetch image {image_source}: {exc}") from exc
    else:
        path = Path(image_source)
        if not path.exists():
            raise ValueError(f"Image file not found: {image_source}")
        data = path.read_bytes()
        mime = _guess_mime(image_source, data)

    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def file_to_base64_url(file_path: str, mime_type: str = "application/octet-stream") -> str:
    """Convert any file to a base64 data URL.

    Args:
        file_path: Path to the file.
        mime_type: MIME type to embed in the data URL.

    Returns:
        A ``data:...;base64,...`` string.

    Raises:
        ValueError: If the file cannot be read.
    """
    path = Path(file_path)
    if not path.exists():
        raise ValueError(f"File not found: {file_path}")
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{b64}"
