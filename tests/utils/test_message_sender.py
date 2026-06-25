from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from nbot.utils.message_sender import send_file, send_text, set_bot_client


def _make_bot():
    bot = MagicMock()
    bot.api.post_private_msg = AsyncMock()
    bot.api.post_group_file = AsyncMock()
    bot.api.upload_private_file = AsyncMock()
    return bot


@pytest.mark.asyncio
async def test_send_text_group() -> None:
    bot = _make_bot()
    set_bot_client(bot)
    msg = MagicMock()
    msg.reply = AsyncMock()
    await send_text(msg, "hello", is_group=True)
    msg.reply.assert_awaited_once_with(text="hello")
    bot.api.post_private_msg.assert_not_called()


@pytest.mark.asyncio
async def test_send_text_private() -> None:
    bot = _make_bot()
    set_bot_client(bot)
    msg = MagicMock()
    msg.user_id = 12345
    await send_text(msg, "hello", is_group=False)
    bot.api.post_private_msg.assert_awaited_once_with(12345, text="hello")


@pytest.mark.asyncio
async def test_send_file_group(tmp_path) -> None:
    bot = _make_bot()
    set_bot_client(bot)
    msg = MagicMock()
    msg.group_id = 111
    path = tmp_path / "doc.txt"
    path.write_text("x")
    await send_file(msg, str(path), is_group=True)
    bot.api.post_group_file.assert_awaited_once_with(111, file=str(path), filename="doc.txt")


@pytest.mark.asyncio
async def test_send_file_private(tmp_path) -> None:
    bot = _make_bot()
    set_bot_client(bot)
    msg = MagicMock()
    msg.user_id = 12345
    path = tmp_path / "doc.txt"
    path.write_text("x")
    await send_file(msg, str(path), is_group=False, filename="custom.txt")
    bot.api.upload_private_file.assert_awaited_once_with(12345, str(path), "custom.txt")
