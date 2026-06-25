from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import requests

from nbot.utils.http_client import (
    HTTPClientError,
    download_file,
    get_async,
    get_sync,
    head_sync,
    post_async,
    post_sync,
)


class TestGetSync:
    def test_get_sync_uses_default_timeout(self) -> None:
        with patch("nbot.utils.http_client.requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            get_sync("https://example.com")
            mock_get.assert_called_once_with("https://example.com", timeout=30)

    def test_get_sync_forwards_kwargs(self) -> None:
        with patch("nbot.utils.http_client.requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            get_sync("https://example.com", headers={"X-Test": "1"}, timeout=5)
            mock_get.assert_called_once_with(
                "https://example.com", headers={"X-Test": "1"}, timeout=5
            )

    def test_get_sync_raises_on_failure(self) -> None:
        with patch(
            "nbot.utils.http_client.requests.get",
            side_effect=requests.RequestException("boom"),
        ):
            with pytest.raises(HTTPClientError):
                get_sync("https://example.com")


class TestPostSync:
    def test_post_sync_forwards_kwargs(self) -> None:
        with patch("nbot.utils.http_client.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=201)
            post_sync("https://example.com", json={"key": "value"}, timeout=10)
            mock_post.assert_called_once_with(
                "https://example.com", json={"key": "value"}, timeout=10
            )


class TestHeadSync:
    def test_head_sync_forwards_kwargs(self) -> None:
        with patch("nbot.utils.http_client.requests.head") as mock_head:
            mock_head.return_value = MagicMock(status_code=200)
            head_sync("https://example.com", timeout=5)
            mock_head.assert_called_once_with("https://example.com", timeout=5)


class TestGetAsync:
    def test_get_async_uses_httpx(self) -> None:
        mock_response = MagicMock(status_code=200)
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        async def run():
            with patch("nbot.utils.http_client.httpx.AsyncClient") as mock_cls:
                mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                return await get_async("https://example.com", headers={"X-Test": "1"})

        response = asyncio.run(run())
        assert response.status_code == 200
        mock_client.get.assert_called_once_with(
            "https://example.com", headers={"X-Test": "1"}
        )

    def test_get_async_raises_on_failure(self) -> None:
        async def run():
            with patch("nbot.utils.http_client.httpx.AsyncClient") as mock_cls:
                mock_cls.return_value.__aenter__ = AsyncMock(
                    side_effect=httpx.HTTPError("boom")
                )
                mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                await get_async("https://example.com")

        with pytest.raises(HTTPClientError):
            asyncio.run(run())


class TestPostAsync:
    def test_post_async_forwards_kwargs(self) -> None:
        mock_response = MagicMock(status_code=201)
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        async def run():
            with patch("nbot.utils.http_client.httpx.AsyncClient") as mock_cls:
                mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                return await post_async("https://example.com", json={"key": "value"})

        response = asyncio.run(run())
        assert response.status_code == 201
        mock_client.post.assert_called_once_with(
            "https://example.com", json={"key": "value"}
        )


class TestDownloadFile:
    def test_download_file_writes_content(self, tmp_path) -> None:
        dest = tmp_path / "downloaded.bin"
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_response.raise_for_status.return_value = None

        with patch("nbot.utils.http_client.requests.get") as mock_get:
            mock_get.return_value.__enter__ = MagicMock(return_value=mock_response)
            mock_get.return_value.__exit__ = MagicMock(return_value=False)
            result = download_file("https://example.com/file", str(dest))

        assert result == str(dest)
        assert dest.read_bytes() == b"chunk1chunk2"

    def test_download_file_raises_on_failure(self, tmp_path) -> None:
        with patch(
            "nbot.utils.http_client.requests.get",
            side_effect=requests.RequestException("boom"),
        ):
            with pytest.raises(HTTPClientError):
                download_file("https://example.com/file", str(tmp_path / "file"))
