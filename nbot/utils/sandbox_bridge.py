from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable

from ncatbot.core import BotAPI
from nbot.utils.logger import get_logger

_log = get_logger(__name__)

QQ_SANDBOX_DIR = os.path.expanduser(
    "~/Library/Containers/com.tencent.qq/Data/Library/Application Support/QQ/nekobot_files"
)

_BRIDGABLE_KWARGS = ("file", "image", "video", "record", "markdown")
_UPLOAD_METHODS_WITH_FILE_AS_POSITIONAL = ("upload_group_file", "upload_private_file")


def _should_bridge(path: Any) -> bool:
    """Return True if ``path`` is a local file that needs sandbox bridging."""
    if not isinstance(path, str):
        return False
    return not path.startswith(("http://", "https://", "base64://", "data:"))


def _bridge_to_qq_sandbox(local_path: str) -> str:
    """Hard-link ``local_path`` into the QQ sandbox and return the sandbox path.

    If hard-linking fails, the original path is returned as a fallback.
    """
    os.makedirs(QQ_SANDBOX_DIR, exist_ok=True)
    sandbox_path = os.path.join(QQ_SANDBOX_DIR, os.path.basename(local_path))
    if os.path.exists(sandbox_path):
        try:
            os.remove(sandbox_path)
        except OSError:
            pass
    try:
        os.link(local_path, sandbox_path)
        return sandbox_path
    except OSError as exc:
        _log.warning(f"[qq-sandbox] hard link failed ({local_path}): {exc}, using original path")
        return local_path


def _wrap_botapi_upload(orig_method: Callable) -> Callable:
    """Wrap a BotAPI upload method to auto-bridge local files into the QQ sandbox."""
    method_name = orig_method.__name__
    is_upload_with_positional_file = method_name in _UPLOAD_METHODS_WITH_FILE_AS_POSITIONAL

    @wraps(orig_method)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        if is_upload_with_positional_file:
            if len(args) >= 2 and _should_bridge(args[1]):
                args = args[:1] + (_bridge_to_qq_sandbox(args[1]),) + args[2:]
            elif "file" in kwargs and _should_bridge(kwargs["file"]):
                kwargs["file"] = _bridge_to_qq_sandbox(kwargs["file"])
        else:
            for key in _BRIDGABLE_KWARGS:
                if key in kwargs and _should_bridge(kwargs[key]):
                    kwargs[key] = _bridge_to_qq_sandbox(kwargs[key])
        return await orig_method(self, *args, **kwargs)

    wrapper.__wrapped__ = orig_method  # type: ignore[attr-defined]
    return wrapper


def apply_qq_sandbox_bridge() -> None:
    """Patch BotAPI upload methods once so local files are hard-linked into the QQ sandbox."""
    if getattr(BotAPI, "_nbot_sandbox_wrapped", False):
        return
    for method_name in (
        "post_group_file",
        "post_private_file",
        "upload_group_file",
        "upload_private_file",
    ):
        setattr(BotAPI, method_name, _wrap_botapi_upload(getattr(BotAPI, method_name)))
    BotAPI._nbot_sandbox_wrapped = True
