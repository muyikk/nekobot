from __future__ import annotations

import os
from typing import Any

import httpx
import requests


class HTTPClientError(Exception):
    """Raised when an HTTP request fails unexpectedly."""


def get_sync(url: str, **kwargs: Any) -> requests.Response:
    """Execute a synchronous GET request.

    Args:
        url: Target URL.
        **kwargs: Extra arguments forwarded to ``requests.get``.

    Returns:
        The ``requests.Response`` object.

    Raises:
        HTTPClientError: If the request cannot be completed.
    """
    kwargs.setdefault("timeout", 30)
    try:
        return requests.get(url, **kwargs)
    except requests.RequestException as exc:
        raise HTTPClientError(f"GET {url} failed: {exc}") from exc


def head_sync(url: str, **kwargs: Any) -> requests.Response:
    """Execute a synchronous HEAD request.

    Args:
        url: Target URL.
        **kwargs: Extra arguments forwarded to ``requests.head``.

    Returns:
        The ``requests.Response`` object.

    Raises:
        HTTPClientError: If the request cannot be completed.
    """
    kwargs.setdefault("timeout", 30)
    try:
        return requests.head(url, **kwargs)
    except requests.RequestException as exc:
        raise HTTPClientError(f"HEAD {url} failed: {exc}") from exc


def post_sync(url: str, **kwargs: Any) -> requests.Response:
    """Execute a synchronous POST request.

    Args:
        url: Target URL.
        **kwargs: Extra arguments forwarded to ``requests.post``.

    Returns:
        The ``requests.Response`` object.

    Raises:
        HTTPClientError: If the request cannot be completed.
    """
    kwargs.setdefault("timeout", 30)
    try:
        return requests.post(url, **kwargs)
    except requests.RequestException as exc:
        raise HTTPClientError(f"POST {url} failed: {exc}") from exc


async def get_async(url: str, **kwargs: Any) -> httpx.Response:
    """Execute an asynchronous GET request.

    Args:
        url: Target URL.
        **kwargs: Extra arguments forwarded to ``httpx.AsyncClient.get``.
            ``timeout`` is extracted and passed to the client (default 30s).

    Returns:
        The ``httpx.Response`` object.

    Raises:
        HTTPClientError: If the request cannot be completed.
    """
    timeout = kwargs.pop("timeout", 30)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.get(url, **kwargs)
    except httpx.HTTPError as exc:
        raise HTTPClientError(f"GET {url} failed: {exc}") from exc


async def post_async(url: str, **kwargs: Any) -> httpx.Response:
    """Execute an asynchronous POST request.

    Args:
        url: Target URL.
        **kwargs: Extra arguments forwarded to ``httpx.AsyncClient.post``.
            ``timeout`` is extracted and passed to the client (default 30s).

    Returns:
        The ``httpx.Response`` object.

    Raises:
        HTTPClientError: If the request cannot be completed.
    """
    timeout = kwargs.pop("timeout", 30)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, **kwargs)
    except httpx.HTTPError as exc:
        raise HTTPClientError(f"POST {url} failed: {exc}") from exc


def download_file(url: str, dest: str, timeout: int = 60) -> str:
    """Download a file from ``url`` to ``dest``.

    Intermediate directories are created automatically.

    Args:
        url: Source URL.
        dest: Local destination path.
        timeout: Request timeout in seconds.

    Returns:
        The destination path.

    Raises:
        HTTPClientError: If the download cannot be completed.
    """
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        with requests.get(url, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as out:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        out.write(chunk)
        return dest
    except requests.RequestException as exc:
        raise HTTPClientError(f"Download {url} failed: {exc}") from exc
