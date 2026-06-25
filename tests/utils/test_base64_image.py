from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest

from nbot.utils.base64_image import file_to_base64_url, image_to_base64_url


class TestImageToBase64Url:
    def test_local_image(self, tmp_path) -> None:
        img = tmp_path / "test.png"
        img.write_bytes(b"fake-image-data")
        result = image_to_base64_url(str(img))
        expected = f"data:image/png;base64,{base64.b64encode(b'fake-image-data').decode('ascii')}"
        assert result == expected

    def test_local_image_without_extension_defaults_to_jpeg(self, tmp_path) -> None:
        img = tmp_path / "test"
        img.write_bytes(b"fake-image-data")
        result = image_to_base64_url(str(img))
        assert result.startswith("data:image/jpeg;base64,")

    def test_url_image_uses_content_type(self) -> None:
        mock_resp = MagicMock()
        mock_resp.content = b"fake-image-data"
        mock_resp.headers = {"Content-Type": "image/webp"}
        with patch("nbot.utils.base64_image.requests.get", return_value=mock_resp):
            result = image_to_base64_url("https://example.com/img.webp")
        expected = f"data:image/webp;base64,{base64.b64encode(b'fake-image-data').decode('ascii')}"
        assert result == expected

    def test_missing_local_file_raises(self, tmp_path) -> None:
        with pytest.raises(ValueError):
            image_to_base64_url(str(tmp_path / "missing.jpg"))


class TestFileToBase64Url:
    def test_encodes_any_file(self, tmp_path) -> None:
        path = tmp_path / "doc.pdf"
        path.write_bytes(b"pdf-data")
        result = file_to_base64_url(str(path), mime_type="application/pdf")
        expected = f"data:application/pdf;base64,{base64.b64encode(b'pdf-data').decode('ascii')}"
        assert result == expected

    def test_missing_file_raises(self, tmp_path) -> None:
        with pytest.raises(ValueError):
            file_to_base64_url(str(tmp_path / "missing.bin"))
