"""角色卡平台集成——将角色卡推送到外部角色卡平台。"""
import json
import mimetypes
import os
import uuid
import urllib.error
import urllib.request

from nbot.utils.logger import get_logger

_log = get_logger(__name__)


def _role_card_platform_url(server):
    url = getattr(server, "settings", {}).get("role_card_platform_url", "") if hasattr(server, "settings") else ""
    if not str(url).strip():
        url = os.getenv("ROLE_CARD_PLATFORM_URL", "").strip()
    return str(url or "http://127.0.0.1:7861").strip().rstrip("/")


def _role_card_platform_token(server):
    token = getattr(server, "settings", {}).get("role_card_platform_token", "") if hasattr(server, "settings") else ""
    if not str(token).strip():
        token = os.getenv("ROLE_CARD_PLATFORM_TOKEN", "").strip()
    return str(token or "").strip()


def _local_portrait_path(server, portrait_url):
    if not portrait_url or not portrait_url.startswith("/static/uploads/portraits/"):
        return None
    filename = os.path.basename(portrait_url)
    path = os.path.join(server.base_dir, "nbot", "web", "static", "uploads", "portraits", filename)
    return path if os.path.exists(path) else None


def _post_card_to_platform(server, character):
    boundary = f"----NekoBotRoleCard{uuid.uuid4().hex}"
    chunks = []

    def add_field(name, value):
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")

    def add_file(name, filename, content, content_type):
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        chunks.append(content)
        chunks.append(b"\r\n")

    payload = dict(character)
    payload["source"] = "nekobot"
    add_field("character", json.dumps(payload, ensure_ascii=False))

    portrait_path = _local_portrait_path(server, character.get("portrait", ""))
    if portrait_path:
        content_type = mimetypes.guess_type(portrait_path)[0] or "application/octet-stream"
        with open(portrait_path, "rb") as f:
            add_file("avatar", os.path.basename(portrait_path), f.read(), content_type)

    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(chunks)
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    token = _role_card_platform_token(server)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request_obj = urllib.request.Request(
        f"{_role_card_platform_url(server)}/api/cards",
        data=body,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request_obj, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_preview_token(server, card_id: str) -> dict:
    """获取卡片预览token

    Args:
        server: NBotWebServer 实例
        card_id: 卡片ID

    Returns:
        包含 preview_url 和 expires_in 的字典，失败返回空字典
    """
    token = _role_card_platform_token(server)
    if not token or not card_id:
        return {}

    try:
        request_obj = urllib.request.Request(
            f"{_role_card_platform_url(server)}/api/cards/{card_id}/preview-token",
            headers={"Authorization": f"Bearer {token}"},
            method="POST",
        )
        with urllib.request.urlopen(request_obj, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        _log.error(f"Failed to get preview token: {e.code} {detail}")
        return {}
    except Exception as e:
        _log.error(f"Failed to get preview token: {e}")
        return {}
