"""
测试 BotAPI 上传方法的 QQ sandbox 桥接逻辑。

macOS 把 QQ Helper 限制在 ~/Library/Containers/com.tencent.qq/ 容器内，
容器外的 fs.open() 会被 sandbox 拦截返回 EPERM。我们在 BotAPI 类级别
包装 4 个上传方法，把本地文件 hard link 到沙盒里绕过这个限制。
"""
import asyncio
import inspect
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)


# --- _should_bridge ---


def test_should_bridge_skips_urls():
    from nbot import commands

    assert commands._should_bridge("http://example.com/x.mp4") is False
    assert commands._should_bridge("https://example.com/x.mp4") is False
    assert commands._should_bridge("base64://abc123") is False
    assert commands._should_bridge("data:image/png;base64,abc") is False
    print("✓ test_should_bridge_skips_urls")


def test_should_bridge_accepts_local_paths():
    from nbot import commands

    assert commands._should_bridge("/Users/feewee009/cache/x.pdf") is True
    assert commands._should_bridge("relative/path.mp4") is True
    assert commands._should_bridge(None) is False
    assert commands._should_bridge(123) is False
    print("✓ test_should_bridge_accepts_local_paths")


# --- _bridge_to_qq_sandbox ---


def test_bridge_creates_hardlink_and_overwrites():
    """hard link 必须共享 inode，覆盖旧 link 时新内容生效"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_src, tempfile.TemporaryDirectory() as tmp_sandbox:
        from nbot import commands

        original = commands.QQ_SANDBOX_DIR
        commands.QQ_SANDBOX_DIR = tmp_sandbox
        try:
            src = os.path.join(tmp_src, "video.mp4")
            with open(src, "wb") as f:
                f.write(b"v1")

            # 第一次：建 link
            s1 = commands._bridge_to_qq_sandbox(src)
            assert os.path.exists(s1)
            assert os.stat(src).st_ino == os.stat(s1).st_ino, "不是 hard link"

            # 第二次：源文件内容变了，旧 link 要被覆盖
            with open(src, "wb") as f:
                f.write(b"v2 updated")
            s2 = commands._bridge_to_qq_sandbox(src)
            with open(s2, "rb") as f:
                assert f.read() == b"v2 updated", "旧 link 没被覆盖"
        finally:
            commands.QQ_SANDBOX_DIR = original
    print("✓ test_bridge_creates_hardlink_and_overwrites")


def test_bridge_falls_back_on_failure():
    """hard link 失败时回退到原路径，不让上传崩"""
    from nbot import commands

    # 文件不存在，os.link 必然失败
    result = commands._bridge_to_qq_sandbox("/nonexistent/file.mp4")
    assert result == "/nonexistent/file.mp4", f"应该回退到原路径，实际: {result}"
    print("✓ test_bridge_falls_back_on_failure")


# --- _wrap_botapi_upload ---


def test_wrap_post_group_file_bridges_kwargs():
    """post_group_file 的 file= 本地路径要被桥接"""
    from nbot import commands

    captured = {}

    async def fake_method(self, *args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"status": "ok"}

    wrapped = commands._wrap_botapi_upload(fake_method)
    fake_self = object()

    # 模拟一个会被 _bridge_to_qq_sandbox 处理的本地路径
    # 但要避免实际 hard link（用 monkey-patch 桥接函数）
    original_bridge = commands._bridge_to_qq_sandbox
    commands._bridge_to_qq_sandbox = lambda p: f"/sandbox/{os.path.basename(p)}"
    try:
        asyncio.run(wrapped(fake_self, group_id=123, file="/path/to/comic.pdf"))
    finally:
        commands._bridge_to_qq_sandbox = original_bridge

    assert captured["kwargs"]["file"] == "/sandbox/comic.pdf", (
        f"file 应该被桥接到沙盒，实际: {captured['kwargs'].get('file')}"
    )
    assert captured["kwargs"]["group_id"] == 123
    print("✓ test_wrap_post_group_file_bridges_kwargs")


def test_wrap_post_group_file_bridges_all_file_kwargs():
    """post_*_file 的 image/video/record/markdown 也要被桥接"""
    from nbot import commands

    captured = {}

    async def fake_method(self, *args, **kwargs):
        captured["kwargs"] = kwargs
        return {"status": "ok"}

    wrapped = commands._wrap_botapi_upload(fake_method)
    original_bridge = commands._bridge_to_qq_sandbox
    commands._bridge_to_qq_sandbox = lambda p: f"/sandbox/{os.path.basename(p)}"
    try:
        asyncio.run(
            wrapped(
                fake_self := object(),
                group_id=1,
                image="/a/img.png",
                record="/a/voice.amr",
                video="/a/v.mp4",
                file="/a/doc.pdf",
                markdown="/a/readme.md",
            )
        )
    finally:
        commands._bridge_to_qq_sandbox = original_bridge

    for k in ("image", "record", "video", "file", "markdown"):
        assert captured["kwargs"][k] == f"/sandbox/{os.path.basename(captured['kwargs'][k])}", (
            f"{k} 没被桥接: {captured['kwargs'][k]}"
        )
    print("✓ test_wrap_post_group_file_bridges_all_file_kwargs")


def test_wrap_post_group_file_skips_http():
    """http URL 不桥接（让 ncatbot 自己处理下载）"""
    from nbot import commands

    captured = {}

    async def fake_method(self, *args, **kwargs):
        captured["kwargs"] = kwargs
        return {"status": "ok"}

    wrapped = commands._wrap_botapi_upload(fake_method)
    original_bridge = commands._bridge_to_qq_sandbox
    bridge_called = []
    commands._bridge_to_qq_sandbox = lambda p: bridge_called.append(p) or f"/sandbox/{p}"
    try:
        asyncio.run(
            wrapped(
                object(),
                group_id=1,
                image="http://example.com/img.png",
                file="https://example.com/doc.pdf",
            )
        )
    finally:
        commands._bridge_to_qq_sandbox = original_bridge

    assert captured["kwargs"]["image"] == "http://example.com/img.png"
    assert captured["kwargs"]["file"] == "https://example.com/doc.pdf"
    assert bridge_called == [], f"http URL 不应该被桥接，但调用了: {bridge_called}"
    print("✓ test_wrap_post_group_file_skips_http")


def test_wrap_upload_group_file_bridges_positional():
    """upload_group_file(self, group_id, file, name, folder_id) 的第 2 个位置参数是 file"""
    from nbot import commands

    captured = {}

    async def fake_method(self, *args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"status": "ok"}

    # fake_method 名字必须是 upload_group_file，否则 wrapper 不知道用 positional 模式
    fake_method.__name__ = "upload_group_file"

    wrapped = commands._wrap_botapi_upload(fake_method)
    original_bridge = commands._bridge_to_qq_sandbox
    commands._bridge_to_qq_sandbox = lambda p: f"/sandbox/{os.path.basename(p)}"
    try:
        asyncio.run(wrapped(object(), 123, "/path/to/x.pdf", "x.pdf", ""))
    finally:
        commands._bridge_to_qq_sandbox = original_bridge

    # args = (self 已绑定, group_id, file, name, folder_id) → 我们看到 (group_id, file, name, folder_id)
    assert captured["args"][1] == "/sandbox/x.pdf", (
        f"positional file 应该被桥接，实际: {captured['args'][1]}"
    )
    print("✓ test_wrap_upload_group_file_bridges_positional")


# --- BotAPI 包装的幂等性 ---


def test_botapi_upload_methods_are_wrapped():
    """导入 commands.py 后，4 个上传方法都应该被包装过"""
    from ncatbot.core import BotAPI

    # 已经在模块加载时包装过了
    assert getattr(BotAPI, "_nbot_sandbox_wrapped", False) is True
    for name in ("post_group_file", "post_private_file", "upload_group_file", "upload_private_file"):
        method = getattr(BotAPI, name)
        assert hasattr(method, "__wrapped__"), f"{name} 没被包装"
    print("✓ test_botapi_upload_methods_are_wrapped")


def test_botapi_sandbox_flag_uses_underscore_prefix():
    """_nbot_sandbox_wrapped 标志存在，避免和现有 _nbot_patched 冲突"""
    from ncatbot.core import BotAPI

    assert hasattr(BotAPI, "_nbot_sandbox_wrapped")
    # 不和现有的 _nbot_patched 冲突
    assert hasattr(BotAPI, "_nbot_patched")
    print("✓ test_botapi_sandbox_flag_uses_underscore_prefix")


# --- ncatbot API 签名校验 ---


def test_upload_group_file_signature():
    """如果 ncatbot 升级改了签名，这里会立刻失败"""
    from ncatbot.core import BotAPI

    # 跳过包装层看原始方法
    raw = BotAPI.upload_group_file.__wrapped__ if hasattr(BotAPI.upload_group_file, "__wrapped__") else BotAPI.upload_group_file
    sig = inspect.signature(raw)
    params = list(sig.parameters.keys())
    assert params == ["self", "group_id", "file", "name", "folder_id"], (
        f"upload_group_file 签名变了: {params}"
    )
    print("✓ test_upload_group_file_signature")


def test_upload_private_file_signature():
    from ncatbot.core import BotAPI

    raw = BotAPI.upload_private_file.__wrapped__ if hasattr(BotAPI.upload_private_file, "__wrapped__") else BotAPI.upload_private_file
    sig = inspect.signature(raw)
    params = list(sig.parameters.keys())
    assert params == ["self", "user_id", "file", "name"], (
        f"upload_private_file 签名变了: {params}"
    )
    print("✓ test_upload_private_file_signature")


if __name__ == "__main__":
    test_should_bridge_skips_urls()
    test_should_bridge_accepts_local_paths()
    test_bridge_creates_hardlink_and_overwrites()
    test_bridge_falls_back_on_failure()
    test_wrap_post_group_file_bridges_kwargs()
    test_wrap_post_group_file_bridges_all_file_kwargs()
    test_wrap_post_group_file_skips_http()
    test_wrap_upload_group_file_bridges_positional()
    test_botapi_upload_methods_are_wrapped()
    test_botapi_sandbox_flag_uses_underscore_prefix()
    test_upload_group_file_signature()
    test_upload_private_file_signature()
    print("\n所有测试通过 ✓")
